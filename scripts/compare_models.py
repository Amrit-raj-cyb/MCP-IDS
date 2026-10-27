"""Verdict of every saved model on the same logged sessions, side by side.

    python -m scripts.compare_models --models models/expanded_20261009 --data-dir data/demo_live

Each session is read and neutralized once; every ``<model>.joblib`` in
``--models`` then scores it with its own input: the training feature code
(``features.extractor``) for feature models, the masked wire messages
(``ml.raw``) for the raw-traffic CNN. Read-only: nothing is written.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from features.session import load_wire_session
from ml.inference import Detector
from ml.models import ALL_BUILDERS, LABELS, is_probabilistic


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--models", type=Path, required=True, help="model directory (e.g. models/expanded_20261009)")
    p.add_argument("--data-dir", type=Path, required=True, help="dataset directory with raw/sessions")
    p.add_argument("--last", type=int, default=10, help="only the most recent N sessions (default 10)")
    a = p.parse_args()

    sessions_dir = a.data_dir / "raw" / "sessions"
    sessions = sorted((d for d in sessions_dir.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)[-a.last:]
    if not sessions:
        raise SystemExit(f"no sessions in {sessions_dir}")
    names = [n for n in ALL_BUILDERS if (a.models / f"{n}.joblib").is_file()]
    detectors = {n: Detector(a.models / f"{n}.joblib") for n in names}

    width = max(len(LABELS[n]) for n in names)
    for s in sessions:
        session = load_wire_session(s.name, sessions_dir)
        print(f"\nsession {s.name}")
        for n in names:
            out, _ = detectors[n].classify_wire_session(session)
            kind = "P(attack)" if is_probabilistic(detectors[n].pipeline) else "margin   "
            print(f"  {LABELS[n]:<{width}}  {out['prediction'].upper():6s}  {kind} {out['score']:+.3f}")


if __name__ == "__main__":
    main()
