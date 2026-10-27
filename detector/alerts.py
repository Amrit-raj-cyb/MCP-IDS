"""Alert records and where they go.

An alert is the detector's *opinion* about one session at one moment. It is
written as one JSON line (``alerts.jsonl``) and optionally printed. Example::

    {"alert": true, "prediction": "attack", "confidence": 0.91,
     "session_id": "abc123", "stage": "early", "model": "random_forest", ...}

* ``stage = "early"``: the session is still running; verdict from the
  messages seen so far (an alert is raised once per session at most).
* ``stage = "final"``: every proxy of the session has stopped; one final
  verdict per session, benign or attack.

The detector never blocks or changes traffic. Alerts are for a human (or a
later system) to act on.
"""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO


@dataclass
class Alert:
    alert: bool
    prediction: str                 # "attack" | "benign"
    confidence: float | None        # P(attack) for probabilistic models, else None
    score: float                    # raw model score (probability or SVM margin)
    session_id: str
    stage: str                      # "early" | "final"
    model: str
    n_messages: int
    servers: list[str]
    detection_ms: float             # feature extraction + model, for this verdict
    evidence: dict[str, float] = field(default_factory=dict)  # a few feature values for the analyst
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


class AlertSink:
    """Append alerts to a JSONL file and/or print a one-line summary."""

    def __init__(self, path: Path | None, stream: TextIO | None = sys.stdout) -> None:
        self.path = Path(path) if path else None
        self.stream = stream
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, a: Alert) -> None:
        with self._lock:
            if self.path:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(a.to_json() + "\n")
            if self.stream:
                flag = "ALERT " if a.alert else "ok    "
                conf = f"{a.confidence:.2f}" if a.confidence is not None else f"score={a.score:+.2f}"
                print(f"[{a.timestamp[11:23]}] {flag} {a.stage:<5} {a.prediction:<6} {conf:<12} "
                      f"session={a.session_id[:12]} servers={','.join(a.servers)} msgs={a.n_messages} "
                      f"({a.detection_ms:.0f} ms)", file=self.stream, flush=True)


def load_alerts(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
