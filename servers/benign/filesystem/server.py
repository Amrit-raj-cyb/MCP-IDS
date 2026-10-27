"""Benign Filesystem MCP server (sandboxed).

Simple explanation
------------------
This MCP server lets an AI agent list, read, write, and search text files.
It is one of the *benign* servers of the lab: its only job is to produce
realistic, normal MCP traffic (tools/list, tools/call, results, errors).

Safety
------
Every path the client sends is resolved against a single sandbox directory
(``MCP_FS_SANDBOX``, default ``./sandbox``). Any path that resolves outside the
sandbox -- e.g. ``../../etc/passwd``, an absolute path, or a symlink that points
out -- is rejected with a tool error. Reads and writes are size-limited.

Transport
---------
stdio. IMPORTANT: stdout carries JSON-RPC, so this module must never ``print``.
Diagnostics go to stderr through :mod:`logging`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from common.descriptions import describe
from common.logsetup import configure_server_logging
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

SERVER_ID = "filesystem"
MAX_READ_BYTES = 256 * 1024   # 256 KiB: plenty for lab files, bounds response size
MAX_WRITE_BYTES = 64 * 1024   # 64 KiB
MAX_SEARCH_RESULTS = 100

log = logging.getLogger(__name__)


def sandbox_root() -> Path:
    """Return the absolute, symlink-resolved sandbox directory."""
    root = Path(os.getenv("MCP_FS_SANDBOX", "sandbox")).resolve()
    if not root.is_dir():
        raise RuntimeError(f"Sandbox directory does not exist: {root}")
    return root


def resolve_in_sandbox(relative_path: str, root: Path | None = None) -> Path:
    """Map a client-supplied path to a real path *inside* the sandbox.

    ``Path.resolve()`` collapses ``..`` and follows symlinks, so checking the
    resolved result with ``is_relative_to`` blocks traversal, absolute paths
    (joining an absolute path replaces the root), and symlink escapes.
    """
    root = root or sandbox_root()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ToolError(f"Access denied: '{relative_path}' is outside the sandbox")
    return candidate


def _rel(path: Path, root: Path) -> str:
    """Sandbox-relative, forward-slash path (stable across Windows/Linux)."""
    return path.relative_to(root).as_posix() or "."


mcp = MCPServer(
    name="lab-filesystem",
    instructions="Read, write, list and search text files in the lab sandbox directory.",
    version="0.1.0",
)


@mcp.tool(description=describe("filesystem", "list_directory"))
def list_directory(path: str = ".") -> str:
    """List files and folders in a sandbox directory. Folders end with '/'."""
    root = sandbox_root()
    target = resolve_in_sandbox(path, root)
    if not target.is_dir():
        raise ToolError(f"Not a directory: '{path}'")
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = [p.name + ("/" if p.is_dir() else "") for p in entries]
    log.info("list_directory %s -> %d entries", path, len(lines))
    return "\n".join(lines) if lines else "(empty directory)"


@mcp.tool(description=describe("filesystem", "read_file"))
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the sandbox."""
    root = sandbox_root()
    target = resolve_in_sandbox(path, root)
    if not target.is_file():
        raise ToolError(f"File not found: '{path}'")
    if target.stat().st_size > MAX_READ_BYTES:
        raise ToolError(f"File too large (limit {MAX_READ_BYTES} bytes): '{path}'")
    log.info("read_file %s", path)
    return target.read_text(encoding="utf-8", errors="replace")


@mcp.tool(description=describe("filesystem", "write_file"))
def write_file(path: str, content: str) -> str:
    """Create or overwrite a UTF-8 text file in the sandbox."""
    root = sandbox_root()
    target = resolve_in_sandbox(path, root)
    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        raise ToolError(f"Content too large (limit {MAX_WRITE_BYTES} bytes)")
    if target.is_dir():
        raise ToolError(f"Path is a directory: '{path}'")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    log.info("write_file %s (%d bytes)", path, len(data))
    return f"Wrote {len(data)} bytes to {_rel(target, root)}"


@mcp.tool(description=describe("filesystem", "search_files"))
def search_files(pattern: str, path: str = ".") -> str:
    """Find files whose name contains `pattern` (case-insensitive)."""
    root = sandbox_root()
    base = resolve_in_sandbox(path, root)
    if not base.is_dir():
        raise ToolError(f"Not a directory: '{path}'")
    needle = pattern.lower()
    matches: list[str] = []
    for p in sorted(base.rglob("*")):
        # rglob can follow into symlinked dirs; re-check every hit.
        if p.is_file() and needle in p.name.lower() and p.resolve().is_relative_to(root):
            matches.append(_rel(p, root))
            if len(matches) >= MAX_SEARCH_RESULTS:
                break
    log.info("search_files %r in %s -> %d", pattern, path, len(matches))
    return "\n".join(matches) if matches else "(no matches)"


def main() -> None:
    configure_server_logging("fs-server")
    log.info("starting; sandbox=%s session=%s", sandbox_root(), os.getenv("MCP_SESSION_ID", "-"))
    mcp.run("stdio")


if __name__ == "__main__":
    main()
