"""Phases 11-12: train every model on a stratified split, optionally with hyperparameter tuning.

Run:  python -m ml.train --features data/try6_ml --models models/try6 --seed 42 --test-size 0.3 [--tune]

Models: Random Forest, SVM, XGBoost, RF + XGBoost, Decision Tree and 1-D CNN on
the 65 session features, and the raw-traffic CNN (``cnn_raw``) on the sessions'
wire messages (read from the dataset recorded in ``dataset_summary.json``).

Writes to ``--models``:
* ``<model>.joblib`` for ``random_forest``, ``svm``, ``xgboost``, ``rf_xgb``, ``decision_tree``, ``cnn``,
  ``cnn_raw``: complete pipelines (preprocessing + model)
* ``split.json``: which session ids are train / test (the evaluation reuses it), and how they were chosen
* ``<model>_metadata.json``: parameters (``tuned_params``: what tuning changed), input, dataset hash,
  seed, library versions
* ``tuning.json`` (with ``--tune``): every candidate setting and its inner-CV score (``ml/tuning.py``)
* ``feature_schema.json``: copy of the schema the models were trained with

The split is **task-grouped** by default (``--split task-grouped``): whole tasks
go to the test set, so no task is on both sides. A random split put
near-identical sessions of the same task (same task, another seed) on both
sides: on the 1,354-session dataset 185 of 407 test sessions had an exact twin
in training, so its perfect test scores mostly measured memory.
``--split stratified`` reproduces the earlier random, stratified split.

``--tune`` chooses each model's hyperparameters on the **training rows only**,
with whole tasks held out in inner folds (``ml/tuning.py``), then fits the
final model on all training rows with the winning settings.

``--only decision_tree cnn`` adds models to an existing model directory without
rewriting the others. The split is recomputed from the same seed and must be
identical to the saved ``split.json`` (and the dataset hash to the saved
models'), otherwise nothing is written.

The test rows are set aside **before** fitting, and nothing is tuned on them.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from ml.dataset import FeatureData, load_features
from ml.models import ALL_BUILDERS, build, effective_params, is_raw
from ml.raw import RAW_COLUMN, RAW_VIEW_VERSION, load_raw
from ml.tuning import RAW_SINGLE_FIT, tune_models


def versions() -> dict[str, str]:
    import pandas
    import torch
    import xgboost
    return {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
            "numpy": np.__version__, "pandas": pandas.__version__, "joblib": joblib.__version__,
            "xgboost": xgboost.__version__, "torch": torch.__version__}


SPLIT_METHODS = ("task-grouped", "stratified")


def _strata(data: FeatureData) -> np.ndarray:
    families = data.meta["attack_family"].fillna("benign").astype(str).to_numpy()
    return np.asarray([f"{int(label)}:{family}" for label, family in zip(data.y, families, strict=True)])


def stratified_split(data: FeatureData, test_size: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Random split, stratified on label + attack family (sessions of one task can land on both sides)."""
    idx = np.arange(len(data.y))
    train_idx, test_idx = train_test_split(idx, test_size=test_size, stratify=_strata(data), random_state=seed)
    return np.sort(train_idx), np.sort(test_idx)


def task_grouped_split(data: FeatureData, test_size: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Whole tasks go to the test set: no task is on both sides of the split.

    ``StratifiedGroupKFold`` with about 1/test_size folds keeps each fold's mix of
    label + attack family as even as whole tasks allow. The test set is the first
    fold (in seeded order; seeds ``seed``, ``seed + 1``, ... if needed) that leaves
    benign and attack sessions on both sides **and** every attack family in
    training, so the saved models (used by the live detector) have seen each
    family. Unseen families are evaluated separately (family holdout, grouped CV).
    If no fold can keep every family in training, the first fold with both
    classes on both sides is used.
    """
    groups = data.meta["task_id"].astype(str).to_numpy()
    families = data.meta["attack_family"].fillna("benign").astype(str).to_numpy()
    attack_families = set(families[data.y == 1])
    n_splits = max(2, min(round(1 / test_size), len(set(groups))))
    fallback = None
    for s in range(seed, seed + 50):
        cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=s)
        for tr, te in cv.split(np.zeros(len(data.y)), _strata(data), groups):
            if len(set(data.y[tr])) < 2 or len(set(data.y[te])) < 2:
                continue
            if set(families[tr][data.y[tr] == 1]) == attack_families:
                return np.sort(tr), np.sort(te)
            fallback = fallback or (np.sort(tr), np.sort(te))
    if fallback is not None:
        return fallback
    raise ValueError("no task-grouped split leaves benign and attack sessions on both sides; "
                     "use --split stratified for this dataset")


def make_split(data: FeatureData, test_size: float, seed: int, method: str) -> tuple[np.ndarray, np.ndarray]:
    if method not in SPLIT_METHODS:
        raise ValueError(f"unknown split method {method!r}; choose from {SPLIT_METHODS}")
    return (task_grouped_split if method == "task-grouped" else stratified_split)(data, test_size, seed)


def _check_existing(model_dir: Path, split: dict, dataset_sha256: str) -> None:
    """``--only``: the new models must share the saved models' split and dataset exactly."""
    old = json.loads((model_dir / "split.json").read_text(encoding="utf-8"))
    for key in ("train_session_ids", "test_session_ids"):
        if old[key] != split[key]:
            raise RuntimeError(f"{model_dir / 'split.json'}: recomputed {key} differ; use the original seed "
                               "and test size, or train all models into a new directory")
    for meta_file in model_dir.glob("*_metadata.json"):
        sha = json.loads(meta_file.read_text(encoding="utf-8")).get("dataset_sha256")
        if sha != dataset_sha256:
            raise RuntimeError(f"{meta_file.name} was trained on a different dataset version")


def _saved_tuned(model_dir: Path, name: str) -> dict:
    f = model_dir / f"{name}_metadata.json"
    return (json.loads(f.read_text(encoding="utf-8")).get("tuned_params") or {}) if f.is_file() else {}


def train(feature_dir: Path, model_dir: Path, seed: int = 42, test_size: float = 0.3,
          only: list[str] | None = None, tune: bool = False, n_jobs: int | None = None,
          split_method: str | None = None) -> dict:
    """``split_method``: "task-grouped" (default) or "stratified"; when models are added to an existing
    directory (``only``), the method stored in its ``split.json`` is used unless one is given."""
    names = list(only) if only else list(ALL_BUILDERS)
    unknown = sorted(set(names) - set(ALL_BUILDERS))
    if unknown:
        raise ValueError(f"unknown model(s) {unknown}; choose from {list(ALL_BUILDERS)}")
    data = load_features(feature_dir)
    saved = model_dir / "split.json"
    if split_method is None:
        split_method = (json.loads(saved.read_text(encoding="utf-8")).get("method", "stratified")
                        if only and saved.is_file() else "task-grouped")
    train_idx, test_idx = make_split(data, test_size, seed, split_method)
    model_dir.mkdir(parents=True, exist_ok=True)
    summary = json.loads((feature_dir / "dataset_summary.json").read_text(encoding="utf-8"))

    split = {
        "seed": seed, "test_size": test_size, "method": split_method,
        "stratified_on": "label+attack_family",
        "grouped_on": "task_id" if split_method == "task-grouped" else None,
        "n_train_tasks": int(data.meta["task_id"].iloc[train_idx].nunique()),
        "n_test_tasks": int(data.meta["task_id"].iloc[test_idx].nunique()),
        "tasks_in_both": sorted(set(data.meta["task_id"].iloc[train_idx]) & set(data.meta["task_id"].iloc[test_idx])),
        "train_session_ids": data.meta["session_id"].iloc[train_idx].tolist(),
        "test_session_ids": data.meta["session_id"].iloc[test_idx].tolist(),
        "n_train": len(train_idx), "n_test": len(test_idx),
        "train_benign": int((data.y[train_idx] == 0).sum()), "train_attack": int(data.y[train_idx].sum()),
        "test_benign": int((data.y[test_idx] == 0).sum()), "test_attack": int(data.y[test_idx].sum()),
    }
    if only and (model_dir / "split.json").is_file():
        _check_existing(model_dir, split, summary["dataset_sha256"])  # keep split/schema files as they are
    else:
        (model_dir / "split.json").write_text(json.dumps(split, indent=2), encoding="utf-8")
        shutil.copy(feature_dir / "feature_schema.json", model_dir / "feature_schema.json")

    raw = load_raw(feature_dir) if any(is_raw(n) for n in names) else None
    inputs = {"features": data.X.iloc[train_idx], "raw": raw.X.iloc[train_idx] if raw is not None else None}
    y_train = data.y[train_idx]
    tuning: dict[str, dict] = {}
    if tune:
        groups = data.meta["task_id"].astype(str).to_numpy()[train_idx]
        known = {m: _saved_tuned(model_dir, m) for m in ("random_forest", "xgboost")}
        tuning = tune_models(names, inputs, y_train, groups, seed, n_jobs, known)
        tuning_file = model_dir / "tuning.json"
        saved = json.loads(tuning_file.read_text(encoding="utf-8")) if tuning_file.is_file() else {}
        tuning_file.write_text(json.dumps({**saved, **tuning}, indent=2, default=str), encoding="utf-8")

    for name in names:
        tuned = tuning[name]["best_params"] if name in tuning else None
        run = {**(tuned or {}), **(RAW_SINGLE_FIT if is_raw(name) else {})}
        pipe = build(name, seed, run).fit(inputs["raw" if is_raw(name) else "features"], y_train)
        joblib.dump(pipe, model_dir / f"{name}.joblib")
        features = [RAW_COLUMN] if is_raw(name) else data.feature_names
        meta = {
            "model": name, "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "pipeline_steps": [s for s, _ in pipe.steps], "params": effective_params(name, run),
            "tuned_params": tuned, "tuning": ({k: v for k, v in tuning[name].items() if k != "candidates"}
                                              if name in tuning else None),
            "seed": seed, "input": "raw_session_text" if is_raw(name) else "features",
            "raw_view_version": RAW_VIEW_VERSION if is_raw(name) else None,
            "features": features, "n_features": len(features),
            "feature_dir": str(feature_dir), "dataset_path": summary["dataset_path"],
            "dataset_sha256": summary["dataset_sha256"], "split_file": "split.json",
            "n_train": split["n_train"], "versions": versions(),
            "positive_class": "attack (label == 'attack', i.e. attack_attempted)",
        }
        (model_dir / f"{name}_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return split


def main() -> None:
    p = argparse.ArgumentParser(description="Train all models (features + raw-traffic CNN), optionally tuned")
    p.add_argument("--features", type=Path, required=True, help="feature directory (features.csv + schema)")
    p.add_argument("--models", type=Path, required=True, help="output directory for models")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--test-size", type=float, default=0.3)
    p.add_argument("--only", nargs="+", choices=list(ALL_BUILDERS), default=None,
                   help="train only these models into an existing directory (split must match)")
    p.add_argument("--tune", action="store_true",
                   help="choose hyperparameters on the training rows (task-grouped inner CV) first")
    p.add_argument("--jobs", type=int, default=None, help="parallel fits while tuning (default: CPU-based)")
    p.add_argument("--split", choices=SPLIT_METHODS, default=None,
                   help="task-grouped (default: whole tasks in the test set) or stratified (earlier random split)")
    a = p.parse_args()
    split = train(a.features, a.models, a.seed, a.test_size, a.only, a.tune, a.jobs, a.split)
    print(json.dumps({k: v for k, v in split.items() if not k.endswith("_ids")}, indent=2))
    print(f"models written to {a.models}")


if __name__ == "__main__":
    main()
