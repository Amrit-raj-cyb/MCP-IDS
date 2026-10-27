"""XGBoost and the RF + XGBoost soft-voting ensemble: builders, training, inference and evaluation."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

import ml.evaluate as ev
from ml.inference import Detector
from ml.models import (ALL_BUILDERS, BUILDERS, LABELS, PARAMS, SHORT, XGB_PARAMS, BalancedXGBClassifier, _xgb, build_rf_xgb,
                       score)
from ml.train import train


def _xy(n: int = 200, seed: int = 0) -> tuple[pd.DataFrame, np.ndarray]:
    """Imbalanced (about 1 attack in 5), learnable but not trivially separable."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(n, 4)), columns=["a", "b", "c", "d"])
    y = (X["a"] + 0.4 * rng.normal(size=n) > 0.8).astype(int).to_numpy()
    return X, y


def test_every_model_has_params_label_and_file_tag() -> None:
    assert list(BUILDERS) == ["random_forest", "svm", "xgboost", "rf_xgb", "decision_tree", "cnn"]
    assert set(PARAMS) == set(LABELS) == set(SHORT) == set(ALL_BUILDERS) == set(BUILDERS) | {"cnn_raw"}
    assert SHORT["random_forest"] == "rf" and SHORT["svm"] == "svm"  # old plot names unchanged


def test_balanced_xgb_uses_balanced_sample_weights() -> None:
    X, y = _xy()
    params = {k: v for k, v in XGB_PARAMS.items() if k != "class_weight"}
    ours = _xgb(3).fit(X, y).predict_proba(X)
    explicit = XGBClassifier(random_state=3, **params).fit(
        X, y, sample_weight=compute_sample_weight("balanced", y)).predict_proba(X)
    unweighted = XGBClassifier(random_state=3, **params).fit(X, y).predict_proba(X)
    np.testing.assert_allclose(ours, explicit)
    assert not np.allclose(ours, unweighted)


def test_clone_keeps_class_and_params_so_the_ensemble_members_stay_balanced() -> None:
    c = clone(_xgb(5))
    assert type(c) is BalancedXGBClassifier
    assert c.get_params()["n_estimators"] == 300 and c.get_params()["random_state"] == 5
    X, y = _xy()
    vote = build_rf_xgb(5).fit(X, y).named_steps["model"]
    assert type(vote.named_estimators_["xgboost"]) is BalancedXGBClassifier


def test_ensemble_probability_is_the_mean_of_its_members() -> None:
    X, y = _xy()
    pipe = build_rf_xgb(7).fit(X, y)
    Xt = pipe[:-1].transform(X)
    members = np.mean([m.predict_proba(Xt) for m in pipe.named_steps["model"].estimators_], axis=0)
    np.testing.assert_allclose(pipe.predict_proba(X), members)
    np.testing.assert_array_equal(pipe.predict(X), (members[:, 1] > 0.5).astype(int))


@pytest.mark.parametrize("name", ["xgboost", "rf_xgb"])
def test_new_models_are_deterministic_and_work_through_the_detector(name: str, tmp_path: Path) -> None:
    X, y = _xy()
    a, b = BUILDERS[name](42).fit(X, y), BUILDERS[name](42).fit(X, y)
    assert score(a, X) == score(b, X)
    path = tmp_path / f"{name}.joblib"
    joblib.dump(a, path)
    path.with_name(f"{name}_metadata.json").write_text(json.dumps({"model": name, "features": list(X.columns)}),
                                                       encoding="utf-8")
    det = Detector(path)
    for i in range(10):
        out = det.classify_features(X.iloc[i].to_dict())
        assert 0.0 <= out["score"] <= 1.0  # a probability, unlike the SVM margin
        assert out["prediction"] == ("attack" if a.predict(X.iloc[[i]])[0] else "benign")


def test_pickle_uses_the_portable_xgboost_format() -> None:
    """Models trained in the Linux container must load on the Windows host (memory snapshots did not)."""
    import pickle
    X, y = _xy()
    pipe = build_rf_xgb(3).fit(X, y)
    xgb = pipe.named_steps["model"].named_estimators_["xgboost"]
    state = xgb.__getstate__()
    assert "_Booster" not in state and state["_booster_ubj"][:1] == b"{"  # UBJSON object, not a snapshot
    loaded = pickle.loads(pickle.dumps(pipe))
    np.testing.assert_array_equal(loaded.predict_proba(X), pipe.predict_proba(X))
    np.testing.assert_array_equal(loaded.named_steps["model"].named_estimators_["xgboost"].feature_importances_,
                                  xgb.feature_importances_)
    assert "_Booster" in xgb.__dict__  # pickling must not strip the live model


# ------------------------------------------------- train --only and evaluate

def _feature_dir(root: Path, n_tasks: int = 6, per_task: int = 16, seed: int = 11) -> Path:
    """A tiny feature dataset in the on-disk format of features.extractor."""
    rng = np.random.default_rng(seed)
    fams, styles = ["poisoned_tool", "shadowing", "sampling_injection"], ["style_a", "style_b"]
    rows = []
    for t in range(n_tasks):
        for i in range(per_task):
            attack = i % 4 == 3
            fam = fams[(t + i) % 3] if attack else None
            rows.append({"session_id": f"t{t}s{i}", "task_id": f"task{t}", "scenario_id": f"sc{t}",
                         "label": "attack" if attack else "benign", "attack_family": fam,
                         "attack_variant": styles[(i // 4) % 2] if fam == "poisoned_tool" else None,
                         "attack_succeeded": bool(attack and i % 8 == 3),
                         "n_servers_mounted": 2 + i % 2, "size_mean": rng.normal(200, 20),
                         "desc_len_max": rng.normal(300 if attack else 100, 30)})
    out = root / "features"
    out.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(out / "features.csv", index=False)
    cats = {"n_servers_mounted": "structural", "size_mean": "behavioral", "desc_len_max": "content"}
    (out / "feature_schema.json").write_text(json.dumps({
        "features": [{"name": n, "category": c, "used_for_training": True} for n, c in cats.items()],
        "metadata_columns": ["session_id", "task_id", "scenario_id", "label", "attack_family",
                             "attack_variant", "attack_succeeded"]}), encoding="utf-8")
    (root / "dataset" / "raw" / "sessions").mkdir(parents=True)
    n_attack = sum(r["label"] == "attack" for r in rows)
    (out / "dataset_summary.json").write_text(json.dumps({
        "dataset_path": str(root / "dataset"), "dataset_sha256": "0" * 64, "n_sessions": len(rows),
        "n_benign": len(rows) - n_attack, "n_attack": n_attack, "attack_families": fams,
        "attack_variants": styles, "attack_succeeded": sum(r["attack_succeeded"] for r in rows),
        "features_per_category": {"structural": 1, "behavioral": 1, "content": 1}}), encoding="utf-8")
    return out


def test_train_only_adds_models_and_leaves_the_others_untouched(tmp_path: Path) -> None:
    feats, models = _feature_dir(tmp_path), tmp_path / "models"
    train(feats, models, seed=42, test_size=0.3, only=["random_forest", "svm"])
    before = {p.name: p.read_bytes() for p in models.iterdir()}
    assert not (models / "xgboost.joblib").exists()

    train(feats, models, seed=42, test_size=0.3, only=["xgboost", "rf_xgb"])
    assert {p.name: p.read_bytes() for p in models.iterdir() if p.name in before} == before
    for name in ("xgboost", "rf_xgb"):
        meta = json.loads((models / f"{name}_metadata.json").read_text(encoding="utf-8"))
        assert meta["model"] == name and meta["params"] == PARAMS[name] and "xgboost" in meta["versions"]

    with pytest.raises(RuntimeError, match="differ"):  # another seed gives another split: refuse
        train(feats, models, seed=7, test_size=0.3, only=["xgboost"])
    with pytest.raises(ValueError, match="unknown"):
        train(feats, models, only=["lightgbm"])


def test_evaluate_reports_every_model(tmp_path: Path, monkeypatch) -> None:
    feats, models = _feature_dir(tmp_path), tmp_path / "models"
    train(feats, models, seed=42, test_size=0.3, only=["random_forest", "svm"])
    with pytest.raises(FileNotFoundError, match="--only xgboost rf_xgb decision_tree cnn"):
        ev.evaluate(feats, models, tmp_path / "results", "exp_test", tmp_path / "experiments")
    train(feats, models, seed=42, test_size=0.3, only=["xgboost", "rf_xgb", "decision_tree", "cnn"])

    # Latency needs real session logs; everything else runs for real.
    monkeypatch.setattr(ev, "latency", lambda *a, **k: {"model_only_ms_median": 1.0, "end_to_end_ms_median": 2.0})
    original_cv = ev.repeated_cv
    monkeypatch.setattr(ev, "repeated_cv",
                        lambda data, seed, **kw: original_cv(data, seed, splits=2, repeats=1, **kw))
    m = ev.evaluate(feats, models, tmp_path / "results", "exp_test", tmp_path / "experiments")

    for name in BUILDERS:
        assert name in m["models"] and name in m["grouped_cv"] and name in m["headline"]
        assert name in m["repeated_cv"] and name in m["ablation"]["content"]
        assert all(name in fold for fold in m["holdout_attack_family"]["folds"].values())
        assert (tmp_path / "results" / f"confusion_matrix_{SHORT[name]}.png").is_file()
    assert (tmp_path / "results" / "feature_importance_xgb.png").is_file()
    assert m["xgb_feature_importance_top15"][0]["feature"] == "desc_len_max"
    text = (tmp_path / "results" / "evaluation_report.md").read_text(encoding="utf-8")
    for name in BUILDERS:
        assert text.count(LABELS[name]) >= 5  # headline, train, test, holdouts, ablation, CV ...
    assert "6a. Most important XGBoost features" in text

