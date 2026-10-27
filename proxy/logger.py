"""Turn raw protocol lines into :class:`LogEvent` records and write JSONL.

Request/response correlation
----------------------------
JSON-RPC responses don't repeat the method name; they only carry the ``id`` of
the request they answer. The logger remembers every request it has seen:
``(direction, id) -> (seq, ts_ns, method)``. When a response arrives in the
*opposite* direction with that id, it is labelled with the method, the
request's ``seq`` and the latency. This works both ways:

* client request (``tools/call``) -> server response
* server request (``sampling/createMessage``, Phase 8) -> client response

Ordering race (fixed 2026-10-07): each direction has its own thread, and each
thread forwards a line *before* logging it. A fast server can therefore answer
a request, and the other thread can log that response, before the request's
own thread has logged the request. The response then found no pending request
(no method, no latency) and the request stayed "unanswered", so the log ended
``unclean``. Now a response without a pending match waits briefly
(``EARLY_RESPONSE_WAIT_S``) for its request to be registered. The wait happens
in the logging step, after the response was already forwarded, so traffic is
not delayed; a genuinely unmatched response is logged after the wait as before.

Robustness rule: logging must never break the traffic it observes. A write
failure is reported once on stderr and logging is disabled; forwarding goes on.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from proxy.models import (CLIENT_TO_SERVER, PROXY, SCHEMA_VERSION, SERVER_TO_CLIENT,
                          LogEvent, classify, error_info, iso)

log = logging.getLogger("proxy.logger")

_OPPOSITE = {CLIENT_TO_SERVER: SERVER_TO_CLIENT, SERVER_TO_CLIENT: CLIENT_TO_SERVER}

# How long a response that arrived "before" its request may wait for the request
# to be logged by the other thread (see the module docstring). The other thread
# only has to finish one flush, so microseconds are normal; this is an upper bound.
EARLY_RESPONSE_WAIT_S = 0.1


def session_log_path(log_dir: Path, session_id: str, server_id: str) -> Path:
    """``<log_dir>/<session_id>/<server_id>.jsonl`` -- one file per proxy.

    One file per server (instead of one shared file per session) because several
    proxy *processes* write concurrently; appends from different processes to one
    file can interleave on Windows. The reader merges the files by ``mono_ns``
    (precise, cross-process), falling back to ``ts_ns`` for schema-v1 logs.
    """
    return log_dir / session_id / f"{server_id}.jsonl"


class SessionLogger:
    def __init__(self, path: Path | None, session_id: str, server_id: str) -> None:
        self.session_id = session_id
        self.server_id = server_id
        self.path = path
        self._lock = threading.Lock()   # two forwarding threads share one logger
        self._registered = threading.Condition(self._lock)  # signalled when a request is registered
        self._seq = 0
        self._pending: dict[tuple[str, str], tuple[int, int, str | None]] = {}
        self._fh = None
        self.counts = {CLIENT_TO_SERVER: 0, SERVER_TO_CLIENT: 0}
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._fh = open(path, "a", encoding="utf-8")
            except OSError as exc:
                log.error("logging disabled, cannot open %s: %s", path, exc)

    # ---------------------------------------------------------------- events

    def record_line(self, direction: str, line: bytes, ts_ns: int | None = None,
                    mono_ns: int | None = None) -> LogEvent:
        """Log one protocol line (as raw bytes, newline included or not)."""
        # ts_ns should be the moment the proxy *read* the line (passed in by the
        # pump). Taking it here, after forwarding, let a later message on another
        # server's proxy get an earlier timestamp (the client reacts as soon as
        # the line is forwarded), which scrambled the merged session order.
        ts_ns = ts_ns if ts_ns is not None else time.time_ns()
        mono_ns = mono_ns if mono_ns is not None else time.perf_counter_ns()
        payload = line.rstrip(b"\r\n")
        body: Any = None
        raw: str | None = None
        try:
            body = json.loads(payload.decode("utf-8"))
            kind, method, msg_id = classify(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raw = payload.decode("utf-8", errors="replace")
            kind, method, msg_id = "invalid", None, None
        is_error, code, message = error_info(body)

        with self._registered:
            match = None
            if kind in ("response", "error") and msg_id is not None:
                req_key = (_OPPOSITE[direction], json.dumps(msg_id))
                if req_key not in self._pending:
                    # The request may have been forwarded but not yet logged by the other thread.
                    self._registered.wait_for(lambda: req_key in self._pending, timeout=EARLY_RESPONSE_WAIT_S)
                match = self._pending.pop(req_key, None)
            seq = self._next_seq()
            request_seq = latency = None
            key = (direction, json.dumps(msg_id)) if msg_id is not None else None
            if kind == "request" and key:
                self._pending[key] = (seq, mono_ns, method)
                self._registered.notify_all()
            elif kind in ("response", "error") and msg_id is not None:
                if match:
                    request_seq, req_mono, method = match
                    latency = round((mono_ns - req_mono) / 1e6, 3)  # precise clock, not 15.6 ms ticks
            self.counts[direction] = self.counts.get(direction, 0) + 1
            event = LogEvent(SCHEMA_VERSION, self.session_id, self.server_id, seq, ts_ns, iso(ts_ns),
                             direction, kind, method, msg_id, len(payload), is_error, code, message,
                             request_seq, latency, body, raw, mono_ns)
            self._write(event)
        return event

    def record_lifecycle(self, method: str, info: dict[str, Any]) -> None:
        ts_ns, mono_ns = time.time_ns(), time.perf_counter_ns()
        with self._lock:
            event = LogEvent(SCHEMA_VERSION, self.session_id, self.server_id, self._next_seq(), ts_ns,
                             iso(ts_ns), PROXY, "lifecycle", method, None, 0, False, None, None,
                             None, None, info, None, mono_ns)
            self._write(event)

    @property
    def unanswered_requests(self) -> int:
        return len(self._pending)

    # -------------------------------------------------------------- internals

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _write(self, event: LogEvent) -> None:
        if self._fh is None:
            return
        try:
            self._fh.write(event.to_json() + "\n")
            self._fh.flush()  # survive the proxy being killed at shutdown
        except OSError as exc:
            log.error("logging disabled after write error: %s", exc)
            self._fh = None

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.close()
                self._fh = None
