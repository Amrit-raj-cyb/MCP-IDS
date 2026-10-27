"""Generate the largest *unique* benign corpus the lab can currently produce.

Why this exists
---------------
Repeating benign scenarios with more seeds mostly re-creates sessions the
models have already seen: the mock agent has only a limited number of distinct
behaviours per task. This script enumerates them and runs each distinct
behaviour exactly once in each server mix:

* for every benign task, materialise the mock agent's plan for seeds
  ``seed_base .. seed_base + search - 1`` and keep the first seed of every
  distinct plan (no servers needed for this step);
* run that seed in both benign scenarios of the task: ``benign:<task>`` (only
  the servers it needs) and ``benign:<task>:all_servers`` (all benign servers
  mounted).

Benign only: the script refuses any scenario whose label is not ``benign``.
It is meant as a held-out false-positive / drift test set for models trained
on other data.

Run inside the Docker lab (fixed ``testweb`` origin, 2 GB memory limit)::

    docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_unique_081
    docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_unique_081 --verify-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from agent.llm import MockLLM, ToolInfo, ToolResult
from agent.tasks import TASKS, Task, render_task
from common.descriptions import N_VARIANTS
from common.registry import PROJECT_ROOT
from orchestrator.main import DataPaths, run_session, verify
from orchestrator.manifest import LAB_VERSION, load_manifest
from orchestrator.scenarios import SCENARIOS, Scenario
from scripts.generate_phase9 import sha256_files, write_json

DATASET_TAG = "benign_unique"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "benign_unique_090"


async def _plan(task: Task, seed: int) -> tuple:
    """The mock agent's call sequence for ``seed`` (all calls assumed to succeed)."""
    m = MockLLM(seed, susceptibility=0.0)
    await m.start(task, [ToolInfo(s.tool, "", {}) for s in task.plan])
    calls, results = [], []
    while not (d := await m.step(results)).done:
        calls += [(c.name, json.dumps(c.arguments, sort_keys=True)) for c in d.tool_calls]
        results = [ToolResult(c.call_id, "ok", False) for c in d.tool_calls]
    return tuple(calls)


async def distinct_plan_seeds(seed_base: int, search: int, tasks: list[str] | None = None) -> dict[str, list[int]]:
    """task_id -> first seed (in the search window) of each distinct mock plan (``tasks``: only these)."""
    out: dict[str, list[int]] = {}
    for task_id, task in TASKS.items():
        if tasks is not None and task_id not in tasks:
            continue
        rendered = render_task(task, {"web": "http://testweb:8080"})  # URL doesn't affect plan choice
        first: dict[tuple, int] = {}
        for seed in range(seed_base, seed_base + search):
            first.setdefault(await _plan(rendered, seed), seed)
        out[task_id] = sorted(first.values())
    return out


def benign_jobs(seeds: dict[str, list[int]], server_mix: str = "both") -> list[tuple[Scenario, int]]:
    """(scenario, seed) pairs. ``server_mix``: "both", "own" (task's servers) or "all"."""
    jobs = []
    for scenario in SCENARIOS.values():
        if scenario.label != "benign":
            continue
        is_all = scenario.scenario_id.endswith(":all_servers")
        if (server_mix == "own" and is_all) or (server_mix == "all" and not is_all):
            continue
        if scenario.task_id not in seeds:  # task not selected (--tasks)
            continue
        for seed in seeds[scenario.task_id]:
            jobs.append((scenario, seed))
    for scenario, _ in jobs:  # defence in depth: never generate attack traffic here
        if scenario.label != "benign" or scenario.attack_family is not None:
            raise SystemExit(f"refusing non-benign scenario {scenario.scenario_id}")
    return jobs


def description_variant_for(mode: str, index: int) -> int:
    """'0'..'3' -> fixed wording; 'cycle' -> 1, 2, 3, 1, ... (never the original)."""
    if mode == "cycle":
        return 1 + index % N_VARIANTS
    return int(mode)


async def run_jobs(jobs: list[tuple[Scenario, int]], paths: DataPaths, parallel: int,
                   description_mode: str = "0") -> list:
    sem = asyncio.Semaphore(max(1, parallel))
    done = 0
    variants = {i: description_variant_for(description_mode, i) for i in range(len(jobs))}

    async def one(i: int, scenario: Scenario, seed: int):
        nonlocal done
        async with sem:
            entry = await run_session(scenario, seed, paths, provider="mock", dataset_tag=DATASET_TAG,
                                      description_variant=variants[i])
        done += 1
        print(f"[{done:>4}/{len(jobs)}] {entry.status:<6} {scenario.scenario_id:<45} seed={seed:<6} "
              f"calls={entry.n_tool_calls} events={entry.n_log_events}", flush=True)
        return entry

    return list(await asyncio.gather(*(one(i, s, seed) for i, (s, seed) in enumerate(jobs))))


def summarize(paths: DataPaths, seeds: dict[str, list[int]] | None) -> dict:
    rows = load_manifest(paths.manifest)
    problems = verify(paths)
    return {
        "dataset_tag": DATASET_TAG,
        "n_sessions": len(rows),
        "n_ok": sum(r["status"] == "ok" for r in rows),
        "labels": dict(Counter(r["label"] for r in rows)),
        "n_tasks": len({r["task_id"] for r in rows}),
        "n_scenarios": len({r["scenario_id"] for r in rows}),
        "distinct_plans_per_task": {k: len(v) for k, v in seeds.items()} if seeds else None,
        "servers_per_session": dict(sorted(Counter(len(r["servers"]) for r in rows).items())),
        "description_variants": dict(sorted(Counter(r.get("description_variant") or 0 for r in rows).items())),
        "lab_versions": dict(Counter(r.get("lab_version") for r in rows)),
        "verify_problems": problems,
        "dataset_sha256": sha256_files(paths.root),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Generate a unique benign-only corpus")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--seed-base", type=int, default=50000)
    p.add_argument("--search", type=int, default=2000, help="seeds searched per task for distinct plans")
    p.add_argument("--parallel", type=int, default=4)
    p.add_argument("--server-mix", choices=("both", "own", "all"), default="both",
                   help="run each plan with the task's own servers, all benign servers, or both")
    p.add_argument("--description-variant", choices=("0", "1", "2", "3", "cycle"), default="0",
                   help="benign tool-description wording: 0 = original (default), 1-3, or cycle through 1-3")
    p.add_argument("--tasks", default=None,
                   help="comma-separated task ids to generate (default: every benign task)")
    p.add_argument("--verify-only", action="store_true")
    a = p.parse_args()
    tasks = [t.strip() for t in a.tasks.split(",") if t.strip()] if a.tasks else None
    unknown = sorted(set(tasks or []) - set(TASKS))
    if unknown:
        raise SystemExit(f"unknown task(s): {unknown}")
    paths = DataPaths(a.output.resolve())

    if a.verify_only:
        cfg = json.loads((paths.root / "generation_config.json").read_text(encoding="utf-8"))
        summary = summarize(paths, cfg.get("seeds"))
        print(json.dumps({k: v for k, v in summary.items() if k != "distinct_plans_per_task"}, indent=2))
        sys.exit(1 if summary["verify_problems"] else 0)

    if paths.root.exists() and any(paths.root.iterdir()):
        raise SystemExit(f"refusing to write into non-empty {paths.root}")
    seeds = asyncio.run(distinct_plan_seeds(a.seed_base, a.search, tasks))
    jobs = benign_jobs(seeds, a.server_mix)
    paths.root.mkdir(parents=True, exist_ok=True)
    write_json(paths.root / "generation_config.json", {
        "dataset_tag": DATASET_TAG, "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "lab_version": LAB_VERSION, "llm": "mock", "seed_base": a.seed_base, "search": a.search,
        "parallel": a.parallel, "n_jobs": len(jobs), "seeds": seeds,
        "server_mix": a.server_mix, "description_variant": a.description_variant, "tasks": tasks,
        "python": platform.python_version(), "platform": platform.platform(),
    })
    print(f"{sum(len(v) for v in seeds.values())} distinct benign plans over {len(seeds)} tasks "
          f"-> {len(jobs)} sessions (each plan in both server mixes)", flush=True)
    entries = asyncio.run(run_jobs(jobs, paths, a.parallel, a.description_variant))
    summary = summarize(paths, seeds)
    write_json(paths.root / "metadata.json", summary)
    (paths.root / "README.md").write_text(
        f"# Unique benign corpus ({LAB_VERSION}, mix={a.server_mix}, descriptions={a.description_variant})\n\n"
        f"{summary['n_sessions']} benign sessions: every distinct mock-agent behaviour of all "
        f"{summary['n_tasks']} benign tasks, once in each server mix. Generated by "
        "`python -m scripts.generate_benign_corpus`. Benign only; intended as a held-out "
        "false-positive / drift test set. See `metadata.json` and `generation_config.json`.\n",
        encoding="utf-8")
    failed = [e for e in entries if e.status != "ok"]
    print(json.dumps({k: v for k, v in summary.items() if k != "distinct_plans_per_task"}, indent=2))
    sys.exit(1 if failed or summary["verify_problems"] else 0)


if __name__ == "__main__":
    main()
