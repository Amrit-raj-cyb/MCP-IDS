"""Benign servers that legitimately use MCP sampling (lab 0.9.1) and the task-grouped baseline split."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agent.tasks import TASKS
from common.descriptions import N_VARIANTS, VARIANTS
from common.registry import SERVERS
from features.extractor import extract_session_features
from ml.dataset import FeatureData
from ml.raw import session_text_from_logs
from ml.train import make_split, train
from orchestrator.main import DataPaths, run_session, verify
from orchestrator.manifest import LAB_VERSION
from orchestrator.scenarios import BENIGN_ONLY_TASKS, SCENARIOS, get_scenario
from proxy.reader import load_session
from scripts.generate_benign_corpus import benign_jobs, distinct_plan_seeds

SAMPLING_SERVERS = ("writing_assistant", "helpdesk")


def test_sampling_servers_are_benign_and_documented_in_every_wording() -> None:
    for sid in SAMPLING_SERVERS:
        assert SERVERS[sid].kind == "benign" and SERVERS[sid].wire_id is None
        for tool, texts in VARIANTS[sid].items():
            assert len(texts) == N_VARIANTS and len(set(texts)) == N_VARIANTS
            assert all("[LAB-SIMULATION]" not in t for t in texts)
    assert LAB_VERSION == "0.9.1"


def test_new_tasks_are_benign_only_and_use_the_sampling_servers() -> None:
    assert BENIGN_ONLY_TASKS <= set(TASKS)
    for task_id in BENIGN_ONLY_TASKS:
        assert set(TASKS[task_id].servers) & set(SAMPLING_SERVERS)
        scenarios = [s for s in SCENARIOS.values() if s.task_id == task_id]
        assert {s.scenario_id for s in scenarios} == {f"benign:{task_id}", f"benign:{task_id}:all_servers"}
        assert all(s.label == "benign" and s.attack_family is None for s in scenarios)


@pytest.fixture(scope="module")
def sampling_sessions(tmp_path_factory) -> DataPaths:
    paths = DataPaths(tmp_path_factory.mktemp("bs") / "data")
    for scenario in ("benign:assist_summarize_text", "benign:helpdesk_triage_ticket"):
        assert asyncio.run(run_session(get_scenario(scenario), seed=5, paths=paths)).status == "ok"
    return paths


def test_benign_sessions_now_contain_server_initiated_sampling(sampling_sessions: DataPaths) -> None:
    assert verify(sampling_sessions) == []
    for d in sampling_sessions.sessions.iterdir():
        events = load_session(d.name, sampling_sessions.sessions)
        sampling = [e for e in events if e.get("method") == "sampling/createMessage"]
        requests = [e for e in sampling if e["kind"] == "request"]
        assert requests and all(e["direction"] == "server_to_client" for e in requests)
        assert len(sampling) == 2 * len(requests)            # every request answered by the client
        assert extract_session_features(d.name, sampling_sessions.sessions)["server_initiated_request_count"] >= 1
        assert "sampling/createMessage" in session_text_from_logs(d.name, sampling_sessions.sessions)
    manifest = [json.loads(line) for line in sampling_sessions.manifest.read_text(encoding="utf-8").splitlines()]
    assert all(r["label"] == "benign" and r["lab_version"] == "0.9.1" for r in manifest)


def test_corpus_generator_can_restrict_itself_to_the_new_tasks() -> None:
    seeds = asyncio.run(distinct_plan_seeds(80000, 300, sorted(BENIGN_ONLY_TASKS)))
    assert set(seeds) == BENIGN_ONLY_TASKS
    jobs = benign_jobs(seeds)
    assert jobs and {s.task_id for s, _ in jobs} == BENIGN_ONLY_TASKS and all(s.label == "benign" for s, _ in jobs)


# ------------------------------------------------------------- task-grouped baseline split

def _data(n_tasks: int = 9, per_task: int = 20, seed: int = 0) -> FeatureData:
    rng = np.random.default_rng(seed)
    fams = ["poisoned_tool", "poisoned_tool", "shadowing", "sampling_injection"]
    rows = []
    for t in range(n_tasks):
        fam = fams[t % len(fams)] if t < 6 else None   # tasks 0-5 carry attacks, the rest are benign-only
        for i in range(per_task):
            attack = fam is not None and i % 2 == 0
            rows.append({"session_id": f"t{t}s{i}", "task_id": f"task{t}",
                         "attack_family": fam if attack else None, "y": int(attack)})
    meta = pd.DataFrame(rows)
    X = pd.DataFrame(rng.normal(size=(len(meta), 3)), columns=["a", "b", "c"])
    return FeatureData(X, meta["y"].to_numpy(), meta, ["a", "b", "c"], {})


def test_task_grouped_split_holds_out_whole_tasks_and_keeps_every_family_in_training() -> None:
    d = _data()
    tr, te = make_split(d, 0.3, 42, "task-grouped")
    tasks = d.meta["task_id"].to_numpy()
    assert not set(tasks[tr]) & set(tasks[te]) and len(tr) + len(te) == len(d.y)
    assert set(d.y[tr]) == set(d.y[te]) == {0, 1}
    fam = d.meta["attack_family"].fillna("benign").to_numpy()
    assert set(fam[tr][d.y[tr] == 1]) == {"poisoned_tool", "shadowing", "sampling_injection"}
    np.testing.assert_array_equal(make_split(d, 0.3, 42, "task-grouped")[1], te)   # deterministic
    tr_s, te_s = make_split(d, 0.3, 42, "stratified")                               # old split still there
    assert set(tasks[tr_s]) & set(tasks[te_s])
    with pytest.raises(ValueError):
        make_split(d, 0.3, 42, "random")


def test_training_records_the_split_and_reuses_it_when_adding_models(tmp_path: Path) -> None:
    from tests.test_xgboost_ensemble import _feature_dir
    feats, models = _feature_dir(tmp_path), tmp_path / "models"
    train(feats, models, seed=42, test_size=0.3, only=["random_forest"])
    split = json.loads((models / "split.json").read_text(encoding="utf-8"))
    assert split["method"] == "task-grouped" and split["tasks_in_both"] == []
    train(feats, models, seed=42, test_size=0.3, only=["decision_tree"])      # same split recomputed
    old = tmp_path / "old"                                                       # a pre-2026-10-10 model dir
    train(feats, old, seed=42, test_size=0.3, only=["random_forest"], split_method="stratified")
    s = json.loads((old / "split.json").read_text(encoding="utf-8"))
    s.pop("method")
    (old / "split.json").write_text(json.dumps(s), encoding="utf-8")
    train(feats, old, seed=42, test_size=0.3, only=["decision_tree"])         # falls back to stratified
