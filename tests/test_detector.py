"""Phase 14 tests: live detector (observe-only), alert format, replay.

A stub model with a fixed answer (always "attack" / always "benign") makes
the detector's control flow testable without any attack traffic. Real benign
sessions from the orchestrator provide realistic logs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

from detector.alerts import Alert, AlertSink, load_alerts
from detector.detector import LiveDetector, read_events_tolerant, replay, watch
from features.extractor import FEATURE_NAMES, extract_session_features, features_from_session
from features.session import session_from_events
from orchestrator.main import DataPaths, run_session
from orchestrator.scenarios import get_scenario
from proxy.reader import load_session


def _stub_model(tmp_path: Path, answer: int) -> Path:
    X = pd.DataFrame(np.zeros((4, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    pipe = Pipeline([("model", DummyClassifier(strategy="constant", constant=answer))]).fit(X, [0, 1, 0, 1])
    path = tmp_path / f"stub_{answer}.joblib"
    joblib.dump(pipe, path)
    path.with_name(path.stem + "_metadata.json").write_text(
        json.dumps({"model": "random_forest", "features": FEATURE_NAMES}), encoding="utf-8")
    return path


def _tree_hash(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.rglob("*.jsonl")):
        h.update(f.relative_to(d).as_posix().encode() + f.read_bytes())
    return h.hexdigest()


@pytest.fixture
def benign_data(tmp_path: Path) -> DataPaths:
    import asyncio
    paths = DataPaths(tmp_path / "data")
    for seed in (1, 2):
        e = asyncio.run(run_session(get_scenario("benign:calc_add"), seed=seed, paths=paths))
        assert e.status == "ok"
    return paths


# -------------------------------------------------------------- log reading

def test_tolerant_reader_skips_unfinished_line(tmp_path: Path) -> None:
    d = tmp_path / "s1"
    d.mkdir()
    ok = {"ts_ns": 1, "server_id": "a", "seq": 1, "method": "tools/list", "kind": "request"}
    stop = {"ts_ns": 2, "server_id": "a", "seq": 2, "method": "proxy/stop", "kind": "lifecycle"}
    (d / "a.jsonl").write_text(json.dumps(ok) + "\n" + json.dumps(stop)[:20], encoding="utf-8")  # half-written
    events, n_files, n_stops = read_events_tolerant(d)
    assert [e["seq"] for e in events] == [1] and (n_files, n_stops) == (1, 0)
    (d / "a.jsonl").write_text(json.dumps(ok) + "\n" + json.dumps(stop) + "\n", encoding="utf-8")
    assert read_events_tolerant(d)[1:] == (1, 1)


def test_live_and_offline_features_are_identical(benign_data: DataPaths) -> None:
    sid = next(p.name for p in benign_data.sessions.iterdir())
    live = features_from_session(session_from_events(sid, read_events_tolerant(benign_data.sessions / sid)[0]))
    assert live == extract_session_features(sid, benign_data.sessions)


# ---------------------------------------------------------- detector logic

def test_stub_attack_model_gives_one_early_and_one_final_alert(tmp_path: Path, benign_data: DataPaths) -> None:
    src = benign_data.sessions / next(p.name for p in benign_data.sessions.iterdir())
    events = load_session(src.name, benign_data.sessions)
    live = tmp_path / "live" / src.name
    live.mkdir(parents=True)
    sink_path = tmp_path / "alerts.jsonl"
    det = LiveDetector(_stub_model(tmp_path, 1), AlertSink(sink_path, None))
    for e in events:  # replay the session line by line, polling after each line
        with open(live / f"{e['server_id']}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e) + "\n")
        det.check_session(live)
    alerts = load_alerts(sink_path)
    assert [a["stage"] for a in alerts] == ["early", "final"]
    assert all(a["alert"] and a["prediction"] == "attack" for a in alerts)
    assert alerts[1]["n_messages"] == sum(e["kind"] != "lifecycle" for e in events)


@pytest.mark.parametrize("name", ["random_forest", "svm", "xgboost", "rf_xgb"])
def test_confidence_is_a_probability_for_every_probabilistic_model(name: str, tmp_path: Path,
                                                                    benign_data: DataPaths) -> None:
    """Regression: only models *named* random_forest used to get a confidence (XGBoost showed None)."""
    from ml.models import BUILDERS
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(40, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    path = tmp_path / f"{name}.joblib"
    joblib.dump(BUILDERS[name](0).fit(X, [0, 1] * 20), path)
    path.with_name(f"{name}_metadata.json").write_text(json.dumps({"model": name, "features": FEATURE_NAMES}),
                                                       encoding="utf-8")
    sid = next(p.name for p in benign_data.sessions.iterdir())
    alert = LiveDetector(path, AlertSink(tmp_path / "a.jsonl", None)).verdict(
        sid, load_session(sid, benign_data.sessions), "final")
    if name == "svm":
        assert alert.confidence is None  # a margin, not P(attack)
    else:
        assert alert.confidence == alert.score and 0.0 <= alert.confidence <= 1.0


def test_stub_benign_model_never_alerts_early(tmp_path: Path, benign_data: DataPaths) -> None:
    sink_path = tmp_path / "alerts.jsonl"
    det = watch(benign_data.sessions, _stub_model(tmp_path, 0), sink_path, include_existing=True,
                max_final=2, timeout=30, quiet=True)
    alerts = load_alerts(sink_path)
    assert len(det.finals) == 2 and [a["stage"] for a in alerts] == ["final", "final"]
    assert not any(a["alert"] for a in alerts)


def test_watch_ignores_sessions_finished_before_start(tmp_path: Path, benign_data: DataPaths) -> None:
    det = watch(benign_data.sessions, _stub_model(tmp_path, 1), None, include_existing=False,
                timeout=1.0, quiet=True)
    assert det.finals == []


def test_detector_is_observe_only(tmp_path: Path, benign_data: DataPaths) -> None:
    before = _tree_hash(benign_data.root)
    replay(benign_data.root, _stub_model(tmp_path, 1), tmp_path / "a.jsonl", quiet=True)
    watch(benign_data.sessions, _stub_model(tmp_path, 1), None, include_existing=True, max_final=2,
          timeout=30, quiet=True)
    assert _tree_hash(benign_data.root) == before
    assert not list(benign_data.root.rglob("alerts*"))  # alerts never written into the dataset


# ------------------------------------------------------------ replay/alerts

def test_replay_counts(tmp_path: Path, benign_data: DataPaths) -> None:
    res = replay(benign_data.root, _stub_model(tmp_path, 1), None, quiet=True)
    assert res["sessions"] == 2 and res["alerts"] == 2
    assert res["all_sessions"] == {"n": 2, "tp": 0, "fp": 2, "tn": 0, "fn": 0}
    assert res["model_trained_on_this_dataset"] is False and res["held_out_test_sessions_only"] is None


def test_alert_json_format() -> None:
    a = Alert(alert=True, prediction="attack", confidence=0.91, score=0.91, session_id="abc123", stage="final",
              model="random_forest", n_messages=9, servers=["calculator"], detection_ms=12.3)
    d = json.loads(a.to_json())
    assert {"alert", "prediction", "confidence", "session_id", "stage", "timestamp"} <= set(d)
    assert d["alert"] is True and d["confidence"] == 0.91


def test_default_model_is_the_tuned_rf_xgb_and_loads() -> None:
    from detector.detector import DEFAULT_MODEL
    from ml.inference import Detector
    from ml.models import is_probabilistic
    if not DEFAULT_MODEL.is_file():
        pytest.skip(f"trained model not present: {DEFAULT_MODEL}")
    det = Detector(DEFAULT_MODEL)
    assert det.meta["model"] == "rf_xgb" and is_probabilistic(det.pipeline)
    assert det.meta["tuned_params"] is not None  # chosen by task-grouped inner CV (ml/tuning.py)
    assert det.meta["n_train"] == 1540  # training tasks of the 2,220-session dataset (task-grouped split)
    out = det.classify_features({f: 0.0 for f in det.features})
    assert 0.0 <= out["score"] <= 1.0
