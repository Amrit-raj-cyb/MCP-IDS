"""Inert MCP ``sampling/createMessage`` request generator.

The only outbound request contains a labelled synthetic test prompt. The
client has a deterministic local callback, not a real model, and returns a
fixed acknowledgement. No tools, files, network destinations, or real data
are involved.
"""
from __future__ import annotations

from mcp import types
from mcp.server.mcpserver import Context, MCPServer

from common.logsetup import configure_server_logging
from servers.benign.sampling_control.server import RESULT

SIMULATED_PROMPT = (
    "[LAB-SIMULATION] Please return the harmless test token LAB-SAMPLING-ACK. "
    "This is a protocol exercise only; do not call tools, access files, or use a network."
)

server = MCPServer("lab-sampling-control", version="0.1.0")


@server.tool(name="request_summary", description=(
    "[LAB-SIMULATION] Sends one controlled sampling/createMessage request containing "
    "a harmless synthetic prompt; the lab client returns a fixed acknowledgement."
))
async def request_summary(ctx: Context) -> str:
    """Send one bounded protocol request, then return the control's exact result."""
    await ctx.request_context.session.create_message(
        messages=[types.SamplingMessage(role="user", content=types.TextContent(text=SIMULATED_PROMPT))],
        max_tokens=24,
        system_prompt="Controlled MCP-IDS lab sampling callback; synthetic input only.",
        include_context="none",
    )
    # The callback's reply is visible on the wire (client_to_server response);
    # the tool result itself stays identical to the benign control's.
    return RESULT


def main() -> None:
    configure_server_logging("sampling-injector")
    server.run("stdio")


if __name__ == "__main__":
    main()
