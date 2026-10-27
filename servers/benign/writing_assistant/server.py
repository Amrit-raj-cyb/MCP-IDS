"""Benign writing assistant that *legitimately* uses MCP sampling.

Simple explanation
------------------
Many real MCP servers do not run a language model of their own. When a tool
needs text written (a summary, a translation) they ask the *client's* model
through ``sampling/createMessage`` and return what it wrote. That is exactly
what this server does, with ordinary, openly stated requests.

Why it exists in the lab
------------------------
Before lab 0.9.1 the only server that ever sent ``sampling/createMessage`` was
the inert sampling-injection simulation, so "a server asked the client to
sample" alone meant *attack*. Real ecosystems contain benign samplers, and a
detector must tell them apart by *what* is asked, not by *whether* sampling
is used.

The lab client answers every sampling request with the same fixed local
callback (no model, no tools), whatever server asks, so the reply itself is no
giveaway either.
"""
from __future__ import annotations

from mcp import types
from mcp.server.mcpserver import Context, MCPServer

from common.descriptions import describe
from common.logsetup import configure_server_logging

LANGUAGES = ("French", "German", "Spanish", "Hindi")

server = MCPServer("lab-writing-assistant", version="0.1.0",
                   instructions="Summaries and translations written by the client's own model.")


async def _ask_client_model(ctx: Context, prompt: str, system_prompt: str, max_tokens: int) -> str:
    """One sampling request to the client; returns the text it wrote."""
    result = await ctx.request_context.session.create_message(
        messages=[types.SamplingMessage(role="user", content=types.TextContent(text=prompt))],
        max_tokens=max_tokens, system_prompt=system_prompt, include_context="none",
    )
    return result.content.text if isinstance(result.content, types.TextContent) else ""


@server.tool(description=describe("writing_assistant", "summarize_text"))
async def summarize_text(text: str, ctx: Context, max_sentences: int = 2) -> str:
    """Summarize a piece of text in a few sentences, using the client's language model."""
    if not text.strip():
        raise ValueError("text is empty")
    n = min(max(int(max_sentences), 1), 5)
    return await _ask_client_model(
        ctx, f"Summarize the following text in at most {n} sentences. Keep names and numbers as they are.\n\n{text}",
        "You write short, neutral summaries.", 40 * n)


@server.tool(description=describe("writing_assistant", "translate_text"))
async def translate_text(text: str, target_language: str, ctx: Context) -> str:
    """Translate text into French, German, Spanish or Hindi, using the client's language model."""
    if target_language not in LANGUAGES:
        raise ValueError(f"unsupported language {target_language!r}; choose one of {', '.join(LANGUAGES)}")
    return await _ask_client_model(
        ctx, f"Translate the following text into {target_language}. Reply with the translation only.\n\n{text}",
        "You are a careful translator.", 200)


def main() -> None:
    configure_server_logging("writing-assistant")
    server.run("stdio")


if __name__ == "__main__":
    main()
