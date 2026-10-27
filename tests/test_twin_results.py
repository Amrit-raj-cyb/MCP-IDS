"""Twin-design tests for the Phase 7/8 servers (fix #4).

A benign control and its attack twin must be identical on the wire except
for what the simulation is about:

* shadowing: only the tool *description* differs;
* sampling:  the description differs and the twin sends one
  ``sampling/createMessage`` request (plus the client's reply).

In particular, tool **results** must be byte-identical. Otherwise a model
could learn the label from result text and sizes instead of the behaviour
under study.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orchestrator.main import DataPaths, run_session
from orchestrator.scenarios import get_scenario
from proxy.reader import load_session
from servers.attack.sampling_injector import server as sampling_twin
from servers.attack.shadowing import server as shadow_twin
from servers.benign.sampling_control import server as sampling_ctrl
from servers.benign.shadowing_control import server as shadow_ctrl

PAIRS = [
    pytest.param(shadow_ctrl, shadow_twin, id="shadowing"),
    pytest.param(sampling_ctrl, sampling_twin, id="sampling"),
]


def _shape(schema):
    """JSON schema with every description removed."""
    if isinstance(schema, dict):
        return {k: _shape(v) for k, v in schema.items() if k != "description"}
    if isinstance(schema, list):
        return [_shape(v) for v in schema]
    return schema


@pytest.mark.parametrize("ctrl,twin", PAIRS)
def test_twins_share_result_constant_and_identity(ctrl, twin) -> None:
    assert twin.RESULT is ctrl.RESULT                      # one source of truth
    assert twin.server.name == ctrl.server.name            # same serverInfo name
    assert twin.server.version == ctrl.server.version


@pytest.mark.parametrize("ctrl,twin", PAIRS)
def test_twins_expose_same_tool_shape(ctrl, twin) -> None:
    a = asyncio.run(ctrl.server.list_tools())
    b = asyncio.run(twin.server.list_tools())
    assert [t.name for t in a] == [t.name for t in b]
    assert [_shape(t.input_schema) for t in a] == [_shape(t.input_schema) for t in b]
    assert [_shape(t.output_schema) for t in a] == [_shape(t.output_schema) for t in b]
    assert [t.description for t in a] != [t.description for t in b]  # the metadata under study


def test_shadowing_tool_results_are_identical() -> None:
    a = asyncio.run(shadow_ctrl.server.call_tool("read_file", {}))
    b = asyncio.run(shadow_twin.server.call_tool("read_file", {}))
    assert a == b


def _wire(session_id: str, paths: DataPaths) -> list[tuple]:
    """Wire messages minus ids/timestamps; tool descriptions blanked out."""
    out = []
    for e in load_session(session_id, paths.sessions):
        if e["kind"] == "lifecycle":
            continue
        body = json.loads(json.dumps(e["body"]))
        body.pop("id", None)
        if e["method"] == "tools/list" and e["kind"] == "response":
            for t in body["result"]["tools"]:
                t["description"] = ""
                for p in (t.get("inputSchema") or {}).get("properties", {}).values():
                    p.pop("description", None)
            size = None                                    # length differs with the description
        else:
            size = e["message_size"]
        out.append((e["server_id"], e["direction"], e["kind"], e["method"], size,
                    json.dumps(body, sort_keys=True)))
    return out


@pytest.mark.parametrize("benign_id,attack_id,extra_methods", [
    ("benign:fs_sampling_probe", "attack:sampling_injection:fs_sampling_probe", {"sampling/createMessage"}),
    ("benign:fs_shadowing_probe", "attack:shadowing:fs_shadowing_probe", set()),
])
def test_twin_sessions_differ_only_in_the_simulated_part(tmp_path: Path, benign_id, attack_id,
                                                         extra_methods) -> None:
    paths = DataPaths(tmp_path / "data")
    b = asyncio.run(run_session(get_scenario(benign_id), seed=21, paths=paths, susceptibility=0.0))
    a = asyncio.run(run_session(get_scenario(attack_id), seed=21, paths=paths, susceptibility=0.0))
    assert b.status == a.status == "ok"
    wb, wa = _wire(b.session_id, paths), _wire(a.session_id, paths)
    extra = [m for m in wa if m[3] in extra_methods]
    assert len(extra) == (2 if extra_methods else 0)      # sampling: server request + client reply
    common = [m for m in wa if m[3] not in extra_methods]
    assert common == wb, "apart from the simulated messages, twin sessions must be identical"


def test_sampling_tool_result_identical_on_the_wire(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "data")
    results = []
    for sid in ("benign:fs_sampling_probe", "attack:sampling_injection:fs_sampling_probe"):
        e = asyncio.run(run_session(get_scenario(sid), seed=5, paths=paths, susceptibility=0.0))
        resp = [ev for ev in load_session(e.session_id, paths.sessions)
                if ev["server_id"] == "sampling_control" and ev["method"] == "tools/call"
                and ev["kind"] == "response"]
        assert len(resp) == 1
        results.append((resp[0]["message_size"], resp[0]["body"]["result"]))
    assert results[0] == results[1]
