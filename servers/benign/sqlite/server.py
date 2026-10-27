"""Benign SQLite MCP server (dummy database).

Simple explanation
------------------
Lets the agent look at and query a small synthetic shop database (users,
products, orders, logs) and add rows to two tables. Produces normal database
traffic, *including normal mistakes*: bad SQL, unknown tables, constraint
violations. Real users make those mistakes too, so the IDS must learn they
are benign.

Tools
-----
``list_tables``, ``describe_table``, ``read_query`` (SELECT only),
``insert_row`` (``orders`` and ``logs`` only, parameterised).

Safety
------
* ``read_query`` uses a **read-only** connection (``mode=ro``) plus an SQLite
  *authorizer* that allows only SELECT/READ/FUNCTION/RECURSIVE. Everything
  else is rejected *by SQLite itself*, including ``ATTACH`` (which could open
  other files on disk), writes and ``PRAGMA``.
* A progress handler aborts queries that run longer than 2 s (e.g. an
  accidental infinite recursive CTE). Results are capped at 200 rows.
* ``insert_row`` never builds SQL from values: the table must be on an
  allow-list, column names must exist in the schema, values are bound with
  ``?`` placeholders.
* The database path comes from ``MCP_SQLITE_DB`` and is a per-session copy.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from common.descriptions import describe
from common.logsetup import configure_server_logging
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

SERVER_ID = "sqlite"
MAX_ROWS = 200
QUERY_TIMEOUT_S = 2.0
INSERTABLE_TABLES = {"orders", "logs"}

log = logging.getLogger(__name__)

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                    sqlite3.SQLITE_RECURSIVE}


def db_path() -> Path:
    path = Path(os.getenv("MCP_SQLITE_DB", "database/dummy.db"))
    if not path.is_file():
        raise RuntimeError(f"Database not found: {path}")
    return path


def _read_only_authorizer(action: int, arg1: Any, arg2: Any, db: Any, trigger: Any) -> int:
    if action not in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and arg2 in ("load_extension", "readfile", "writefile"):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


@contextmanager
def _connect_rw() -> Iterator[sqlite3.Connection]:
    """Read-write connection that commits on success and is *always closed*.

    (``with sqlite3.connect(...)`` only commits; on Windows an unclosed
    connection keeps the file locked and the per-session copy can't be deleted.)
    """
    con = sqlite3.connect(db_path())
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _connect_ro() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db_path().as_posix()}?mode=ro", uri=True)
    deadline = time.monotonic() + QUERY_TIMEOUT_S
    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
    con.set_authorizer(_read_only_authorizer)
    return con


def _table_names(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [r[0] for r in rows]


def _columns(con: sqlite3.Connection, table: str) -> list[tuple]:
    # Safe: table is validated against sqlite_master before being interpolated.
    return con.execute(f"PRAGMA table_info({table})").fetchall()


mcp = MCPServer(
    name="lab-sqlite",
    instructions="Query a synthetic shop database (users, products, orders, logs).",
    version="0.1.0",
)


@mcp.tool(description=describe("sqlite", "list_tables"))
def list_tables() -> str:
    """List the tables in the database with their row counts."""
    with _connect_rw() as con:
        names = _table_names(con)
        counts = {n: con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}
    return json.dumps({"tables": counts})


@mcp.tool(description=describe("sqlite", "describe_table"))
def describe_table(table: str) -> str:
    """Show the columns of a table (name, type, nullable, primary key)."""
    with _connect_rw() as con:
        if table not in _table_names(con):
            raise ToolError(f"Unknown table '{table}'")
        cols = [{"name": c[1], "type": c[2], "not_null": bool(c[3]), "primary_key": bool(c[5])}
                for c in _columns(con, table)]
    return json.dumps({"table": table, "columns": cols})


@mcp.tool(description=describe("sqlite", "read_query"))
def read_query(sql: str) -> str:
    """Run a read-only SELECT query and return up to 200 rows as JSON."""
    con = _connect_ro()
    try:
        cur = con.execute(sql)
        if cur.description is None:
            raise ToolError("Only SELECT queries are allowed")
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
    except sqlite3.DatabaseError as exc:
        # Includes syntax errors, "not authorized" and timeouts ("interrupted").
        raise ToolError(f"SQL error: {exc}") from None
    finally:
        con.close()
    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    log.info("read_query -> %d rows%s", len(rows), " (truncated)" if truncated else "")
    return json.dumps({"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated})


@mcp.tool(description=describe("sqlite", "insert_row"))
def insert_row(table: str, values: dict[str, Any]) -> str:
    """Insert one row into 'orders' or 'logs'. `values` maps column names to values."""
    if table not in INSERTABLE_TABLES:
        raise ToolError(f"Inserting into '{table}' is not allowed (allowed: {sorted(INSERTABLE_TABLES)})")
    if not values:
        raise ToolError("No values given")
    with _connect_rw() as con:
        con.execute("PRAGMA foreign_keys = ON")
        known = {c[1] for c in _columns(con, table)}
        unknown = set(values) - known
        if unknown:
            raise ToolError(f"Unknown column(s) for {table}: {sorted(unknown)}")
        cols = list(values)
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        try:
            cur = con.execute(sql, [values[c] for c in cols])
        except sqlite3.DatabaseError as exc:  # constraint violations, type errors
            raise ToolError(f"Insert failed: {exc}") from None
    log.info("insert_row %s id=%s", table, cur.lastrowid)
    return json.dumps({"inserted": table, "id": cur.lastrowid})


def main() -> None:
    configure_server_logging("sqlite-server")
    log.info("starting; db=%s session=%s", db_path(), os.getenv("MCP_SESSION_ID", "-"))
    mcp.run("stdio")


if __name__ == "__main__":
    main()
