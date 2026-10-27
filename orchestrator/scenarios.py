"""Scenarios: what one lab session is (task + servers + ground-truth label).

Simple explanation
------------------
A *task* is what the user asks for. A *scenario* adds the experimental
setup: which MCP servers are mounted and what the correct label is. The same
task can appear in several scenarios. For example, ``fs_summarize_notes``
with only the filesystem server, or with all three benign servers mounted
but only one used, as real users often have many servers connected.

Benign scenarios are generated from the task list. Attack scenarios are
registered by the attack phases (6-8) with :func:`register`.

Scenario ids: ``benign:<task_id>``, ``benign:<task_id>:all_servers`` and, for
attacks, ``attack:<family>:<task_id>[:all_servers]``.

Attack scenarios are built as **twins** of benign scenarios: same task, same
mounted servers, but one benign server swapped for its attack twin. The pair
differs only in what the attack adds, which makes comparisons fair
(``Scenario.twin_of`` names the benign partner).
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.tasks import TASKS, get_task
from common.registry import SERVERS

BENIGN_SERVERS = ("filesystem", "sqlite", "web_fetch", "calculator",
                  "shadowing_control", "sampling_control")

# attack family -> (benign server it replaces, its attack twin)
ATTACK_TWINS = {
    "poisoned_tool": ("calculator", "calculator_poisoned"),
    "shadowing": ("shadowing_control", "shadowing_sim"),
    "sampling_injection": ("sampling_control", "sampling_injector"),
}
# Benign-only tasks: no attack twins are registered for them. The lab-0.9.1 tasks exist to put
# *benign* sampling traffic (writing_assistant, helpdesk) into the data.
BENIGN_ONLY_TASKS = frozenset({"assist_summarize_text", "assist_translate_notes", "helpdesk_triage_ticket",
                               "helpdesk_order_reply"})


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    task_id: str
    servers: tuple[str, ...]
    label: str = "benign"                 # "benign" | "attack"
    attack_family: str | None = None
    description: str = ""
    twin_of: str | None = None             # attack scenario: its benign partner

    @property
    def is_attack(self) -> bool:
        return self.label == "attack"


SCENARIOS: dict[str, Scenario] = {}


def register(scenario: Scenario) -> Scenario:
    if scenario.scenario_id in SCENARIOS:
        raise ValueError(f"duplicate scenario id {scenario.scenario_id}")
    get_task(scenario.task_id)  # fail fast on unknown tasks
    SCENARIOS[scenario.scenario_id] = scenario
    return scenario


def _register_benign() -> None:
    for task in TASKS.values():
        register(Scenario(f"benign:{task.task_id}", task.task_id, task.servers,
                          description=f"{task.task_id} with only the servers it needs"))
        if set(task.servers) != set(BENIGN_SERVERS):
            # Same task, every benign server mounted (extra servers unused).
            extra = tuple(s for s in BENIGN_SERVERS if s not in task.servers)
            register(Scenario(f"benign:{task.task_id}:all_servers", task.task_id,
                              task.servers + extra,
                              description=f"{task.task_id} with all benign servers mounted"))


def _register_attack_twins(family: str) -> None:
    benign_server, attack_server = ATTACK_TWINS[family]
    for b in [s for s in SCENARIOS.values() if s.label == "benign" and benign_server in s.servers
              and s.task_id not in BENIGN_ONLY_TASKS]:
        suffix = b.scenario_id.removeprefix("benign:")
        servers = tuple(attack_server if s == benign_server else s for s in b.servers)
        register(Scenario(f"attack:{family}:{suffix}", b.task_id, servers, label="attack",
                          attack_family=family, twin_of=b.scenario_id,
                          description=f"twin of {b.scenario_id} with {attack_server}"))


_register_benign()
for _family in ATTACK_TWINS:
    _register_attack_twins(_family)


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError:
        raise KeyError(f"Unknown scenario '{scenario_id}'. "
                       f"Use 'python -m orchestrator.main list' to see all.") from None


def select(spec: str) -> list[Scenario]:
    """Resolve a selection: a group (``benign``, ``attack``, ``all``) or a
    comma-separated list of scenario ids."""
    if spec == "all":
        return list(SCENARIOS.values())
    if spec in ("benign", "attack"):
        return [s for s in SCENARIOS.values() if s.label == spec]
    return [get_scenario(s.strip()) for s in spec.split(",") if s.strip()]


def check_scenarios() -> list[str]:
    """Consistency problems in the registry (empty list = OK)."""
    problems = []
    for s in SCENARIOS.values():
        for server in s.servers:
            if server not in SERVERS:
                problems.append(f"{s.scenario_id}: unknown server {server}")
        # An attack twin (same wire name, same tools) satisfies its benign twin's role.
        provided = {SERVERS[x].log_id for x in s.servers if x in SERVERS}
        missing = set(get_task(s.task_id).servers) - provided
        if missing:
            problems.append(f"{s.scenario_id}: task needs servers {sorted(missing)}")
        if s.is_attack and not s.attack_family:
            problems.append(f"{s.scenario_id}: attack scenario without attack_family")
        kinds = [SERVERS[x].kind for x in s.servers if x in SERVERS]
        if s.is_attack and "attack" not in kinds:
            problems.append(f"{s.scenario_id}: attack scenario without an attack server")
        if not s.is_attack and "attack" in kinds:
            problems.append(f"{s.scenario_id}: benign scenario mounts an attack server")
    return problems
