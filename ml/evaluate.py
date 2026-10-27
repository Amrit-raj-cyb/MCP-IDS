"""Phase 13: evaluate the trained models and run the supporting experiments.

    python -m ml.evaluate --features data/try6_ml --models models/try6 --results results/try6

What is computed (all numbers come from code, nothing is hand-written):

Models: Random Forest, SVM, XGBoost, the RF + XGBoost soft-voting ensemble,
a Decision Tree and a 1-D CNN on the 65 features (``ml.models.BUILDERS``), and
the raw-traffic CNN on the sessions' wire messages (``ml.models.RAW_BUILDERS``,
included when ``cnn_raw.joblib`` is in the model directory). Every experiment
below runs all of them, except the feature ablation, the confound check and the
repeated CV (feature models only: they need features, or 25 fits per model).

Hyperparameters: the saved models' settings (``tuned_params`` in their
metadata, chosen by ``ml.train --tune`` on the training split) are reused when
experiments 2-4 and 6 refit a model. The plain task-grouped CV (7) always uses
the *default* settings; with ``--nested-tuning`` the headline is the **nested**
task-grouped CV (7a), which re-tunes inside every outer training fold so the
held-out tasks never influence the chosen settings (``ml.tuning``).

1. **Baseline (saved models, split from ``split.json``: task-grouped since 2026-10-10, earlier
   stratified-random)**: metrics
   on the TRAINING rows and, separately, on the TEST rows; confusion matrices;
   per-variant recall on the test rows; inference latency.
2. **Hold-one-payload-style-out**: for each poisoned-tool style, retrain on
   benign-train + other poisoned-tool styles, test on benign-test + the
   held-out style.
3. **Hold-one-attack-family-out**: each family is held out in turn while
   training uses the other families plus benign sessions.
4. **Feature-group ablation**: same split, models trained on one group at a time.
5. **Confound check**: a model that sees only ``n_servers_mounted``.
6. **Repeated stratified 5-fold CV (5 repeats)**: supplementary, steadier
   estimate on a small dataset.
7. **Task-grouped CV** (``GroupKFold`` on ``task_id``): no task is in both train
   and test, so sessions that differ only by the mock's seed can't be memorised. Random splits of a lab
   dataset built from few tasks mostly test sessions the model has already
   seen; this is the more honest generalization estimate.
8. **Baseline duplicate check**: how many baseline test sessions have an exact
   feature-vector copy in the training set (a memorisation warning).
9. **Benign-only anomaly detection** (``ml.anomaly``), task-grouped like 7:
   IsolationForest and One-Class SVM fitted on the training tasks' benign
   sessions only, so they need no attack examples.
10. Plots: confusion matrices (test) for every model; RF and XGBoost feature importance.

7a. **Nested task-grouped CV** (``--nested-tuning``): as 7, with hyperparameter
   tuning on the outer training tasks only (inner ``GroupKFold`` by task).

The **headline** result is the task-grouped CV (7a if run, else 7), reported first with 95 %
confidence intervals (``ml.uncertainty``: Wilson per session, and a bootstrap
that resamples whole tasks). The single baseline split is kept for comparison only.

Outputs: ``metrics.json``, ``evaluation_report.md``, PNGs in ``--results``,
plus a copy under ``experiments/<id>/``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")  # file output only, no display needed
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score  # noqa: E402
from sklearn.model_selection import GroupKFold, RepeatedStratifiedKFold  # noqa: E402

from ml.anomaly import ANOMALY_BUILDERS, ANOMALY_PARAMS, DEFAULT_QUANTILE, BenignOnlyDetector  # noqa: E402
from ml.dataset import (FeatureData, feature_matrix, group_columns, load_features,  # noqa: E402
                        resolve_dataset_dir)
from ml.inference import Detector  # noqa: E402
from ml.models import ALL_BUILDERS, BUILDERS, LABELS, PARAMS, RAW_BUILDERS, SHORT, build, is_raw  # noqa: E402
from ml.raw import load_raw  # noqa: E402
from ml.train import versions  # noqa: E402
from ml.tuning import RAW_SINGLE_FIT, tune_models  # noqa: E402
from ml.uncertainty import cluster_bootstrap, wilson_intervals  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ABBR = {"random_forest": "RF", "svm": "SVM", "xgboost": "XGB", "rf_xgb": "RF+XGB", "decision_tree": "DT",
        "cnn": "CNN", "cnn_raw": "Raw CNN"}  # table headers
SMALL_DATA_NOTE = ("This experiment demonstrates the functionality of the ML pipeline, but the dataset is "
                   "too small to establish strong real-world generalization.")


# ------------------------------------------------------------------ metrics

def binary_metrics(y_true, y_pred) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y_true)), "n_benign": int((np.asarray(y_true) == 0).sum()),
        "n_attack": int(np.asarray(y_true).sum()),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "fpr": round(float(fp / (fp + tn)) if (fp + tn) else 0.0, 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def _fit_predict(name: str, seed: int, X_tr, y_tr, X_te, params: dict | None = None):
    """Fit a fresh model (with ``params``, e.g. tuned settings) and predict ``X_te``."""
    run = {**(params or {}), **(RAW_SINGLE_FIT if is_raw(name) else {})}
    return build(name, seed, run).fit(X_tr, y_tr).predict(X_te)


def _models(models: list[str] | None) -> list[str]:
    return list(models) if models is not None else list(BUILDERS)


def _merge(a: dict, b: dict) -> dict:
    """Deep-merge the raw-model results ``b`` into the feature-model results ``a``."""
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else out.get(k, v)
    return out


# ------------------------------------------------------------------ pieces

def latency(model_path: Path, data: FeatureData, test_idx: np.ndarray, sessions_dir: Path) -> dict:
    """Model-only latency per session (single-row predict) and end-to-end (features + model)."""
    pipe = joblib.load(model_path)
    X_test = data.X.iloc[test_idx]
    single = []
    for _ in range(10):
        for i in range(len(X_test)):
            row = X_test.iloc[[i]]
            t = time.perf_counter()
            pipe.predict(row)
            single.append((time.perf_counter() - t) * 1000)
    det = Detector(model_path)
    e2e = [det.classify_session(sid, sessions_dir) for sid in data.meta["session_id"].iloc[test_idx]]
    tot = [r["feature_ms"] + r["model_ms"] for r in e2e]
    return {
        "model_only_ms_median": round(float(np.median(single)), 3),
        "model_only_ms_p95": round(float(np.percentile(single, 95)), 3),
        "end_to_end_ms_median": round(float(np.median(tot)), 3),
        "feature_extraction_ms_median": round(float(np.median([r["feature_ms"] for r in e2e])), 3),
        "note": "per session, single-threaded, this laptop; end-to-end = read logs + neutralize + features + model",
    }


def per_variant_recall(meta, y_true, y_pred) -> dict:
    out = {}
    families = meta["attack_family"].fillna("benign").astype(str) if "attack_family" in meta else None
    for v in sorted(meta["attack_variant"].dropna().unique()):
        mask_series = meta["attack_variant"] == v
        if families is not None:
            mask_series &= families == "poisoned_tool"
        mask = mask_series.to_numpy()
        if mask.any():
            out[v] = {"n": int(mask.sum()), "detected": int(y_pred[mask].sum()),
                      "recall": round(float(y_pred[mask].mean()), 4)}
    return out


def holdout_payload_styles(data: FeatureData, train_idx, test_idx, seed: int, models: list[str] | None = None,
                           params: dict | None = None) -> dict:
    meta, y = data.meta, data.y
    family = meta["attack_family"].fillna("benign").astype(str).to_numpy()
    poisoned = (y == 1) & (family == "poisoned_tool")
    benign = (y == 0)
    benign_train = np.intersect1d(train_idx, np.where(benign)[0])
    benign_test = np.intersect1d(test_idx, np.where(benign)[0])
    results = {"description": "Train: benign-train + attacks of the other 4 styles. Test: benign-test + "
                              "all attacks of the held-out style. Payload-style holdout, NOT a family holdout.",
               "n_benign_train": int(len(benign_train)), "n_benign_test": int(len(benign_test)), "folds": {}}
    for v in sorted(meta["attack_variant"].dropna().unique()):
        is_v = (meta["attack_variant"] == v).to_numpy() & poisoned
        if not is_v.any():
            continue
        att_other = np.where(poisoned & ~is_v)[0]
        att_v = np.where(is_v)[0]
        tr = np.concatenate([benign_train, att_other])
        te = np.concatenate([benign_test, att_v])
        fold = {"n_train_attack": int(len(att_other)), "n_test_attack": int(len(att_v))}
        for name in _models(models):
            pred = _fit_predict(name, seed, data.X.iloc[tr], y[tr], data.X.iloc[te], (params or {}).get(name))
            fold[name] = binary_metrics(y[te], pred)
        results["folds"][v] = fold
    return results


def holdout_attack_families(data: FeatureData, train_idx, test_idx, seed: int, models: list[str] | None = None,
                            params: dict | None = None) -> dict:
    """Train on other attack families and benign data; evaluate each unseen family."""
    families = data.meta["attack_family"].fillna("benign").astype(str).to_numpy()
    attack_families = sorted(set(families[data.y == 1]) - {"benign", "nan", "None"})
    description = ("For each fold, train on benign training sessions and all other attack families; "
                   "test on benign test sessions plus the held-out attack family. This is a family holdout.")
    if len(attack_families) < 2:
        # Holding out the only family would leave no attacks to train on.
        return {"description": description, "folds": {},
                "skipped": f"needs at least 2 attack families, dataset has {len(attack_families)}"}
    benign_train = np.intersect1d(train_idx, np.where(data.y == 0)[0])
    benign_test = np.intersect1d(test_idx, np.where(data.y == 0)[0])
    folds = {}
    for family in attack_families:
        held = (data.y == 1) & (families == family)
        other = (data.y == 1) & (families != family)
        tr = np.concatenate([benign_train, np.where(other)[0]])
        te = np.concatenate([benign_test, np.where(held)[0]])
        fold = {"n_train_attack": int(other.sum()), "n_test_attack": int(held.sum()),
                "n_benign_train": int(len(benign_train)), "n_benign_test": int(len(benign_test))}
        for name in _models(models):
            pred = _fit_predict(name, seed, data.X.iloc[tr], data.y[tr], data.X.iloc[te], (params or {}).get(name))
            fold[name] = binary_metrics(data.y[te], pred)
        folds[family] = fold
    return {"description": description, "folds": folds}


def ablation(data: FeatureData, train_idx, test_idx, seed: int, params: dict | None = None) -> dict:
    df_all = data.X  # already leakage-checked; subsets re-checked below
    groups = {"all": None, "structural": ("structural",), "behavioral": ("behavioral",),
              "content": ("content",), "structural+behavioral": ("structural", "behavioral")}
    out = {}
    for gname, cats in groups.items():
        cols = data.feature_names if cats is None else group_columns(data.schema, *cats)
        X = feature_matrix(df_all, data.schema, cols)
        out[gname] = {"n_features": len(cols)}
        for name in BUILDERS:
            pred = _fit_predict(name, seed, X.iloc[train_idx], data.y[train_idx], X.iloc[test_idx],
                                (params or {}).get(name))
            out[gname][name] = binary_metrics(data.y[test_idx], pred)
    # Confound: only the number of mounted servers.
    Xs = feature_matrix(df_all, data.schema, ["n_servers_mounted"])
    pred = _fit_predict("random_forest", seed, Xs.iloc[train_idx], data.y[train_idx], Xs.iloc[test_idx],
                        (params or {}).get("random_forest"))
    out["confound_n_servers_only"] = {"n_features": 1, "random_forest": binary_metrics(data.y[test_idx], pred)}
    return out


def repeated_cv(data: FeatureData, seed: int, splits: int = 5, repeats: int = 5,
                params: dict | None = None) -> dict:
    cv = RepeatedStratifiedKFold(n_splits=splits, n_repeats=repeats, random_state=seed)
    out = {"scheme": f"RepeatedStratifiedKFold(n_splits={splits}, n_repeats={repeats})"}
    for name in BUILDERS:
        scores = {k: [] for k in ("accuracy", "precision", "recall", "f1", "fpr")}
        for tr, te in cv.split(data.X, data.y):
            m = binary_metrics(data.y[te], _fit_predict(name, seed, data.X.iloc[tr], data.y[tr], data.X.iloc[te],
                                                        (params or {}).get(name)))
            for k in scores:
                scores[k].append(m[k])
        out[name] = {k: {"mean": round(float(np.mean(v)), 4), "std": round(float(np.std(v)), 4)}
                     for k, v in scores.items()}
    return out


def grouped_cv(data: FeatureData, seed: int, group_col: str = "task_id", max_splits: int = 5,
               models: list[str] | None = None) -> dict:
    """Out-of-fold predictions with whole tasks held out (GroupKFold on ``group_col``), default settings.

    Every session is predicted by a model that never saw its task, so sessions
    that differ only by the mock's seed cannot be memorised across the split.
    Metrics are pooled over all out-of-fold predictions.
    """
    tf = _task_folds(data, group_col, max_splits)
    if "skipped" in tf:
        return tf
    groups, folds = tf.pop("groups"), tf.pop("folds_idx")
    out: dict = dict(tf)
    for name in _models(models):
        pred = np.zeros_like(data.y)
        for tr, te in folds:
            pred[te] = _fit_predict(name, seed, data.X.iloc[tr], data.y[tr], data.X.iloc[te])
        out[name] = _pooled_result(data, pred, groups, seed)
    return out


def grouped_cv_tuned(data: FeatureData, seed: int, models: list[str] | None = None, n_jobs: int | None = None,
                     group_col: str = "task_id", max_splits: int = 5) -> dict:
    """Nested task-grouped CV: the same outer folds as :func:`grouped_cv`, but in every outer fold the
    hyperparameters are chosen (``ml.tuning``) on that fold's training tasks only, then the model is
    refitted on them and predicts the held-out tasks. The held-out tasks never influence the settings."""
    tf = _task_folds(data, group_col, max_splits)
    if "skipped" in tf:
        return tf
    groups, folds = tf.pop("groups"), tf.pop("folds_idx")
    names = _models(models)
    out: dict = dict(tf)
    out["description"] = ("Nested CV: for each outer fold, hyperparameters are searched on the outer training "
                          "tasks only (inner GroupKFold(3) on task_id, pooled out-of-fold F1; ml/tuning.py), "
                          "then the model is refitted with the winner and predicts the held-out tasks.")
    preds = {n: np.zeros_like(data.y) for n in names}
    chosen: dict[str, list] = {n: [] for n in names}
    for tr, te in folds:
        X_tr = data.X.iloc[tr]
        tuned = tune_models(names, {"features": X_tr, "raw": X_tr}, data.y[tr], groups[tr], seed, n_jobs)
        for n in names:
            best = tuned[n]["best_params"] if n in tuned else None
            preds[n][te] = _fit_predict(n, seed, X_tr, data.y[tr], data.X.iloc[te], best)
            chosen[n].append(best)
    for n in names:
        out[n] = _pooled_result(data, preds[n], groups, seed)
        out[n]["params_per_fold"] = chosen[n]
    return out


def _task_folds(data: FeatureData, group_col: str = "task_id", max_splits: int = 5) -> dict:
    """GroupKFold folds on ``group_col`` plus a description; ``{"skipped": ...}`` if impossible."""
    if group_col not in data.meta.columns:
        return {"skipped": f"no '{group_col}' column in the feature metadata"}
    groups = data.meta[group_col].astype(str).to_numpy()
    n_groups = len(set(groups))
    if n_groups < 2:
        return {"skipped": f"only {n_groups} distinct {group_col}; grouped CV needs at least 2"}
    n_splits = min(max_splits, n_groups)
    folds = list(GroupKFold(n_splits=n_splits).split(data.X, data.y, groups))
    return {"scheme": f"GroupKFold(n_splits={n_splits}) on {group_col}", "group_col": group_col,
            "n_groups": n_groups,
            "folds": [{"test_groups": sorted(set(groups[te])), "n_test": int(len(te)),
                       "n_test_attack": int(data.y[te].sum())} for _, te in folds],
            "groups": groups, "folds_idx": folds}


def _pooled_result(data: FeatureData, pred: np.ndarray, groups: np.ndarray, seed: int) -> dict:
    """Metrics over all out-of-fold predictions, recall per family and 95 % intervals."""
    families = data.meta["attack_family"].fillna("benign").astype(str).to_numpy()
    res = binary_metrics(data.y, pred)
    res["recall_by_family"] = {f: round(float(pred[(families == f) & (data.y == 1)].mean()), 4)
                               for f in sorted(set(families) - {"benign"})
                               if ((families == f) & (data.y == 1)).any()}
    res["ci95_wilson"] = wilson_intervals(data.y, pred)
    res["ci95_task_bootstrap"] = cluster_bootstrap(data.y, pred, groups, seed=seed)
    false_alarms = (pred == 1) & (data.y == 0)
    res["false_alarms_by_task"] = {str(t): int(n) for t, n in zip(*np.unique(groups[false_alarms], return_counts=True))}
    return res


def anomaly_grouped_cv(data: FeatureData, seed: int, quantile: float = DEFAULT_QUANTILE,
                       group_col: str = "task_id", max_splits: int = 5) -> dict:
    """Benign-only detectors with the same task-grouped folds as ``grouped_cv``.

    In each fold the detector sees only the *benign* sessions of the training
    tasks; attack sessions are never used for fitting or for the threshold.
    """
    tf = _task_folds(data, group_col, max_splits)
    if "skipped" in tf:
        return tf
    groups, folds = tf.pop("groups"), tf.pop("folds_idx")
    out: dict = dict(tf)
    out["description"] = (f"Fitted on benign sessions of the training tasks only; threshold = "
                          f"{quantile:.2f} quantile of their anomaly scores (target FPR about "
                          f"{1 - quantile:.0%}). No attack data used for fitting or thresholds.")
    out["params"] = ANOMALY_PARAMS
    for name in ANOMALY_BUILDERS:
        pred = np.zeros_like(data.y)
        for tr, te in folds:
            benign_tr = tr[data.y[tr] == 0]
            if len(benign_tr) == 0:
                pred[te] = 1  # nothing benign to learn from in this fold: everything is unusual
                continue
            det = BenignOnlyDetector(name, seed, quantile).fit(data.X.iloc[benign_tr])
            pred[te] = det.predict(data.X.iloc[te])
        out[name] = _pooled_result(data, pred, groups, seed)
    return out


def baseline_duplicates(data: FeatureData, train_idx, test_idx) -> dict:
    """How many baseline test sessions have an exact feature-vector copy in training."""
    def key(i: int) -> bytes:
        return np.round(data.X.iloc[i].to_numpy(dtype=float), 9).tobytes()

    train_keys = {key(i) for i in train_idx}
    dup = [i for i in test_idx if key(i) in train_keys]
    families = data.meta["attack_family"].fillna("benign").astype(str).to_numpy()
    by_group: dict[str, int] = {}
    for i in dup:
        by_group[families[i]] = by_group.get(families[i], 0) + 1
    return {"n_test": int(len(test_idx)), "n_test_with_exact_training_copy": len(dup),
            "by_group": by_group,
            "n_distinct_feature_vectors": len({key(i) for i in range(len(data.y))}),
            "n_sessions": int(len(data.y))}


# ------------------------------------------------------------------ plots

def plot_confusion(cm: dict, title: str, path: Path) -> None:
    m = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
    fig, ax = plt.subplots(figsize=(4.2, 3.8), dpi=150)
    ax.imshow(m, cmap="Blues", vmin=0)
    for (i, j), v in np.ndenumerate(m):
        ax.text(j, i, str(v), ha="center", va="center", fontsize=14,
                color="white" if v > m.max() / 2 else "black")
    ax.set_xticks([0, 1], ["benign", "attack"])
    ax.set_yticks([0, 1], ["benign", "attack"])
    ax.set_xlabel("predicted")
    ax.set_ylabel("actual")
    ax.set_title(title, fontsize=9)
    fig.text(0.5, 0.01, "small controlled laboratory dataset, test split", ha="center", fontsize=7, color="gray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def plot_importance(model_path: Path, features: list[str], schema: dict, path: Path, top: int = 15,
                    title: str = "Random Forest feature importance (top 15), small lab dataset",
                    xlabel: str = "mean decrease in impurity") -> list:
    rf = joblib.load(model_path).named_steps["model"]  # any fitted model with feature_importances_
    order = np.argsort(rf.feature_importances_)[::-1][:top]
    cat = {f["name"]: f["category"] for f in schema["features"]}
    colors = {"structural": "#3b6ea8", "behavioral": "#2e8b57", "content": "#b5651d"}
    names = [features[i] for i in order][::-1]
    vals = [rf.feature_importances_[i] for i in order][::-1]
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    ax.barh(names, vals, color=[colors[cat[n]] for n in names])
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=9)
    ax.legend(handles=[Patch(color=col, label=c) for c, col in colors.items()], fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [{"feature": features[i], "category": cat[features[i]],
             "importance": round(float(rf.feature_importances_[i]), 4)} for i in order]


# ------------------------------------------------------------------ main flow

def evaluate(feature_dir: Path, model_dir: Path, results_dir: Path, experiment_id: str,
             experiments_dir: Path | None = None, nested_tuning: bool = False, n_jobs: int | None = None) -> dict:
    data = load_features(feature_dir)
    split = json.loads((model_dir / "split.json").read_text(encoding="utf-8"))
    sid = data.meta["session_id"].tolist()
    pos = {s: i for i, s in enumerate(sid)}
    train_idx = np.array(sorted(pos[s] for s in split["train_session_ids"]))
    test_idx = np.array(sorted(pos[s] for s in split["test_session_ids"]))
    if set(train_idx) & set(test_idx):
        raise RuntimeError("train/test overlap")
    seed = split["seed"]
    summary = json.loads((feature_dir / "dataset_summary.json").read_text(encoding="utf-8"))
    sessions_dir = resolve_dataset_dir(summary["dataset_path"]) / "raw" / "sessions"
    results_dir.mkdir(parents=True, exist_ok=True)

    missing = [n for n in BUILDERS if not (model_dir / f"{n}.joblib").is_file()]
    if missing:
        raise FileNotFoundError(f"{model_dir} has no {', '.join(missing)} model(s); add them with "
                                f"python -m ml.train ... --models {model_dir} --only {' '.join(missing)}")
    raw_names = [n for n in RAW_BUILDERS if (model_dir / f"{n}.joblib").is_file()]
    raw = load_raw(feature_dir) if raw_names else None
    if raw is not None and raw.meta["session_id"].tolist() != sid:
        raise RuntimeError("raw sessions are not aligned with features.csv")
    names = list(BUILDERS) + raw_names
    models, tuned = {}, {}
    for name in names:
        path = model_dir / f"{name}.joblib"
        meta = json.loads((model_dir / f"{name}_metadata.json").read_text(encoding="utf-8"))
        if meta["dataset_sha256"] != summary["dataset_sha256"]:
            raise RuntimeError(f"{name} was trained on a different dataset version")
        tuned[name] = meta.get("tuned_params")
        d = raw if is_raw(name) else data
        pipe = joblib.load(path)
        p_tr = pipe.predict(d.X.iloc[train_idx])
        p_te = pipe.predict(d.X.iloc[test_idx])
        models[name] = {
            "params": meta.get("params", PARAMS[name]), "tuned_params": tuned[name],
            "input": meta.get("input", "features"), "pipeline_steps": meta["pipeline_steps"],
            "train": binary_metrics(data.y[train_idx], p_tr),
            "test": binary_metrics(data.y[test_idx], p_te),
            "test_per_variant_recall": per_variant_recall(data.meta.iloc[test_idx].reset_index(drop=True),
                                                          data.y[test_idx], p_te),
            "test_recall_by_outcome": {
                "succeeded": _recall_where(data, test_idx, p_te, True),
                "not_succeeded": _recall_where(data, test_idx, p_te, False),
            },
            "latency": latency(path, d, test_idx, sessions_dir),
        }
        plot_confusion(models[name]["test"]["confusion_matrix"], f"{LABELS[name]}: test set (n={len(test_idx)})",
                       results_dir / f"confusion_matrix_{SHORT[name]}.png")

    importance = plot_importance(model_dir / "random_forest.joblib", data.feature_names, data.schema,
                                 results_dir / "feature_importance_rf.png")
    importance_xgb = plot_importance(model_dir / "xgboost.joblib", data.feature_names, data.schema,
                                     results_dir / "feature_importance_xgb.png",
                                     title="XGBoost feature importance (top 15), small lab dataset",
                                     xlabel="share of total gain")
    metrics = {
        "experiment_id": experiment_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": SMALL_DATA_NOTE,
        "dataset": {k: summary[k] for k in ("dataset_path", "dataset_sha256", "n_sessions", "n_benign",
                                            "n_attack", "attack_families", "attack_variants", "attack_succeeded")},
        "feature_dir": str(feature_dir), "n_features": len(data.feature_names),
        "features_per_category": summary["features_per_category"],
        "split": {k: v for k, v in split.items() if not k.endswith("_ids")},
        "models": models,
        "hyperparameters": {"source": "saved models' tuned_params (ml.train --tune on the training split); "
                                      "None = library/project defaults",
                            "tuned_params": tuned},
        "holdout_payload_style": _both(holdout_payload_styles, data, raw, raw_names, tuned, train_idx, test_idx,
                                       seed),
        "holdout_attack_family": _both(holdout_attack_families, data, raw, raw_names, tuned, train_idx, test_idx,
                                       seed),
        "ablation": ablation(data, train_idx, test_idx, seed, params=tuned),
        "repeated_cv": repeated_cv(data, seed, params=tuned),
        "grouped_cv": _merge(grouped_cv(data, seed),
                             grouped_cv(raw, seed, models=raw_names) if raw_names else {}),
        "anomaly_benign_only": anomaly_grouped_cv(data, seed),
        "baseline_duplicates": baseline_duplicates(data, train_idx, test_idx),
        "rf_feature_importance_top15": importance,
        "xgb_feature_importance_top15": importance_xgb,
        "versions": versions(),
    }
    if nested_tuning:
        metrics["grouped_cv_tuned"] = _merge(
            grouped_cv_tuned(data, seed, n_jobs=n_jobs),
            grouped_cv_tuned(raw, seed, models=raw_names, n_jobs=n_jobs) if raw_names else {})
    metrics["headline"] = headline(metrics)
    (results_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (results_dir / "evaluation_report.md").write_text(report(metrics), encoding="utf-8")

    exp = (experiments_dir or PROJECT_ROOT / "experiments") / experiment_id
    exp.mkdir(parents=True, exist_ok=True)
    shutil.copy(results_dir / "metrics.json", exp / "metrics.json")
    (exp / "config.json").write_text(json.dumps({
        "experiment_id": experiment_id, "dataset": metrics["dataset"], "feature_dir": str(feature_dir),
        "model_dir": str(model_dir), "results_dir": str(results_dir), "split": metrics["split"],
        "models": {n: {"params": models[n]["params"], "tuned_params": models[n]["tuned_params"],
                       "pipeline_steps": models[n]["pipeline_steps"]} for n in names},
        "n_features": metrics["n_features"], "versions": metrics["versions"],
    }, indent=2), encoding="utf-8")
    (exp / "notes.md").write_text(f"# {experiment_id}\n\nSee `{results_dir / 'evaluation_report.md'}` for the "
                                  f"full report.\n\n{SMALL_DATA_NOTE}\n", encoding="utf-8")
    return metrics


def _both(fn, data, raw, raw_names, params, *args) -> dict:
    """Run an experiment for the feature models and, if present, the raw-traffic models; merge."""
    res = fn(data, *args, models=list(BUILDERS), params=params)
    return _merge(res, fn(raw, *args, models=raw_names, params=params)) if raw_names else res


def headline(m: dict) -> dict:
    """The number to quote: (nested-tuned) task-grouped CV with intervals, next to the random-split score."""
    plain = m.get("grouped_cv", {})
    nested = m.get("grouped_cv_tuned", {})
    g = nested if nested and "skipped" not in nested else plain
    if not g or "skipped" in g:
        return {"protocol": "random split (task-grouped CV unavailable: "
                            f"{g.get('skipped', 'not computed')})",
                **{name: {k: m["models"][name]["test"][k] for k in ("f1", "precision", "recall", "fpr")}
                   for name in m["models"]}}
    tuned = g is nested
    out: dict = {"protocol": (f"nested task-grouped cross-validation ({g['scheme']}, {g['n_groups']} tasks; "
                              "hyperparameters tuned inside each outer training fold)" if tuned else
                              f"task-grouped cross-validation ({g['scheme']}, {g['n_groups']} tasks; "
                              "default hyperparameters)"),
                 "why": "no task is in both train and test, so seed-level near-duplicates cannot be memorised"
                        + ("; the held-out tasks never influence the chosen settings" if tuned else ""),
                 "tuned": tuned}
    for name in ALL_BUILDERS:
        if name not in g or name not in m["models"]:
            continue
        r = g[name]
        out[name] = {k: r[k] for k in ("f1", "precision", "recall", "fpr", "recall_by_family",
                                        "ci95_task_bootstrap", "ci95_wilson")}
        out[name]["random_split_f1_for_comparison"] = m["models"][name]["test"]["f1"]
        if tuned and name in plain:
            out[name]["untuned_f1"] = plain[name]["f1"]
    return out


def _present(d: dict) -> list[str]:
    """Model names that have results in ``d``, in the standard order."""
    return [n for n in ALL_BUILDERS if n in d]


def _ci(ci: dict, key: str) -> str:
    v = ci.get(key) if ci else None
    return f"[{v[0]:.2f}, {v[1]:.2f}]" if v else "n/a"


def _recall_where(data: FeatureData, test_idx, pred, succeeded: bool) -> dict:
    succ = data.meta["attack_succeeded"].iloc[test_idx].astype(str).str.lower().eq("true").to_numpy()
    mask = (data.y[test_idx] == 1) & (succ == succeeded)
    return {"n": int(mask.sum()), "detected": int(pred[mask].sum()),
            "recall": round(float(pred[mask].mean()), 4) if mask.any() else None}


# ------------------------------------------------------------------ report

def _row(name: str, m: dict, lat: dict | None = None) -> str:
    l = f"{lat['model_only_ms_median']:.2f} ms" if lat else "-"
    return (f"| {name} | {m['accuracy']:.3f} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} "
            f"| {m['fpr']:.3f} | {l} |")


def headline_section(m: dict) -> list[str]:
    h = m["headline"]
    L = ["## Headline: task-grouped cross-validation with 95 % confidence intervals"
         + (" (hyperparameters tuned, nested)" if h.get("tuned") else "")]
    if "random_forest" not in h or "ci95_task_bootstrap" not in h["random_forest"]:
        return L + [f"Protocol: {h['protocol']}.", ""]
    ci_note = h["random_forest"]["ci95_task_bootstrap"]["method"]
    fams = sorted(h["random_forest"]["recall_by_family"])
    L += [f"Protocol: {h['protocol']}; {h['why']}. **Quote these numbers**, not the single split in section 2.", "",
          "| Model | F1 [95 % CI] | Precision [95 % CI] | Recall [95 % CI] | FPR [95 % CI] | "
          + " | ".join(f"Recall {f}" for f in fams) + " | Baseline-split F1 |"
          + (" Untuned F1 |" if h.get("tuned") else ""),
          "|---|---|---|---|---|" + "---|" * len(fams) + "---|" + ("---|" if h.get("tuned") else "")]
    for name in _present(h):
        lab, r = LABELS[name], h[name]
        ci = r["ci95_task_bootstrap"]
        L.append(f"| {lab} | {r['f1']:.3f} {_ci(ci, 'f1')} | {r['precision']:.3f} {_ci(ci, 'precision')} | "
                 f"{r['recall']:.3f} {_ci(ci, 'recall')} | {r['fpr']:.3f} {_ci(ci, 'fpr')} | "
                 + " | ".join(f"{r['recall_by_family'][f]:.2f}" for f in fams)
                 + f" | {r['random_split_f1_for_comparison']:.3f} |"
                 + (f" {r['untuned_f1']:.3f} |" if "untuned_f1" in r else ""))
    w = h["random_forest"]["ci95_wilson"]
    L += ["", f"Intervals: {ci_note} (valid resamples: "
          f"{h['random_forest']['ci95_task_bootstrap']['n_valid_resamples']}). Sessions of one task are not "
          "independent, so whole tasks are resampled; with few tasks the intervals are wide. Per-session Wilson "
          f"intervals, which ignore that dependence, are narrower (Random Forest recall {_ci(w, 'recall')}, "
          f"FPR {_ci(w, 'fpr')}) and are stored in `metrics.json` for every model.", ""]
    return L


def _long_rows(fold: dict, prefix: list[str]) -> list[str]:
    """One table row per model: <prefix cells> | model | recall | FPR | F1."""
    return [f"| {' | '.join(prefix)} | {LABELS[n]} | {fold[n]['recall']:.2f} | {fold[n]['fpr']:.2f} "
            f"| {fold[n]['f1']:.2f} |" for n in _present(fold)]


def report(m: dict) -> str:
    ms = m["models"]
    names = _present(ms)
    s, d = m["split"], m["dataset"]
    L = [f"# Evaluation report: {m['experiment_id']}", "",
         f"> **{SMALL_DATA_NOTE}**", "",
         "## Setup",
         f"* Dataset: `{d['dataset_path']}` (read-only), SHA-256 `{d['dataset_sha256'][:16]}...`",
         f"* Sessions: {d['n_sessions']} ({d['n_benign']} benign, {d['n_attack']} attack across "
         f"{', '.join(d['attack_families'])}); protocol/mock success count (not real LLM influence): "
         f"{d['attack_succeeded']}",
         f"* Features: {m['n_features']} ({m['features_per_category']}); lab marker/canary removed with `neutralize()`",
         f"* Split: {s.get('method', 'stratified')}"
         + (f" (whole tasks held out: {s['n_train_tasks']} training / {s['n_test_tasks']} test tasks)"
            if s.get("method") == "task-grouped" else " (random; sessions of a task on both sides)")
         + f", seed {s['seed']}, test size {s['test_size']} → train {s['n_train']} "
         f"({s['train_benign']} benign / {s['train_attack']} attack), test {s['n_test']} "
         f"({s['test_benign']} benign / {s['test_attack']} attack)",
         "* Positive class: `attack` = attack **attempted** (not success)", ""]
    L += headline_section(m)
    L += ["## 1. Baseline split: TRAINING metrics (not evidence of generalization)",
         "| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |", "|---|---|---|---|---|---|---|",
         *[_row(LABELS[n], ms[n]["train"]) for n in names], "",
         f"## 2. Baseline split: TEST metrics ({s.get('method', 'stratified')} split; one split only, "
         "see the headline above)",
         "| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |",
         "|---|---|---|---|---|---|---|",
         *[_row(LABELS[n], ms[n]["test"], ms[n]["latency"]) for n in names], "",
         "Confusion matrices (test): " + ", ".join(f"`confusion_matrix_{SHORT[n]}.png`" for n in names), ""]
    for name, r in ((LABELS[n], ms[n]) for n in names):
        cm = r["test"]["confusion_matrix"]
        L.append(f"* {name}: TN={cm['tn']} FP={cm['fp']} FN={cm['fn']} TP={cm['tp']}; "
                 f"end-to-end latency (read logs + features + model) median "
                 f"{r['latency']['end_to_end_ms_median']:.1f} ms; recall on attacks that succeeded "
                 f"{r['test_recall_by_outcome']['succeeded']['recall']} "
                 f"(n={r['test_recall_by_outcome']['succeeded']['n']}), that did not succeed "
                 f"{r['test_recall_by_outcome']['not_succeeded']['recall']} "
                 f"(n={r['test_recall_by_outcome']['not_succeeded']['n']})")
    L += ["", "Per payload style in the test set (n is tiny):", "",
          "| Style | n | " + " | ".join(f"{ABBR[n]} recall" for n in names) + " |",
          "|---|---|" + "---|" * len(names)]
    for v, r in ms["random_forest"]["test_per_variant_recall"].items():
        L.append(f"| {v} | {r['n']} | "
                 + " | ".join(f"{ms[n]['test_per_variant_recall'][v]['recall']:.2f}" for n in names) + " |")

    h = m["holdout_payload_style"]
    L += ["", "## 3. Hold-one-payload-style-out (generalization to an unseen style)",
          f"{h['description']} Benign train/test: {h['n_benign_train']}/{h['n_benign_test']}.", "",
          "**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.", "",
          "| Held-out poisoned-tool style | test attacks | Model | Recall | FPR | F1 |",
          "|---|---:|---|---:|---:|---:|"]
    for v, f in h["folds"].items():
        L += _long_rows(f, [v, str(f["n_test_attack"])])

    fh = m["holdout_attack_family"]
    L += ["", "## 3a. Hold-one-attack-family-out"]
    if fh.get("skipped"):
        L.append(f"Skipped: {fh['skipped']}.")
    else:
        L += [fh["description"], "",
              "| Held-out family | test attacks | Model | Recall | FPR | F1 |",
              "|---|---:|---|---:|---:|---:|"]
    for family, fold in fh["folds"].items():
        L += _long_rows(fold, [family, str(fold["n_test_attack"])])

    a = m["ablation"]
    L += ["", "## 4. Feature-group ablation (same split, test set)",
          "| Features | # | Model | Recall | FPR | F1 |",
          "|---|---:|---|---:|---:|---:|"]
    for g, r in a.items():
        if g == "confound_n_servers_only":
            continue
        L += _long_rows(r, [g, str(r["n_features"])])
    c = a["confound_n_servers_only"]["random_forest"]
    L += ["", "**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches "
          f"accuracy {c['accuracy']:.2f}, recall {c['recall']:.2f}, FPR {c['fpr']:.2f} on the test set "
          f"(majority-class accuracy would be {s['test_benign'] / s['n_test']:.2f}). "
          "Server-count distributions are matched by construction in this Phase 9 dataset."]

    cv = m["repeated_cv"]
    L += ["", f"## 5. Supplementary: {cv['scheme']} on all {m['dataset']['n_sessions']} sessions",
          "| Model | Accuracy | Precision | Recall | F1 | FPR |", "|---|---|---|---|---|---|"]
    for name in _present(cv):
        r, lab = cv[name], LABELS[name]
        L.append(f"| {lab} | " + " | ".join(f"{r[k]['mean']:.3f} ± {r[k]['std']:.3f}"
                                             for k in ("accuracy", "precision", "recall", "f1", "fpr")) + " |")

    d = m.get("baseline_duplicates")
    if d:
        n_dup = d["n_test_with_exact_training_copy"]
        verdict = ("High baseline scores on such a split largely reflect memorisation; use the task-grouped "
                   "results below as the generalization estimate." if n_dup > d["n_test"] // 4 else
                   "Few or no exact copies: the baseline split is not dominated by memorised sessions "
                   "(near-duplicates can still exist; compare with the task-grouped results below).")
        L += ["", "## 5a. Baseline duplicate check",
              f"{n_dup} of {d['n_test']} baseline test sessions have an **exact "
              f"feature-vector copy** in the training set (by group: {d['by_group'] or 'none'}). The dataset has "
              f"{d['n_distinct_feature_vectors']} distinct feature vectors among {d['n_sessions']} sessions. "
              + verdict]
    g = m.get("grouped_cv")
    if g:
        L += ["", "## 5b. Task-grouped CV (more honest generalization estimate)"]
        if "skipped" in g:
            L.append(f"Skipped: {g['skipped']}.")
        else:
            fams = sorted(g["random_forest"]["recall_by_family"])
            L += [f"{g['scheme']} over {g['n_groups']} tasks: no task is in both train and test; every "
                  "session is predicted out-of-fold and metrics are pooled.", "",
                  "| Model | Accuracy | Precision | Recall | F1 | FPR | " + " | ".join(f"Recall {f}" for f in fams) + " |",
                  "|---|---|---|---|---|---|" + "---|" * len(fams)]
            for name in _present(g):
                r, lab = g[name], LABELS[name]
                L.append(f"| {lab} | {r['accuracy']:.3f} | {r['precision']:.3f} | {r['recall']:.3f} | "
                         f"{r['f1']:.3f} | {r['fpr']:.3f} | "
                         + " | ".join(f"{r['recall_by_family'][f]:.2f}" for f in fams) + " |")
            L += ["", "Folds (held-out tasks): " + "; ".join(
                f"{i + 1}: {', '.join(fo['test_groups'])} ({fo['n_test']} sessions)" for i, fo in enumerate(g["folds"]))]

    gt = m.get("grouped_cv_tuned")
    if gt and "skipped" not in gt:
        fams = sorted(gt["random_forest"]["recall_by_family"])
        L += ["", "## 5b-tuned. Nested task-grouped CV (hyperparameters tuned inside each outer fold)",
              gt["description"], "",
              "| Model | Precision | Recall | F1 | FPR | " + " | ".join(f"Recall {f}" for f in fams)
              + " | Untuned F1 (5b) |", "|---|---|---|---|---|" + "---|" * len(fams) + "---|"]
        for name in _present(gt):
            r = gt[name]
            plain = (m.get("grouped_cv") or {}).get(name, {}).get("f1")
            L.append(f"| {LABELS[name]} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} | "
                     f"{r['fpr']:.3f} | " + " | ".join(f"{r['recall_by_family'][f]:.2f}" for f in fams)
                     + (f" | {plain:.3f} |" if plain is not None else " | - |"))
        L += ["", "Settings chosen in each outer fold (fold 1 ... 5):", ""]
        for name in _present(gt):
            L.append(f"* {LABELS[name]}: " + "; ".join(
                json.dumps(p, default=str) if p else "defaults" for p in gt[name]["params_per_fold"]))

    an = m.get("anomaly_benign_only")
    if an:
        L += ["", "## 5c. Benign-only anomaly detection (task-grouped, no attack data used)"]
        if "skipped" in an:
            L.append(f"Skipped: {an['skipped']}.")
        else:
            fams = sorted(an["isolation_forest"]["recall_by_family"])
            L += [an["description"], "",
                  "| Detector | Precision | Recall [95 % CI] | F1 [95 % CI] | FPR [95 % CI] | "
                  + " | ".join(f"Recall {f}" for f in fams) + " |",
                  "|---|---|---|---|---|" + "---|" * len(fams)]
            for name, lab in (("isolation_forest", "Isolation Forest"), ("one_class_svm", "One-Class SVM")):
                r = an[name]
                ci = r["ci95_task_bootstrap"]
                L.append(f"| {lab} | {r['precision']:.3f} | {r['recall']:.3f} {_ci(ci, 'recall')} | "
                         f"{r['f1']:.3f} {_ci(ci, 'f1')} | {r['fpr']:.3f} {_ci(ci, 'fpr')} | "
                         + " | ".join(f"{r['recall_by_family'][f]:.2f}" for f in fams) + " |")
            L += ["", "Intervals: task-cluster bootstrap (see the headline). A benign-only detector flags what "
                  "is *unusual*, not what is malicious: on a closed-world lab dataset, unfamiliar benign tasks "
                  "can look as unusual as attacks."]

    L += ["", "## 6. Most important Random Forest features (impurity-based)", "",
          "| Feature | Category | Importance |", "|---|---|---|"]
    for r in m["rf_feature_importance_top15"][:10]:
        L.append(f"| `{r['feature']}` | {r['category']} | {r['importance']:.3f} |")
    L += ["", "Plot: `feature_importance_rf.png`", "",
          "## 6a. Most important XGBoost features (share of total gain)", "",
          "| Feature | Category | Importance |", "|---|---|---|"]
    for r in m["xgb_feature_importance_top15"][:10]:
        L.append(f"| `{r['feature']}` | {r['category']} | {r['importance']:.3f} |")
    L += ["", "Plot: `feature_importance_xgb.png`", "",
          "## 7. Interpretation and limitations",
          "* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so "
          "*any* change to `tools/list` (size, wording) can separate the classes. Several single "
          "features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they "
          "do not show that the detector would work on real, varied MCP servers.",
          "* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations "
          "or attack designs. Results are proof of concept, not real-world validation.",
          "* **Template and author bias.** Benign descriptions are fixed and payload templates were written by "
          "the same project team; richer benign variation is needed.",
          "* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange "
          "completed, not that an LLM was influenced.",
          "* **Lexicon bias.** Content lexicons were written by people who knew the payloads.",
          "* **No model ranking.** Differences between the models (" + ", ".join(LABELS[n] for n in names) + ") are within "
          "what a different split could change and inside each other's task-bootstrap intervals; no statistical "
          "test supports calling one of them better. The ensemble cannot recover information that neither "
          "member has: an attack family missing from training stays missed.", ""]
    return "\n".join(L)


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate trained models")
    p.add_argument("--features", type=Path, required=True)
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--experiment-id", default="exp_001_try6_baseline")
    p.add_argument("--experiments-dir", type=Path, default=None,
                   help="where experiments/<id>/ is written (default: the repo's experiments/)")
    p.add_argument("--nested-tuning", action="store_true",
                   help="headline = nested task-grouped CV with tuning inside every outer fold (slow)")
    p.add_argument("--jobs", type=int, default=None, help="parallel fits while tuning (default: CPU-based)")
    a = p.parse_args()
    m = evaluate(a.features, a.models, a.results, a.experiment_id, a.experiments_dir, a.nested_tuning, a.jobs)
    h = m["headline"]
    print(f"HEADLINE ({h['protocol']}):")
    for name in _present(h):
        r = h[name]
        ci = r.get("ci95_task_bootstrap", {}).get("f1")
        print(f"  {name:14s} F1 {r['f1']:.3f}" + (f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "")
              + f" recall {r['recall']:.3f} FPR {r['fpr']:.3f}")
    print(f"baseline {m['split'].get('method', 'stratified')} split (comparison only):")
    for name in _present(m["models"]):
        print(f"{name:14s} TRAIN {json.dumps({k: m['models'][name]['train'][k] for k in ('accuracy', 'precision', 'recall', 'f1', 'fpr')})}")
        print(f"{name:14s} TEST  {json.dumps({k: m['models'][name]['test'][k] for k in ('accuracy', 'precision', 'recall', 'f1', 'fpr')})}")
    print(f"report: {a.results / 'evaluation_report.md'}")


if __name__ == "__main__":
    main()
