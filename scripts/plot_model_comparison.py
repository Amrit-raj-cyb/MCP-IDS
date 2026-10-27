"""One figure comparing the models across the three datasets (from saved metrics only).

    python -m scripts.plot_model_comparison --run 20261008 --out results/model_comparison_20261008.png
    python -m scripts.plot_model_comparison --run 20261009 --out results/model_comparison_20261009.png
    python -m scripts.plot_model_comparison --run 20261010 --out results/model_comparison_20261010.png

``--run`` picks the saved results folders: 20261008 has four models, 20261009 adds the
Decision Tree and the CNN, and 20261010 is the final dataset with benign sampling servers and the
original-wording benign corpus (2,220 sessions; task-grouped split, every model tuned, plus the
raw-traffic CNN): panel (a)
shows its nested-tuned task-grouped CV, panel (c) how the 9 October models (never trained on
benign sampling) react to the new benign sampling sessions. Models missing from a run's
results are left out.

Panels: (a) task-grouped F1 with 95 % task-cluster bootstrap intervals; (b) recall
when the whole poisoning family is held out of training; (c) false-positive rate
on held-out benign corpora with 95 % Wilson intervals.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from ml.models import ALL_BUILDERS, LABELS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RUNS = {
    "20261008": {
        "datasets": [("Original\n(180)", "phase9_081"), ("Matched\n(720)", "phase9_expanded_20261006"),
                     ("Combined\n(1,354)", "expanded_20261006")],
        # (label, results folder, model folder whose models were scored there)
        "benign": [("Unseen benign tasks\n(200; original models)", "benign_unique_081_eval", "phase9_081"),
                   ("Canonical corpus\n(634; matched models)", "phase9_expanded_20261006_external_original",
                    "phase9_expanded_20261006"),
                   ("Reworded corpus\n(634; matched models)", "phase9_expanded_20261006_external_varied",
                    "phase9_expanded_20261006")]},
    "20261009": {
        "datasets": [("Original\n(180)", "phase9_081_20261009"), ("Matched\n(720)", "phase9_expanded_20261009"),
                     ("Combined\n(1,354)", "expanded_20261009")],
        "benign": [("Unseen benign tasks\n(200; original models)", "benign_unique_081_eval_20261009",
                    "phase9_081_20261009"),
                   ("Canonical corpus\n(634; matched models)", "phase9_expanded_20261009_external_original",
                    "phase9_expanded_20261009"),
                   ("Reworded corpus\n(634; matched models)", "phase9_expanded_20261009_external_varied",
                    "phase9_expanded_20261009")]},
    "20261010": {
        "datasets": [("Final dataset\n(2,220; task-grouped split)", "combined_canonical_20261010")],
        "benign": [("New benign sampling sessions\n(232; 9 Oct models, never saw any)",
                    "benign_sampling_091_eval_20261009_models", "expanded_20261009")]},
}
COLORS = {"random_forest": "#3b6ea8", "svm": "#d08c2e", "xgboost": "#2e8b57", "rf_xgb": "#7b5ea7",
          "decision_tree": "#8c564b", "cnn": "#c0392b", "cnn_raw": "#2b2b2b"}


def _load(folder: str) -> dict:
    return json.loads((ROOT / "results" / folder / "metrics.json").read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run", choices=list(RUNS), default="20261008")
    p.add_argument("--out", type=Path, default=None, help="default: results/model_comparison_<run>.png")
    a = p.parse_args()
    a.out = a.out or ROOT / "results" / f"model_comparison_{a.run}.png"
    DATASETS, BENIGN = RUNS[a.run]["datasets"], RUNS[a.run]["benign"]

    def grouped(folder: str) -> dict:  # nested-tuned task-grouped CV when the run has it
        m = _load(folder)
        return m.get("grouped_cv_tuned") or m["grouped_cv"]

    names = [n for n in ALL_BUILDERS if n in grouped(DATASETS[0][1])]
    width = 0.8 / len(names)
    offsets = (np.arange(len(names)) - (len(names) - 1) / 2) * width
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), dpi=150)

    ax = axes[0]
    for j, (_, folder) in enumerate(DATASETS):
        g = grouped(folder)
        for k, n in enumerate(names):
            f1, (lo, hi) = g[n]["f1"], g[n]["ci95_task_bootstrap"]["f1"]
            ax.errorbar(j + offsets[k], f1, yerr=[[f1 - lo], [hi - f1]], fmt="o", color=COLORS[n], capsize=3,
                        label=LABELS[n] if j == 0 else None)
    for j, (_, folder) in enumerate(DATASETS):
        # Flagging every session as an attack: precision = attack share p, recall = 1, F1 = 2p / (1 + p).
        # Computed per dataset (0.67 only when half the sessions are attacks).
        d = _load(folder)["dataset"]
        p = d["n_attack"] / d["n_sessions"]
        base = 2 * p / (1 + p)
        ax.hlines(base, j - 0.45, j + 0.45, ls="--", lw=0.8, color="gray")
        ax.text(j - 0.45, base + 0.015, f"flag everything: {base:.2f}", fontsize=7, color="gray", ha="left")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1")
    nested = "grouped_cv_tuned" in _load(DATASETS[0][1])
    ax.set_title("(a) Task-grouped CV" + (", tuned (nested)" if nested else "") + ": F1 with 95% task-bootstrap CI",
                 fontsize=9)

    ax = axes[1]
    for j, (_, folder) in enumerate(DATASETS):
        fold = _load(folder)["holdout_attack_family"]["folds"]["poisoned_tool"]
        for k, n in enumerate(names):
            r = fold[n]["recall"]
            ax.bar(j + offsets[k], r, width * 0.9, color=COLORS[n])
            ax.text(j + offsets[k], r + 0.02, f"{r:.2f}", ha="center", fontsize=6.5)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("recall")
    ax.set_title("(b) Poisoning family held out of training: recall", fontsize=9)

    for ax in axes[:2]:
        ax.set_xticks(range(len(DATASETS)), [d for d, _ in DATASETS], fontsize=8)

    ax = axes[2]
    for j, (_, folder, model_dir) in enumerate(BENIGN):
        models = {m["model_path"].replace("\\", "/").split("/")[-2] + "/" + m["model_path"].replace("\\", "/")
                  .split("/")[-1]: m for m in _load(folder)["models"]}
        for k, n in enumerate(names):
            if f"{model_dir}/{n}.joblib" not in models:  # e.g. the raw-traffic CNN did not exist then
                continue
            g = models[f"{model_dir}/{n}.joblib"]["all"]
            fpr, (lo, hi) = g["fpr"], g["fpr_wilson95"]
            ax.bar(j + offsets[k], fpr, width * 0.9, color=COLORS[n])
            ax.errorbar(j + offsets[k], fpr, yerr=[[fpr - lo], [hi - fpr]], fmt="none", ecolor="black",
                        capsize=2, lw=0.8)
            ax.text(j + offsets[k], hi + 0.02, f"{g['confusion_matrix']['fp']}", ha="center", fontsize=6.5)
    ax.set_xticks(range(len(BENIGN)), [b for b, _, _ in BENIGN], fontsize=7.5)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("false-positive rate")
    ax.set_title("(c) False alarms on held-out benign corpora (count above bar)", fontsize=9)

    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=len(names), fontsize=8, frameon=False)
    fig.text(0.995, 0.01, "small controlled laboratory datasets", ha="right", fontsize=7, color="gray")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out)
    print(f"written {a.out}")


if __name__ == "__main__":
    main()
