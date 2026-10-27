"""Confidence intervals, task-grouped headline, and benign-only anomaly detection."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import ml.evaluate as ev
from ml.anomaly import BenignOnlyDetector
from ml.dataset import FeatureData
from ml.models import BUILDERS
from ml.uncertainty import cluster_bootstrap, wilson, wilson_intervals


def _data(n_tasks: int = 6, per_task: int = 10, seed: int = 3) -> FeatureData:
    """Each task has benign and attack sessions; attacks sit far from benign in feature space."""
    rng = np.random.default_rng(seed)
    rows, labels, meta = [], [], []
    families = ["poisoned_tool", "shadowing", "sampling_injection"]
    for t in range(n_tasks):
        for i in range(per_task):
            attack = i % 2 == 1
            rows.append({"desc_len_max": rng.normal(300 if attack else 100, 5),
                         "size_mean": rng.normal(200, 5)})
            labels.append(int(attack))
            meta.append({"session_id": f"t{t}s{i}", "task_id": f"task{t}",
                         "attack_family": families[t % 3] if attack else None,
                         "attack_succeeded": False, "attack_variant": None})
    X = pd.DataFrame(rows)
    schema = {"features": [{"name": c, "category": "content", "used_for_training": True} for c in X]}
    return FeatureData(X, np.asarray(labels), pd.DataFrame(meta), list(X.columns), schema)


def test_wilson_matches_known_values() -> None:
    assert wilson(0, 0) == (0.0, 1.0)
    lo, hi = wilson(0, 27)
    assert lo == 0.0 and hi == pytest.approx(0.125, abs=0.002)  # "0 of 27" allows up to ~12.5 %
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.404, abs=0.002) and hi == pytest.approx(0.596, abs=0.002)
    ci = wilson_intervals([0, 0, 1, 1], [0, 1, 1, 1])
    assert set(ci) == {"recall", "fpr", "precision"}


def test_cluster_bootstrap_is_deterministic_and_respects_perfect_predictions() -> None:
    y = np.array([0, 1] * 30)
    groups = np.repeat([f"g{i}" for i in range(6)], 10)
    perfect = cluster_bootstrap(y, y, groups, n_boot=200, seed=1)
    assert perfect["f1"] == (1.0, 1.0) and perfect["fpr"] == (0.0, 0.0)
    noisy = y.copy()
    noisy[:10] = 1 - noisy[:10]  # one task predicted completely wrong
    a = cluster_bootstrap(y, noisy, groups, n_boot=200, seed=1)
    b = cluster_bootstrap(y, noisy, groups, n_boot=200, seed=1)
    assert a == b
    assert a["f1"][0] < a["f1"][1] <= 1.0


def test_cluster_bootstrap_skips_resamples_without_both_classes() -> None:
    y = np.array([0] * 10 + [1] * 10)
    groups = np.array(["benign_task"] * 10 + ["attack_task"] * 10)
    r = cluster_bootstrap(y, y, groups, n_boot=400, seed=2)
    assert 0 < r["n_valid_resamples"] < 400


def test_benign_only_detector_flags_outliers_and_needs_fit() -> None:
    rng = np.random.default_rng(0)
    benign = pd.DataFrame({"a": rng.normal(0, 1, 400), "b": rng.normal(0, 1, 400)})
    for name in ("isolation_forest", "one_class_svm"):
        det = BenignOnlyDetector(name, seed=0)
        with pytest.raises(RuntimeError):
            det.predict(benign)
        det.fit(benign)
        assert det.predict(benign).mean() == pytest.approx(0.05, abs=0.02)  # threshold = 0.95 quantile
        far = pd.DataFrame({"a": [12.0, -12.0], "b": [12.0, 12.0]})
        assert det.predict(far).tolist() == [1, 1]
    with pytest.raises(ValueError):
        BenignOnlyDetector("isolation_forest", seed=0).fit(benign.iloc[:0])


def test_anomaly_cv_never_fits_on_attack_sessions(monkeypatch) -> None:
    seen: list[float] = []

    class Spy(BenignOnlyDetector):
        def fit(self, X_benign):
            seen.append(float(X_benign["desc_len_max"].max()))
            return super().fit(X_benign)

    monkeypatch.setattr(ev, "BenignOnlyDetector", Spy)
    out = ev.anomaly_grouped_cv(_data(per_task=40), seed=0)
    assert seen and max(seen) < 200  # attack rows (desc_len ~300) never reach fit()
    for name in ("isolation_forest", "one_class_svm"):
        assert out[name]["recall"] >= 0.8  # far-off sessions are mostly flagged without any attack training
        assert "ci95_task_bootstrap" in out[name] and "ci95_wilson" in out[name]
    assert out["isolation_forest"]["fpr"] <= 0.15


def test_grouped_cv_is_the_headline_with_intervals() -> None:
    data = _data()
    g = ev.grouped_cv(data, seed=0)
    assert g["n_groups"] == 6 and len(g["folds"]) == 5
    m = {"grouped_cv": g, "models": {n: {"test": {"f1": 1.0, "precision": 1.0, "recall": 1.0, "fpr": 0.0}}
                                     for n in BUILDERS}}
    h = ev.headline(m)
    assert h["protocol"].startswith("task-grouped")
    for name in BUILDERS:
        assert h[name]["random_split_f1_for_comparison"] == 1.0
        assert h[name]["ci95_task_bootstrap"]["f1"] is not None
    m["headline"] = h
    text = "\n".join(ev.headline_section(m))
    assert "Quote these numbers" in text and "[" in text


def test_headline_falls_back_when_grouping_is_impossible() -> None:
    m = {"grouped_cv": {"skipped": "only 1 distinct task_id"},
         "models": {n: {"test": {"f1": 0.9, "precision": 0.9, "recall": 0.9, "fpr": 0.1}}
                    for n in BUILDERS}}
    h = ev.headline(m)
    assert h["protocol"].startswith("random split") and h["svm"]["f1"] == 0.9 and h["rf_xgb"]["f1"] == 0.9
