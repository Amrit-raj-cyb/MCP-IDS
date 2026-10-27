"""Feature specification shared by the feature modules.

Every feature is declared once with its documentation. The extractor checks
that each module returns exactly the features it declares, and the schema
file (``feature_schema.json``) is generated from these declarations, so code
and documentation can't drift apart.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    category: str            # structural | behavioral | content
    dtype: str               # int | float
    description: str
    source: str              # which log events it is computed from
    preprocessing: str = "neutralize() applied to message bodies before extraction"
    used_for_training: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def stats(values: list[float]) -> tuple[float, float, float, float]:
    """mean, std, min, max (all 0.0 for an empty list)."""
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    a = np.asarray(values, dtype=float)
    return float(a.mean()), float(a.std()), float(a.min()), float(a.max())


def ratio(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0
