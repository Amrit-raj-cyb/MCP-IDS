"""Evaluate already-trained models on an *external* feature dataset.

``ml.evaluate`` scores a model on the split of the dataset it was trained on.
This module answers a different question: how does a saved model behave on
sessions from another dataset it has never seen, for example a held-out
benign corpus (false-positive rate / drift)?

    python -m ml.evaluate_external --features data/benign_unique_081_ml \\
        --model models/phase9_081/random_forest.joblib --model models/phase9_081/svm.joblib \\
        --results results/benign_unique_081_eval

Per model it reports:
* accuracy / precision / recall / F1 / FPR on the external data;
* a Wilson 95 % interval for the FPR (0 false positives in 27 is not "0 %");
* the same split by *task seen in the model's training split* vs *unseen task*
  and by number of mounted servers;
* the highest attack score among benign sessions;
* how many external rows are exact feature-vector copies of training rows
  (copies measure memorisation, not generalisation).

Model inputs come from each model's own feature list (``*_metadata.json``)
and pass the same leakage guard as training. Raw-traffic models (metadata
``"input": "raw_session_text"``) read the external sessions' wire messages
instead (``ml.raw``); their "exact copy" count compares the masked session texts.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.dataset import assert_no_leakage, load_features
from ml.evaluate import binary_metrics
from ml.models import score
from ml.raw import RAW_COLUMN, load_raw
from ml.uncertainty import wilson

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(path_str: str) -> Path:
    """Model metadata may hold container paths (/lab/...); map them to the repo."""
    p = Path(path_str)
    if p.exists():
        return p
    s = path_str.replace("\\", "/")
    if s.startswith("/lab/"):
        return PROJECT_ROOT / s[len("/lab/"):]
    return p


def _training_rows(meta: dict, model_path: Path) -> pd.DataFrame | None:
    """Training rows (features + metadata) of a saved model, if available."""
    feature_dir = _resolve(meta["feature_dir"])
    split_file = model_path.with_name(meta.get("split_file", "split.json"))
    if not (feature_dir / "features.csv").is_file() or not split_file.is_file():
        return None
    df = pd.read_csv(feature_dir / "features.csv")
    train_ids = set(json.loads(split_file.read_text(encoding="utf-8"))["train_session_ids"])
    return df[df["session_id"].isin(train_ids)]


def _group_metrics(y, pred, scores, mask) -> dict:
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        return {"n": 0}
    m = binary_metrics(y[mask], pred[mask])
    fp, tn = m["confusion_matrix"]["fp"], m["confusion_matrix"]["tn"]
    benign = mask & (y == 0)
    m["fpr_wilson95"] = wilson(fp, fp + tn)
    m["max_benign_score"] = round(float(np.max(scores[benign])), 4) if benign.any() else None
    return m


def _raw_training_texts(meta: dict, train: pd.DataFrame) -> set[str]:
    raw = load_raw(_resolve(meta["feature_dir"]))
    keep = raw.meta["session_id"].isin(set(train["session_id"])).to_numpy()
    return set(raw.X[RAW_COLUMN][keep])


def evaluate_model(model_path: Path, data, raw_loader=None) -> dict:
    """``raw_loader()`` returns the external dataset's raw texts (``ml.raw.load_raw``), for raw models."""
    model_path = Path(model_path)
    pipe = joblib.load(model_path)
    meta = json.loads(model_path.with_name(model_path.stem + "_metadata.json").read_text(encoding="utf-8"))
    is_raw_model = meta.get("input") == "raw_session_text"
    cols = meta["features"]
    if is_raw_model:
        if raw_loader is None:
            return {"model": str(model_path), "error": "raw-traffic model needs the external sessions' logs"}
        X = raw_loader().X
    else:
        missing = [c for c in cols if c not in data.X.columns]
        if missing:
            return {"model": str(model_path), "error": f"external data lacks model features: {missing[:5]}"}
        assert_no_leakage(cols, cols)
        X = data.X[cols]
    y = data.y
    pred = pipe.predict(X)
    scores = np.asarray(score(pipe, X), dtype=float)

    train = _training_rows(meta, model_path)
    train_tasks = set(train["task_id"]) if train is not None else set()
    seen = data.meta["task_id"].isin(train_tasks).to_numpy()
    n_servers = data.X["n_servers_mounted"].to_numpy() if "n_servers_mounted" in data.X else None

    exact_copies = None
    if train is not None and is_raw_model:
        train_texts = _raw_training_texts(meta, train)
        exact_copies = int(sum(t in train_texts for t in X[RAW_COLUMN]))
    elif train is not None:
        train_vectors = {tuple(np.round(r, 6)) for r in train[cols].astype(float).to_numpy()}
        exact_copies = int(sum(tuple(np.round(r, 6)) in train_vectors for r in X.astype(float).to_numpy()))

    out = {
        "model": f"{model_path.parent.name}/{meta.get('model')}", "model_path": str(model_path).replace("\\", "/"),
        "trained_on_sha256": meta.get("dataset_sha256"), "n_features": len(cols),
        "input": meta.get("input", "features"),
        "score_kind": "probability of attack" if hasattr(pipe.named_steps["model"], "predict_proba")
                      else "SVM margin (>0 means attack)",
        "all": _group_metrics(y, pred, scores, np.ones(len(y), dtype=bool)),
        "task_seen_in_training": _group_metrics(y, pred, scores, seen),
        "task_not_seen_in_training": _group_metrics(y, pred, scores, ~seen),
        "n_training_tasks": len(train_tasks),
        "external_rows_identical_to_a_training_row": exact_copies,
    }
    if n_servers is not None:
        out["by_n_servers"] = {int(k): _group_metrics(y, pred, scores, n_servers == k)
                               for k in sorted(set(n_servers.astype(int)))}
    if y.any():
        fam = data.meta["attack_family"].fillna("")
        out["recall_by_family"] = {
            f: {"n": int(((fam == f) & (y == 1)).sum()),
                "detected": int(pred[((fam == f) & (y == 1)).to_numpy()].sum()),
                "recall": round(float(pred[((fam == f) & (y == 1)).to_numpy()].mean()), 4)}
            for f in sorted(set(fam[y == 1]))}
    flagged = data.meta.loc[(pred == 1) & (y == 0), "scenario_id"].value_counts().to_dict()
    out["flagged_benign_scenarios"] = {k: int(v) for k, v in flagged.items()} if flagged else {}
    return out


def report(res: dict) -> str:
    L = [f"# External evaluation: {res['features_dir']}", "",
         f"* Sessions: {res['n_sessions']} ({res['n_benign']} benign, {res['n_attack']} attack); "
         f"distinct feature vectors: {res['n_distinct_vectors']}",
         f"* Source dataset SHA-256: `{res['dataset_sha256']}`", "",
         "| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |",
         "|---|---|---|---|---|---|---|---|"]
    for m in res["models"]:
        if "error" in m:
            L.append(f"| {m['model_path']} | – | – | – | – | – | – | {m['error']} |")
            continue
        for group in ("all", "task_seen_in_training", "task_not_seen_in_training"):
            g = m[group]
            if not g.get("n"):
                continue
            cm = g["confusion_matrix"]
            rec = f"{g['recall']:.3f}" if g["n_attack"] else "–"
            copies = m["external_rows_identical_to_a_training_row"] if group == "all" else ""
            L.append(f"| {m['model']} ({group.replace('_', ' ')}) | {g['n']} | {cm['fp']} | {g['fpr']:.3f} | "
                     f"{g['fpr_wilson95'][0]:.3f}–{g['fpr_wilson95'][1]:.3f} | {g['max_benign_score']} | {rec} | {copies} |")
    L += ["", "False positives by number of mounted servers:", "",
          "| Model | " + " | ".join(f"{k} servers" for k in res["models"][0].get("by_n_servers", {})) + " |",
          "|---|" + "---|" * len(res["models"][0].get("by_n_servers", {}))]
    for m in res["models"]:
        if "by_n_servers" in m:
            L.append(f"| {m['model']} | " + " | ".join(
                f"{g['confusion_matrix']['fp']}/{g['n']} (max {g['max_benign_score']})"
                for g in m["by_n_servers"].values()) + " |")
    fams = [m for m in res["models"] if m.get("recall_by_family")]
    if fams:
        L += ["", "Recall by attack family:", "", "| Model | " + " | ".join(fams[0]["recall_by_family"]) + " |",
              "|---|" + "---|" * len(fams[0]["recall_by_family"])]
        for m in fams:
            L.append(f"| {m['model']} | " + " | ".join(f"{v['detected']}/{v['n']} ({v['recall']:.2f})"
                                                     for v in m["recall_by_family"].values()) + " |")
    L += ["", "Flagged benign scenarios (false positives):", ""]
    for m in res["models"]:
        L.append(f"* {m.get('model')}: {m.get('flagged_benign_scenarios') or 'none'}")
    return "\n".join(L) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate saved models on an external feature dataset")
    p.add_argument("--features", type=Path, required=True)
    p.add_argument("--model", type=Path, action="append", required=True)
    p.add_argument("--results", type=Path, required=True)
    a = p.parse_args()
    data = load_features(a.features)
    raw_cache: list = []

    def raw_loader():  # read the external logs once, and only if a raw-traffic model needs them
        if not raw_cache:
            raw_cache.append(load_raw(a.features))
        return raw_cache[0]

    summary = json.loads((a.features / "dataset_summary.json").read_text(encoding="utf-8"))
    res = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "features_dir": str(a.features).replace("\\", "/"), "dataset_sha256": summary.get("dataset_sha256"),
        "n_sessions": int(len(data.y)), "n_benign": int((data.y == 0).sum()), "n_attack": int(data.y.sum()),
        "n_distinct_vectors": int(len({tuple(r) for r in np.round(data.X.to_numpy(dtype=float), 6)})),
        "models": [evaluate_model(m, data, raw_loader) for m in a.model],
    }
    a.results.mkdir(parents=True, exist_ok=True)
    (a.results / "metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    (a.results / "report.md").write_text(report(res), encoding="utf-8")
    print(report(res))


if __name__ == "__main__":
    main()
