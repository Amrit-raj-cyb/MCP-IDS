"""Transparent stdio logging proxy for MCP.

Simple explanation
------------------
The agent thinks it is talking to the MCP server, but it is really talking to
this proxy, which starts the real server and sits in the middle::

    agent  --stdin-->  PROXY  --stdin-->  real MCP server
    agent  <--stdout-- PROXY  <--stdout-- real MCP server
                         |
                         +--> data/raw/sessions/<session_id>/<server_id>.jsonl

Every line is forwarded **byte-for-byte unchanged**; a *copy* is parsed and
logged. The proxy never alters, delays on purpose, or blocks traffic.

Technical detail
----------------
* stdio MCP frames = one JSON-RPC message per line.
* Two threads, one per direction. Threads (not asyncio) because asyncio cannot
  portably read anonymous stdin pipes on Windows.
* The server's stderr is inherited, so its diagnostics still reach the agent's
  console.
* Shutdown: agent closes our stdin -> we log ``proxy/client_eof`` and close
  the server's stdin -> server exits -> its stdout hits EOF -> we log
  ``proxy/stop`` and exit with the server's exit code.
* The MCP SDK waits only 2 s for that, then terminates the process tree. On
  POSIX a SIGTERM handler still records ``proxy/stop`` (``terminated``); on
  Windows (hard kill) ``proxy/client_eof`` is the last record. Either way all
  traffic was complete, and every log line is already flushed.

Configuration (environment)
---------------------------
``MCP_SESSION_ID``  shared session id (set by the agent/orchestrator)
``MCP_LOG_DIR``     log root (default ``data/raw/sessions``)

Run:  python -m proxy.proxy --server-id filesystem -- python -m servers.benign.filesystem.server
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from proxy.logger import SessionLogger, session_log_path
from proxy.models import CLIENT_TO_SERVER, SERVER_TO_CLIENT

log = logging.getLogger("proxy")

DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "sessions"


def pump(src: BinaryIO, dst: BinaryIO, direction: str, logger: SessionLogger,
         close_dst: bool, on_eof: Callable[[], None] | None = None) -> None:
    """Copy lines from ``src`` to ``dst`` unchanged, logging a copy of each.

    ``on_eof`` runs when ``src`` reaches a genuine end of file (not when the
    destination breaks).
    """
    try:
        for line in iter(src.readline, b""):
            # Timestamps at *read* time (before forwarding) keep cross-proxy order causal:
            # the client can only react after we forward. mono_ns is the precise clock.
            read_ns, read_mono = time.time_ns(), time.perf_counter_ns()
            try:
                dst.write(line)       # forward first: logging must not add latency
                dst.flush()
            except (BrokenPipeError, OSError):
                log.warning("%s: destination closed", direction)
                break
            if line.strip():
                logger.record_line(direction, line, read_ns, read_mono)
        else:
            if on_eof is not None:
                on_eof()
    finally:
        if close_dst:
            try:
                dst.close()
            except OSError:
                pass


def run_proxy(server_id: str, command: list[str], session_id: str, log_dir: Path,
              stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> int:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    logger = SessionLogger(session_log_path(log_dir, session_id, server_id), session_id, server_id)
    logger.record_lifecycle("proxy/start", {"command": command, "pid": os.getpid()})

    try:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    except OSError as exc:
        logger.record_lifecycle("proxy/stop", {"error": f"spawn failed: {exc}"})
        logger.close()
        log.error("could not start server %s: %s", command, exc)
        return 127

    assert child.stdin is not None and child.stdout is not None
    stop_written = threading.Event()

    def stop_info(**extra) -> dict:
        return {**extra, "messages": dict(logger.counts), "unanswered_requests": logger.unanswered_requests}

    def on_client_eof() -> None:
        # The client closed our stdin: the session is over from its side. The MCP
        # SDK does this *before* its 2 s shutdown grace period, after which it may
        # kill this process, so this event is the one that is never lost.
        logger.record_lifecycle("proxy/client_eof", stop_info())

    _install_term_handler(logger, stop_written, stop_info)
    c2s = threading.Thread(target=pump, name="c2s", daemon=True,
                           args=(stdin, child.stdin, CLIENT_TO_SERVER, logger, True, on_client_eof))
    s2c = threading.Thread(target=pump, name="s2c", daemon=True,
                           args=(child.stdout, stdout, SERVER_TO_CLIENT, logger, False))
    c2s.start()
    s2c.start()

    s2c.join()               # server's stdout closed => server is done
    code = child.wait()
    if not stop_written.is_set():
        stop_written.set()
        logger.record_lifecycle("proxy/stop", stop_info(exit_code=code))
    logger.close()
    return code


def _install_term_handler(logger: SessionLogger, stop_written: threading.Event,
                          stop_info: Callable[..., dict]) -> None:
    """On SIGTERM, record ``proxy/stop`` (``terminated: "SIGTERM"``) before exiting.

    On POSIX the MCP SDK sends SIGTERM to the proxy's process group when a
    server misses the shutdown grace period, and only later SIGKILL. Without
    this handler such a proxy would end without a stop event. (Windows kills
    immediately; there ``proxy/client_eof`` is the last record.)
    """
    if not hasattr(signal, "SIGTERM") or os.name == "nt":
        return

    def handler(signum: int, _frame: object) -> None:
        if stop_written.is_set():
            return               # the normal path is already writing the stop event
        stop_written.set()
        logger.record_lifecycle("proxy/stop", stop_info(exit_code=None, terminated=signal.Signals(signum).name))
        logger.close()
        os._exit(128 + signum)

    try:
        signal.signal(signal.SIGTERM, handler)
    except ValueError:           # not in the main thread (e.g. embedded use); skip
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Transparent MCP stdio logging proxy")
    parser.add_argument("--server-id", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="real server command, after '--'")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("missing server command after '--'")

    logging.basicConfig(stream=sys.stderr, level=os.getenv("LOG_LEVEL", "WARNING"),
                        format="%(asctime)s %(levelname)s [proxy:" + args.server_id + "] %(message)s")
    session_id = os.getenv("MCP_SESSION_ID") or "no-session"
    log_dir = Path(os.getenv("MCP_LOG_DIR") or DEFAULT_LOG_DIR)
    sys.exit(run_proxy(args.server_id, command, session_id, log_dir))


if __name__ == "__main__":
    main()
