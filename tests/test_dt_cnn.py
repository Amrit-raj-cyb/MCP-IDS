"""Decision Tree and 1-D CNN: builders, determinism, portable pickles, training and the live detector."""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.tree import DecisionTreeClassifier

from ml.cnn import CNN1DClassifier
from ml.inference import Detector
from ml.models import BUILDERS, CNN_PARAMS, DT_PARAMS, PARAMS, is_probabilistic, score
from ml.train import train


def _xy(n: int = 200, seed: int = 0) -> tuple[pd.DataFrame, np.ndarray]:
    """Imbalanced (about 1 attack in 5), learnable but not trivially separable."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(n, 6)), columns=list("abcdef"))
    y = (X["a"] + 0.4 * rng.normal(size=n) > 0.8).astype(int).to_numpy()
    return X, y


def _small_cnn(seed: int = 0, **kw) -> CNN1DClassifier:
    return CNN1DClassifier(random_state=seed, **{**CNN_PARAMS, "epochs": 15, **kw})


def test_pipelines_have_the_documented_steps_and_params() -> None:
    dt, cnn = BUILDERS["decision_tree"](1), BUILDERS["cnn"](1)
    assert [s for s, _ in dt.steps] == ["impute", "model"]  # trees need no scaling
    assert [s for s, _ in cnn.steps] == ["impute", "scale", "model"]  # the network does
    assert isinstance(dt.named_steps["model"], DecisionTreeClassifier)
    assert dt.named_steps["model"].get_params()["class_weight"] == "balanced"
    assert {k: cnn.named_steps["model"].get_params()[k] for k in CNN_PARAMS} == CNN_PARAMS
    assert PARAMS["decision_tree"] == DT_PARAMS and PARAMS["cnn"] == CNN_PARAMS


def test_cnn_learns_and_outputs_probabilities() -> None:
    X, y = _xy(seed=1)
    m = _small_cnn(epochs=40).fit(X.to_numpy(), y)
    p = m.predict_proba(X.to_numpy())
    assert p.shape == (len(y), 2)
    np.testing.assert_allclose(p.sum(axis=1), 1.0)
    assert ((p >= 0) & (p <= 1)).all()
    assert m.loss_curve_[-1] < m.loss_curve_[0]  # training reduces the loss
    assert (m.predict(X.to_numpy()) == y).mean() > 0.9
    np.testing.assert_array_equal(m.predict(X.to_numpy()), (p[:, 1] > 0.5).astype(int))


def test_cnn_keeps_original_class_labels_and_is_binary_only() -> None:
    X, y = _xy()
    labels = np.where(y == 1, "attack", "benign")
    m = _small_cnn().fit(X.to_numpy(), labels)
    assert m.classes_.tolist() == ["attack", "benign"]
    assert set(m.predict(X.to_numpy())) <= {"attack", "benign"}
    with pytest.raises(ValueError, match="binary"):
        _small_cnn().fit(X.to_numpy(), np.arange(len(y)) % 3)
    with pytest.raises(ValueError, match="odd"):
        _small_cnn(kernel_size=4).fit(X.to_numpy(), y)


def test_cnn_handles_a_single_feature() -> None:
    """The ablation and confound checks can leave very few features."""
    X, y = _xy()
    m = _small_cnn().fit(X[["a"]].to_numpy(), y)
    assert m.predict_proba(X[["a"]].to_numpy()).shape == (len(y), 2)


def test_cnn_balances_classes_with_sample_weights() -> None:
    """With 1 attack in 5, an unweighted network tends to favour 'benign'; balancing raises attack recall."""
    X, y = _xy(n=300, seed=4)
    balanced = _small_cnn(seed=2, epochs=25).fit(X.to_numpy(), y)
    p = balanced.predict(X.to_numpy())
    assert p[y == 1].mean() >= 0.8


def test_cnn_clone_keeps_params() -> None:
    c = clone(_small_cnn(seed=9))
    assert type(c) is CNN1DClassifier and c.get_params()["random_state"] == 9 and c.get_params()["epochs"] == 15
    assert not hasattr(c, "net_")


@pytest.mark.parametrize("name", ["decision_tree", "cnn"])
def test_new_models_are_deterministic_and_work_through_the_detector(name: str, tmp_path: Path) -> None:
    X, y = _xy()
    a, b = BUILDERS[name](42).fit(X, y), BUILDERS[name](42).fit(X, y)
    assert score(a, X) == score(b, X)
    assert is_probabilistic(a)
    path = tmp_path / f"{name}.joblib"
    joblib.dump(a, path)
    path.with_name(f"{name}_metadata.json").write_text(json.dumps({"model": name, "features": list(X.columns)}),
                                                       encoding="utf-8")
    det = Detector(path)
    for i in range(10):
        out = det.classify_features(X.iloc[i].to_dict())
        assert 0.0 <= out["score"] <= 1.0
        assert out["prediction"] == ("attack" if a.predict(X.iloc[[i]])[0] else "benign")


def test_cnn_pickle_is_portable_and_exact() -> None:
    """Weights are stored as NumPy arrays (no torch objects), and predictions survive the round trip."""
    X, y = _xy()
    pipe = BUILDERS["cnn"](3).fit(X, y)
    cnn = pipe.named_steps["model"]
    state = cnn.__getstate__()
    assert "net_" not in state
    assert all(isinstance(v, np.ndarray) for v in state["_weights"].values())
    assert "net_" in cnn.__dict__  # pickling must not strip the live network
    loaded = pickle.loads(pickle.dumps(pipe))
    np.testing.assert_array_equal(loaded.predict_proba(X), pipe.predict_proba(X))


def test_train_only_adds_dt_and_cnn(tmp_path: Path) -> None:
    from tests.test_xgboost_ensemble import _feature_dir
    feats, models = _feature_dir(tmp_path), tmp_path / "models"
    train(feats, models, seed=42, test_size=0.3, only=["random_forest"])
    before = {p.name: p.read_bytes() for p in models.iterdir()}
    train(feats, models, seed=42, test_size=0.3, only=["decision_tree", "cnn"])
    assert {p.name: p.read_bytes() for p in models.iterdir() if p.name in before} == before
    for name in ("decision_tree", "cnn"):
        meta = json.loads((models / f"{name}_metadata.json").read_text(encoding="utf-8"))
        assert meta["model"] == name and "torch" in meta["versions"]
        assert joblib.load(models / f"{name}.joblib").predict(pd.DataFrame(
            np.zeros((1, meta["n_features"])), columns=meta["features"])).shape == (1,)
