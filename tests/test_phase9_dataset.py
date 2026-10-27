"""Dataset selection and non-overwrite checks for Phase 9."""
from __future__ import annotations

from orchestrator.scenarios import select
from scripts.generate_phase9 import paired_scenarios


def test_phase9_pairs_are_balanced_including_all_server_scenarios() -> None:
    pairs = paired_scenarios()
    assert len(pairs) % 2 == 0
    assert sum(s.label == "benign" for s in pairs) == sum(s.label == "attack" for s in pairs)
    assert {s.attack_family for s in pairs if s.label == "attack"} == {
        "poisoned_tool", "shadowing", "sampling_injection",
    }
    assert len(pairs) == 180
    assert any(s.scenario_id.endswith(":all_servers") for s in pairs)
    assert all(sessions == 30 for sessions in {
        family: sum(s.label == "attack" and s.attack_family == family for s in pairs)
        for family in ("poisoned_tool", "shadowing", "sampling_injection")
    }.values())
    benign = {s.scenario_id for s in pairs if s.label == "benign"}
    for scenario in pairs:
        if scenario.label == "attack":
            assert scenario.twin_of in benign
    assert len(select("benign")) > 0


def test_phase9_server_count_distribution_is_matched() -> None:
    pairs = paired_scenarios(15)
    benign = sorted(len(s.servers) for s in pairs if s.label == "benign")
    attacks = sorted(len(s.servers) for s in pairs if s.label == "attack")
    assert benign == attacks


def test_phase9_attack_scenarios_use_family_probe_tasks() -> None:
    expected = {"poisoned_tool": {"calc_add", "calc_temperature", "multi_order_share", "multi_region_share"},
                "shadowing": {"fs_shadowing_probe"}, "sampling_injection": {"fs_sampling_probe"}}
    for scenario in paired_scenarios():
        if scenario.label == "attack":
            assert scenario.task_id in expected[scenario.attack_family]
