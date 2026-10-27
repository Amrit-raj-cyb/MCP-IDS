"""Compose a new dataset folder from several existing lab datasets.

Raw logs are immutable, so datasets are never edited in place. This script
*copies* the manifests and raw session logs of the source datasets into a new
folder, which then works with every existing tool (``verify``,
``features.extractor``, ``ml.train``, ``ml.evaluate``) unchanged.

    python -m scripts.compose_dataset --source data/phase9_081_targeted \\
        --source data/benign_unique_090 --output data/combined_p9_benign090

Safety checks: the output must be empty or absent; session IDs must be unique
across sources; only ``status == "ok"`` sessions are copied; the result must
pass ``verify``. ``composition.json`` records each source's path, SHA-256
(``features.extractor.dataset_hash``), session counts and labels.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from features.extractor import dataset_hash
from orchestrator.main import DataPaths, verify
from orchestrator.manifest import load_manifest


def compose(sources: list[Path], output: Path) -> dict:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"refusing to write into non-empty {output}")
    out = DataPaths(output)
    out.sessions.mkdir(parents=True, exist_ok=True)
    out.manifest.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    record = []
    with open(out.manifest, "w", encoding="utf-8") as manifest:
        for src in sources:
            src = src.resolve()
            paths = DataPaths(src)
            rows = [r for r in load_manifest(paths.manifest) if r["status"] == "ok"]
            for r in rows:
                sid = r["session_id"]
                if sid in seen:
                    raise SystemExit(f"duplicate session id {sid} (in {src})")
                seen.add(sid)
                shutil.copytree(paths.sessions / sid, out.sessions / sid)
                manifest.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
            record.append({
                "path": str(src), "dataset_sha256": dataset_hash(src), "n_sessions": len(rows),
                "labels": dict(Counter(r["label"] for r in rows)),
                "attack_families": dict(Counter(r["attack_family"] for r in rows if r["attack_family"])),
                "lab_versions": dict(Counter(r.get("lab_version") for r in rows)),
            })
    problems = verify(out)
    summary = {
        "composed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": record, "n_sessions": len(seen), "dataset_sha256": dataset_hash(output),
        "verify_problems": problems,
    }
    (output / "composition.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Compose a dataset by copying existing datasets")
    p.add_argument("--source", type=Path, action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    s = compose(a.source, a.output)
    print(json.dumps(s, indent=2))
    sys.exit(1 if s["verify_problems"] else 0)


if __name__ == "__main__":
    main()
