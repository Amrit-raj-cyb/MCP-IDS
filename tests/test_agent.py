"""Phase 2 tests: agent driver, mock LLM, Claude backend (with a fake client).

The real Claude API is only exercised by ``test_live_claude``, which is skipped
unless RUN_LIVE_LLM=1 (costs money, needs credentials and internet).
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

from agent.driver import namespaced, run_agent
from agent.client import run_demo
from agent.llm import ClaudeLLM, Decision, MockLLM, ToolCallRequest, ToolInfo, ToolResult, make_backend
from agent.tasks import TASKS, PlanStep, Task, get_task
from common.sandbox import SEED_SANDBOX


def _snapshot(path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


# ------------------------------------------------------------------ mock LLM

async def _mock_plan(task: Task, seed: int) -> list[tuple[str, dict]]:
    """Materialise the mock's calls without any server (all calls succeed)."""
    tools = [ToolInfo(s.tool, "", {}) for s in task.plan]
    m = MockLLM(seed)
    await m.start(task, tools)
    calls, results = [], []
    while not (d := await m.step(results)).done:
        calls += [(c.name, c.arguments) for c in d.tool_calls]
        results = [ToolResult(c.call_id, "ok", False) for c in d.tool_calls]
    return calls


async def test_mock_is_deterministic_per_seed() -> None:
    for task in TASKS.values():
        assert await _mock_plan(task, 42) == await _mock_plan(task, 42)


async def test_mock_varies_across_seeds() -> None:
    task = get_task("fs_report_digest")
    plans = {repr(await _mock_plan(task, s)) for s in range(20)}
    assert len(plans) > 3, "benign traffic should not be identical across seeds"


async def test_mock_retries_once_on_error() -> None:
    task = Task("t", "p", ("filesystem",), plan=(
        PlanStep("fs__read", ({"path": "bad"},), on_error={"path": "good"}),
    ))
    m = MockLLM(0)
    await m.start(task, [ToolInfo("fs__read", "", {})])
    d1 = await m.step([])
    d2 = await m.step([ToolResult(d1.tool_calls[0].call_id, "nope", True)])
    assert d2.tool_calls[0].arguments == {"path": "good"}
    d3 = await m.step([ToolResult(d2.tool_calls[0].call_id, "still bad", True)])
    assert d3.done  # single retry only, no infinite loop


def test_factory_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert make_backend().name == "mock"
    with pytest.raises(ValueError):
        make_backend("gpt")


def test_namespacing_is_api_safe() -> None:
    assert namespaced("filesystem", "read_file") == "filesystem__read_file"
    assert namespaced("web.fetch", "get page") == "web_fetch__get_page"
    assert len(namespaced("s" * 50, "t" * 50)) == 64


# ------------------------------------------------------- driver end-to-end

async def test_driver_runs_every_task_with_mock() -> None:
    for task in TASKS.values():
        run = await run_agent(task, MockLLM(seed=3), seed=3)
        assert run.stop_reason == "end_turn"
        assert run.calls, f"{task.task_id} made no calls"
        assert all(c.server_id in task.servers for c in run.calls), "plan uses a tool the servers lack"
        assert run.final_text.startswith("[mock]")


async def test_driver_records_real_results_and_errors() -> None:
    run = await run_agent(get_task("fs_report_digest"), MockLLM(seed=0), seed=0)
    by_args = {(c.tool, c.arguments.get("path")): c for c in run.calls}
    assert by_args[("read_file", "reports/report.txt")].is_error          # wrong path
    assert "Quarterly Report" in by_args[("read_file", "report.txt")].result_preview
    assert not by_args[("write_file", "documents/digest.txt")].is_error


async def test_driver_never_modifies_seed_sandbox() -> None:
    before = _snapshot(SEED_SANDBOX)
    for seed in range(3):
        await run_agent(get_task("fs_report_digest"), MockLLM(seed), seed=seed)
    assert _snapshot(SEED_SANDBOX) == before


async def test_direct_client_always_advertises_sampling(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_LOG_DIR", str(tmp_path))
    result = await run_demo("calculator")
    from proxy.reader import load_session
    events = load_session(result.session_id, tmp_path)
    initialize = next(e for e in events if e.get("method") == "initialize" and e["direction"] == "client_to_server")
    assert initialize["body"]["params"]["capabilities"].get("sampling") == {}


class _ScriptedBackend:
    """Backend that replays a fixed list of decisions (for edge cases)."""
    name = "scripted"

    def __init__(self, decisions: list[Decision]) -> None:
        self.decisions, self.seen_results = decisions, []

    async def start(self, task, tools) -> None:
        self.tools = tools

    async def step(self, results):
        self.seen_results.append(results)
        return self.decisions.pop(0) if self.decisions else Decision(final_text="done", stop_reason="end_turn")


async def test_unknown_tool_is_reported_to_llm_not_crash() -> None:
    b = _ScriptedBackend([Decision([ToolCallRequest("c1", "nope__tool", {})])])
    run = await run_agent(get_task("fs_summarize_notes"), b)
    assert run.calls[0].is_error and run.calls[0].server_id == ""
    assert b.seen_results[1][0].is_error  # the LLM was told
    assert run.stop_reason == "end_turn"


async def test_max_steps_is_enforced() -> None:
    loop = [Decision([ToolCallRequest(f"c{i}", "filesystem__list_directory", {})]) for i in range(50)]
    run = await run_agent(get_task("fs_summarize_notes"), _ScriptedBackend(loop), max_steps=4)
    assert run.stop_reason == "max_steps" and run.steps == 4 and len(run.calls) == 4


# ------------------------------------------- Claude backend (fake client)

class _FakeMessages:
    def __init__(self, responses: list[Any]) -> None:
        self.responses, self.requests = responses, []

    async def create(self, **kwargs: Any) -> Any:
        # Snapshot messages: the backend keeps appending to the same list.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def _fake_client(responses: list[Any]) -> tuple[Any, _FakeMessages]:
    msgs = _FakeMessages(responses)
    return SimpleNamespace(beta=SimpleNamespace(messages=msgs)), msgs


async def test_claude_backend_tool_loop_with_fake_client() -> None:
    tool_use = SimpleNamespace(type="tool_use", id="toolu_1", name="filesystem__read_file",
                               input={"path": "notes.txt"})
    client, fake = _fake_client([
        SimpleNamespace(stop_reason="tool_use", content=[tool_use], usage=None),
        SimpleNamespace(stop_reason="end_turn", usage=None,
                        content=[SimpleNamespace(type="text", text="Notes mention a Thursday sync.")]),
    ])
    llm = ClaudeLLM(model="claude-opus-5-5", effort="low", client=client)
    run = await run_agent(get_task("fs_summarize_notes"), llm)

    assert [(c.tool, c.arguments) for c in run.calls] == [("read_file", {"path": "notes.txt"})]
    assert run.final_text == "Notes mention a Thursday sync." and run.stop_reason == "end_turn"

    first, second = fake.requests
    assert first["model"] == "claude-opus-5-5"
    assert first["output_config"] == {"effort": "low"}
    assert first["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in first["betas"]
    assert "thinking" not in first  # adaptive is implicit on this model
    tool_names = {t["name"] for t in first["tools"]}
    assert "filesystem__read_file" in tool_names
    assert first["tools"][0]["input_schema"]["type"] == "object"
    assert first["messages"] == [{"role": "user", "content": get_task("fs_summarize_notes").prompt}]

    # Turn 2 = original prompt, assistant content verbatim, then the tool_result.
    assert second["messages"][1] == {"role": "assistant", "content": [tool_use]}
    result_block = second["messages"][2]["content"][0]
    assert result_block["tool_use_id"] == "toolu_1" and result_block["is_error"] is False
    assert "Lab notes" in result_block["content"]


async def test_claude_refusal_ends_run_cleanly() -> None:
    client, _ = _fake_client([SimpleNamespace(stop_reason="refusal", content=[], usage=None)])
    run = await run_agent(get_task("fs_summarize_notes"), ClaudeLLM(client=client))
    assert run.stop_reason == "refusal" and run.calls == []


@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM") != "1", reason="set RUN_LIVE_LLM=1 to call the real API")
async def test_live_claude() -> None:
    run = await run_agent(get_task("fs_summarize_notes"), ClaudeLLM(effort="low"))
    assert run.stop_reason in ("end_turn", "refusal")
    assert any(c.tool == "read_file" for c in run.calls)


def test_request_params_match_model_capabilities() -> None:
    client, _ = _fake_client([])
    opus = ClaudeLLM(model="claude-opus-5-5", client=client).request_kwargs()
    assert opus["output_config"] == {"effort": "medium"} and opus["fallbacks"] == "default"
    haiku = ClaudeLLM(model="claude-haiku-4-5", client=client).request_kwargs()
    assert "output_config" not in haiku and "fallbacks" not in haiku and "betas" not in haiku
    sonnet = ClaudeLLM(model="claude-sonnet-5-5", client=client).request_kwargs()
    assert "output_config" in sonnet and sonnet["fallbacks"] == "default"


def test_usage_summary_estimates_cost() -> None:
    client, _ = _fake_client([])
    llm = ClaudeLLM(model="claude-opus-5-5", client=client)
    llm.usage = [SimpleNamespace(input_tokens=1_000_000, output_tokens=100_000), None]
    u = llm.usage_summary()
    assert (u["input_tokens"], u["output_tokens"]) == (1_000_000, 100_000)
    assert u["est_cost_usd"] == 6.0  # $4 input + $2 output
