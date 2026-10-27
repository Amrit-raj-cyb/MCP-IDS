"""Task-grouped feature-group ablation for every model (the main research question).

``ml.evaluate`` runs its ablation on the random split, where duplicated
sessions make almost every feature group look perfect. This script repeats the
ablation under the headline protocol instead: the same task-grouped folds as
``ml.evaluate.grouped_cv`` (GroupKFold on ``task_id``), every session
predicted out of fold, metrics pooled, for each feature group and each model in
``ml.models.BUILDERS``. Optionally each configuration is repeated without the
two single-family signature features (server-initiated requests: sampling;
cross-server tool references: shadowing).

    python -m scripts.grouped_ablation --features data/phase9_081_ml --out results/phase9_081/grouped_ablation.json

Writes JSON plus a Markdown table next to it (same name, ``.md``).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ml.dataset import feature_matrix, group_columns, load_features
from ml.evaluate import _task_folds, binary_metrics
from ml.models import BUILDERS, LABELS
from ml.train import versions

GROUPS = {"all": ("structural", "behavioral", "content"), "structural": ("structural",),
          "behavioral": ("behavioral",), "content": ("content",),
          "structural+behavioral": ("structural", "behavioral")}
SIGNATURES = ("server_initiated_request_count", "cross_server_tool_reference_count")


def grouped_ablation(feature_dir: Path, seed: int = 42, without_signatures: bool = True) -> dict:
    data = load_features(feature_dir)
    tf = _task_folds(data)
    if "skipped" in tf:
        return tf
    folds = tf["folds_idx"]
    families = data.meta["attack_family"].fillna("benign").astype(str).to_numpy()
    out = {"feature_dir": str(feature_dir).replace("\\", "/"), "scheme": tf["scheme"], "n_groups": tf["n_groups"],
           "seed": seed, "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "versions": versions(), "configs": {}}
    variants = [("", ())] + ([(" (no signatures)", SIGNATURES)] if without_signatures else [])
    for gname, cats in GROUPS.items():
        for suffix, drop in variants:
            cols = [c for c in group_columns(data.schema, *cats) if c not in drop]
            X = feature_matrix(data.X, data.schema, cols)
            cfg = {"n_features": len(cols)}
            for name, build in BUILDERS.items():
                pred = np.zeros_like(data.y)
                for tr, te in folds:
                    pred[te] = build(seed).fit(X.iloc[tr], data.y[tr]).predict(X.iloc[te])
                m = binary_metrics(data.y, pred)
                m["recall_by_family"] = {f: round(float(pred[(families == f) & (data.y == 1)].mean()), 4)
                                         for f in sorted(set(families) - {"benign"})}
                cfg[name] = m
            out["configs"][gname + suffix] = cfg
    return out


def to_markdown(res: dict) -> str:
    names = list(BUILDERS)
    L = [f"# Task-grouped feature-group ablation: `{res['feature_dir']}`", "",
         f"{res['scheme']} over {res['n_groups']} tasks, pooled out-of-fold predictions, seed {res['seed']}.", "",
         "| Features | # | " + " | ".join(f"{LABELS[n]} F1 / FPR" for n in names) + " |",
         "|---|---:|" + "---|" * len(names)]
    for g, cfg in res["configs"].items():
        L.append(f"| {g} | {cfg['n_features']} | "
                 + " | ".join(f"{cfg[n]['f1']:.2f} / {cfg[n]['fpr']:.2f}" for n in names) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Task-grouped feature-group ablation for every model")
    p.add_argument("--features", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="output JSON path")
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    res = grouped_ablation(a.features, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    a.out.with_suffix(".md").write_text(to_markdown(res), encoding="utf-8")
    print(to_markdown(res))


if __name__ == "__main__":
    main()
