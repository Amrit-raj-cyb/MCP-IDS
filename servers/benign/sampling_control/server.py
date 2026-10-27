"""Static no-sampling control tool."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from common.logsetup import configure_server_logging

# Single source of truth for the tool result, shared with the sampling
# simulation so the twins return identical results; the only wire difference
# is the simulation's sampling/createMessage request (and its description).
RESULT = "Synthetic summary fixture: fixed lab text."

server = MCPServer("lab-sampling-control", version="0.1.0")


@server.tool(name="request_summary", description=(
    "Return a fixed local summary without asking the client to sample or generate text."
))
def request_summary() -> str:
    return RESULT


def main() -> None:
    configure_server_logging("sampling-control")
    server.run("stdio")


if __name__ == "__main__":
    main()
