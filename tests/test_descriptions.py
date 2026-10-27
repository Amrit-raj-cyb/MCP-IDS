"""Tests for the opt-in alternative benign tool descriptions (common/descriptions.py)."""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest

from common.descriptions import N_VARIANTS, VARIANTS
from orchestrator.main import DataPaths, run_session, verify
from orchestrator.scenarios import get_scenario
from proxy.reader import load_session
from scripts.generate_benign_corpus import description_variant_for

MODULES = {
    "filesystem": "servers.benign.filesystem.server",
    "sqlite": "servers.benign.sqlite.server",
    "web_fetch": "servers.benign.web_fetch.server",
}


def _tools(module: str, variant: str | None, monkeypatch: pytest.MonkeyPatch) -> list:
    if variant is None:
        monkeypatch.delenv("MCP_DESCRIPTION_VARIANT", raising=False)
    else:
        monkeypatch.setenv("MCP_DESCRIPTION_VARIANT", variant)
    mod = importlib.reload(importlib.import_module(module))
    return asyncio.run(mod.mcp.list_tools())


@pytest.fixture(autouse=True)
def _restore_modules(monkeypatch: pytest.MonkeyPatch):
    yield
    monkeypatch.delenv("MCP_DESCRIPTION_VARIANT", raising=False)
    for m in MODULES.values():
        importlib.reload(importlib.import_module(m))


@pytest.mark.parametrize("server", MODULES)
def test_variant_zero_is_byte_identical_to_original(server, monkeypatch) -> None:
    original = [t.model_dump() for t in _tools(MODULES[server], None, monkeypatch)]
    zero = [t.model_dump() for t in _tools(MODULES[server], "0", monkeypatch)]
    assert json.dumps(original, sort_keys=True) == json.dumps(zero, sort_keys=True)


@pytest.mark.parametrize("server", MODULES)
def test_variants_change_only_descriptions(server, monkeypatch) -> None:
    base = _tools(MODULES[server], "0", monkeypatch)
    seen = {tuple(t.description for t in base)}
    for v in range(1, N_VARIANTS + 1):
        tools = _tools(MODULES[server], str(v), monkeypatch)
        assert [t.name for t in tools] == [t.name for t in base]
        assert [t.input_schema for t in tools] == [t.input_schema for t in base]
        assert [t.description for t in tools] == [VARIANTS[server][t.name][v - 1] for t in tools]
        seen.add(tuple(t.description for t in tools))
    assert len(seen) == N_VARIANTS + 1          # all wordings distinct


LIST_TOOLS = (
    "import asyncio, importlib, json, sys; m = importlib.import_module(sys.argv[1]); "
    "s = getattr(m, 'server', None) or m.build_calculator(); "
    "print(json.dumps([t.description for t in asyncio.run(s.list_tools())]))"
)


def test_twin_servers_ignore_the_variant() -> None:
    # Checked in fresh processes (as the lab starts servers), so modules that
    # other tests hold references to are never reloaded here.
    import os
    import subprocess
    import sys
    from common.registry import PROJECT_ROOT
    for module in ("servers.benign.calculator.server", "servers.benign.shadowing_control.server",
                   "servers.benign.sampling_control.server"):
        outs = []
        for variant in ("0", "2"):
            env = {**os.environ, "MCP_DESCRIPTION_VARIANT": variant, "PYTHONPATH": str(PROJECT_ROOT)}
            outs.append(subprocess.run([sys.executable, "-c", LIST_TOOLS, module], capture_output=True,
                                       text=True, env=env, cwd=PROJECT_ROOT, check=True).stdout)
        assert outs[0] == outs[1], module


def test_cycle_never_uses_original_wording() -> None:
    assert [description_variant_for("cycle", i) for i in range(6)] == [1, 2, 3, 1, 2, 3]
    assert description_variant_for("0", 5) == 0 and description_variant_for("2", 0) == 2


def test_session_records_variant_and_sends_reworded_metadata(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "data")
    e = asyncio.run(run_session(get_scenario("benign:fs_summarize_notes"), seed=1, paths=paths,
                                description_variant=3))
    assert e.status == "ok" and e.description_variant == 3
    listing = next(ev for ev in load_session(e.session_id, paths.sessions)
                   if ev["method"] == "tools/list" and ev["kind"] == "response")
    texts = {t["name"]: t["description"] for t in listing["body"]["result"]["tools"]}
    assert texts["read_file"] == VARIANTS["filesystem"]["read_file"][2]
    assert verify(paths) == []
