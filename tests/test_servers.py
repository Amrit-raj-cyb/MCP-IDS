"""Phase 1 smoke tests: filesystem MCP server + basic client.

Two layers:
* Unit tests of the sandbox path guard (fast, no subprocess).
* End-to-end tests that spawn the real server over stdio and talk MCP to it.

Every test works on a temporary *copy* of ``sandbox/`` so the seed data is
never modified.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from agent.client import connect, new_session_id, run_demo
from common.registry import PROJECT_ROOT, get_server
from servers.benign.filesystem.server import resolve_in_sandbox


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    dest = tmp_path / "sandbox"
    shutil.copytree(PROJECT_ROOT / "sandbox", dest)
    return dest.resolve()


# ---------------------------------------------------------------- unit tests

@pytest.mark.parametrize("ok_path", [".", "notes.txt", "data/sample.csv", "data/../report.txt"])
def test_paths_inside_sandbox_are_allowed(sandbox: Path, ok_path: str) -> None:
    assert resolve_in_sandbox(ok_path, sandbox).is_relative_to(sandbox)


@pytest.mark.parametrize("bad_path", [
    "../secret.txt",
    "data/../../secret.txt",
    "/etc/passwd",
])
def test_paths_outside_sandbox_are_rejected(sandbox: Path, bad_path: str) -> None:
    with pytest.raises(ToolError):
        resolve_in_sandbox(bad_path, sandbox)


def test_native_absolute_path_is_rejected(sandbox: Path) -> None:
    # Built from the OS's own path format (C:\... on Windows, /tmp/... on Linux).
    # A literal "C:/x" would be a *relative* path on Linux, i.e. inside the sandbox.
    outside = str(sandbox.parent / "secret.txt")
    with pytest.raises(ToolError):
        resolve_in_sandbox(outside, sandbox)


def test_symlink_escape_is_rejected(sandbox: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = sandbox / "escape"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this system")
    with pytest.raises(ToolError):
        resolve_in_sandbox("escape/x.txt", sandbox)


# ----------------------------------------------------------- end-to-end (stdio)

async def test_client_lists_and_calls_filesystem_tools(sandbox: Path) -> None:
    res = await run_demo("filesystem", extra_env={"MCP_FS_SANDBOX": str(sandbox)})

    assert set(res.tools) == {"list_directory", "read_file", "write_file", "search_files"}
    by_tool = [(c.tool, c.is_error) for c in res.calls]
    assert by_tool == [
        ("list_directory", False),
        ("read_file", False),
        ("search_files", False),
        ("read_file", True),  # path traversal must come back as an MCP tool error
    ]
    assert "notes.txt" in res.calls[0].text
    assert "synthetic" in res.calls[1].text
    assert "data/sample.csv" in res.calls[2].text
    assert "outside the sandbox" in res.calls[3].text


async def test_write_then_read_roundtrip(sandbox: Path) -> None:
    spec = get_server("filesystem")
    async with connect(spec, new_session_id(), {"MCP_FS_SANDBOX": str(sandbox)}) as s:
        w = await s.call_tool("write_file", {"path": "documents/new.txt", "content": "hello lab"})
        assert not w.is_error
        r = await s.call_tool("read_file", {"path": "documents/new.txt"})
        assert r.content[0].text == "hello lab"
        bad = await s.call_tool("write_file", {"path": "../evil.txt", "content": "x"})
        assert bad.is_error
    assert (sandbox / "documents" / "new.txt").read_text() == "hello lab"
    assert not (sandbox.parent / "evil.txt").exists()


async def test_missing_file_is_tool_error_not_crash(sandbox: Path) -> None:
    spec = get_server("filesystem")
    async with connect(spec, new_session_id(), {"MCP_FS_SANDBOX": str(sandbox)}) as s:
        r = await s.call_tool("read_file", {"path": "does_not_exist.txt"})
        assert r.is_error
        # Server must still be alive and responsive after an error.
        assert len((await s.list_tools()).tools) == 4


# =================================================================== SQLite
# The tool functions are plain Python functions, so most checks call them
# directly (fast); one end-to-end test goes through stdio + proxy.

import sqlite3
from contextlib import closing

from common.lab_env import fresh_database
from servers.benign.sqlite import server as sq
from servers.benign.sqlite.seed_db import build_database


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = build_database(tmp_path / "dummy.db")
    monkeypatch.setenv("MCP_SQLITE_DB", str(path))
    return path


def _dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as con:  # always close: Windows locks open files
        return list(con.iterdump())


def _scalar(path: Path, sql: str):
    with closing(sqlite3.connect(path)) as con:
        return con.execute(sql).fetchone()[0]


def test_database_is_deterministic(tmp_path: Path) -> None:
    dump = _dump
    assert dump(build_database(tmp_path / "a.db", seed=7)) == dump(build_database(tmp_path / "b.db", seed=7))
    assert dump(build_database(tmp_path / "c.db", seed=7)) != dump(build_database(tmp_path / "d.db", seed=8))


def test_read_query_returns_rows(db: Path) -> None:
    out = json.loads(sq.read_query("SELECT id, username FROM users ORDER BY id LIMIT 2"))
    assert out["columns"] == ["id", "username"] and out["rows"][0] == [1, "alice_01"]


@pytest.mark.parametrize("sql", [
    "DELETE FROM users",
    "UPDATE products SET price = 0",
    "DROP TABLE orders",
    "INSERT INTO logs VALUES (999, 'x', 'INFO', 'x')",
    "ATTACH DATABASE 'other.db' AS other",          # would open another file on disk
    "PRAGMA writable_schema = 1",
    "SELECT load_extension('evil')",
    "SELECT 1; DROP TABLE users",                    # stacked statements
    "SELEC name FROM users",                         # plain syntax error
])
def test_read_query_rejects_non_select(db: Path, sql: str) -> None:
    before = _dump(db)
    with pytest.raises(ToolError):
        sq.read_query(sql)
    assert _dump(db) == before


def test_runaway_query_is_interrupted(db: Path) -> None:
    import time
    t = time.monotonic()
    with pytest.raises(ToolError, match="interrupted"):
        sq.read_query("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c")
    assert time.monotonic() - t < sq.QUERY_TIMEOUT_S + 3


def test_result_rows_are_capped(db: Path) -> None:
    out = json.loads(sq.read_query(
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 500) SELECT x FROM c"))
    assert out["row_count"] == sq.MAX_ROWS and out["truncated"] is True


def test_insert_row_rules(db: Path) -> None:
    ok = json.loads(sq.insert_row("logs", {"ts": "2026-10-01T00:00:00Z", "level": "INFO", "message": "hi"}))
    assert ok["inserted"] == "logs"
    with pytest.raises(ToolError, match="not allowed"):
        sq.insert_row("users", {"username": "x"})
    with pytest.raises(ToolError, match="Unknown column"):
        sq.insert_row("logs", {"id) VALUES (1); DROP TABLE logs; --": 1})   # injection via column name
    with pytest.raises(ToolError, match="Insert failed"):
        sq.insert_row("logs", {"ts": "t", "level": "NOTICE", "message": "m"})  # CHECK constraint
    assert _scalar(db, "SELECT count(*) FROM logs") == 51


def test_each_session_gets_a_fresh_database() -> None:
    with fresh_database() as a:
        with closing(sqlite3.connect(a)) as con:
            con.execute("DELETE FROM logs")
            con.commit()
        assert _scalar(a, "SELECT count(*) FROM logs") == 0
    with fresh_database() as b:
        assert _scalar(b, "SELECT count(*) FROM logs") == 50


async def test_sqlite_server_end_to_end() -> None:
    res = await run_demo("sqlite")
    assert set(res.tools) == {"list_tables", "describe_table", "read_query", "insert_row"}
    assert [c.is_error for c in res.calls] == [False, False, False, True]
    assert "not authorized" in res.calls[-1].text


# ================================================================ Web fetch

from servers.benign.web_fetch import server as wf
from servers.benign.web_fetch.testsite import serve_site


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch):
    with serve_site() as base:
        monkeypatch.setenv("MCP_WEB_BASE_URL", base)
        yield base


@pytest.mark.parametrize("make_url", [
    lambda b: "http://example.com/",
    lambda b: b.replace("127.0.0.1", "localhost") + "/index.html",     # same machine, different host string
    lambda b: b.rsplit(":", 1)[0] + ":1/index.html",                    # different port
    lambda b: b.replace("http://", "https://") + "/index.html",        # different scheme
    lambda b: b.replace("http://", "http://user@evil.example@") + "/",  # userinfo trick (host parses as allowed!)
    lambda b: b.replace("http://", "http://user:pw@") + "/",            # credentials in URL
    lambda b: "http://evil.example/#@" + b[7:],                         # fragment trick
    lambda b: "file:///etc/passwd",
    lambda b: "not a url",
])
def test_fetch_refuses_urls_outside_allowlist(site: str, make_url) -> None:
    with pytest.raises(ToolError, match="not allowed|Invalid URL"):
        wf.fetch(make_url(site))


def test_fetch_returns_page_text(site: str) -> None:
    out = wf.fetch(site + "/docs/getting-started.html")
    assert out.startswith("Title: Getting Started") and "demo mode" in out and "<h2>" not in out


def test_fetch_does_not_follow_redirects(site: str) -> None:
    # The static server answers /docs with a 301 to /docs/; it must not be followed.
    with pytest.raises(ToolError, match="HTTP 301"):
        wf.fetch(site + "/docs")


def test_fetch_missing_page_is_tool_error(site: str) -> None:
    with pytest.raises(ToolError, match="HTTP 404"):
        wf.fetch(site + "/nope.html")


def test_fetch_pagination_reassembles_page(site: str) -> None:
    full = wf.fetch(site + "/faq.html", max_length=10**6)
    body = full.split("\n\n", 1)[1]
    chunks, start = [], 0
    while True:
        out = wf.fetch(site + "/faq.html", max_length=3000, start_index=start)
        text = out.split("\n\n", 1)[1] if start == 0 else out
        text = text.split("\n\n[Content truncated.")[0]
        chunks.append(text)
        start += len(text)
        if "[Content truncated." not in out:
            break
    assert "".join(chunks) == body and len(chunks) >= 4


def test_html_to_text_drops_scripts() -> None:
    title, text = wf.html_to_text("<title>T</title><script>alert(1)</script><p>Hello</p><style>p{}</style>")
    assert title == "T" and text == "Hello"


def test_fetch_server_refuses_to_start_without_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_WEB_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="allow-list"):
        wf.allowed_origin()


async def test_web_fetch_server_end_to_end() -> None:
    res = await run_demo("web_fetch")
    assert res.tools == ["fetch"]
    assert [c.is_error for c in res.calls] == [False, True, True]
    assert "Lab Widgets" in res.calls[0].text and "not allowed" in res.calls[2].text
