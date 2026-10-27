"""Tests for the unique benign corpus generator and the external evaluator helpers."""

from __future__ import annotations

import asyncio

import pytest

from ml.evaluate_external import wilson
from orchestrator.scenarios import SCENARIOS
from scripts.generate_benign_corpus import benign_jobs, distinct_plan_seeds


def test_wilson_interval() -> None:
    assert wilson(0, 27) == (0.0, 0.1246)       # "0 of 27" still allows up to ~12.5 %
    assert wilson(0, 200)[1] < 0.02
    lo, hi = wilson(5, 100)
    assert lo < 0.05 < hi
    assert wilson(0, 0) == (0.0, 1.0)


@pytest.fixture(scope="module")
def seeds() -> dict[str, list[int]]:
    return asyncio.run(distinct_plan_seeds(50000, 400))


def test_every_task_has_at_least_one_plan_and_seeds_are_unique_per_plan(seeds) -> None:
    benign_tasks = {s.task_id for s in SCENARIOS.values() if s.label == "benign"}
    assert set(seeds) >= benign_tasks
    assert all(len(v) >= 1 and len(v) == len(set(v)) for v in seeds.values())


def test_jobs_are_benign_only_and_cover_both_server_mixes(seeds) -> None:
    jobs = benign_jobs(seeds)
    assert jobs and all(s.label == "benign" and s.attack_family is None for s, _ in jobs)
    # each (task, seed) appears once with the task's own servers and once with all servers
    per_task_seed: dict[tuple, int] = {}
    for s, seed in jobs:
        per_task_seed[(s.task_id, seed)] = per_task_seed.get((s.task_id, seed), 0) + 1
    assert set(per_task_seed.values()) == {2}


def test_full_search_finds_the_documented_number_of_plans() -> None:
    seeds = asyncio.run(distinct_plan_seeds(50000, 2000))
    # 100 distinct behaviours over the original 22 tasks; 317 since the lab-0.9.0 tasks;
    # 346 since the four lab-0.9.1 benign sampling tasks (29 more)
    assert sum(len(v) for v in seeds.values()) == 346


def test_compose_copies_sources_and_refuses_duplicates(tmp_path) -> None:
    import json as _json
    from orchestrator.main import DataPaths, run_session
    from orchestrator.scenarios import get_scenario
    from scripts.compose_dataset import compose
    a, b = DataPaths(tmp_path / "a"), DataPaths(tmp_path / "b")
    asyncio.run(run_session(get_scenario("benign:calc_add"), seed=1, paths=a))
    asyncio.run(run_session(get_scenario("benign:calc_temperature"), seed=2, paths=b))
    before = (a.manifest.read_bytes(), b.manifest.read_bytes())
    s = compose([a.root, b.root], tmp_path / "c")
    assert s["n_sessions"] == 2 and s["verify_problems"] == []
    assert (a.manifest.read_bytes(), b.manifest.read_bytes()) == before        # sources untouched
    assert _json.loads((tmp_path / "c" / "composition.json").read_text())["sources"][0]["n_sessions"] == 1
    with pytest.raises(SystemExit):                                            # same source twice
        compose([a.root, a.root], tmp_path / "d")
    with pytest.raises(SystemExit):                                            # non-empty output
        compose([a.root], tmp_path / "c")
