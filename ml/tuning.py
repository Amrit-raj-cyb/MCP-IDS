"""Hyperparameter tuning ("fine-tuning"), on training data only, with whole tasks held out.

What is tuned
-------------
Every model has settings that are not learned from data but chosen before
training (*hyperparameters*): the depth of a tree, the SVM's ``C`` and
``gamma``, the CNN's learning rate, ... :data:`GRIDS` lists the candidate
values for each model. The **first** value of every list is the model's
default (``ml.models``), so candidate 0 is always the untuned model.

How a candidate is scored (no test data involved)
-------------------------------------------------
Only the rows we are allowed to train on are used. They are split again,
**by task** (``GroupKFold`` on ``task_id``, 3 inner folds), and every candidate
is trained on two inner folds and predicts the third, until each training row
has one out-of-fold prediction. The candidate's score is the F1 of those
pooled predictions. Grouping by task matters: with a random inner split,
near-identical sessions of the same task would sit on both sides and every
candidate would look perfect.

The best candidate wins (highest F1, then lowest false-positive rate, then
the earlier candidate, i.e. the default wins ties: a setting is only changed
when that actually helps on held-out tasks).

Where it is used
----------------
* ``ml.train --tune``: tuned on the training split, then the final model is
  fitted on the whole training split with the winning settings.
* ``ml.evaluate --nested-tuning``: **nested** cross-validation for the
  headline. For each outer fold (whole tasks held out) the search runs on the
  outer training tasks only, so the held-out tasks never influence the choice
  of settings. This is the honest estimate of a tuned model.

The RF + XGBoost ensemble has no grid of its own: it is built from the tuned
Random Forest and tuned XGBoost settings of the same training data.
"""

from __future__ import annotations

import os

import numpy as np
from joblib import Parallel, delayed
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold, ParameterGrid

from ml.models import build, is_raw

# First value of each list = the default in ml.models (checked by tests).
GRIDS: dict[str, dict[str, list]] = {
    "random_forest": {"n_estimators": [300, 600], "max_depth": [None, 8], "min_samples_leaf": [1, 3],
                      "max_features": ["sqrt", 0.5]},
    "svm": {"C": [1.0, 0.1, 10.0, 100.0], "gamma": ["scale", 0.001, 0.01, 0.1]},
    "xgboost": {"n_estimators": [300, 100], "learning_rate": [0.3, 0.1, 0.03], "max_depth": [6, 3],
                "subsample": [1.0, 0.8]},
    "decision_tree": {"criterion": ["gini", "entropy"], "max_depth": [None, 3, 5, 8], "min_samples_leaf": [1, 3, 10]},
    "cnn": {"channels": [(16, 32), (32, 64)], "dropout": [0.2, 0.5], "epochs": [50, 100],
            "learning_rate": [1e-3, 3e-3]},
    # max_len: read the whole session (32 KiB) or only its first 8 KiB, where the handshake and the
    # tool descriptions are; later messages carry mostly task-specific arguments and results.
    "cnn_raw": {"max_len": [32768, 8192], "dropout": [0.2, 0.5], "learning_rate": [1e-3, 3e-3]},
}
ENSEMBLES = {"rf_xgb": ("random_forest", "xgboost")}  # built from its members' tuned settings
INNER_SPLITS = 3
# Raw-traffic CNN fits are heavy: fewer parallel fits, several torch threads each (runtime only, not tuned).
RAW_RUNTIME = {"n_threads": 4}
RAW_SINGLE_FIT = {"n_threads": 8}  # one fit at a time (final model, holdouts): more threads


def candidates(name: str) -> list[dict]:
    """Every combination of the model's grid, the all-defaults combination first."""
    grid = GRIDS[name]
    keys = sorted(grid)
    return [{k: c[k] for k in keys} for c in ParameterGrid({k: grid[k] for k in keys})]


def default_jobs(name: str) -> int:
    cpus = os.cpu_count() or 2
    return max(1, cpus // RAW_RUNTIME["n_threads"]) if is_raw(name) else max(1, cpus - 2)


def _fit_fold(name: str, seed: int, params: dict, X_tr, y_tr, X_te) -> np.ndarray:
    if len(np.unique(y_tr)) < 2:  # an inner training fold with one class only: predict that class
        return np.full(len(X_te), int(y_tr[0]) if len(y_tr) else 0)
    run = {**params, **(RAW_RUNTIME if is_raw(name) else {})}
    return np.asarray(build(name, seed, run).fit(X_tr, y_tr).predict(X_te))


def _scores(y: np.ndarray, pred: np.ndarray) -> dict:
    neg = y == 0
    return {"f1": round(float(f1_score(y, pred, zero_division=0)), 4),
            "recall": round(float(pred[y == 1].mean()), 4) if (y == 1).any() else 0.0,
            "fpr": round(float(pred[neg].mean()), 4) if neg.any() else 0.0}


def search(name: str, X, y, groups, seed: int, n_jobs: int | None = None, inner_splits: int = INNER_SPLITS) -> dict:
    """Choose ``name``'s hyperparameters on (X, y) only, with tasks (``groups``) held out in inner folds."""
    y, groups = np.asarray(y), np.asarray(groups).astype(str)
    cands = candidates(name)
    n_groups = len(set(groups))
    if n_groups < 2 or len(np.unique(y)) < 2:
        return {"model": name, "best_params": cands[0], "best_index": 0, "candidates": [],
                "note": f"not tuned: {n_groups} task(s) and {len(np.unique(y))} class(es) in the training rows"}
    folds = list(GroupKFold(n_splits=min(inner_splits, n_groups)).split(np.zeros(len(y)), y, groups))
    jobs = [(c, f) for c in range(len(cands)) for f in range(len(folds))]
    preds = Parallel(n_jobs=n_jobs or default_jobs(name))(
        delayed(_fit_fold)(name, seed, cands[c], X.iloc[folds[f][0]], y[folds[f][0]], X.iloc[folds[f][1]])
        for c, f in jobs)
    oof = {c: np.zeros(len(y), dtype=int) for c in range(len(cands))}
    for (c, f), p in zip(jobs, preds, strict=True):
        oof[c][folds[f][1]] = p
    table = [{"params": cands[c], **_scores(y, oof[c])} for c in range(len(cands))]
    best = max(range(len(cands)), key=lambda c: (table[c]["f1"], -table[c]["fpr"], -c))
    return {"model": name, "best_params": cands[best], "best_index": best,
            "inner_scheme": f"GroupKFold(n_splits={len(folds)}) on task_id, pooled out-of-fold F1",
            "n_candidates": len(cands), "default_f1": table[0]["f1"], "best_f1": table[best]["f1"],
            "candidates": table}


def tune_models(names: list[str], X_by_kind: dict, y, groups, seed: int, n_jobs: int | None = None,
                known: dict | None = None) -> dict[str, dict]:
    """Search every model in ``names``; ensembles reuse their members' winners.

    ``X_by_kind`` maps "features"/"raw" to the matching input table. ``known``
    holds already-chosen settings (e.g. from saved models) for ensemble members
    that are not searched in this call.
    """
    out: dict[str, dict] = {}
    for name in names:
        if name in GRIDS:
            out[name] = search(name, X_by_kind["raw" if is_raw(name) else "features"], y, groups, seed, n_jobs)
    for name, members in ENSEMBLES.items():
        if name in names:
            chosen = {m: (out[m]["best_params"] if m in out else (known or {}).get(m, {})) for m in members}
            out[name] = {"model": name, "best_params": chosen,
                         "note": "no search of its own: built from its members' tuned settings"}
    return out
