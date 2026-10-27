"""Confidence intervals for detection metrics.

Two kinds of interval are reported, because they answer different questions:

* **Wilson score interval** for a single proportion (recall = TP / attacks,
  FPR = FP / benign, precision = TP / alarms). It treats every session as an
  independent trial. Sessions generated from the same task are *not*
  independent, so this interval is too narrow for lab data; it is kept because
  it is the standard interval for a proportion and is comparable across reports.
* **Task-cluster bootstrap**: resample whole tasks with replacement, recompute
  the metric from the pooled out-of-fold predictions, take the 2.5 / 97.5
  percentiles. This respects the fact that the unit of independence is the task.
  With few tasks the interval is wide, which is the honest answer.
"""

from __future__ import annotations

import math

import numpy as np

Z95 = 1.96


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n (returns (0, 1) when n == 0)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def wilson_intervals(y_true, y_pred) -> dict:
    """Wilson intervals for recall, FPR and precision from one set of predictions."""
    y, p = np.asarray(y_true), np.asarray(y_pred)
    tp = int(((y == 1) & (p == 1)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    return {"recall": wilson(tp, int((y == 1).sum())),
            "fpr": wilson(fp, int((y == 0).sum())),
            "precision": wilson(tp, tp + fp)}


def _point(y: np.ndarray, p: np.ndarray) -> dict[str, float] | None:
    tp = int(((y == 1) & (p == 1)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum())
    pos, neg = tp + fn, int((y == 0).sum())
    if pos == 0 or neg == 0:
        return None  # a resample without both classes says nothing about recall or FPR
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / pos
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"f1": f1, "recall": rec, "precision": prec, "fpr": fp / neg}


def cluster_bootstrap(y_true, y_pred, groups, n_boot: int = 2000, seed: int = 42) -> dict:
    """95 % percentile intervals from resampling whole groups (tasks) with replacement."""
    y, p, g = np.asarray(y_true), np.asarray(y_pred), np.asarray(groups).astype(str)
    names = np.array(sorted(set(g)))
    index = {name: np.where(g == name)[0] for name in names}
    rng = np.random.default_rng(seed)
    draws: dict[str, list[float]] = {"f1": [], "recall": [], "precision": [], "fpr": []}
    for _ in range(n_boot):
        pick = rng.choice(names, size=len(names), replace=True)
        rows = np.concatenate([index[name] for name in pick])
        point = _point(y[rows], p[rows])
        if point is None:
            continue
        for k, v in point.items():
            draws[k].append(v)
    n_valid = len(draws["f1"])
    out: dict = {"method": f"task-cluster bootstrap, {n_boot} resamples of {len(names)} groups",
                 "n_valid_resamples": n_valid}
    for k, v in draws.items():
        out[k] = ((round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4))
                  if v else None)
    return out
