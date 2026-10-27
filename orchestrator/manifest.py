"""Session manifest: one labelled line per session.

Simple explanation
------------------
The proxy logs say *what happened* in a session. The manifest says *what the
session was*: benign or attack, which attack family, whether the attack was
attempted and whether it succeeded, which servers, task, seed and brain were
used. The ML pipeline joins the two by ``session_id``. Labels come only from
here, never from the logs, so the detector can't "read the answer" from them.

File: ``<data_dir>/manifests/sessions.jsonl`` (append-only, one JSON object
per line).

Label rules (enforced by :func:`validate_entry`)
------------------------------------------------
* ``benign``: ``attack_family`` is null, ``attack_attempted`` and
  ``attack_succeeded`` are false.
* ``attack``: ``attack_family`` is a known family and ``attack_attempted`` is
  true.
* ``attack_succeeded`` implies ``attack_attempted``.

**Attempt vs success.** The IDS label is the *attempt*: malicious metadata
was on the wire. Success (the model actually followed it) is recorded for
analysis only, because it depends on the model, not on the traffic.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = 1
LAB_VERSION = "0.9.1"   # bump when traffic-generating code changes meaningfully
# 0.9.1: benign servers that use sampling (writing_assistant, helpdesk) and their tasks

LABELS = {"benign", "attack"}
ATTACK_FAMILIES = {"poisoned_tool", "shadowing", "sampling_injection"}


class ManifestError(ValueError):
    pass


@dataclass
class ManifestEntry:
    session_id: str
    scenario_id: str
    task_id: str
    label: str
    attack_family: str | None
    attack_attempted: bool
    attack_succeeded: bool
    servers: list[str]
    backend: str
    seed: int | None
    status: str                     # "ok" | "failed"
    started_at: str
    ended_at: str
    duration_ms: float
    stop_reason: str = ""
    n_tool_calls: int = 0
    n_tool_errors: int = 0
    log_dir: str | None = None      # relative to the data dir
    log_files: list[str] = field(default_factory=list)
    n_log_events: int = 0
    # How each server's log ended (proxy.reader.log_end_state): "stopped",
    # "client_closed", ... Recorded so a later `verify` complaint is explainable.
    log_end_states: dict[str, str] | None = None
    error: str | None = None
    dataset_tag: str = "dev"
    llm_usage: dict[str, Any] | None = None
    attack_variant: str | None = None        # e.g. payload style of the poisoned tool
    twin_of: str | None = None               # benign partner scenario of an attack scenario
    agent_config: dict[str, Any] | None = None  # e.g. {"susceptibility": 0.35} for the mock
    description_variant: int | None = None   # benign tool-description wording (None/0 = original)
    schema_version: int = MANIFEST_SCHEMA_VERSION
    lab_version: str = LAB_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))


def validate_entry(e: ManifestEntry) -> None:
    """Raise :class:`ManifestError` if the labels are inconsistent."""
    if e.label not in LABELS:
        raise ManifestError(f"label must be one of {sorted(LABELS)}, got {e.label!r}")
    if e.label == "benign":
        if e.attack_family is not None or e.attack_attempted or e.attack_succeeded:
            raise ManifestError("benign sessions must have attack_family=None and no attack flags")
    else:
        if e.attack_family not in ATTACK_FAMILIES:
            raise ManifestError(f"attack_family must be one of {sorted(ATTACK_FAMILIES)}, got {e.attack_family!r}")
        if not e.attack_attempted:
            raise ManifestError("attack sessions must have attack_attempted=True")
    if e.label == "benign" and e.attack_variant is not None:
        raise ManifestError("benign sessions must not have an attack_variant")
    if e.attack_succeeded and not e.attack_attempted:
        raise ManifestError("attack_succeeded requires attack_attempted")
    if e.status not in ("ok", "failed"):
        raise ManifestError(f"status must be 'ok' or 'failed', got {e.status!r}")
    if not e.servers:
        raise ManifestError("servers must not be empty")


class ManifestWriter:
    """Append-only, validated, thread-safe manifest writer (one process)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: ManifestEntry) -> None:
        validate_entry(entry)
        with self._lock, open(self.path, "a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")


def load_manifest(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
