"""Phase 14: live detector (observe-only demonstration).

Simple explanation
------------------
While the lab runs, every logging proxy appends MCP messages to
``<log-dir>/<session_id>/<server>.jsonl``. The detector is a separate process
that **reads** those files about twice per second. For each session it:

1. rebuilds the session from the log lines written so far (the same
   neutralization and feature code as training);
2. asks the trained model for a verdict;
3. raises an **early** alert the first time a running session looks like an
   attack (poisoned metadata already shows up in ``tools/list``, before any
   tool is used);
4. gives one **final** verdict when every proxy of the session has stopped.

Why a sidecar and not inside the proxy: the detector can't delay, alter or
block traffic, because it isn't on the traffic path. If it crashes, the lab
keeps running and logging.

Commands
--------
    python -m detector.detector watch  --log-dir data/live/raw/sessions
    python -m detector.detector replay --data-dir data/try6

Caveat: early verdicts are computed on *partial* sessions, while the model
was trained on complete ones, so they are a heuristic signal (see docs/detector.md).
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from detector.alerts import Alert, AlertSink
from features.extractor import dataset_hash
from features.session import session_from_events
from ml.inference import Detector as ModelDetector
from ml.models import is_probabilistic
from orchestrator.manifest import load_manifest
from proxy.reader import is_complete, log_end_state, sort_events

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Tuned RF + XGBoost soft vote trained on the final dataset (exp_017, 2,220 sessions incl. benign sampling
# servers and the original-wording benign corpus; task-grouped split): nested task-grouped F1 0.796,
# FPR 0.2 %, the best of the seven models. Any saved pipeline works via --model, e.g.
# models/combined_canonical_20261010/random_forest.joblib or .../cnn_raw.joblib (the raw-traffic CNN).
DEFAULT_MODEL = PROJECT_ROOT / "models" / "combined_canonical_20261010" / "rf_xgb.joblib"
DEFAULT_ALERTS = PROJECT_ROOT / "data" / "alerts" / "alerts.jsonl"
EVIDENCE = ("tools_list_resp_size_max", "desc_len_max", "param_desc_len_max", "directive_word_count",
            "model_address_count", "n_tools_call", "n_servers_mounted")


# ------------------------------------------------------------- log reading

def read_events_tolerant(session_dir: Path) -> tuple[list[dict[str, Any]], int, int]:
    """Read all complete JSON lines of a (possibly still running) session.

    Returns (events sorted like proxy.reader, number of files, number of
    server logs that have *ended*: clean ``proxy/stop`` or ``proxy/client_eof``,
    see :func:`proxy.reader.log_end_state`). A trailing line without a newline
    is still being written by a proxy; it is skipped now and picked up on the
    next poll.
    """
    events: list[dict[str, Any]] = []
    files = sorted(session_dir.glob("*.jsonl"))
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = text.split("\n")
        for line in lines[:-1]:          # the last element is "" or an unfinished line
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    events = sort_events(events)
    servers = {f.stem for f in files}
    ended = sum(is_complete(log_end_state([e for e in events if e.get("server_id") == s])[0]) for s in servers)
    return events, len(files), ended


def _signature(session_dir: Path) -> tuple:
    return tuple((f.name, f.stat().st_size) for f in sorted(session_dir.glob("*.jsonl")))


# ------------------------------------------------------------- detector core

@dataclass
class _State:
    signature: tuple = ()
    early_alerted: bool = False
    final: bool = False


class LiveDetector:
    def __init__(self, model_path: Path, sink: AlertSink, early: bool = True) -> None:
        self.model = ModelDetector(model_path)
        self.sink = sink
        self.early = early
        self.states: dict[str, _State] = {}
        self.finals: list[Alert] = []

    def verdict(self, session_id: str, events: list[dict[str, Any]], stage: str) -> Alert | None:
        t0 = time.perf_counter()
        session = session_from_events(session_id, events)
        if not session.events:
            return None
        out, row = self.model.classify_wire_session(session)  # features, or raw text for raw-traffic models
        ms = (time.perf_counter() - t0) * 1000
        prob = out["score"] if is_probabilistic(self.model.pipeline) else None  # SVM margin is not P(attack)
        return Alert(alert=out["alert"], prediction=out["prediction"], confidence=prob, score=out["score"],
                     session_id=session_id, stage=stage, model=out["model"], n_messages=len(session.events),
                     servers=sorted({e.server_id for e in session.events}), detection_ms=round(ms, 2),
                     evidence={k: row[k] for k in EVIDENCE if k in row})

    def check_session(self, session_dir: Path) -> None:
        sid = session_dir.name
        st = self.states.setdefault(sid, _State())
        if st.final:
            return
        sig = _signature(session_dir)
        if sig == st.signature:
            return                       # nothing new since the last poll
        st.signature = sig
        events, n_files, n_stops = read_events_tolerant(session_dir)
        complete = n_files > 0 and n_stops >= n_files
        if complete:
            a = self.verdict(sid, events, "final")
            st.final = True
            if a:
                self.finals.append(a)
                self.sink.emit(a)
        elif self.early and not st.early_alerted:
            a = self.verdict(sid, events, "early")
            if a and a.alert:            # early: only report suspicion, once per session
                st.early_alerted = True
                self.sink.emit(a)

    def poll(self, log_dir: Path) -> None:
        if not log_dir.is_dir():
            return
        for d in sorted(p for p in log_dir.iterdir() if p.is_dir()):
            self.check_session(d)


def watch(log_dir: Path, model: Path, alerts: Path | None, interval: float = 0.5, early: bool = True,
          include_existing: bool = False, max_final: int | None = None, timeout: float | None = None,
          quiet: bool = False) -> LiveDetector:
    det = LiveDetector(model, AlertSink(alerts, None if quiet else __import__("sys").stdout), early)
    if not include_existing and log_dir.is_dir():
        for d in log_dir.iterdir():      # sessions finished before we started are not "live"
            if d.is_dir():
                _, n_files, n_stops = read_events_tolerant(d)
                if n_files and n_stops >= n_files:
                    det.states[d.name] = _State(final=True)
    start = time.monotonic()
    while True:
        det.poll(log_dir)
        if max_final is not None and len(det.finals) >= max_final:
            break
        if timeout is not None and time.monotonic() - start > timeout:
            break
        time.sleep(interval)
    return det


# ------------------------------------------------------------- replay

def replay(data_dir: Path, model: Path, alerts: Path | None, quiet: bool = False) -> dict:
    """Final verdict for every session of a finished dataset (read-only)."""
    det = LiveDetector(model, AlertSink(alerts, None if quiet else __import__("sys").stdout), early=False)
    det.poll(data_dir / "raw" / "sessions")
    labels = {r["session_id"]: r["label"] for r in load_manifest(data_dir / "manifests" / "sessions.jsonl")}
    trained_on_this = det.model.meta.get("dataset_sha256") == dataset_hash(data_dir)
    split_file = Path(model).with_name("split.json")
    test_ids = set(json.loads(split_file.read_text())["test_session_ids"]) if (trained_on_this and split_file.is_file()) else None

    def score(ids: set[str] | None) -> dict:
        tp = fp = tn = fn = 0
        for a in det.finals:
            if a.session_id not in labels or (ids is not None and a.session_id not in ids):
                continue
            actual = labels[a.session_id] == "attack"
            tp += a.alert and actual
            fp += a.alert and not actual
            tn += (not a.alert) and not actual
            fn += (not a.alert) and actual
        return {"n": tp + fp + tn + fn, "tp": tp, "fp": fp, "tn": tn, "fn": fn}

    return {"sessions": len(det.finals), "alerts": sum(a.alert for a in det.finals),
            "all_sessions": score(None),
            "model_trained_on_this_dataset": trained_on_this,
            "held_out_test_sessions_only": score(test_ids) if test_ids is not None else None,
            "median_detection_ms": sorted(a.detection_ms for a in det.finals)[len(det.finals) // 2] if det.finals else None}


def main() -> None:
    p = argparse.ArgumentParser(description="Observe-only MCP IDS detector")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="watch a live log directory")
    w.add_argument("--log-dir", type=Path, required=True, help="the proxies' MCP_LOG_DIR")
    w.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    w.add_argument("--alerts", type=Path, default=DEFAULT_ALERTS)
    w.add_argument("--interval", type=float, default=0.5)
    w.add_argument("--no-early", action="store_true", help="only final verdicts")
    w.add_argument("--include-existing", action="store_true", help="also judge sessions finished before start")
    w.add_argument("--max-sessions", type=int, default=None, help="stop after N final verdicts")
    w.add_argument("--timeout", type=float, default=None, help="stop after N seconds")
    r = sub.add_parser("replay", help="judge every session of a finished dataset")
    r.add_argument("--data-dir", type=Path, required=True)
    r.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    r.add_argument("--alerts", type=Path, default=None)
    r.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    if a.cmd == "watch":
        print(f"watching {a.log_dir} with {a.model.name} (observe-only; Ctrl+C to stop); alerts -> {a.alerts}")
        try:
            det = watch(a.log_dir, a.model, a.alerts, a.interval, not a.no_early, a.include_existing,
                        a.max_sessions, a.timeout)
            print(f"stopped: {len(det.finals)} final verdicts, {sum(x.alert for x in det.finals)} alerts")
        except KeyboardInterrupt:
            print("stopped")
    else:
        res = replay(a.data_dir, a.model, a.alerts, a.quiet)
        print(json.dumps(res, indent=2))
        if res["model_trained_on_this_dataset"]:
            print("NOTE: the model was trained on this dataset; only 'held_out_test_sessions_only' "
                  "reflects unseen data.")


if __name__ == "__main__":
    main()
