"""Registry of MCP servers available in the lab.

One place that says *how to launch* each server. The agent (Phase 2), the
logging proxy (Phase 3) and the orchestrator (Phase 5) all read from here, so a
server is added to the lab by adding one entry.

Each server is launched as ``python -m <module>`` over stdio, using the same
interpreter that runs the caller (so the venv / container Python is reused).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ServerSpec:
    server_id: str
    module: str
    kind: str  # "benign" | "attack"
    description: str
    env: dict[str, str] = field(default_factory=dict)
    # Name the server presents on the wire and in logs. An attack twin uses
    # its benign twin's name, so the server identity itself is no giveaway;
    # the registry key (server_id) stays the ground truth in the manifest.
    wire_id: str | None = None

    @property
    def log_id(self) -> str:
        return self.wire_id or self.server_id

    def command(self, proxied: bool = False) -> tuple[str, list[str]]:
        """Executable and args to spawn this server over stdio.

        With ``proxied=True`` the logging proxy is spawned instead, and it
        spawns the real server: ``python -m proxy.proxy --server-id X -- python -m <module>``.
        """
        direct = [sys.executable, "-m", self.module]
        if not proxied:
            return direct[0], direct[1:]
        return sys.executable, ["-m", "proxy.proxy", "--server-id", self.log_id, "--", *direct]


SERVERS: dict[str, ServerSpec] = {
    "filesystem": ServerSpec(
        server_id="filesystem",
        module="servers.benign.filesystem.server",
        kind="benign",
        description="Sandboxed read/write/list/search of synthetic text files",
    ),
    "sqlite": ServerSpec(
        server_id="sqlite",
        module="servers.benign.sqlite.server",
        kind="benign",
        description="Read-only queries + controlled inserts on a synthetic shop database",
    ),
    "web_fetch": ServerSpec(
        server_id="web_fetch",
        module="servers.benign.web_fetch.server",
        kind="benign",
        description="Fetch pages from the allow-listed synthetic test site",
    ),
    "writing_assistant": ServerSpec(
        server_id="writing_assistant",
        module="servers.benign.writing_assistant.server",
        kind="benign",
        description="Summaries and translations written by the client's model via MCP sampling",
    ),
    "helpdesk": ServerSpec(
        server_id="helpdesk",
        module="servers.benign.helpdesk.server",
        kind="benign",
        description="Ticket triage and reply drafts written by the client's model via MCP sampling",
    ),
    "calculator": ServerSpec(
        server_id="calculator",
        module="servers.benign.calculator.server",
        kind="benign",
        description="Arithmetic / unit conversion; clean twin of the poisoned calculator",
    ),
    # ----------------------------------------------- inert attack simulations
    "calculator_poisoned": ServerSpec(
        server_id="calculator_poisoned",
        module="servers.attack.poisoned_tool.server",
        kind="attack",
        description="INERT poisoned-tool simulation: calculator with injected tool metadata",
        wire_id="calculator",
    ),
    "shadowing_control": ServerSpec(
        server_id="shadowing_control",
        module="servers.benign.shadowing_control.server",
        kind="benign",
        description="Static harmless tool-catalog fixture used as a shadowing control",
    ),
    "shadowing_sim": ServerSpec(
        server_id="shadowing_sim",
        module="servers.attack.shadowing.server",
        kind="attack",
        description="Inert cross-server metadata-overlap simulation",
        wire_id="shadowing_control",
    ),
    "sampling_control": ServerSpec(
        server_id="sampling_control",
        module="servers.benign.sampling_control.server",
        kind="benign",
        description="Static harmless sampling-protocol control tool",
    ),
    "sampling_injector": ServerSpec(
        server_id="sampling_injector",
        module="servers.attack.sampling_injector.server",
        kind="attack",
        description="Inert server-initiated sampling request simulation",
        wire_id="sampling_control",
    ),
}


def get_server(server_id: str) -> ServerSpec:
    try:
        return SERVERS[server_id]
    except KeyError:
        raise KeyError(f"Unknown server '{server_id}'. Known: {sorted(SERVERS)}") from None
