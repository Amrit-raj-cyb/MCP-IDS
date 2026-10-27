"""Phase 3 tests: logging proxy (classification, correlation, forwarding, logging)."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from agent.client import connect, new_session_id
from agent.driver import run_agent
from agent.llm import MockLLM
from agent.tasks import get_task
from common.registry import PROJECT_ROOT, ServerSpec, get_server
from proxy.logger import SessionLogger
from proxy.models import CLIENT_TO_SERVER, SERVER_TO_CLIENT, classify, error_info
from proxy.reader import load_session

ECHO_SERVER = ("import sys\n"
               "for l in iter(sys.stdin.buffer.readline, b''):\n"
               "    sys.stdout.buffer.write(l); sys.stdout.buffer.flush()\n")


def _line(obj: dict) -> bytes:
    return (json.dumps(obj) + "\n").encode()


# ------------------------------------------------------------ classification

def test_classify_jsonrpc_kinds() -> None:
    assert classify({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) == ("request", "tools/list", 1)
    assert classify({"jsonrpc": "2.0", "method": "notifications/initialized"})[0] == "notification"
    assert classify({"jsonrpc": "2.0", "id": 1, "result": {}})[0] == "response"
    assert classify({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "x"}})[0] == "error"
    assert classify([{"id": 1}])[0] == "batch"
    assert classify("nonsense")[0] == "invalid"


def test_error_info_detects_protocol_and_tool_errors() -> None:
    assert error_info({"id": 1, "error": {"code": -32602, "message": "bad"}}) == (True, -32602, "bad")
    assert error_info({"id": 1, "result": {"content": [], "isError": True}}) == (True, None, None)
    assert error_info({"id": 1, "result": {"content": [], "isError": False}}) == (False, None, None)


def test_correlation_both_directions() -> None:
    lg = SessionLogger(None, "s", "srv")  # path=None: classify only, no file
    req = lg.record_line(CLIENT_TO_SERVER, _line({"jsonrpc": "2.0", "id": 7, "method": "tools/call"}))
    resp = lg.record_line(SERVER_TO_CLIENT, _line({"jsonrpc": "2.0", "id": 7, "result": {}}))
    assert resp.method == "tools/call" and resp.request_seq == req.seq and resp.latency_ms >= 0

    # Server-initiated request (e.g. sampling) answered by the client.
    lg.record_line(SERVER_TO_CLIENT, _line({"jsonrpc": "2.0", "id": 0, "method": "sampling/createMessage"}))
    back = lg.record_line(CLIENT_TO_SERVER, _line({"jsonrpc": "2.0", "id": 0, "result": {}}))
    assert back.method == "sampling/createMessage"

    # Same id in the *same* direction is not a response to itself; ids are per direction.
    orphan = lg.record_line(SERVER_TO_CLIENT, _line({"jsonrpc": "2.0", "id": 99, "result": {}}))
    assert orphan.method is None and orphan.request_seq is None
    assert lg.unanswered_requests == 0


def test_response_logged_before_its_request_is_still_matched() -> None:
    """Regression: a fast server's response can reach the logger before the request's own thread logs it.

    Seen in a demo run: the response got no method and the request stayed unanswered, so the log was
    classified ``unclean``. The response must now wait for the request and be matched.
    """
    import threading
    import time

    from proxy.reader import log_end_state

    lg = SessionLogger(None, "s", "srv")
    out: dict = {}

    def log_response() -> None:
        out["resp"] = lg.record_line(SERVER_TO_CLIENT, _line({"jsonrpc": "2.0", "id": 3, "result": {}}),
                                     mono_ns=2_000_000)

    t = threading.Thread(target=log_response)
    t.start()
    time.sleep(0.02)  # the request's thread is still busy forwarding
    req = lg.record_line(CLIENT_TO_SERVER, _line({"jsonrpc": "2.0", "id": 3, "method": "tools/call"}),
                         mono_ns=1_000_000)
    t.join(timeout=2)
    resp = out["resp"]
    assert resp.method == "tools/call" and resp.request_seq == req.seq and resp.seq > req.seq
    assert resp.latency_ms == 1.0  # from the read timestamps, not from logging order
    assert lg.unanswered_requests == 0
    stop = {"method": "proxy/stop", "body": {"exit_code": 0, "unanswered_requests": lg.unanswered_requests}}
    assert log_end_state([stop])[0] == "stopped"


def test_unmatched_response_waits_only_briefly() -> None:
    import time

    from proxy.logger import EARLY_RESPONSE_WAIT_S

    lg = SessionLogger(None, "s", "srv")
    t0 = time.perf_counter()
    orphan = lg.record_line(SERVER_TO_CLIENT, _line({"jsonrpc": "2.0", "id": 42, "result": {}}))
    assert time.perf_counter() - t0 < EARLY_RESPONSE_WAIT_S + 0.5
    assert orphan.method is None and orphan.request_seq is None and lg.unanswered_requests == 0


def test_invalid_line_is_logged_not_dropped() -> None:
    ev = SessionLogger(None, "s", "srv").record_line(CLIENT_TO_SERVER, b"not json {\n")
    assert ev.kind == "invalid" and ev.raw == "not json {" and ev.body is None


# ------------------------------------------------------- forwarding (bytes)

def test_proxy_forwards_bytes_unchanged(log_dir: Path) -> None:
    lines = [
        _line({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        b'{"jsonrpc":"2.0","id":"a-\xc3\xa9","method":"x"}\r\n',  # CRLF + UTF-8
        b"\n",                                                       # blank line
        b"this is not json\n",
        _line({"jsonrpc": "2.0", "method": "notifications/progress", "params": {"p": 0.5}}),
    ]
    payload = b"".join(lines)
    proc = subprocess.run(
        [sys.executable, "-m", "proxy.proxy", "--server-id", "echo", "--", sys.executable, "-c", ECHO_SERVER],
        input=payload, capture_output=True, timeout=30, cwd=PROJECT_ROOT,
        env={**__import__("os").environ, "MCP_SESSION_ID": "fwd-test", "MCP_LOG_DIR": str(log_dir)},
    )
    assert proc.returncode == 0, proc.stderr.decode()
    assert proc.stdout == payload  # byte-for-byte, CRLF and UTF-8 included

    events = load_session("fwd-test", log_dir)
    wire = [e for e in events if e["kind"] != "lifecycle"]
    # 4 non-blank lines, each seen once in each direction (echo server).
    assert len(wire) == 8
    assert {e["session_id"] for e in events} == {"fwd-test"}
    assert [e["method"] for e in events if e["kind"] == "lifecycle"] == ["proxy/start", "proxy/client_eof", "proxy/stop"]
    assert sum(e["kind"] == "invalid" for e in wire) == 2
    utf8 = next(e for e in wire if e["jsonrpc_id"] == "a-é")
    assert utf8["message_size"] == len(lines[1].rstrip(b"\r\n"))


# --------------------------------------------- integration with the agent

async def test_agent_session_is_fully_logged(log_dir: Path) -> None:
    run = await run_agent(get_task("fs_report_digest"), MockLLM(seed=1), seed=1)
    events = load_session(run.session_id, log_dir)
    wire = [e for e in events if e["kind"] != "lifecycle"]

    assert {e["session_id"] for e in events} == {run.session_id}
    assert {e["server_id"] for e in events} == {"filesystem"}
    assert wire[0]["method"] == "initialize" and wire[0]["direction"] == CLIENT_TO_SERVER
    assert wire[1]["method"] == "initialize" and wire[1]["kind"] == "response"

    calls = [e for e in wire if e["method"] == "tools/call" and e["kind"] == "request"]
    results = [e for e in wire if e["method"] == "tools/call" and e["kind"] == "response"]
    assert len(calls) == len(results) == len(run.calls)
    # The proxy's view agrees with the agent's own record, call by call.
    for rec, req, res in zip(run.calls, calls, results, strict=True):
        assert req["body"]["params"]["name"] == rec.tool
        assert req["body"]["params"]["arguments"] == rec.arguments
        assert res["is_error"] == rec.is_error and res["request_seq"] == req["seq"]

    stop = events[-1]
    assert stop["method"] == "proxy/stop" and stop["body"]["exit_code"] == 0
    assert stop["body"]["unanswered_requests"] == 0


async def test_two_servers_one_session_merge(log_dir: Path, tmp_path: Path) -> None:
    import shutil
    sandbox = tmp_path / "sb"
    shutil.copytree(PROJECT_ROOT / "sandbox", sandbox)
    fs = get_server("filesystem")
    fs_b = ServerSpec("filesystem_b", fs.module, "benign", "second copy for the merge test")
    sid, env = new_session_id(), {"MCP_FS_SANDBOX": str(sandbox)}

    async with connect(fs, sid, env) as a, connect(fs_b, sid, env) as b:
        await asyncio.gather(a.call_tool("read_file", {"path": "notes.txt"}),
                             b.call_tool("list_directory", {"path": "."}))

    assert sorted(p.name for p in (log_dir / sid).iterdir()) == ["filesystem.jsonl", "filesystem_b.jsonl"]
    events = load_session(sid, log_dir)
    assert {e["server_id"] for e in events} == {"filesystem", "filesystem_b"}
    assert [e["ts_ns"] for e in events] == sorted(e["ts_ns"] for e in events)


async def test_unwritable_log_dir_does_not_break_traffic(tmp_path: Path, monkeypatch) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")  # a *file* where the log directory should be
    monkeypatch.setenv("MCP_LOG_DIR", str(blocker))
    run = await run_agent(get_task("fs_summarize_notes"), MockLLM(seed=0))
    assert run.stop_reason == "end_turn" and run.calls and not run.calls[-1].is_error


async def test_no_proxy_mode_writes_no_logs(log_dir: Path) -> None:
    run = await run_agent(get_task("fs_summarize_notes"), MockLLM(seed=0), proxied=False)
    assert run.calls and run.log_dir is None and not (log_dir / run.session_id).exists()


# ------------------------------------------------------- event ordering (v2)

def test_sort_events_prefers_precise_clock_and_falls_back() -> None:
    from proxy.reader import sort_events
    # Windows wall clock ticks every ~15.6 ms: equal ts_ns, true order only in mono_ns.
    late = {"ts_ns": 100, "mono_ns": 20, "server_id": "a_server", "seq": 9}
    early = {"ts_ns": 100, "mono_ns": 10, "server_id": "z_server", "seq": 1}
    assert sort_events([late, early]) == [early, late]
    # Schema-v1 logs (no mono_ns): deterministic (ts_ns, server_id, seq) order, no recursion.
    v1 = [{"ts_ns": 5, "server_id": "b", "seq": 1}, {"ts_ns": 5, "server_id": "a", "seq": 2}]
    assert [e["server_id"] for e in sort_events(v1)] == ["a", "b"]
    assert sort_events([]) == []


def test_new_logs_carry_mono_ns(log_dir: Path) -> None:
    import asyncio
    from proxy.models import SCHEMA_VERSION
    run = asyncio.run(run_agent(get_task("fs_summarize_notes"), MockLLM(seed=0)))
    events = load_session(run.session_id, log_dir)
    assert all(e["schema_version"] == SCHEMA_VERSION == 2 and isinstance(e["mono_ns"], int) for e in events)
    monos = [e["mono_ns"] for e in events]
    assert monos == sorted(monos)
