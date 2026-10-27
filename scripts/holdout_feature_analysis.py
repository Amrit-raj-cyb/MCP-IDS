"""Why are unseen attack families missed? Feature evidence for the family holdout.

For each feature directory and each held-out family (poisoned_tool,
sampling_injection), trains the Random Forest and XGBoost exactly as
``ml.evaluate.holdout_attack_families`` does (benign training sessions of the
saved split + every other attack family), then reports recall on the held-out
family and the features the model relies on (impurity / gain importance).
It also compares the range of key description features in benign sessions
with poisoned sessions, and the sampling signature per group.

    python -m scripts.holdout_feature_analysis --features data/phase9_081_ml --features data/expanded_20261008_ml \\
        --out results/expanded_20261008/holdout_feature_analysis.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ml.dataset import load_features
from ml.models import BUILDERS, LABELS
from ml.train import stratified_split

HELD = ("poisoned_tool", "sampling_injection")
MODELS = ("random_forest", "xgboost")
RANGE_FEATURES = ("desc_len_std", "desc_len_max", "directive_word_count", "model_address_count")


def analyse(feature_dir: Path, seed: int = 42) -> dict:
    d = load_features(feature_dir)
    tr, _ = stratified_split(d, 0.3, seed)
    fam = d.meta["attack_family"].fillna("benign").astype(str).to_numpy()
    benign_tr = np.intersect1d(tr, np.where(d.y == 0)[0])
    out = {"feature_dir": str(feature_dir).replace("\\", "/"), "n_sessions": int(len(d.y)), "holdouts": {}}
    for held in HELD:
        idx = np.concatenate([benign_tr, np.where((d.y == 1) & (fam != held))[0]])
        held_X = d.X[(d.y == 1) & (fam == held)]
        for name in MODELS:
            pipe = BUILDERS[name](seed).fit(d.X.iloc[idx], d.y[idx])
            imp = pipe.named_steps["model"].feature_importances_
            top = np.argsort(imp)[::-1][:3]
            out["holdouts"][f"{held}/{name}"] = {
                "recall": round(float(pipe.predict(held_X).mean()), 3),
                "top_features": [[d.feature_names[i], round(float(imp[i]), 3)] for i in top],
                "signature_constant_in_training": {
                    f: bool(d.X[f].iloc[idx].nunique() == 1)
                    for f in ("server_initiated_request_count", "cross_server_tool_reference_count")}}
    benign = d.X[fam == "benign"]
    poisoned = d.X[fam == "poisoned_tool"]
    out["ranges"] = {f: {"benign_max": round(float(benign[f].max()), 1),
                         "poisoned_median": round(float(poisoned[f].median()), 1),
                         "share_poisoned_above_benign_max": round(float((poisoned[f] > benign[f].max()).mean()), 2)}
                     for f in RANGE_FEATURES}
    out["sampling_signature_median"] = {g: float(d.X["server_initiated_request_count"][fam == g].median())
                                        for g in sorted(set(fam))}
    return out


def to_markdown(results: list[dict]) -> str:
    L = ["# Why unseen attack families are missed (family holdout, feature evidence)", "",
         "| Training set | Held-out family | Model | Recall | Top features (importance) |", "|---|---|---|---:|---|"]
    for r in results:
        for key, h in r["holdouts"].items():
            held, name = key.split("/")
            feats = ", ".join(f"`{f}` {v:.2f}" for f, v in h["top_features"])
            L.append(f"| {r['n_sessions']} | {held} | {LABELS[name]} | {h['recall']:.2f} | {feats} |")
    L += ["", "| Training set | Feature | Benign max | Poisoned median | Poisoned above benign max |",
          "|---|---|---:|---:|---:|"]
    for r in results:
        for f, v in r["ranges"].items():
            L.append(f"| {r['n_sessions']} | `{f}` | {v['benign_max']} | {v['poisoned_median']} | "
                     f"{v['share_poisoned_above_benign_max']:.0%} |")
    L += ["", "Median `server_initiated_request_count` per group: "
          + "; ".join(f"{r['n_sessions']} sessions: {r['sampling_signature_median']}" for r in results), ""]
    return "\n".join(L)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--features", type=Path, action="append", required=True)
    p.add_argument("--out", type=Path, required=True, help="Markdown output; JSON is written next to it")
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    results = [analyse(f, a.seed) for f in a.features]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(to_markdown(results), encoding="utf-8")
    a.out.with_suffix(".json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(to_markdown(results))


if __name__ == "__main__":
    main()
