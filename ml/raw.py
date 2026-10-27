"""Raw-traffic view of a session: the wire messages themselves, as text, for the raw-byte CNN.

The feature models see 65 numbers computed from a session. The raw-byte CNN
(:mod:`ml.raw_cnn`) instead reads the session's JSON-RPC messages directly and
learns its own patterns. This module turns one logged session into that text:

    <server> > {"jsonrpc":"2.0","id":0,"method":"tools/list"}          (client -> server)
    <server> < {"jsonrpc":"2.0","id":0,"result":{"tools":[...]}}       (server -> client)
    ...one line per message, in time order

Preprocessing (the same for training, evaluation and the live detector):

1. :func:`features.session.session_from_events`: proxy lifecycle records are
   dropped, and ``neutralize()`` removes the ``[LAB-SIMULATION]`` marker and
   replaces the canary token by ``REFCODE`` (exactly as for the features).
2. ``REFCODE`` is removed together with the space before it (so no tell-tale
   double space is left behind). It only ever appears inside attack payloads,
   so a model reading raw text could learn this lab word instead of the attack.
3. Every run of digits becomes ``0``. This hides the canary call's arguments
   (``add_numbers(1337, 7331)``, which only an obeyed poisoning attack sends),
   JSON-RPC ids and other numbers that identify a lab run rather than a
   behaviour. Message *sizes* are left alone.

Nothing else is removed or added: no labels, task ids, scenario ids or
session ids appear in message bodies, server names are identical in benign
and attack sessions (twin servers), and the client's capabilities are the
same in every session (checked in tests/test_raw_cnn.py).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from features.session import Session, load_wire_session

RAW_COLUMN = "wire_text"           # the single input column of raw models
RAW_VIEW_VERSION = "1.0"
CANARY_PLACEHOLDER = "REFCODE"     # what neutralize() puts in place of the canary token
_DIGITS = re.compile(r"\d+")
_CANARY = re.compile(r"\s?" + CANARY_PLACEHOLDER)
_ARROW = {"client_to_server": ">", "server_to_client": "<"}


def session_text(s: Session) -> str:
    """The session's wire messages as masked text, one line per message."""
    lines = []
    for e in s.events:
        body = json.dumps(e.body, ensure_ascii=False, separators=(",", ":"))
        lines.append(f"{e.server_id} {_ARROW.get(e.direction, '?')} {body}")
    text = _CANARY.sub("", "\n".join(lines))
    return _DIGITS.sub("0", text)


def session_text_from_logs(session_id: str, sessions_dir: Path) -> str:
    return session_text(load_wire_session(session_id, sessions_dir))


def raw_frame(texts: list[str]) -> pd.DataFrame:
    """Model input for raw models: one column of session texts."""
    return pd.DataFrame({RAW_COLUMN: pd.Series(list(texts), dtype=object)})


def raw_texts(X) -> list[str]:
    """Accept the DataFrame from :func:`raw_frame`, a Series or any sequence of strings."""
    if isinstance(X, pd.DataFrame):
        X = X[RAW_COLUMN]
    return [str(t) for t in (X.tolist() if hasattr(X, "tolist") else list(X))]


def load_raw(feature_dir: Path):
    """Raw texts of every session in a feature dataset, aligned row by row with ``features.csv``.

    Returns a :class:`ml.dataset.FeatureData` whose ``X`` is :func:`raw_frame`
    (labels and metadata come from ``features.csv``; the session logs from the
    dataset recorded in ``dataset_summary.json``).
    """
    from ml.dataset import FeatureData, load_features, resolve_dataset_dir

    feat = load_features(feature_dir)
    summary = json.loads((Path(feature_dir) / "dataset_summary.json").read_text(encoding="utf-8"))
    sessions_dir = resolve_dataset_dir(summary["dataset_path"]) / "raw" / "sessions"
    texts = [session_text_from_logs(sid, sessions_dir) for sid in feat.meta["session_id"]]
    return FeatureData(raw_frame(texts), np.asarray(feat.y), feat.meta, [RAW_COLUMN],
                       {"raw_view_version": RAW_VIEW_VERSION, "metadata_columns": feat.schema["metadata_columns"]})
