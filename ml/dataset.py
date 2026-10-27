"""Load the feature dataset and split it into X (features) / y (target) / meta.

Leakage guard
-------------
:func:`feature_matrix` is the *only* way the ML code gets X. It takes the
column list from ``feature_schema.json`` (features with
``used_for_training``) and then calls :func:`assert_no_leakage`, which fails
loudly if any column is metadata or *looks* like it carries the answer
(label, attack family/variant, success, scenario, session, seed, lab
marker...). The check runs on every training and evaluation call, not just
in tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

TARGET = "label"
POSITIVE = "attack"

FORBIDDEN_COLUMNS = {
    "session_id", "scenario_id", "task_id", "label", "attack_family", "attack_variant",
    "attack_succeeded", "attack_attempted", "seed", "twin_of", "servers", "backend", "dataset_tag",
    "log_dir", "log_files", "status", "agent_config", "lab_version", "y",
}
# Substrings that must never appear in a feature name.
FORBIDDEN_SUBSTRINGS = ("label", "attack", "scenario", "variant", "succeed", "success", "twin", "seed",
                        "session", "marker", "canary", "simulation", "dataset", "task")


class LeakageError(AssertionError):
    pass


def assert_no_leakage(columns: list[str], allowed: list[str]) -> None:
    """Raise :class:`LeakageError` if any column must not be a model input."""
    problems = []
    for c in columns:
        if c in FORBIDDEN_COLUMNS:
            problems.append(f"{c}: metadata/label column")
        elif any(s in c.lower() for s in FORBIDDEN_SUBSTRINGS):
            problems.append(f"{c}: name suggests label information")
        elif c not in allowed:
            problems.append(f"{c}: not a documented training feature in feature_schema.json")
    if problems:
        raise LeakageError("Leakage guard failed:\n  " + "\n  ".join(problems))


@dataclass
class FeatureData:
    X: pd.DataFrame          # features only
    y: np.ndarray            # 1 = attack, 0 = benign
    meta: pd.DataFrame       # metadata columns (never used for training)
    feature_names: list[str]
    schema: dict


def load_schema(feature_dir: Path) -> dict:
    return json.loads((Path(feature_dir) / "feature_schema.json").read_text(encoding="utf-8"))


def training_features(schema: dict) -> list[str]:
    return [f["name"] for f in schema["features"] if f["used_for_training"]]


def feature_matrix(df: pd.DataFrame, schema: dict, columns: list[str] | None = None) -> pd.DataFrame:
    """The guarded way to get X. ``columns`` selects a subset (e.g. one feature group)."""
    allowed = training_features(schema)
    cols = list(columns) if columns is not None else allowed
    assert_no_leakage(cols, allowed)
    return df[cols].astype(float)


def load_features(feature_dir: Path) -> FeatureData:
    feature_dir = Path(feature_dir)
    schema = load_schema(feature_dir)
    df = pd.read_csv(feature_dir / "features.csv")
    if df["session_id"].duplicated().any():
        raise ValueError("duplicate session ids in features.csv")
    if not set(df[TARGET]).issubset({"benign", POSITIVE}):
        raise ValueError(f"unexpected labels: {set(df[TARGET])}")
    X = feature_matrix(df, schema)
    y = (df[TARGET] == POSITIVE).astype(int).to_numpy()
    meta = df[[c for c in schema["metadata_columns"] if c in df.columns]].copy()
    return FeatureData(X, y, meta, list(X.columns), schema)


def group_columns(schema: dict, *categories: str) -> list[str]:
    return [f["name"] for f in schema["features"] if f["used_for_training"] and f["category"] in categories]


def resolve_dataset_dir(recorded: str) -> Path:
    """Find the source dataset on this machine.

    ``dataset_summary.json`` stores the path where features were extracted. If
    that was inside the Docker lab (``/lab/...``) and we now run on the host,
    map it into the project folder (Compose mounts ``./data`` at ``/lab/data``).
    """
    path = Path(recorded)
    if path.is_dir():
        return path
    posix = recorded.replace("\\", "/")
    if posix.startswith("/lab/"):
        mapped = _PROJECT_ROOT / posix[len("/lab/"):]
        if mapped.is_dir():
            return mapped
    raise FileNotFoundError(f"source dataset not found: {recorded} (needed for latency and the raw-traffic model)")
