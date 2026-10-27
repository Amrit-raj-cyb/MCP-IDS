"""Phase 5 tests: manifest validation, scenarios, orchestrator, verification."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from orchestrator.main import DataPaths, run_batch, run_session, verify
from orchestrator.manifest import (ManifestEntry, ManifestError, ManifestWriter, load_manifest,
                                   validate_entry)
from orchestrator.scenarios import SCENARIOS, Scenario, check_scenarios, get_scenario, select
from proxy.reader import load_session


def _entry(**kw) -> ManifestEntry:
    base = dict(session_id="s1", scenario_id="benign:x", task_id="x", label="benign",
                attack_family=None, attack_attempted=False, attack_succeeded=False,
                servers=["filesystem"], backend="mock", seed=0, status="ok",
                started_at="t0", ended_at="t1", duration_ms=1.0)
    return ManifestEntry(**{**base, **kw})


# ------------------------------------------------------------ label rules

def test_valid_entries_pass() -> None:
    validate_entry(_entry())
    validate_entry(_entry(label="attack", attack_family="poisoned_tool", attack_attempted=True))
    validate_entry(_entry(label="attack", attack_family="shadowing", attack_attempted=True,
                          attack_succeeded=True))


@pytest.mark.parametrize("bad", [
    dict(label="malicious"),
    dict(attack_family="poisoned_tool"),                                   # benign with a family
    dict(attack_attempted=True),                                           # benign attempted
    dict(label="attack", attack_family=None, attack_attempted=True),       # attack without family
    dict(label="attack", attack_family="ddos", attack_attempted=True),     # unknown family
    dict(label="attack", attack_family="shadowing", attack_attempted=False),
    dict(label="attack", attack_family="shadowing", attack_attempted=False, attack_succeeded=True),
    dict(status="maybe"),
    dict(servers=[]),
])
def test_inconsistent_labels_are_rejected(bad: dict) -> None:
    with pytest.raises(ManifestError):
        validate_entry(_entry(**bad))


def test_writer_refuses_invalid_entries(tmp_path: Path) -> None:
    w = ManifestWriter(tmp_path / "m.jsonl")
    w.append(_entry())
    with pytest.raises(ManifestError):
        w.append(_entry(session_id="s2", attack_attempted=True))
    assert [e["session_id"] for e in load_manifest(tmp_path / "m.jsonl")] == ["s1"]


# -------------------------------------------------------------- scenarios

def test_scenario_registry_is_consistent() -> None:
    assert check_scenarios() == []
    from agent.tasks import TASKS
    assert len(select("benign")) == 2 * len(TASKS)  # every task: own servers + all benign servers
    assert all(s.label == "benign" for s in select("benign"))
    multi = [s for s in SCENARIOS.values() if len(s.servers) > 1]
    assert len(multi) >= 15, "need benign multi-server sessions as negatives for shadowing"


def test_select_by_ids() -> None:
    picked = select("benign:fs_summarize_notes, benign:web_news")
    assert [s.scenario_id for s in picked] == ["benign:fs_summarize_notes", "benign:web_news"]
    with pytest.raises(KeyError):
        get_scenario("benign:nope")


# --------------------------------------------------------- orchestration

@pytest.fixture
def paths(tmp_path: Path) -> DataPaths:
    return DataPaths(tmp_path / "data")


def _wire_signature(session_id: str, paths: DataPaths) -> list[tuple]:
    """What happened on the wire, minus timing and ids: method, tool, args, error, size."""
    out = []
    for e in load_session(session_id, paths.sessions):
        if e["kind"] == "lifecycle":
            continue
        params = (e["body"] or {}).get("params") or {}
        out.append((e["server_id"], e["direction"], e["kind"], e["method"], params.get("name"),
                    json.dumps(params.get("arguments"), sort_keys=True), e["is_error"], e["message_size"]))
    return out


async def test_run_session_writes_manifest_and_logs(paths: DataPaths) -> None:
    e = await run_session(get_scenario("benign:multi_db_report"), seed=4, paths=paths)
    assert e.status == "ok" and e.label == "benign" and not e.attack_attempted
    assert e.log_files == ["filesystem.jsonl", "sqlite.jsonl"]
    [row] = load_manifest(paths.manifest)
    assert row["session_id"] == e.session_id and row["seed"] == 4
    events = load_session(e.session_id, paths.sessions)
    assert len(events) == e.n_log_events and {ev["session_id"] for ev in events} == {e.session_id}
    assert verify(paths) == []


async def test_same_seed_reproduces_identical_wire_traffic(paths: DataPaths) -> None:
    sc = get_scenario("benign:multi_price_check")
    a = await run_session(sc, seed=11, paths=paths)
    b = await run_session(sc, seed=11, paths=paths)
    assert a.session_id != b.session_id
    sig_a, sig_b = _wire_signature(a.session_id, paths), _wire_signature(b.session_id, paths)
    assert sig_a == sig_b and len(sig_a) > 10


async def test_batch_parallel_and_seeds(paths: DataPaths) -> None:
    scs = select("benign:fs_summarize_notes,benign:db_top_products,benign:web_news")
    entries = await run_batch(scs, repeats=2, base_seed=50, paths=paths, parallel=3, progress=False)
    assert len(entries) == 6 and all(e.status == "ok" for e in entries)
    assert sorted(e.seed for e in entries) == list(range(50, 56))
    assert len({e.session_id for e in entries}) == 6
    assert verify(paths) == []


async def test_failed_session_is_recorded_not_hidden(paths: DataPaths) -> None:
    broken = Scenario("benign:broken", "fs_summarize_notes", ("filesystem", "no_such_server"))
    e = await run_session(broken, seed=0, paths=paths)
    assert e.status == "failed" and "no_such_server" in e.error
    assert load_manifest(paths.manifest)[0]["status"] == "failed"


async def test_verify_detects_tampering(paths: DataPaths) -> None:
    e = await run_session(get_scenario("benign:multi_db_report"), seed=1, paths=paths)
    assert verify(paths) == []
    (paths.sessions / e.session_id / "sqlite.jsonl").unlink()           # lost log file
    shutil.copytree(paths.sessions / e.session_id, paths.sessions / "orphan")  # unlabelled logs
    problems = verify(paths)
    assert any("log files" in p for p in problems)
    assert any("orphan" in p and "without manifest" in p for p in problems)


def test_verify_fails_on_missing_manifest(paths: DataPaths) -> None:
    problems = verify(paths)
    assert len(problems) == 1 and "no manifest entries" in problems[0]
