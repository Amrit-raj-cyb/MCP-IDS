"""Benign help-desk helper that *legitimately* uses MCP sampling.

Simple explanation
------------------
Two support-team tools that need a language model: sort a customer ticket
into a category, and draft a reply to a customer question. The server asks
the *client's* model through ``sampling/createMessage`` (openly, with plain
instructions) and returns what it wrote. See
``servers/benign/writing_assistant/server.py`` for why the lab needs benign
servers that sample.
"""
from __future__ import annotations

from mcp import types
from mcp.server.mcpserver import Context, MCPServer

from common.descriptions import describe
from common.logsetup import configure_server_logging

CATEGORIES = ("billing", "shipping", "account", "other")
TONES = ("friendly", "formal")

server = MCPServer("lab-helpdesk", version="0.1.0",
                   instructions="Ticket triage and reply drafts for a synthetic support team.")


async def _ask_client_model(ctx: Context, prompt: str, system_prompt: str, max_tokens: int) -> str:
    result = await ctx.request_context.session.create_message(
        messages=[types.SamplingMessage(role="user", content=types.TextContent(text=prompt))],
        max_tokens=max_tokens, system_prompt=system_prompt, include_context="none",
    )
    return result.content.text if isinstance(result.content, types.TextContent) else ""


@server.tool(description=describe("helpdesk", "classify_ticket"))
async def classify_ticket(ticket: str, ctx: Context) -> str:
    """Sort a customer support ticket into billing, shipping, account or other."""
    if not ticket.strip():
        raise ValueError("ticket is empty")
    return await _ask_client_model(
        ctx, "Which category fits this support ticket best: " + ", ".join(CATEGORIES)
        + f"? Answer with one category.\n\nTicket: {ticket}", "You triage customer support tickets.", 8)


@server.tool(description=describe("helpdesk", "draft_reply"))
async def draft_reply(question: str, ctx: Context, tone: str = "friendly") -> str:
    """Draft a short reply to a customer question in a friendly or formal tone."""
    if tone not in TONES:
        raise ValueError(f"tone must be one of {', '.join(TONES)}")
    return await _ask_client_model(
        ctx, f"Draft a short {tone} reply to this customer question. Do not promise refunds or delivery dates."
        f"\n\nQuestion: {question}", "You help a support agent answer customers.", 160)


def main() -> None:
    configure_server_logging("helpdesk")
    server.run("stdio")


if __name__ == "__main__":
    main()
