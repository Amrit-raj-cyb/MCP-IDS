"""MCP agent driver: the decide -> call -> observe loop.

Simple explanation
------------------
1. Connect to every MCP server the task needs (each is a stdio child process).
2. Ask each server for its tools (``tools/list``) and merge them into one
   catalogue, renaming each tool ``<server_id>__<tool>`` so two servers can't
   collide (e.g. two servers that both offer ``read_file``).
3. Loop: the LLM backend picks tool calls -> the driver sends ``tools/call`` to
   the right server -> results go back to the backend -> repeat until the
   backend gives a final answer or ``max_steps`` is reached.
4. Return an :class:`AgentRun` record: every call, its server, arguments,
   error flag and latency, plus the final answer and why the run stopped.

Namespacing is our client's policy, not part of MCP. Real clients differ; we
record the *original* tool name and server in every call record so features
never depend on this choice. (Name collisions become relevant again in the
Phase 7 shadowing simulation.)

Run:  python -m agent.driver --task fs_summarize_notes            # mock
      python -m agent.driver --task fs_summarize_notes --llm claude
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field
from typing import Any

from mcp import ClientSession, types

from agent.client import connect, new_session_id
from agent.llm import LLMBackend, ToolCallRequest, ToolInfo, ToolResult, make_backend
from agent.tasks import Task, get_task, render_task
from common.registry import get_server
from common.lab_env import lab_environment
from proxy.proxy import DEFAULT_LOG_DIR

log = logging.getLogger("agent.driver")

NAMESPACE_SEP = "__"
MAX_RESULT_CHARS = 20_000  # bound what we feed back to the LLM


def namespaced(server_id: str, tool: str) -> str:
    """``filesystem`` + ``read_file`` -> ``filesystem__read_file`` (API-safe, <=64 chars)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", f"{server_id}{NAMESPACE_SEP}{tool}")[:64]


@dataclass
class CallRecord:
    step: int
    server_id: str
    tool: str               # original MCP tool name
    llm_name: str           # namespaced name the LLM used
    arguments: dict[str, Any]
    is_error: bool
    latency_ms: float
    result_chars: int
    result_preview: str


@dataclass
class AgentRun:
    session_id: str
    task_id: str
    backend: str
    servers: list[str]
    seed: int | None = None
    tools_seen: list[str] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)
    final_text: str = ""
    stop_reason: str = ""
    steps: int = 0
    duration_ms: float = 0.0
    log_dir: str | None = None              # where the proxy wrote this session's JSONL
    llm_usage: dict[str, Any] | None = None  # tokens / estimated cost (Claude only)
    sampling_interactions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Route:
    server_id: str
    tool: str
    session: ClientSession


def _text_of(result: Any) -> str:
    parts = [getattr(c, "text", "") or f"[{getattr(c, 'type', 'content')}]" for c in result.content]
    return "\n".join(parts)


async def run_agent(
    task: Task,
    backend: LLMBackend,
    session_id: str | None = None,
    servers: list[str] | None = None,
    max_steps: int = 12,
    extra_env: dict[str, str] | None = None,
    seed: int | None = None,
    proxied: bool = True,
) -> AgentRun:
    """Run one agent session. ``servers`` defaults to the task's servers."""
    session_id = session_id or new_session_id()
    server_ids = list(servers or task.servers)
    run = AgentRun(session_id=session_id, task_id=task.task_id,
                   backend=backend.name, servers=server_ids, seed=seed)
    t0 = time.perf_counter()

    async with AsyncExitStack() as stack:
        # Fresh sandbox / database / test site for this session (common/lab_env.py).
        env = stack.enter_context(lab_environment(server_ids, extra_env))
        if "MCP_WEB_BASE_URL" in env:
            task = render_task(task, {"web": env["MCP_WEB_BASE_URL"]})
        routes: dict[str, _Route] = {}
        tools: list[ToolInfo] = []
        # The fixed sampling handler is installed for EVERY connection, whatever
        # servers are mounted. A real client that supports sampling advertises the
        # capability in every `initialize`; advertising it only when the sampling
        # simulation was mounted put the label into the session's first message
        # (176 vs 163 bytes). Servers that don't sample simply never call it.
        async def sampling_callback(_context: Any, params: Any) -> types.CreateMessageResult:
            request_text = "\n".join(
                block.text for message in params.messages
                for block in (message.content if isinstance(message.content, list) else [message.content])
                if isinstance(block, types.TextContent)
            )
            response_text = "LAB-SAMPLING-ACK: fixed local callback; no model or tools invoked."
            run.sampling_interactions.append({
                "request_chars": len(request_text),
                "response_chars": len(response_text),
                "response_model": "lab-fixed-sampling-handler",
                "ack_returned": True,
            })
            return types.CreateMessageResult(
                role="assistant", content=types.TextContent(text=response_text),
                model="lab-fixed-sampling-handler", stop_reason="endTurn",
            )

        for sid in server_ids:
            spec = get_server(sid)
            session = await stack.enter_async_context(connect(
                spec, session_id, env, proxied, sampling_callback=sampling_callback
            ))
            for t in (await session.list_tools()).tools:
                name = namespaced(spec.log_id, t.name)  # the name the agent sees, never the registry key
                if name in routes:
                    log.warning("duplicate tool name %s; keeping first", name)
                    continue
                routes[name] = _Route(sid, t.name, session)
                tools.append(ToolInfo(name, t.description or "", t.input_schema))
        run.tools_seen = [t.name for t in tools]

        await backend.start(task, tools)
        results: list[ToolResult] = []
        while True:
            if run.steps >= max_steps:
                run.stop_reason = "max_steps"
                break
            decision = await backend.step(results)
            if decision.done:
                run.final_text = decision.final_text or ""
                run.stop_reason = decision.stop_reason
                break
            run.steps += 1
            results = [await _execute(call, routes, run) for call in decision.tool_calls]

    run.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    if proxied:
        log_root = (extra_env or {}).get("MCP_LOG_DIR") or os.getenv("MCP_LOG_DIR") or DEFAULT_LOG_DIR
        run.log_dir = str(Path(log_root) / session_id)
    if hasattr(backend, "usage_summary"):
        run.llm_usage = backend.usage_summary()
    return run


async def _execute(call: ToolCallRequest, routes: dict[str, _Route], run: AgentRun) -> ToolResult:
    route = routes.get(call.name)
    if route is None:
        # Model asked for a tool that doesn't exist: tell it, don't crash.
        text = f"Unknown tool '{call.name}'."
        run.calls.append(CallRecord(run.steps, "", call.name, call.name, call.arguments,
                                    True, 0.0, len(text), text))
        return ToolResult(call.call_id, text, True)

    t = time.perf_counter()
    result = await route.session.call_tool(route.tool, call.arguments)
    latency = round((time.perf_counter() - t) * 1000, 2)
    text = _text_of(result)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + "\n[truncated by agent]"
    is_error = bool(result.is_error)
    run.calls.append(CallRecord(run.steps, route.server_id, route.tool, call.name,
                                call.arguments, is_error, latency, len(text), text[:200]))
    log.info("step %d %s.%s error=%s %.1fms", run.steps, route.server_id, route.tool, is_error, latency)
    return ToolResult(call.call_id, text, is_error)


def _print_run(run: AgentRun) -> None:
    print(f"session_id : {run.session_id}")
    print(f"task       : {run.task_id}   backend: {run.backend}   seed: {run.seed}")
    print(f"servers    : {', '.join(run.servers)}")
    print(f"tools      : {', '.join(run.tools_seen)}")
    for c in run.calls:
        status = "ERROR" if c.is_error else "ok"
        print(f"  [{c.step}] {c.server_id}.{c.tool} {json.dumps(c.arguments)} -> {status} ({c.latency_ms} ms)")
    print(f"stop       : {run.stop_reason} after {run.steps} step(s), {run.duration_ms} ms")
    print(f"answer     : {run.final_text}")
    if run.llm_usage:
        u = run.llm_usage
        cost = f"~${u['est_cost_usd']:.4f}" if u["est_cost_usd"] is not None else "n/a (model not in price table)"
        print(f"llm usage  : {u['api_calls']} API call(s), {u['input_tokens']} in / "
              f"{u['output_tokens']} out tokens, est. cost {cost} ({u['model']})")
    if run.log_dir:
        print(f"wire log   : {run.log_dir}   (view: python -m proxy.reader {run.session_id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MCP agent on one task")
    parser.add_argument("--task", default="fs_summarize_notes")
    parser.add_argument("--llm", default=None, help="mock (default) | claude; or env LLM_PROVIDER")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--json", action="store_true", help="print the full run record as JSON")
    parser.add_argument("--no-proxy", action="store_true", help="talk to servers directly (no wire log)")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, level=os.getenv("LOG_LEVEL", "WARNING"),
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    task = get_task(args.task)
    backend = make_backend(args.llm, seed=args.seed)
    try:
        run = asyncio.run(run_agent(task, backend, max_steps=args.max_steps, seed=args.seed,
                                  proxied=not args.no_proxy))
    except BaseException as exc:  # noqa: BLE001 - unwrap task-group errors for a readable message
        root = _root_cause(exc)
        if backend.name == "claude" and _is_auth_or_network(root):
            sys.exit(f"Claude backend unavailable: {type(root).__name__}: {root}\n"
                     "Set ANTHROPIC_API_KEY (and make sure you have internet; the Docker "
                     "lab network is offline by design), or use --llm mock.")
        raise
    print(json.dumps(run.to_dict(), indent=2)) if args.json else _print_run(run)


def _root_cause(exc: BaseException) -> BaseException:
    """anyio wraps errors in (nested) exception groups; dig out the single cause."""
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    return exc


def _is_auth_or_network(exc: BaseException) -> bool:
    import anthropic
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.APIConnectionError)):
        return True
    return isinstance(exc, TypeError) and "authentication" in str(exc)


if __name__ == "__main__":
    main()
