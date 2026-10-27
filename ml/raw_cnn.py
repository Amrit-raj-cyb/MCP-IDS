"""A byte-level convolutional network over a session's raw wire messages.

Unlike the feature models, this model gets **no hand-made features**. Its
input is the session text from :func:`ml.raw.session_text` (every JSON-RPC
message, masked as described there), read as a sequence of bytes:

    bytes (up to max_len)  -> Embedding(256 byte values -> emb_dim numbers each)
      -> Conv1d(kernel k1, every position) -> ReLU   learns short byte patterns ("n-grams")
      -> MaxPool1d(pool)                             keeps the strongest match in each block of `pool`
      -> Conv1d(kernel k2) -> ReLU                   combines them into longer patterns
      -> global max pooling over the whole session: "did this pattern occur anywhere?"
      -> Dropout -> Dense(hidden) -> ReLU -> Dropout -> Dense(1) -> sigmoid = P(attack)

The design follows byte-level malware detectors such as MalConv (Raff et al.,
2018), and global max pooling makes the verdict independent of *where* in the
session a pattern appears.

Why the first convolution reads every position (``arch="pooled"``, the default
since 2026-10-10): the first version used MalConv's *strided* first convolution
(stride 4, ``arch="strided"``). A strided convolution only looks at every 4th
byte offset, so the same sentence shifted by one byte produces different
activations. That model memorised byte alignments: shifting a training attack by
1 byte made 0 % of them detected, by 2 bytes 85 %, and on unseen tasks (where
the same payload sits at another offset) it caught only 30 % of the attacks.
Local max pooling after a stride-1 convolution keeps the cost down but is still
slightly alignment-dependent (a block of ``pool`` bytes has ``pool`` possible
offsets), so training also shifts every session by a random 0 .. pool-1 padding
positions each epoch (``shift_augment``): the network sees every alignment of every
pattern. With both, a payload is recognised wherever it sits (tests/test_raw_cnn.py
checks this). ``arch="strided"`` is kept so models saved before the fix still load.

Padding is masked before the global pooling, so a session's score does not
depend on which other sessions share its batch (the live detector scores
sessions one at a time and gets exactly the same numbers).

Training: Adam, class-balanced binary cross-entropy (weights computed from the
training rows only), fixed number of epochs, deterministic for a given
``random_state`` and number of torch threads (``n_threads``). Hyperparameters are chosen by :mod:`ml.tuning` on training
data only. Pickles store the weights as NumPy arrays (portable between the
Linux lab container and the Windows host). PyTorch is imported lazily.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.utils.validation import check_is_fitted

from ml.cnn import _threads
from ml.raw import raw_texts

PAD = 0  # byte b is token b + 1


def encode(texts: list[str], max_len: int) -> list[np.ndarray]:
    """UTF-8 bytes of each text (first ``max_len``), shifted by one so 0 can mean padding."""
    return [np.frombuffer(t.encode("utf-8")[:max_len], dtype=np.uint8).astype(np.int64) + 1 for t in texts]


def _out_len(n, kernel: int, stride: int):
    return (n - kernel) // stride + 1


ARCHS = ("pooled", "strided")


def valid_positions(lengths, arch: str, kernel_size: int, stride: int, kernel_size2: int, stride2: int, pool: int):
    """Output positions computed from real bytes only (the rest saw padding)."""
    if arch == "strided":
        return _out_len(_out_len(lengths, kernel_size, stride), kernel_size2, stride2)
    return _out_len(_out_len(lengths, kernel_size, 1), pool, pool) - kernel_size2 + 1


def build_network(emb_dim: int, channels: int, kernel_size: int, stride: int, kernel_size2: int, stride2: int,
                  hidden: int, dropout: float, arch: str = "pooled", pool: int = 4):
    import torch
    from torch import nn

    if arch not in ARCHS:
        raise ValueError(f"arch must be one of {ARCHS}")

    class RawNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embed = nn.Embedding(257, emb_dim, padding_idx=PAD)
            if arch == "strided":
                self.conv1 = nn.Conv1d(emb_dim, channels, kernel_size, stride=stride)
                self.conv2 = nn.Conv1d(channels, channels, kernel_size2, stride=stride2)
            else:
                self.conv1 = nn.Conv1d(emb_dim, channels, kernel_size)
                self.pool = nn.MaxPool1d(pool)
                self.conv2 = nn.Conv1d(channels, channels, kernel_size2)
            self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(channels, hidden), nn.ReLU(),
                                      nn.Dropout(dropout), nn.Linear(hidden, 1))

        def forward(self, tokens, lengths):
            x = self.embed(tokens).transpose(1, 2)               # (batch, emb_dim, length)
            x = torch.relu(self.conv1(x))
            if arch == "pooled":
                x = self.pool(x)
            x = torch.relu(self.conv2(x))                        # (batch, channels, positions)
            valid = valid_positions(lengths, arch, kernel_size, stride, kernel_size2, stride2, pool)
            positions = torch.arange(x.shape[2]).unsqueeze(0)
            x = x.masked_fill((positions >= valid.unsqueeze(1)).unsqueeze(1), float("-inf"))
            return self.head(x.max(dim=2).values).squeeze(1)    # global max pooling -> logit

    return RawNet()


class RawByteCNN(ClassifierMixin, BaseEstimator):
    """Binary byte-level CNN over raw session text, with a scikit-learn interface."""

    def __init__(self, max_len: int = 32768, emb_dim: int = 8, channels: int = 64, kernel_size: int = 8,
                 stride: int = 4, kernel_size2: int = 4, stride2: int = 2, hidden: int = 32, dropout: float = 0.2,
                 epochs: int = 15, batch_size: int = 32, learning_rate: float = 1e-3, weight_decay: float = 1e-4,
                 n_threads: int = 1, random_state: int | None = None, arch: str = "pooled", pool: int = 4,
                 shift_augment: bool = True) -> None:
        """``stride``/``stride2`` apply to ``arch="strided"`` only; ``pool`` and ``shift_augment`` (random
        0 .. pool-1 position shifts while training) to ``arch="pooled"`` only."""
        self.max_len = max_len
        self.emb_dim = emb_dim
        self.channels = channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.kernel_size2 = kernel_size2
        self.stride2 = stride2
        self.hidden = hidden
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.n_threads = n_threads
        self.random_state = random_state
        self.arch = arch
        self.pool = pool
        self.shift_augment = shift_augment

    @property
    def _min_len(self) -> int:
        """Shortest input that still leaves one position after both convolutions."""
        if self.arch == "strided":
            return self.kernel_size + self.stride * (self.kernel_size2 - 1)
        return self.kernel_size - 1 + self.pool * self.kernel_size2

    def _network(self):
        return build_network(self.emb_dim, self.channels, self.kernel_size, self.stride, self.kernel_size2,
                             self.stride2, self.hidden, self.dropout, self.arch, self.pool)

    def _batch(self, torch, seqs: list[np.ndarray], shifts: np.ndarray | None = None):
        """Pad a batch. ``shifts`` (training only) moves each sequence right by that many padding positions."""
        shifts = np.zeros(len(seqs), dtype=int) if shifts is None else shifts
        lengths = [max(len(s) + int(k), self._min_len) for s, k in zip(seqs, shifts, strict=True)]
        tokens = np.full((len(seqs), max(lengths)), PAD, dtype=np.int64)
        for i, (s, k) in enumerate(zip(seqs, shifts, strict=True)):
            tokens[i, k:k + len(s)] = s
        return torch.from_numpy(tokens), torch.tensor(lengths)

    def fit(self, X, y):
        seqs = encode(raw_texts(X), self.max_len)
        y = np.asarray(y)
        self.classes_ = np.unique(y)
        if len(self.classes_) != 2:
            raise ValueError(f"RawByteCNN is binary; got classes {self.classes_.tolist()}")
        target = (y == self.classes_[1]).astype(np.float32)
        weight = compute_sample_weight("balanced", y).astype(np.float32)
        seed = 0 if self.random_state is None else int(self.random_state)
        rng = np.random.default_rng(seed)

        with _threads(self.n_threads) as torch:
            torch.manual_seed(seed)
            net = self._network()
            opt = torch.optim.Adam(net.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
            yt, wt = torch.from_numpy(target), torch.from_numpy(weight)
            self.loss_curve_ = []
            net.train()
            for _ in range(self.epochs):
                order = rng.permutation(len(seqs))
                total = 0.0
                for start in range(0, len(seqs), self.batch_size):
                    idx = order[start:start + self.batch_size]
                    shifts = (rng.integers(0, self.pool, size=len(idx))
                              if self.shift_augment and self.arch == "pooled" else None)
                    tokens, lengths = self._batch(torch, [seqs[i] for i in idx], shifts)
                    ti = torch.from_numpy(idx)
                    opt.zero_grad()
                    losses = torch.nn.functional.binary_cross_entropy_with_logits(
                        net(tokens, lengths), yt[ti], reduction="none")
                    loss = (losses * wt[ti]).sum() / wt[ti].sum()
                    loss.backward()
                    opt.step()
                    total += loss.item() * len(idx)
                self.loss_curve_.append(total / len(seqs))
            net.eval()
        self.net_ = net
        return self

    def predict_proba(self, X) -> np.ndarray:
        check_is_fitted(self, "net_")
        seqs = encode(raw_texts(X), self.max_len)
        p = np.zeros(len(seqs))
        order = np.argsort([len(s) for s in seqs], kind="stable")  # similar lengths share a batch
        with _threads(self.n_threads) as torch, torch.no_grad():
            for start in range(0, len(seqs), 64):
                idx = order[start:start + 64]
                tokens, lengths = self._batch(torch, [seqs[i] for i in idx])
                p[idx] = torch.sigmoid(self.net_(tokens, lengths)).numpy()
        return np.column_stack([1.0 - p, p])

    def predict(self, X) -> np.ndarray:
        return self.classes_[(self.predict_proba(X)[:, 1] > 0.5).astype(int)]

    def __getstate__(self):
        state = dict(super().__getstate__())
        net = state.pop("net_", None)
        if net is not None:
            state["_weights"] = {k: v.detach().cpu().numpy().copy() for k, v in net.state_dict().items()}
        return state

    def __setstate__(self, state):
        weights = state.pop("_weights", None)
        state.setdefault("arch", "strided")  # pickled before 2026-10-10: the strided first version
        state.setdefault("pool", 4)
        state.setdefault("shift_augment", False)
        super().__setstate__(state)
        if weights is not None:
            import torch
            net = self._network()
            net.load_state_dict({k: torch.from_numpy(np.array(v)) for k, v in weights.items()})
            net.eval()
            self.net_ = net
