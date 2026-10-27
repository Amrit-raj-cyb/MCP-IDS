"""Read proxy logs back: reconstruct one session from its per-server files.

Run:  python -m proxy.reader                 # list sessions
      python -m proxy.reader latest          # timeline of the newest session
      python -m proxy.reader SESSION_ID      # timeline of one session
      python -m proxy.reader latest --full   # include message bodies
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from proxy.proxy import DEFAULT_LOG_DIR


def log_root() -> Path:
    return Path(os.getenv("MCP_LOG_DIR") or DEFAULT_LOG_DIR)


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Time-order events of one session (several proxy files).

    Schema v2 logs carry ``mono_ns`` (precise, shared by all processes on the
    host) and are ordered by it. Older logs only have ``ts_ns``; on Windows that
    clock ticks every ~15.6 ms, so ties are broken by ``(server_id, seq)``:
    deterministic, but not necessarily the true cross-server order.
    """
    if events and all(e.get("mono_ns") is not None for e in events):
        return sorted(events, key=lambda e: (e["mono_ns"], e["server_id"], e["seq"]))
    return sorted(events, key=lambda e: (e["ts_ns"], e["server_id"], e["seq"]))


def load_session(session_id: str, log_dir: Path | None = None) -> list[dict[str, Any]]:
    """All events of a session, from all servers, in time order.

    Sort: see :func:`sort_events` (``mono_ns`` for v2 logs, else ``ts_ns``);
    ``seq`` keeps a single proxy's own order stable if two events share a ns.
    """
    session_dir = (log_dir or log_root()) / session_id
    if not session_dir.is_dir():
        raise FileNotFoundError(f"No logs for session {session_id} in {session_dir.parent}")
    events: list[dict[str, Any]] = []
    for f in sorted(session_dir.glob("*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            events += [json.loads(line) for line in fh if line.strip()]
    return sort_events(events)


# How one server's log ended (see log_end_state).
STOPPED = "stopped"              # proxy/stop recorded, exit 0 or terminated, nothing unanswered
CLIENT_CLOSED = "client_closed"  # no stop, but the client had finished: killed during shutdown
INCOMPLETE = "incomplete"        # still running, or lost before the client finished
UNCLEAN = "unclean"              # ended with an error or unanswered requests


def log_end_state(events: list[dict[str, Any]]) -> tuple[str, str]:
    """Classify how one server's log ended -> (state, reason).

    A log is complete when it has a clean ``proxy/stop`` **or** a
    ``proxy/client_eof`` with no unanswered requests. The second case occurs
    when the MCP SDK kills the proxy after its 2 s shutdown grace period:
    every request had been answered and the client had already closed the
    connection, so no traffic is missing.
    """
    stop = next((e for e in events if e.get("method") == "proxy/stop"), None)
    eof = next((e for e in events if e.get("method") == "proxy/client_eof"), None)
    if stop is not None:
        body = stop.get("body") or {}
        if body.get("exit_code") not in (0, None) or body.get("error") or body.get("unanswered_requests"):
            return UNCLEAN, f"unclean stop {body}"
        return STOPPED, "terminated during shutdown" if body.get("terminated") else "clean exit"
    if eof is not None:
        body = eof.get("body") or {}
        if body.get("unanswered_requests"):
            return UNCLEAN, f"client closed with {body['unanswered_requests']} unanswered request(s)"
        return CLIENT_CLOSED, "killed after the client finished (no stop event)"
    return INCOMPLETE, "no proxy/stop or proxy/client_eof"


def is_complete(state: str) -> bool:
    return state in (STOPPED, CLIENT_CLOSED)


def list_sessions(log_dir: Path | None = None) -> list[Path]:
    root = log_dir or log_root()
    if not root.is_dir():
        return []
    return sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)


def _summary(e: dict[str, Any]) -> str:
    body = e.get("body") or {}
    if e["kind"] == "lifecycle":
        return json.dumps(body)[:100]
    params = body.get("params") or {}
    if e["method"] == "tools/call" and e["kind"] == "request":
        return f"{params.get('name')} {json.dumps(params.get('arguments', {}))}"[:100]
    result = body.get("result") or {}
    if isinstance(result, dict) and "tools" in result:
        return "tools: " + ", ".join(t.get("name", "?") for t in result["tools"])
    if isinstance(result, dict) and "content" in result:
        text = " ".join(c.get("text", "") for c in result["content"] if isinstance(c, dict))
        return text.replace("\n", " ")[:90]
    if e["kind"] == "invalid":
        return f"unparseable: {e.get('raw', '')[:80]}"
    return ""


def print_timeline(events: list[dict[str, Any]], full: bool = False) -> None:
    arrows = {"client_to_server": "C -> S", "server_to_client": "C <- S", "proxy": "proxy "}
    clock = "mono_ns" if events and all(e.get("mono_ns") is not None for e in events) else "ts_ns"
    t0 = events[0][clock] if events else 0
    for e in events:
        t = (e[clock] - t0) / 1e6
        lat = f"{e['latency_ms']:>7.1f}ms" if e.get("latency_ms") is not None else " " * 9
        err = " ERROR" if e["is_error"] else ""
        print(f"{t:9.1f}ms {e['server_id']:<11} {arrows[e['direction']]} "
              f"{e['kind']:<12} {str(e['method'] or ''):<26} {e['message_size']:>6}B {lat}{err}  {_summary(e)}")
        if full and e.get("body") is not None:
            print("            " + json.dumps(e["body"], ensure_ascii=False)[:2000])


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect proxy JSONL logs")
    parser.add_argument("session_id", nargs="?", help="a session id, or 'latest'")
    parser.add_argument("--full", action="store_true", help="also print message bodies")
    args = parser.parse_args()
    if not args.session_id:
        for d in list_sessions():
            files = list(d.glob("*.jsonl"))
            lines = sum(1 for f in files for _ in open(f, encoding="utf-8"))
            print(f"{d.name}  servers={len(files)}  events={lines}")
        return
    session_id = args.session_id
    if session_id == "latest":
        sessions = list_sessions()
        if not sessions:
            raise SystemExit(f"No sessions in {log_root()}")
        session_id = sessions[-1].name
        print(f"session {session_id}")
    print_timeline(load_session(session_id), full=args.full)


if __name__ == "__main__":
    main()
