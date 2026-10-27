"""A small 1-D convolutional neural network (CNN) for the session feature vector.

The CNN reads one session's standardised features as a one-channel sequence, in
the feature schema's order (structural, then behavioural, then content), so each
convolution kernel looks at a few neighbouring features of the same group:

    features (n) -> Conv1d(1->16, k=3) -> ReLU -> Conv1d(16->32, k=3) -> ReLU
                 -> MaxPool1d(2) -> Flatten -> Dropout -> Dense(32) -> ReLU
                 -> Dropout -> Dense(1) -> sigmoid = P(attack)

It is trained from scratch (no pre-trained weights exist for MCP session
features) with Adam on a class-balanced binary cross-entropy: each sample is
weighted like ``class_weight="balanced"``, using the training rows only. The
number of epochs and the architecture are fixed in advance; nothing is tuned on
test data and there is no early stopping on a test set.

:class:`CNN1DClassifier` is a scikit-learn estimator, so it runs inside the same
``Pipeline`` (imputation + scaling fitted on training data only), the same
cross-validation and holdout code, and the same live detector as the other
models. Training is deterministic for a given ``random_state`` (fixed seeds,
one CPU thread). Pickling stores the weights as NumPy arrays, not torch
objects, so a model saved in the Linux lab container loads on the Windows host.

PyTorch is imported only when a CNN is fitted, used or loaded, so importing
``ml.models`` (e.g. by the live detector with a tree model) stays light.
"""

from __future__ import annotations

from contextlib import contextmanager

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.utils.validation import check_is_fitted


@contextmanager
def _threads(n: int = 1):
    """Run torch on ``n`` CPU threads, then restore the previous setting. One thread (the default)
    gives reproducible results and no oversubscription when many fits run in parallel processes."""
    import torch
    before = torch.get_num_threads()
    torch.set_num_threads(max(1, int(n)))
    try:
        yield torch
    finally:
        torch.set_num_threads(before)


def _single_thread():
    return _threads(1)


def build_network(n_features: int, channels: tuple[int, int], kernel_size: int, hidden: int, dropout: float):
    """The network above as an ``nn.Sequential`` mapping (batch, n_features) to (batch,) logits."""
    from torch import nn
    c1, c2 = channels
    pad = kernel_size // 2  # odd kernel + this padding keeps the sequence length
    pooled = (n_features + 1) // 2  # ceil_mode: also works with a single feature
    return nn.Sequential(
        nn.Unflatten(1, (1, n_features)),
        nn.Conv1d(1, c1, kernel_size, padding=pad), nn.ReLU(),
        nn.Conv1d(c1, c2, kernel_size, padding=pad), nn.ReLU(),
        nn.MaxPool1d(2, ceil_mode=True),
        nn.Flatten(), nn.Dropout(dropout),
        nn.Linear(c2 * pooled, hidden), nn.ReLU(), nn.Dropout(dropout),
        nn.Linear(hidden, 1), nn.Flatten(0))


class CNN1DClassifier(ClassifierMixin, BaseEstimator):
    """Binary 1-D CNN classifier with a scikit-learn interface (``predict_proba`` = P(attack))."""

    def __init__(self, channels: tuple[int, int] = (16, 32), kernel_size: int = 3, hidden: int = 32,
                 dropout: float = 0.2, epochs: int = 50, batch_size: int = 64, learning_rate: float = 1e-3,
                 weight_decay: float = 1e-4, random_state: int | None = None) -> None:
        self.channels = channels
        self.kernel_size = kernel_size
        self.hidden = hidden
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.random_state = random_state

    def _network(self):
        return build_network(self.n_features_in_, tuple(self.channels), self.kernel_size, self.hidden,
                             self.dropout)

    def fit(self, X, y):
        if self.kernel_size % 2 != 1:
            raise ValueError("kernel_size must be odd")
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        self.classes_ = np.unique(y)
        if len(self.classes_) != 2:
            raise ValueError(f"CNN1DClassifier is binary; got classes {self.classes_.tolist()}")
        self.n_features_in_ = X.shape[1]
        target = (y == self.classes_[1]).astype(np.float32)
        weight = compute_sample_weight("balanced", y).astype(np.float32)
        seed = 0 if self.random_state is None else int(self.random_state)
        rng = np.random.default_rng(seed)

        with _single_thread() as torch:
            torch.manual_seed(seed)  # weight initialisation and dropout masks
            net = self._network()
            opt = torch.optim.Adam(net.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
            Xt, yt, wt = torch.from_numpy(X), torch.from_numpy(target), torch.from_numpy(weight)
            self.loss_curve_ = []
            net.train()
            for _ in range(self.epochs):
                order = torch.from_numpy(rng.permutation(len(X)))
                total = 0.0
                for start in range(0, len(X), self.batch_size):
                    idx = order[start:start + self.batch_size]
                    opt.zero_grad()
                    losses = torch.nn.functional.binary_cross_entropy_with_logits(
                        net(Xt[idx]), yt[idx], reduction="none")
                    loss = (losses * wt[idx]).sum() / wt[idx].sum()
                    loss.backward()
                    opt.step()
                    total += loss.item() * len(idx)
                self.loss_curve_.append(total / len(X))
            net.eval()
        self.net_ = net
        return self

    def predict_proba(self, X) -> np.ndarray:
        check_is_fitted(self, "net_")
        X = np.asarray(X, dtype=np.float32)
        with _single_thread() as torch, torch.no_grad():
            p = torch.sigmoid(self.net_(torch.from_numpy(X))).numpy().astype(np.float64)
        return np.column_stack([1.0 - p, p])

    def predict(self, X) -> np.ndarray:
        return self.classes_[(self.predict_proba(X)[:, 1] > 0.5).astype(int)]

    # Portable pickles: weights as NumPy arrays, the network is rebuilt on load.
    def __getstate__(self):
        state = dict(super().__getstate__())
        net = state.pop("net_", None)
        if net is not None:
            state["_weights"] = {k: v.detach().cpu().numpy().copy() for k, v in net.state_dict().items()}
        return state

    def __setstate__(self, state):
        weights = state.pop("_weights", None)
        super().__setstate__(state)
        if weights is not None:
            import torch
            net = self._network()
            net.load_state_dict({k: torch.from_numpy(np.array(v)) for k, v in weights.items()})
            net.eval()
            self.net_ = net
