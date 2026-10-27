"""Model definitions. All models share the same preprocessing step.

Every model is a complete scikit-learn ``Pipeline``. Preprocessing is fitted
**inside** the pipeline on training data only, and is saved and reloaded
together with the model, so inference uses exactly the training
transformations and the test set can't influence them.

* Shared preprocessing: impute missing values with 0 (features are counts,
  sizes and ratios where "absent" means 0).
* Random Forest: no scaling needed (trees split on thresholds).
* SVM (RBF kernel): StandardScaler first, because distances need comparable
  feature scales. The scaler's mean/std come from the training data only.
* XGBoost: gradient-boosted trees, trained from scratch on our features (no
  pre-trained weights: a model trained on other inputs, e.g. network flows,
  cannot be applied to or fine-tuned on MCP session features). No scaling.
* RF + XGBoost: soft voting, i.e. the mean of the two models' attack
  probabilities, thresholded at 0.5. Each member is fitted on the same
  training rows. Soft voting adds no fitted parameters of its own; stacking was
  not used because its meta-model would be trained on inner random-split
  predictions, the near-duplicate problem the task-grouped evaluation avoids.
* Decision Tree: a single CART tree (Gini, fully grown, library defaults), the
  interpretable baseline the Random Forest averages over. No scaling.
* CNN: a small 1-D convolutional network over the standardised feature vector
  (:mod:`ml.cnn`), trained from scratch with PyTorch. StandardScaler first, as
  for the SVM, because neural-network training needs comparable feature scales.
* Raw-traffic CNN (``RAW_BUILDERS``): a byte-level CNN over the session's masked
  wire messages (:mod:`ml.raw`, :mod:`ml.raw_cnn`) instead of the features.

The ``*_PARAMS`` below are the defaults. ``ml.tuning`` searches a grid around them
on training data only (task-grouped inner CV); builders take the winning
settings as ``params`` and :func:`effective_params` records what was used.

``class_weight="balanced"`` keeps training robust if a future dataset or
family-holdout training fold has unequal class counts. XGBoost has no
``class_weight``; :class:`BalancedXGBClassifier` applies the same balanced
sample weights (computed from each training fold only).
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import Booster, XGBClassifier

from ml.cnn import CNN1DClassifier
from ml.raw_cnn import RawByteCNN

RF_PARAMS = {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 1,
             "class_weight": "balanced", "n_jobs": 1}
SVM_PARAMS = {"kernel": "rbf", "C": 1.0, "gamma": "scale", "class_weight": "balanced"}
# Library-default learning rate and depth with 300 rounds (same tree budget as the RF); nothing was tuned
# on test data. tree_method="hist" + n_jobs=1 keep results reproducible run to run.
XGB_PARAMS = {"n_estimators": 300, "learning_rate": 0.3, "max_depth": 6, "subsample": 1.0,
              "colsample_bytree": 1.0, "tree_method": "hist", "eval_metric": "logloss", "n_jobs": 1,
              "class_weight": "balanced (per-sample weights)"}
RF_XGB_PARAMS = {"voting": "soft (mean attack probability, threshold 0.5)", "weights": "equal",
                 "random_forest": RF_PARAMS, "xgboost": XGB_PARAMS}
DT_PARAMS = {"criterion": "gini", "max_depth": None, "min_samples_leaf": 1, "class_weight": "balanced"}
# Fixed in advance (a small network sized for ~1,000 training rows and CPU-only training), not tuned on
# test data.
CNN_PARAMS = {"channels": (16, 32), "kernel_size": 3, "hidden": 32, "dropout": 0.2, "epochs": 50,
              "batch_size": 64, "learning_rate": 1e-3, "weight_decay": 1e-4}
# Raw-traffic CNN (ml/raw_cnn.py): first 32 KiB of the session text (covers all but the very longest
# sessions); stride-1 convolution + local max pooling (shift-robust, see ml/raw_cnn.py). Tuned settings
# (ml/tuning.py) override these.
CNN_RAW_PARAMS = {"max_len": 32768, "emb_dim": 8, "arch": "pooled", "channels": 64, "kernel_size": 8,
                  "pool": 4, "shift_augment": True, "kernel_size2": 4, "hidden": 32, "dropout": 0.2, "epochs": 15, "batch_size": 32,
                  "learning_rate": 1e-3, "weight_decay": 1e-4}


class BalancedXGBClassifier(XGBClassifier):
    """XGBClassifier that weights classes like ``class_weight="balanced"`` when no weights are given.

    Pickling stores the fitted booster in XGBoost's portable model format (UBJSON)
    instead of its default memory snapshot, which is not portable between builds:
    a model trained in the Linux lab container failed to load on the Windows host
    ("input stream corrupted"). Predictions are identical after the round trip.
    """

    def fit(self, X, y, *, sample_weight=None, **kwargs):
        if sample_weight is None:
            sample_weight = compute_sample_weight("balanced", np.asarray(y))
        return super().fit(X, y, sample_weight=sample_weight, **kwargs)

    def __getstate__(self):
        state = dict(super().__getstate__())  # a copy: on Python 3.11+ this can be the live __dict__
        booster = state.pop("_Booster", None)
        if booster is not None:
            state["_booster_ubj"] = bytes(booster.save_raw("ubj"))
        return state

    def __setstate__(self, state):
        raw = state.pop("_booster_ubj", None)
        super().__setstate__(state)
        if raw is not None:
            booster = Booster()
            booster.load_model(bytearray(raw))
            self._Booster = booster


def shared_preprocessing() -> list[tuple[str, object]]:
    return [("impute", SimpleImputer(strategy="constant", fill_value=0.0))]


def _merged(defaults: dict, params: dict | None) -> dict:
    """Default hyperparameters updated with tuned values (``params``), if any."""
    return {**defaults, **(params or {})}


def _rf(seed: int, params: dict | None = None) -> RandomForestClassifier:
    return RandomForestClassifier(random_state=seed, **_merged(RF_PARAMS, params))


def _xgb(seed: int, params: dict | None = None) -> BalancedXGBClassifier:
    p = {k: v for k, v in _merged(XGB_PARAMS, params).items() if k != "class_weight"}
    return BalancedXGBClassifier(random_state=seed, **p)


def build_random_forest(seed: int, params: dict | None = None) -> Pipeline:
    return Pipeline(shared_preprocessing() + [("model", _rf(seed, params))])


def build_svm(seed: int, params: dict | None = None) -> Pipeline:
    return Pipeline(shared_preprocessing() + [("scale", StandardScaler()),
                                               ("model", SVC(random_state=seed, **_merged(SVM_PARAMS, params)))])


def build_xgboost(seed: int, params: dict | None = None) -> Pipeline:
    return Pipeline(shared_preprocessing() + [("model", _xgb(seed, params))])


def build_rf_xgb(seed: int, params: dict | None = None) -> Pipeline:
    """Soft vote of an RF and an XGBoost; ``params`` = {"random_forest": {...}, "xgboost": {...}}
    (the members' own tuned settings, so the ensemble needs no search of its own)."""
    params = params or {}
    vote = VotingClassifier([("random_forest", _rf(seed, params.get("random_forest"))),
                             ("xgboost", _xgb(seed, params.get("xgboost")))], voting="soft")
    return Pipeline(shared_preprocessing() + [("model", vote)])


def build_decision_tree(seed: int, params: dict | None = None) -> Pipeline:
    return Pipeline(shared_preprocessing() + [("model", DecisionTreeClassifier(random_state=seed,
                                                                               **_merged(DT_PARAMS, params)))])


def build_cnn(seed: int, params: dict | None = None) -> Pipeline:
    return Pipeline(shared_preprocessing() + [("scale", StandardScaler()),
                                               ("model", CNN1DClassifier(random_state=seed,
                                                                         **_merged(CNN_PARAMS, params)))])


def build_cnn_raw(seed: int, params: dict | None = None) -> Pipeline:
    """Byte-level CNN over the raw session text (input: :func:`ml.raw.raw_frame`, not features)."""
    return Pipeline([("model", RawByteCNN(random_state=seed, **_merged(CNN_RAW_PARAMS, params)))])


# Feature models: input = the 65 session features.
BUILDERS = {"random_forest": build_random_forest, "svm": build_svm,
            "xgboost": build_xgboost, "rf_xgb": build_rf_xgb,
            "decision_tree": build_decision_tree, "cnn": build_cnn}
# Raw-traffic models: input = the session's wire messages as text (ml/raw.py).
RAW_BUILDERS = {"cnn_raw": build_cnn_raw}
ALL_BUILDERS = {**BUILDERS, **RAW_BUILDERS}
PARAMS = {"random_forest": RF_PARAMS, "svm": SVM_PARAMS, "xgboost": XGB_PARAMS, "rf_xgb": RF_XGB_PARAMS,
          "decision_tree": DT_PARAMS, "cnn": CNN_PARAMS, "cnn_raw": CNN_RAW_PARAMS}
LABELS = {"random_forest": "Random Forest", "svm": "SVM (RBF)", "xgboost": "XGBoost",
          "rf_xgb": "RF + XGBoost (soft vote)", "decision_tree": "Decision Tree", "cnn": "1-D CNN",
          "cnn_raw": "Raw-traffic CNN"}
# File-name tag for plots; rf/svm keep their original names so existing references stay valid.
SHORT = {"random_forest": "rf", "svm": "svm", "xgboost": "xgb", "rf_xgb": "rf_xgb",
         "decision_tree": "dt", "cnn": "cnn", "cnn_raw": "cnn_raw"}


def is_raw(name: str) -> bool:
    """True for models that read the raw session text instead of the features."""
    return name in RAW_BUILDERS


def build(name: str, seed: int, params: dict | None = None) -> Pipeline:
    """An unfitted pipeline for any model, with optional tuned hyperparameters."""
    return ALL_BUILDERS[name](seed, params)


def effective_params(name: str, params: dict | None = None) -> dict:
    """The hyperparameters a model is actually built with (defaults + tuned values)."""
    if name == "rf_xgb":
        params = params or {}
        return {**RF_XGB_PARAMS, "random_forest": _merged(RF_PARAMS, params.get("random_forest")),
                "xgboost": _merged(XGB_PARAMS, params.get("xgboost"))}
    return _merged(PARAMS[name], params)


def is_probabilistic(pipeline: Pipeline) -> bool:
    """True if the model's score is P(attack) (all models except the SVM); False for the SVM margin."""
    return hasattr(pipeline.named_steps["model"], "predict_proba")


def score(pipeline: Pipeline, X) -> list[float]:
    """Attack score: probability of 'attack' (all but the SVM), SVM signed distance to the boundary."""
    if is_probabilistic(pipeline):
        return pipeline.predict_proba(X)[:, 1].tolist()
    return pipeline.decision_function(X).tolist()
