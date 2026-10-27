"""Benign-only anomaly detection: learn what normal MCP sessions look like, flag the rest.

The supervised models need attack examples and miss attack families they never
saw (see the family holdout). An anomaly detector is trained on **benign
sessions only**, so it does not depend on which attacks were simulated. The
price is a threshold that must be set without attack data.

Detectors (complete scikit-learn pipelines, same zero imputation as ml.models):

* ``isolation_forest``: IsolationForest(300 trees); no scaling needed.
* ``one_class_svm``: StandardScaler + OneClassSVM(RBF, nu=0.05).

Threshold: the anomaly score at the ``quantile`` (default 0.95) of the
*training* benign sessions, i.e. a target false-positive rate of about 5 % on
traffic like the training benign data. Test data never influence it.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from ml.models import shared_preprocessing

IF_PARAMS = {"n_estimators": 300, "contamination": "auto"}
OCSVM_PARAMS = {"kernel": "rbf", "nu": 0.05, "gamma": "scale"}
DEFAULT_QUANTILE = 0.95


def build_isolation_forest(seed: int) -> Pipeline:
    return Pipeline(shared_preprocessing() + [("model", IsolationForest(random_state=seed, **IF_PARAMS))])


def build_one_class_svm(seed: int) -> Pipeline:  # seed unused: OneClassSVM is deterministic
    return Pipeline(shared_preprocessing() + [("scale", StandardScaler()), ("model", OneClassSVM(**OCSVM_PARAMS))])


ANOMALY_BUILDERS = {"isolation_forest": build_isolation_forest, "one_class_svm": build_one_class_svm}
ANOMALY_PARAMS = {"isolation_forest": IF_PARAMS, "one_class_svm": OCSVM_PARAMS}


class BenignOnlyDetector:
    """Fit on benign rows only; predict 1 (attack) when the anomaly score exceeds the threshold."""

    def __init__(self, name: str, seed: int, quantile: float = DEFAULT_QUANTILE) -> None:
        self.name, self.quantile = name, quantile
        self.pipeline = ANOMALY_BUILDERS[name](seed)
        self.threshold: float | None = None

    def anomaly_score(self, X) -> np.ndarray:
        # score_samples: higher = more normal; negate so higher = more anomalous.
        return -self.pipeline.score_samples(X)

    def fit(self, X_benign) -> "BenignOnlyDetector":
        if len(X_benign) == 0:
            raise ValueError("benign-only detector needs at least one benign training session")
        self.pipeline.fit(X_benign)
        self.threshold = float(np.quantile(self.anomaly_score(X_benign), self.quantile))
        return self

    def predict(self, X) -> np.ndarray:
        if self.threshold is None:
            raise RuntimeError("fit() first")
        return (self.anomaly_score(X) > self.threshold).astype(int)
