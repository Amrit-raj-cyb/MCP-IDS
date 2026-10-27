"""Smoke and protocol tests for the inert Phase 7 and 8 simulations."""
from __future__ import annotations

import json
from pathlib import Path


from orchestrator.main import DataPaths, run_session, verify
from orchestrator.manifest import load_manifest
from orchestrator.scenarios import check_scenarios, get_scenario
from proxy.reader import load_session
from servers.attack.shadowing.server import DESCRIPTION as SHADOW_DESCRIPTION
from servers.attack.sampling_injector.server import SIMULATED_PROMPT


def test_attack_scenarios_are_registered_and_consistent() -> None:
    assert check_scenarios() == []
    shadow = get_scenario("attack:shadowing:fs_shadowing_probe")
    sampling = get_scenario("attack:sampling_injection:fs_sampling_probe")
    assert shadow.attack_family == "shadowing" and shadow.label == "attack"
    assert sampling.attack_family == "sampling_injection" and sampling.label == "attack"
    assert "filesystem__read_file" in SHADOW_DESCRIPTION
    assert "[LAB-SIMULATION]" in SIMULATED_PROMPT


async def test_shadowing_smoke_shared_session_proxy_and_manifest(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "phase7")
    scenario = get_scenario("attack:shadowing:fs_shadowing_probe")
    entry = await run_session(scenario, seed=33, paths=paths, susceptibility=1.0)

    assert entry.status == "ok"
    assert entry.attack_family == "shadowing" and entry.attack_attempted is True
    assert entry.attack_succeeded is True
    assert set(entry.log_files) == {"filesystem.jsonl", "shadowing_control.jsonl"}
    events = load_session(entry.session_id, paths.sessions)
    assert {e["session_id"] for e in events} == {entry.session_id}
    assert {e["server_id"] for e in events if e["kind"] != "lifecycle"} == {
        "filesystem", "shadowing_control",
    }
    lists = [e for e in events if e["method"] == "tools/list" and e["kind"] == "response"]
    descriptions = [t["description"] for e in lists for t in e["body"]["result"]["tools"]]
    assert any("filesystem__read_file" in d and "[LAB-SIMULATION]" in d for d in descriptions)
    calls = [e for e in events if e["method"] == "tools/call" and e["kind"] == "request"]
    assert any(e["server_id"] == "shadowing_control" and e["body"]["params"]["name"] == "read_file"
               for e in calls)
    assert verify(paths) == []
    record = load_manifest(paths.manifest)[0]
    assert record["attack_family"] == "shadowing" and record["attack_attempted"]


async def test_sampling_smoke_logs_server_request_and_client_response(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "phase8")
    scenario = get_scenario("attack:sampling_injection:fs_sampling_probe")
    entry = await run_session(scenario, seed=34, paths=paths)

    assert entry.status == "ok"
    assert entry.attack_family == "sampling_injection" and entry.attack_attempted is True
    assert entry.attack_succeeded is True
    events = load_session(entry.session_id, paths.sessions)
    sampling = [e for e in events if e["method"] == "sampling/createMessage"]
    assert len(sampling) == 2
    request = next(e for e in sampling if e["kind"] == "request")
    response = next(e for e in sampling if e["kind"] == "response")
    assert request["direction"] == "server_to_client"
    assert response["direction"] == "client_to_server"
    assert response["request_seq"] == request["seq"]
    assert "[LAB-SIMULATION]" in json.dumps(request["body"])
    assert "LAB-SAMPLING-ACK" in json.dumps(response["body"])
    assert all(e["session_id"] == entry.session_id for e in sampling)
    assert verify(paths) == []

