"""Alternative wordings of benign tool descriptions (opt-in).

Why
---
Every benign session used to advertise exactly the same tool descriptions, so
*any* change in ``tools/list`` text separated benign from attack sessions (the
"closed-world" problem in docs/ml.md). Real MCP ecosystems contain many
differently written, entirely benign descriptions. This module provides three
alternative wordings per tool for the filesystem, SQLite and web-fetch servers
(and, since lab 0.9.1, the benign sampling servers writing_assistant and
helpdesk), in different documentation styles:

1. terse API-reference style,
2. friendly prose (some second-person "you", as real docs often use),
3. structured ``Args:`` / ``Returns:`` style with an example.

How
---
``MCP_DESCRIPTION_VARIANT`` (set per session by the orchestrator, default
``0``) selects the wording. Variant ``0`` returns ``None``, so the server keeps
its docstring and traffic is byte-identical to earlier lab versions.

Only servers **without an attack twin** vary. The calculator, shadowing
control and sampling control keep fixed text, because their twins must differ
only in the simulated metadata.
"""

from __future__ import annotations

import os

N_VARIANTS = 3  # alternative wordings per tool (variant 0 = original docstring)

VARIANTS: dict[str, dict[str, tuple[str, str, str]]] = {
    "filesystem": {
        "list_directory": (
            "List entries of a workspace directory; directories carry a trailing '/'.",
            "Shows what is inside a folder of the workspace. You can pass a relative path such as "
            "'documents'; leave it as '.' for the top level. Folder names end with a slash.",
            "List a directory.\n\nArgs:\n  path: workspace-relative directory (default '.').\n"
            "Returns:\n  One entry per line, folders first. Example: 'data/\\nnotes.txt'.",
        ),
        "read_file": (
            "Return the text content of a workspace file (UTF-8).",
            "Opens a text file from the workspace and returns everything in it. Paths are relative "
            "to the workspace root, for example 'report.txt' or 'data/sample.csv'.",
            "Read a text file.\n\nArgs:\n  path: workspace-relative file path.\n"
            "Returns:\n  The file content as a string. Large files are rejected.",
        ),
        "write_file": (
            "Write text to a workspace file, creating or replacing it.",
            "Saves the text you give it into a file in the workspace. If the file already exists it "
            "is replaced; missing folders are created automatically.",
            "Write a text file.\n\nArgs:\n  path: workspace-relative file path.\n  content: text to store.\n"
            "Returns:\n  A short confirmation with the number of bytes written.",
        ),
        "search_files": (
            "Find workspace files whose name contains a substring (case-insensitive).",
            "Looks through the workspace for files with a matching name. The match ignores upper and "
            "lower case, so 'Sample' also finds 'sample.csv'. You can limit the search to a folder.",
            "Search file names.\n\nArgs:\n  pattern: substring to look for.\n  path: folder to search "
            "(default '.').\nReturns:\n  Matching paths, one per line, or '(no matches)'.",
        ),
    },
    "sqlite": {
        "list_tables": (
            "Enumerate database tables and their row counts.",
            "Gives an overview of the shop database: every table together with how many rows it "
            "currently holds. A good first step before writing a query.",
            "List tables.\n\nArgs:\n  (none)\nReturns:\n  JSON object mapping table name to row count, "
            "e.g. {\"tables\": {\"users\": 30}}.",
        ),
        "describe_table": (
            "Return column metadata (name, type, nullability, primary key) for one table.",
            "Explains how a table is structured, listing each column with its type and whether it "
            "can be empty. Useful when you are not sure about column names.",
            "Describe a table.\n\nArgs:\n  table: table name, e.g. 'orders'.\nReturns:\n  JSON with one "
            "entry per column: name, type, not_null, primary_key.",
        ),
        "read_query": (
            "Execute a single read-only SELECT statement; at most 200 rows are returned.",
            "Runs a SELECT query against the shop database and returns the matching rows. Only reading "
            "is allowed, and very large results are cut off after 200 rows.",
            "Query the database.\n\nArgs:\n  sql: one SELECT statement.\nReturns:\n  JSON with columns, "
            "rows, row_count and truncated. Example: SELECT name FROM products LIMIT 3.",
        ),
        "insert_row": (
            "Insert one row into orders or logs from a column-to-value mapping.",
            "Adds a new record to either the orders table or the logs table. Pass the values as a "
            "mapping from column name to value; the new row id is returned.",
            "Insert a row.\n\nArgs:\n  table: 'orders' or 'logs'.\n  values: mapping of column -> value.\n"
            "Returns:\n  JSON with the table name and the id of the inserted row.",
        ),
    },
    "web_fetch": {
        "fetch": (
            "Retrieve a page from the lab website and return it as plain text; long pages are paged "
            "with start_index.",
            "Downloads a page from the lab's test website and turns the HTML into readable text. If a "
            "page is long you get it in parts: call it again with the start_index shown at the end.",
            "Fetch a web page.\n\nArgs:\n  url: page address on the lab site.\n  max_length: characters "
            "per call (default 5000).\n  start_index: offset for the next part.\nReturns:\n  Page title "
            "and text; a note with the next start_index if truncated.",
        ),
    },
    # Benign servers that use MCP sampling (lab 0.9.1). Their requests to the client's model are
    # stated openly in the descriptions, as real sampling servers document them.
    "writing_assistant": {
        "summarize_text": (
            "Summarize text in 1-5 sentences via the client model (sampling/createMessage).",
            "Gives you a short summary of any text. The server has no model of its own, so it asks "
            "your client's model to write the summary and passes the answer back.",
            "Summarize text.\n\nArgs:\n  text: the text to shorten.\n  max_sentences: 1-5 (default 2).\n"
            "Returns:\n  The summary written by the client's model. Example: 'Sales rose 4% in May.'",
        ),
        "translate_text": (
            "Translate text into French, German, Spanish or Hindi via the client model.",
            "Translates a passage for you into French, German, Spanish or Hindi. The translation is "
            "written by your client's model, which the server asks through MCP sampling.",
            "Translate text.\n\nArgs:\n  text: source text.\n  target_language: French, German, Spanish "
            "or Hindi.\nReturns:\n  The translated text only.",
        ),
    },
    "helpdesk": {
        "classify_ticket": (
            "Categorize a support ticket: billing, shipping, account or other (client-model sampling).",
            "Reads a customer's support ticket and tells you whether it is about billing, shipping, "
            "their account or something else. The client's model makes the call.",
            "Triage a ticket.\n\nArgs:\n  ticket: the customer's message.\nReturns:\n  One of billing, "
            "shipping, account, other. Example: 'shipping'.",
        ),
        "draft_reply": (
            "Draft a friendly or formal reply to a customer question via the client model.",
            "Writes a first draft of an answer to a customer's question, in a friendly or formal tone, "
            "for a support agent to check before sending. The client's model writes it.",
            "Draft a reply.\n\nArgs:\n  question: the customer's question.\n  tone: friendly or formal "
            "(default friendly).\nReturns:\n  A short reply draft; it never promises refunds or dates.",
        ),
    },
}


def variant_index() -> int:
    try:
        v = int(os.getenv("MCP_DESCRIPTION_VARIANT", "0"))
    except ValueError:
        return 0
    return v if 0 <= v <= N_VARIANTS else 0


def describe(server: str, tool: str) -> str | None:
    """Description for ``tool`` under the current variant (``None`` = keep docstring)."""
    v = variant_index()
    if v == 0:
        return None
    return VARIANTS[server][tool][v - 1]
