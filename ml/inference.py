"""Inference: classify one session with a saved model, using the *same* preprocessing as training.

    python -m ml.inference --model models/try6/random_forest.joblib --data-dir data/try6 --session SESSION_ID

The saved pipeline contains its own preprocessing. Feature models get their
features from ``features.extractor`` (the code used to build the training
data), in the order stored in the model's metadata file. Raw-traffic models
(metadata ``"input": "raw_session_text"``) get the session's masked wire
messages from ``ml.raw.session_text`` instead.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import pandas as pd

from features.extractor import features_from_session
from features.session import Session, load_wire_session
from ml.dataset import assert_no_leakage
from ml.models import score
from ml.raw import raw_frame, session_text


class Detector:
    def __init__(self, model_path: Path) -> None:
        model_path = Path(model_path)
        self.pipeline = joblib.load(model_path)
        self.meta = json.loads(model_path.with_name(model_path.stem + "_metadata.json").read_text(encoding="utf-8"))
        self.features: list[str] = self.meta["features"]
        self.raw = self.meta.get("input") == "raw_session_text"
        if not self.raw:
            assert_no_leakage(self.features, self.features)

    def _verdict(self, X) -> dict:
        pred = int(self.pipeline.predict(X)[0])
        return {"prediction": "attack" if pred else "benign", "alert": bool(pred),
                "score": round(float(score(self.pipeline, X)[0]), 4), "model": self.meta["model"]}

    def classify_features(self, row: dict[str, float]) -> dict:
        if self.raw:
            raise TypeError(f"{self.meta['model']} reads raw traffic; use classify_text or classify_wire_session")
        return self._verdict(pd.DataFrame([[row[f] for f in self.features]], columns=self.features, dtype=float))

    def classify_text(self, text: str) -> dict:
        if not self.raw:
            raise TypeError(f"{self.meta['model']} reads features; use classify_features or classify_wire_session")
        return self._verdict(raw_frame([text]))

    def classify_wire_session(self, s: Session) -> tuple[dict, dict[str, float]]:
        """Verdict for an already-loaded (neutralized) session, plus its features (for alert evidence)."""
        row = features_from_session(s)
        return (self.classify_text(session_text(s)) if self.raw else self.classify_features(row)), row

    def classify_session(self, session_id: str, sessions_dir: Path) -> dict:
        t0 = time.perf_counter()
        s = load_wire_session(session_id, sessions_dir)
        model_input = session_text(s) if self.raw else features_from_session(s)
        t1 = time.perf_counter()
        out = self.classify_text(model_input) if self.raw else self.classify_features(model_input)
        t2 = time.perf_counter()
        return {"session_id": session_id, **out,
                "feature_ms": round((t1 - t0) * 1000, 2), "model_ms": round((t2 - t1) * 1000, 2)}


def main() -> None:
    p = argparse.ArgumentParser(description="Classify one logged session")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--session", required=True)
    a = p.parse_args()
    print(json.dumps(Detector(a.model).classify_session(a.session, a.data_dir / "raw" / "sessions"), indent=2))


if __name__ == "__main__":
    main()
