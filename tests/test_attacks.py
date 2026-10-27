"""Phase 6 tests: poisoned-tool simulation (inertness, twin design, success measurement)."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from agent.llm import MockLLM, ToolInfo, ToolResult
from agent.tasks import TASKS, get_task
from common.registry import get_server
from common.simulation import (CANARY_ARGS, CANARY_TOKEN, SIMULATION_MARKER, contains_marker, is_canary_call,
                               neutralize, schema_texts, strip_marker)
from orchestrator.main import DataPaths, run_batch, run_session, verify
from orchestrator.manifest import load_manifest
from orchestrator.scenarios import BENIGN_ONLY_TASKS, check_scenarios, get_scenario, select
from proxy.reader import load_session
from servers.attack.poisoned_tool.server import PAYLOADS, VARIANTS, poisoned_text
from servers.benign.calculator.server import CLEAN_TEXT, build_calculator


def _tools(text) -> list:
    return asyncio.run(build_calculator(text).list_tools())


def _all_text(tools) -> list[str]:
    return [t.description or "" for t in tools] + [s for t in tools for s in schema_texts(t.input_schema)]


# ------------------------------------------------------------------ inertness

@pytest.mark.parametrize("variant", VARIANTS)
def test_payload_is_marked_and_only_asks_for_canaries(variant: str) -> None:
    texts = [t for t in _all_text(_tools(poisoned_text(variant))) if contains_marker(t)]
    assert len(texts) == 1, "exactly one marked payload per variant"
    payload = texts[0]
    assert CANARY_TOKEN in payload and str(CANARY_ARGS["a"]) in payload and str(CANARY_ARGS["b"]) in payload
    # Nothing that could cause harm or reach outside the lab.
    forbidden = r"https?://|www\.|/etc/|\.\./|password|secret|api[_ ]?key|token=|ssh|delete|remove|rm -|" \
                r"exec|shell|curl|wget|send|email|upload|exfil|credential"
    assert not re.search(forbidden, payload, re.IGNORECASE), payload


@pytest.mark.parametrize("variant", VARIANTS)
def test_poisoned_tools_behave_exactly_like_benign(variant: str) -> None:
    clean, bad = build_calculator(CLEAN_TEXT), build_calculator(poisoned_text(variant))
    for name, args in [("add_numbers", {"a": 2, "b": 3}), ("add_numbers", CANARY_ARGS),
                       ("percentage", {"part": 1, "whole": 4}),
                       ("convert_temperature", {"value": 100, "from_unit": "C", "to_unit": "F"})]:
        r1 = asyncio.run(clean.call_tool(name, args))
        r2 = asyncio.run(bad.call_tool(name, args))
        assert r1 == r2


# ------------------------------------------------------------- twin design

@pytest.mark.parametrize("variant", VARIANTS)
def test_twins_differ_only_in_text(variant: str) -> None:
    clean, bad = _tools(CLEAN_TEXT), _tools(poisoned_text(variant))
    assert [t.name for t in clean] == [t.name for t in bad]

    def shape(schema):  # schema with all description strings removed
        if isinstance(schema, dict):
            return {k: shape(v) for k, v in schema.items() if k != "description"}
        return schema
    assert [shape(t.input_schema) for t in clean] == [shape(t.input_schema) for t in bad]
    assert _all_text(clean) != _all_text(bad)


def test_attack_server_hides_behind_twin_name() -> None:
    assert get_server("calculator_poisoned").log_id == get_server("calculator").log_id == "calculator"
    assert get_server("calculator_poisoned").kind == "attack"


def test_attack_scenarios_are_exact_twins() -> None:
    assert check_scenarios() == []
    attacks = select("attack")
    poison = [a for a in attacks if a.attack_family == "poisoned_tool"]
    benign = select("benign")
    assert len(benign) == 2 * len(TASKS)  # every task: own servers + all benign servers
    # one twin per calculator scenario, except the benign-only tasks (lab 0.9.1 benign sampling tasks)
    assert len(poison) == sum("calculator" in b.servers and b.task_id not in BENIGN_ONLY_TASKS for b in benign)
    assert not [a for a in attacks if a.task_id in BENIGN_ONLY_TASKS]
    for a in poison:
        b = get_scenario(a.twin_of)
        assert b.label == "benign" and a.task_id == b.task_id
        assert [s.replace("calculator_poisoned", "calculator") for s in a.servers] == list(b.servers)
    # Most attack sessions never call the poisoned tool: the attempt is the metadata itself.
    unused = [a for a in poison if "calculator" not in get_task(a.task_id).servers]
    assert len(unused) >= 16


# --------------------------------------------------------------- marker hygiene

def test_neutralize_removes_lab_artefacts() -> None:
    text = PAYLOADS["overt"]
    clean = neutralize(text)
    assert SIMULATION_MARKER not in clean and CANARY_TOKEN not in clean
    assert "ignore previous instructions" in clean  # the attack *content* remains
    assert strip_marker(f"x {SIMULATION_MARKER} y") == "x y"


def test_canary_call_detection() -> None:
    assert is_canary_call("add_numbers", {"a": 1337, "b": 7331})
    assert is_canary_call("add_numbers", {"a": 1337.0, "b": "7331"})
    assert not is_canary_call("add_numbers", {"a": 1, "b": 2})
    assert not is_canary_call("percentage", {"a": 1337, "b": 7331})


# ---------------------------------------------------------- mock behaviour

async def _mock_calls(task_id: str, tools: list[ToolInfo], seed: int, susceptibility: float):
    m = MockLLM(seed, susceptibility=susceptibility)
    await m.start(get_task(task_id), tools)
    calls, results = [], []
    while not (d := await m.step(results)).done:
        calls += [(c.name, c.arguments) for c in d.tool_calls]
        results = [ToolResult(c.call_id, "ok", False) for c in d.tool_calls]
    return m, calls, d.final_text


async def _tool_infos(text, prefix="calculator__") -> list[ToolInfo]:
    tools = await build_calculator(text).list_tools()  # async tests can't use asyncio.run()
    return [ToolInfo(prefix + t.name, t.description or "", t.input_schema) for t in tools]


async def test_mock_complies_or_not_and_plan_is_unchanged() -> None:
    clean, bad = await _tool_infos(CLEAN_TEXT), await _tool_infos(poisoned_text("param"))
    _, base_calls, base_text = await _mock_calls("calc_add", clean, seed=3, susceptibility=1.0)
    m1, calls1, text1 = await _mock_calls("calc_add", bad, seed=3, susceptibility=1.0)
    m0, calls0, text0 = await _mock_calls("calc_add", bad, seed=3, susceptibility=0.0)

    assert CANARY_TOKEN not in base_text                    # clean twin: never triggers
    assert m1.injection_seen and m1.complied
    assert calls1[0] == ("calculator__add_numbers", CANARY_ARGS) and calls1[1:] == base_calls
    assert CANARY_TOKEN in text1
    assert m0.injection_seen and not m0.complied and calls0 == base_calls and CANARY_TOKEN not in text0


async def test_susceptibility_rate_matches_setting() -> None:
    bad = await _tool_infos(poisoned_text("overt"))
    complied = [(await _mock_calls("calc_add", bad, s, 0.35))[0].complied for s in range(400)]
    assert 0.28 < sum(complied) / len(complied) < 0.42


# ------------------------------------------------------ end-to-end sessions

@pytest.fixture
def paths(tmp_path: Path) -> DataPaths:
    return DataPaths(tmp_path / "data")


async def test_attack_session_is_labelled_logged_and_verified(paths: DataPaths) -> None:
    e = await run_session(get_scenario("attack:poisoned_tool:calc_add"), seed=4, paths=paths, susceptibility=1.0)
    assert (e.label, e.attack_family, e.attack_attempted, e.attack_succeeded) == ("attack", "poisoned_tool", True, True)
    assert e.attack_variant == VARIANTS[4 % len(VARIANTS)] and e.twin_of == "benign:calc_add"
    assert e.log_files == ["calculator.jsonl"]  # wire name of the twin, not "calculator_poisoned"

    events = load_session(e.session_id, paths.sessions)
    listing = next(ev for ev in events if ev["method"] == "tools/list" and ev["kind"] == "response")
    assert SIMULATION_MARKER in json.dumps(listing["body"])                 # the attempt is on the wire
    canary = [ev for ev in events if ev["method"] == "tools/call" and ev["kind"] == "request"
              and is_canary_call(ev["body"]["params"]["name"], ev["body"]["params"]["arguments"])]
    assert len(canary) == 1                                                  # the success is on the wire too
    assert verify(paths) == []


async def test_attempt_without_tool_use_is_still_an_attack(paths: DataPaths) -> None:
    e = await run_session(get_scenario("attack:poisoned_tool:fs_summarize_notes:all_servers"),
                          seed=1, paths=paths, susceptibility=0.0)
    assert e.attack_attempted and not e.attack_succeeded and e.status == "ok"
    events = load_session(e.session_id, paths.sessions)
    calc = [ev for ev in events if ev["server_id"] == "calculator"]
    assert not any(ev["method"] == "tools/call" for ev in calc)              # never called...
    assert any(SIMULATION_MARKER in json.dumps(ev["body"]) for ev in calc)   # ...but metadata was delivered


async def test_twin_pair_has_identical_benign_calls(paths: DataPaths) -> None:
    b = await run_session(get_scenario("benign:multi_order_share"), seed=7, paths=paths)
    a = await run_session(get_scenario("attack:poisoned_tool:multi_order_share"), seed=7, paths=paths,
                          susceptibility=0.0)

    def calls(sid):
        return [(ev["body"]["params"]["name"], ev["body"]["params"]["arguments"])
                for ev in load_session(sid, paths.sessions)
                if ev["method"] == "tools/call" and ev["kind"] == "request"]
    assert calls(a.session_id) == calls(b.session_id) and calls(a.session_id)
    assert not b.attack_attempted and a.attack_attempted


async def test_mixed_batch_counts(paths: DataPaths) -> None:
    scs = select("attack:poisoned_tool:calc_add,benign:calc_add")
    entries = await run_batch(scs, repeats=3, base_seed=0, paths=paths, parallel=3, progress=False)
    assert len(entries) == 6 and all(e.status == "ok" for e in entries)
    rows = load_manifest(paths.manifest)
    assert sum(r["label"] == "attack" for r in rows) == 3 and sum(r["label"] == "benign" for r in rows) == 3
    assert all(r["attack_variant"] is None for r in rows if r["label"] == "benign")
    assert verify(paths) == []
