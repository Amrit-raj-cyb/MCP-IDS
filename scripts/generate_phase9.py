"""Generate a balanced, reproducible lab dataset without touching try6.

Default output is ``data/phase9_verified``. The command refuses to reuse a non-empty
output directory so raw JSONL and manifests are never silently overwritten.
Run inside the isolated Docker Compose lab for the fixed ``testweb`` origin.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator.main import DataPaths, run_session, verify
from orchestrator.manifest import load_manifest
from orchestrator.scenarios import Scenario, get_scenario, select
from proxy.models import SCHEMA_VERSION
from proxy.reader import load_session

from common.registry import PROJECT_ROOT

DATASET_TAG = "phase9"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "phase9_verified"
REQUIRED_EVENT_FIELDS = {
    "schema_version", "session_id", "server_id", "seq", "ts_ns", "timestamp",
    "direction", "kind", "method", "message_size", "is_error", "body", "mono_ns",
}
ALLOWED_FAMILIES = {"poisoned_tool", "shadowing", "sampling_injection"}
PROBE_TASKS = {
    "poisoned_tool": {"calc_add", "calc_temperature", "multi_order_share", "multi_region_share"},
    "shadowing": {"fs_shadowing_probe"},
    "sampling_injection": {"fs_sampling_probe"},
}


def paired_scenarios(sessions_per_family: int = 30) -> list[Scenario]:
    """Build matched benign/attack trials, including all-server twins.

    Repeated trials cycle deterministically through each family's registered
    scenarios. Each attack has a benign twin with the same task/server count.
    """
    candidates: dict[str, list[Scenario]] = {}
    for attack in select("attack"):
        if attack.twin_of and attack.task_id in PROBE_TASKS.get(attack.attack_family or "", set()):
            candidates.setdefault(attack.attack_family or "", []).append(attack)
    selected: list[Scenario] = []
    for family in sorted(ALLOWED_FAMILIES):
        choices = sorted(candidates.get(family, []), key=lambda a: a.scenario_id)
        if not choices:
            raise ValueError(f"no registered scenarios for attack family {family}")
        for i in range(sessions_per_family):
            attack = choices[i % len(choices)]
            selected.extend((get_scenario(attack.twin_of), attack))
    return selected


def sha256_files(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "metadata.json"):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def inspect_dataset(paths: DataPaths, expected_sessions: int | None = None) -> dict[str, Any]:
    """Validate records and logs, returning reproducible summary statistics."""
    problems = verify(paths)
    entries = load_manifest(paths.manifest)
    if expected_sessions is not None and len(entries) != expected_sessions:
        problems.append(f"expected {expected_sessions} manifest records, found {len(entries)}")
    ids = [e.get("session_id") for e in entries]
    if len(set(ids)) != len(ids):
        problems.append("duplicate session IDs in manifest")
    if any(e.get("status") != "ok" for e in entries):
        problems.append("one or more sessions did not complete")
    if any(e.get("label") not in {"benign", "attack"} for e in entries):
        problems.append("unknown session label")
    for e in entries:
        if e.get("label") == "benign" and (e.get("attack_family") is not None or e.get("attack_attempted")):
            problems.append(f"{e.get('session_id')}: inconsistent benign label")
        if e.get("label") == "attack" and (e.get("attack_family") not in ALLOWED_FAMILIES or not e.get("attack_attempted")):
            problems.append(f"{e.get('session_id')}: inconsistent attack label/family")

    event_total = wire_total = 0
    direction_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    methods_by_family: dict[str, Counter[str]] = {}
    for entry in entries:
        sid = entry["session_id"]
        try:
            events = load_session(sid, paths.sessions)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"{sid}: unreadable JSONL: {exc}")
            continue
        for ev in events:
            missing = REQUIRED_EVENT_FIELDS - set(ev)
            if missing:
                problems.append(f"{sid}: event missing fields {sorted(missing)}")
            if ev.get("session_id") != sid:
                problems.append(f"{sid}: event has mismatched session ID")
            if ev.get("kind") not in {"lifecycle", "request", "response", "notification", "error", "batch", "invalid"}:
                problems.append(f"{sid}: invalid event kind {ev.get('kind')!r}")
            direction_counts[ev.get("direction", "?")] += 1
            if ev.get("method"):
                method_counts[ev["method"]] += 1
                if entry.get("label") == "attack":
                    methods_by_family.setdefault(entry["attack_family"], Counter())[ev["method"]] += 1
        event_total += len(events)
        wire_total += sum(e.get("kind") != "lifecycle" for e in events)

    folders = {p.name for p in paths.sessions.iterdir() if p.is_dir()} if paths.sessions.is_dir() else set()
    if folders != set(ids):
        problems.append(f"session folders and manifest IDs differ (folders={len(folders)}, manifest={len(ids)})")
    if problems:
        raise ValueError("dataset verification failed:\n- " + "\n- ".join(problems))

    labels = Counter(e["label"] for e in entries)
    attacks = [e for e in entries if e["label"] == "attack"]
    for entry in attacks:
        if entry["attack_family"] == "sampling_injection":
            events = load_session(entry["session_id"], paths.sessions)
            if not any(e.get("method") == "sampling/createMessage" and e.get("kind") == "request"
                       for e in events):
                raise ValueError(f"{entry['session_id']}: sampling attack emitted no sampling/createMessage request")
    server_counts = {label: dict(sorted(Counter(str(len(e["servers"])) for e in entries
                                                if e["label"] == label).items()))
                     for label in ("benign", "attack")}
    if server_counts["benign"] != server_counts["attack"]:
        raise ValueError(f"class imbalance by mounted server count: {server_counts}")
    benign_pairs = Counter((e["scenario_id"], e.get("seed")) for e in entries if e["label"] == "benign")
    for e in attacks:
        key = (e.get("twin_of"), e.get("seed"))
        if benign_pairs[key] < 1:
            raise ValueError(f"{e['session_id']}: no matched benign twin with same seed")
        benign_pairs[key] -= 1
    return {
        "dataset_tag": DATASET_TAG,
        "n_sessions": len(entries),
        "n_benign": labels["benign"],
        "n_attack": labels["attack"],
        "attack_family_counts": dict(sorted(Counter(e["attack_family"] for e in attacks).items())),
        "attack_variant_counts": dict(sorted(Counter(e["attack_variant"] or "unspecified" for e in attacks).items())),
        "attack_succeeded": sum(bool(e["attack_succeeded"]) for e in attacks),
        "attack_not_succeeded": sum(not bool(e["attack_succeeded"]) for e in attacks),
        "server_count_distribution_by_label": server_counts,
        "server_count_distribution_by_attack_family": {
            family: dict(sorted(Counter(str(len(e["servers"])) for e in attacks
                                        if e["attack_family"] == family).items()))
            for family in sorted(ALLOWED_FAMILIES)
        },
        "event_count": event_total,
        "wire_event_count": wire_total,
        "direction_counts": dict(sorted(direction_counts.items())),
        "method_counts": dict(sorted(method_counts.items())),
        "attack_method_counts_by_family": {family: dict(sorted(counts.items()))
                                           for family, counts in sorted(methods_by_family.items())},
        "manifest_records": len(entries),
        "unique_session_ids": len(set(ids)),
        "all_sessions_ok": all(e["status"] == "ok" for e in entries),
        "schema_version": SCHEMA_VERSION,
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _memory_limit_bytes() -> int | None:
    """Record the effective cgroup v2 memory limit when running in Docker."""
    try:
        value = Path("/sys/fs/cgroup/memory.max").read_text(encoding="ascii").strip()
        return int(value) if value != "max" else None
    except (OSError, ValueError):
        return None


async def run_paired(scenarios: list[Scenario], paths: DataPaths, seed: int,
                     parallel: int, susceptibility: float) -> list[Any]:
    """Run matched pairs while limiting total concurrent sessions to parallel."""
    pairs = [(scenarios[i], scenarios[i + 1], seed + i // 2)
             for i in range(0, len(scenarios), 2)]
    semaphore = asyncio.Semaphore(max(1, parallel))
    completed = 0

    async def run_one(scenario: Scenario, pair_seed: int):
        async with semaphore:
            return await run_session(scenario, pair_seed, paths, provider="mock",
                                     dataset_tag=DATASET_TAG, susceptibility=susceptibility)

    async def run_pair(benign: Scenario, attack: Scenario, pair_seed: int) -> list[Any]:
        nonlocal completed
        left, right = await asyncio.gather(run_one(benign, pair_seed), run_one(attack, pair_seed))
        completed += 1
        print(f"[{completed:>3}/{len(pairs)}] pair {benign.scenario_id} <-> {attack.scenario_id} "
              f"seed={pair_seed} statuses={left.status}/{right.status}", flush=True)
        return [left, right]

    nested = await asyncio.gather(*(run_pair(b, a, s) for b, a, s in pairs))
    return [entry for pair in nested for entry in pair]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=9000)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--sessions-per-family", type=int, default=30)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = args.output.resolve()
    paths = DataPaths(root)

    if args.verify_only:
        summary = inspect_dataset(paths)
        print(json.dumps(summary, indent=2))
        return
    if args.sessions_per_family < 1 or args.parallel < 1:
        raise SystemExit("--sessions-per-family and --parallel must be positive")
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty dataset directory: {root}")
    root.mkdir(parents=True, exist_ok=True)

    paired = paired_scenarios(args.sessions_per_family)
    config = {
        "dataset_tag": DATASET_TAG,
        "seed": args.seed,
        "sessions_per_family": args.sessions_per_family,
        "repeats_per_scenario": "round-robin scenario selection; matched seeds per benign/attack pair",
        "parallel": args.parallel,
        "docker_memory_limit_bytes": _memory_limit_bytes(),
        "lab_mem_limit_env": os.getenv("LAB_MEM_LIMIT", "compose default 2g"),
        "llm": "mock",
        "mock_susceptibility": 0.35,
        "scenario_count": len(paired),
        "scenario_ids": [s.scenario_id for s in paired],
        "pairing": "matched benign/attack twins for each family trial; includes all_servers; balanced by server count",
        "source_datasets_modified": [],
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_json(root / "generation_config.json", config)
    entries = asyncio.run(run_paired(paired, paths, args.seed, args.parallel, 0.35))
    if len(entries) != len(paired) or any(e.status != "ok" for e in entries):
        raise SystemExit("Not all expected sessions completed; inspect manifest and rerun into a fresh output directory.")
    summary = inspect_dataset(paths, expected_sessions=len(paired))
    expected_families = {family: args.sessions_per_family for family in sorted(ALLOWED_FAMILIES)}
    if summary["attack_family_counts"] != expected_families:
        raise SystemExit(f"attack-family counts differ from requested configuration: "
                         f"expected {expected_families}, found {summary['attack_family_counts']}")
    summary.update({
        "generation_timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": args.seed,
        "parallel": args.parallel,
        "project_version": "0.1.0",
        "lab_versions": sorted({e.lab_version for e in entries}),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "dataset_sha256": sha256_files(root),
    })
    write_json(root / "metadata.json", summary)
    (root / "README.md").write_text(
        "# Phase 9 dataset\n\n"
        "Generated by `python -m scripts.generate_phase9` inside the isolated lab. "
        "Raw JSONL and manifest are the collected source records; treat them as immutable. "
        "This dataset uses only existing inert simulations and benign servers.\n\n"
        "Regenerate into a new empty directory with the seed and command recorded in "
        "`generation_config.json`. Verification: `python -m scripts.generate_phase9 "
        f"`--output /lab/data/{root.name} --verify-only`.\n", encoding="utf-8")
    print("Dataset: phase9")
    print(f"Total sessions: {summary['n_sessions']}")
    print(f"Benign: {summary['n_benign']} | Attack: {summary['n_attack']}")
    print(f"Attack success: {summary['attack_succeeded']} | not succeeded: {summary['attack_not_succeeded']}")
    print(f"MCP events: {summary['event_count']} ({summary['wire_event_count']} non-lifecycle)")
    print(f"Families: {summary['attack_family_counts']}")
    print(f"Variants: {summary['attack_variant_counts']}")
    print(f"SHA-256: {summary['dataset_sha256']}")
    print(f"Output: {root}")


if __name__ == "__main__":
    main()
