"""Phase 10: turn a lab dataset (manifest + wire logs) into one feature row per session.

Simple explanation
------------------
For each session listed in the manifest with ``status == "ok"``:

1. read its wire logs (read-only) and neutralize them (features/session.py);
2. compute structural, behavioural and content features;
3. write one CSV row: **metadata columns** (ids and labels, for evaluation
   only) followed by **feature columns** (the only model inputs).

Outputs go to a *separate* directory, never into the source dataset:
``features.csv``, ``feature_schema.json``, ``dataset_summary.json``, ``README.md``.

Run:  python -m features.extractor --data-dir data/try6 --out data/try6_ml
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from features import behavioral, content, structural
from features.base import FeatureSpec
from features.session import Session, load_wire_session
from orchestrator.manifest import load_manifest

GROUPS = (structural, behavioral, content)
FEATURE_SPECS: list[FeatureSpec] = [f for g in GROUPS for f in g.FEATURES]
FEATURE_NAMES: list[str] = [f.name for f in FEATURE_SPECS]

# Columns copied from the manifest for evaluation/analysis. NEVER model inputs.
METADATA_COLUMNS = ["session_id", "scenario_id", "task_id", "label", "attack_family", "attack_variant",
                    "attack_succeeded", "seed", "twin_of"]

EXTRACTOR_VERSION = "1.0"


def dataset_hash(data_dir: Path) -> str:
    """SHA-256 over the manifest and every log file (sorted relative paths + bytes)."""
    h = hashlib.sha256()
    files = [data_dir / "manifests" / "sessions.jsonl", *sorted((data_dir / "raw" / "sessions").glob("*/*.jsonl"))]
    for f in files:
        h.update(f.relative_to(data_dir).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def extract_session_features(session_id: str, sessions_dir: Path) -> dict[str, float]:
    return features_from_session(load_wire_session(session_id, sessions_dir))


def features_from_session(s: Session) -> dict[str, float]:
    """All features of an already-loaded session (offline and live use this)."""
    row: dict[str, float] = {}
    for g in GROUPS:
        values = g.extract(s)
        declared = [f.name for f in g.FEATURES]
        if sorted(values) != sorted(declared):
            raise RuntimeError(f"{g.__name__}: returned {sorted(set(values) ^ set(declared))} not matching declaration")
        row.update(values)
    return row


def build(data_dir: Path, out_dir: Path) -> dict:
    data_dir, out_dir = data_dir.resolve(), out_dir.resolve()
    if out_dir == data_dir or data_dir in out_dir.parents:
        raise ValueError("refusing to write inside the source dataset; choose a separate --out directory")
    manifest = [r for r in load_manifest(data_dir / "manifests" / "sessions.jsonl") if r["status"] == "ok"]
    if not manifest:
        raise ValueError(f"no usable sessions in {data_dir}")
    ids = [r["session_id"] for r in manifest]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate session ids in manifest")

    sessions_dir = data_dir / "raw" / "sessions"
    rows = []
    for r in manifest:
        meta = {c: r.get(c) for c in METADATA_COLUMNS}
        rows.append({**meta, **extract_session_features(r["session_id"], sessions_dir)})

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "features.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=METADATA_COLUMNS + FEATURE_NAMES)
        w.writeheader()
        w.writerows(rows)

    schema = {
        "extractor_version": EXTRACTOR_VERSION,
        "metadata_columns": METADATA_COLUMNS,
        "metadata_note": "Metadata columns identify sessions and carry labels. They are never model inputs.",
        "neutralization": "common.simulation.neutralize(): removes '[LAB-SIMULATION]' and replaces the "
                          "canary token in every message body before any feature is computed; sizes are "
                          "recomputed from the neutralized JSON. Raw logs are not modified.",
        "features": [f.to_dict() for f in FEATURE_SPECS],
    }
    (out_dir / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")

    att = [r for r in manifest if r["label"] == "attack"]
    summary = {
        "dataset_path": str(data_dir),
        "dataset_sha256": dataset_hash(data_dir),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_sessions": len(manifest),
        "n_benign": sum(r["label"] == "benign" for r in manifest),
        "n_attack": len(att),
        "attack_families": dict(Counter(r["attack_family"] for r in att)),
        "attack_variants": dict(Counter(r["attack_variant"] for r in att)),
        "attack_succeeded": sum(r["attack_succeeded"] for r in att),
        "n_features": len(FEATURE_NAMES),
        "features_per_category": dict(Counter(f.category for f in FEATURE_SPECS)),
        "n_wire_events": None,  # filled below
        "extractor_version": EXTRACTOR_VERSION,
        "lab_versions": dict(Counter(r.get("lab_version") for r in manifest)),
        "python": platform.python_version(),
    }
    summary["n_wire_events"] = int(sum(row["n_messages"] for row in rows))
    (out_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(_readme(data_dir, summary), encoding="utf-8")
    return summary


def _readme(data_dir: Path, s: dict) -> str:
    return f"""# Feature dataset derived from `{data_dir.name}`

Generated by `python -m features.extractor` (extractor v{EXTRACTOR_VERSION}) on {s['generated_at']}.

* Source dataset: `{s['dataset_path']}` (read-only), SHA-256 `{s['dataset_sha256']}`
* Sessions: {s['n_sessions']} ({s['n_benign']} benign, {s['n_attack']} attack); attacks succeeded: {s['attack_succeeded']}
* Features: {s['n_features']} ({s['features_per_category']})

Files
* `features.csv`: one row per session. The first columns are **metadata**
  ({', '.join(METADATA_COLUMNS)}). They are used only to label and analyse
  results and are **never** model inputs. The remaining columns are features.
* `feature_schema.json`: every feature: category, type, description, source, preprocessing.
* `dataset_summary.json`: counts, hash, versions.

Lab artefacts (`[LAB-SIMULATION]` marker, canary token) were removed with
`neutralize()` before feature extraction. See docs/ml.md.
"""


def main() -> None:
    p = argparse.ArgumentParser(description="Extract per-session features from a lab dataset")
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    s = build(a.data_dir, a.out)
    print(json.dumps({k: s[k] for k in ("n_sessions", "n_benign", "n_attack", "attack_variants",
                                         "n_features", "features_per_category", "n_wire_events",
                                         "dataset_sha256")}, indent=2))
    print(f"wrote {a.out / 'features.csv'}", file=sys.stderr)


if __name__ == "__main__":
    main()
