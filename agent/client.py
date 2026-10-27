"""Basic MCP client (Phase 1).

Simple explanation
------------------
Starts one MCP server as a child process, performs the MCP handshake
(``initialize``), asks which tools exist (``tools/list``) and calls some of
them (``tools/call``). There is no LLM yet -- the calls are scripted. The
LLM-driven agent arrives in Phase 2 and will reuse :func:`connect`.

Technical detail
----------------
* Transport is stdio: JSON-RPC 2.0 messages, one per line, on the child's
  stdin/stdout.
* A session ID is generated here and passed through the ``MCP_SESSION_ID``
  environment variable. stdio has no notion of a session, so the lab defines
  one; the logging proxy stamps it on every log line.
* By default the server runs behind the logging proxy (``proxied=True``).

Run:  python -m agent.client --server filesystem   (or sqlite, web_fetch)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

from mcp import ClientSession, StdioServerParameters, stdio_client, types

from common.registry import PROJECT_ROOT, ServerSpec, get_server

log = logging.getLogger("agent.client")


async def _fixed_sampling_callback(_context: Any, _params: Any) -> types.CreateMessageResult:
    """Inert local sampling handler; advertises identical client capability in every session."""
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(text="LAB-SAMPLING-ACK: fixed local callback; no model or tools invoked."),
        model="mcp-ids-fixed-sampling",
        stop_reason="endTurn",
    )


def new_session_id() -> str:
    return uuid.uuid4().hex


@asynccontextmanager
async def connect(
    spec: ServerSpec,
    session_id: str,
    extra_env: dict[str, str] | None = None,
    proxied: bool = True,
    sampling_callback: Callable[..., Any] | None = None,
) -> AsyncIterator[ClientSession]:
    """Spawn ``spec`` over stdio and yield an initialized ``ClientSession``.

    By default the server is started *behind the logging proxy* (Phase 3), so
    every JSON-RPC message of the session is recorded under ``MCP_LOG_DIR``.
    """
    command, args = spec.command(proxied=proxied)
    env = {
        "MCP_SESSION_ID": session_id,
        "MCP_SERVER_ID": spec.log_id,
        "PYTHONPATH": str(PROJECT_ROOT),
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "WARNING"),
        "MCP_LOG_DIR": os.getenv("MCP_LOG_DIR", str(PROJECT_ROOT / "data" / "raw" / "sessions")),
        "MCP_FS_SANDBOX": os.getenv("MCP_FS_SANDBOX", str(PROJECT_ROOT / "sandbox")),
        **spec.env,
        **(extra_env or {}),
    }
    params = StdioServerParameters(command=command, args=args, env=env, cwd=str(PROJECT_ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, sampling_callback=sampling_callback or _fixed_sampling_callback,
            sampling_capabilities=types.SamplingCapability(),
        ) as session:
            init = await session.initialize()
            log.info("connected to %s (%s %s)", spec.server_id,
                     init.server_info.name, init.server_info.version)
            yield session


@dataclass
class ToolCallRecord:
    tool: str
    arguments: dict[str, Any]
    is_error: bool
    text: str


@dataclass
class DemoResult:
    session_id: str
    server_id: str
    tools: list[str] = field(default_factory=list)
    calls: list[ToolCallRecord] = field(default_factory=list)


def _result_text(result: Any) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


# Scripted demo calls per server. The last filesystem call is a deliberate
# path-traversal attempt to show the sandbox returning an error result.
DEMO_CALLS: dict[str, list[tuple[str, dict[str, Any]]]] = {
    "filesystem": [
        ("list_directory", {"path": "."}),
        ("read_file", {"path": "notes.txt"}),
        ("search_files", {"pattern": "sample"}),
        ("read_file", {"path": "../outside.txt"}),
    ],
    "sqlite": [
        ("list_tables", {}),
        ("describe_table", {"table": "products"}),
        ("read_query", {"sql": "SELECT name, price FROM products ORDER BY price DESC LIMIT 3"}),
        ("read_query", {"sql": "DELETE FROM users"}),  # must be refused: read-only
    ],
    "web_fetch": [
        ("fetch", {"url": "{web}/index.html"}),
        ("fetch", {"url": "{web}/missing.html"}),         # 404 -> tool error
        ("fetch", {"url": "http://example.com/"}),        # must be refused: not allow-listed
    ],
}


async def run_demo(server_id: str, session_id: str | None = None,
                   extra_env: dict[str, str] | None = None) -> DemoResult:
    """Connect, list tools, run scripted calls; return what happened."""
    spec = get_server(server_id)
    session_id = session_id or new_session_id()
    result = DemoResult(session_id=session_id, server_id=server_id)
    from common.lab_env import lab_environment  # local import: avoids a cycle at module load
    with lab_environment([server_id], extra_env) as env:
        async with connect(spec, session_id, env) as session:
            listed = await session.list_tools()
            result.tools = [t.name for t in listed.tools]
            for tool, arguments in DEMO_CALLS.get(server_id, []):
                if "url" in arguments:
                    arguments = {**arguments, "url": arguments["url"].replace("{web}", env["MCP_WEB_BASE_URL"])}
                r = await session.call_tool(tool, arguments)
                result.calls.append(ToolCallRecord(tool, arguments, bool(r.is_error), _result_text(r)))
    return result


def _print_result(res: DemoResult) -> None:
    print(f"session_id : {res.session_id}")
    print(f"server     : {res.server_id}")
    print(f"tools      : {', '.join(res.tools)}")
    for c in res.calls:
        status = "ERROR" if c.is_error else "ok"
        preview = c.text if len(c.text) < 300 else c.text[:300] + "..."
        print(f"\n> tools/call {c.tool} {json.dumps(c.arguments)}  [{status}]")
        print("  " + preview.replace("\n", "\n  "))


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic scripted MCP client")
    parser.add_argument("--server", default="filesystem")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, level=os.getenv("LOG_LEVEL", "WARNING"),
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    _print_result(asyncio.run(run_demo(args.server, args.session_id)))


if __name__ == "__main__":
    main()
