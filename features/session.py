"""Load one session's wire log into a neutralized, analysis-ready form.

Simple explanation
------------------
The proxy logs are the raw evidence and are **never modified**. For feature
extraction we read them into memory and remove the lab artefacts first:

* every message body is serialised to JSON text, passed through
  :func:`common.simulation.neutralize` (removes the ``[LAB-SIMULATION]``
  marker and replaces the canary token), then parsed back;
* message sizes are recomputed from the neutralized text, so the marker's
  bytes don't count towards size features either.

Lifecycle events written by the proxy itself (``proxy/start``,
``proxy/stop``) are dropped: they describe the lab, not MCP traffic.
Timing is deliberately not carried over (see docs/ml.md: server start-up
time dominates and says nothing about attacks).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common.simulation import neutralize
from proxy.reader import load_session

REQUIRED_FIELDS = ("session_id", "timestamp", "direction", "server_id", "method", "message_size", "body")


@dataclass
class WireEvent:
    direction: str            # client_to_server | server_to_client
    kind: str                 # request | response | notification | error | ...
    method: str | None
    server_id: str
    is_error: bool
    size: int                 # bytes of the *neutralized* compact JSON body
    body: dict[str, Any]      # neutralized body

    @property
    def tool(self) -> str | None:
        """Tool name for tools/call requests."""
        if self.method == "tools/call" and self.kind == "request":
            return (self.body.get("params") or {}).get("name")
        return None

    @property
    def arguments(self) -> dict[str, Any]:
        return (self.body.get("params") or {}).get("arguments") or {}


@dataclass
class Session:
    session_id: str
    events: list[WireEvent] = field(default_factory=list)


def neutralize_body(body: Any) -> tuple[dict[str, Any], int]:
    """Return (neutralized body, size in bytes of its compact JSON)."""
    text = neutralize(json.dumps(body, ensure_ascii=False, separators=(",", ":")))
    return json.loads(text), len(text.encode("utf-8"))


def load_wire_session(session_id: str, sessions_dir: Path) -> Session:
    """Read a session's logs (read-only) and return neutralized wire events."""
    return session_from_events(session_id, load_session(session_id, sessions_dir))


def session_from_events(session_id: str, raw: list[dict[str, Any]]) -> Session:
    """Neutralize already-loaded log events (time-ordered). Shared by offline
    extraction and the live detector, so both use identical preprocessing."""
    out = Session(session_id)
    for e in raw:
        if e["kind"] == "lifecycle":
            continue
        missing = [k for k in REQUIRED_FIELDS if k not in e]
        if missing:
            raise ValueError(f"{session_id}: event missing fields {missing}")
        if e["session_id"] != session_id:
            raise ValueError(f"{session_id}: event from another session {e['session_id']}")
        body, size = neutralize_body(e["body"] if e["body"] is not None else {})
        out.events.append(WireEvent(e["direction"], e["kind"], e["method"], e["server_id"],
                                    bool(e["is_error"]), size, body))
    return out
