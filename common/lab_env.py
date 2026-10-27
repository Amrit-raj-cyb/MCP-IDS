"""Prepare the per-session lab environment for a set of MCP servers.

Every session gets *fresh, isolated* resources so that sessions are
independent and reproducible:

=============  ========================  =====================================
server         env var                   resource
=============  ========================  =====================================
filesystem     ``MCP_FS_SANDBOX``        temp copy of ``sandbox/``
sqlite         ``MCP_SQLITE_DB``         temp database built from a fixed seed
web_fetch      ``MCP_WEB_BASE_URL``      the synthetic test site
=============  ========================  =====================================

For ``web_fetch``: if ``MCP_WEB_BASE_URL`` is already set (Docker sets it to
the ``testweb`` container) that site is used; otherwise one shared local site is
started per process on 127.0.0.1:18080 (fixed port => reproducible URLs).

Values passed in ``overrides`` win (tests use this to pin resources).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from common.sandbox import fresh_sandbox

DB_SEED = 1234


@contextmanager
def fresh_database(seed: int = DB_SEED) -> Iterator[Path]:
    from servers.benign.sqlite.seed_db import build_database
    with tempfile.TemporaryDirectory(prefix="mcp-ids-db-") as tmp:
        yield build_database(Path(tmp) / "dummy.db", seed=seed)


@contextmanager
def lab_environment(server_ids: list[str] | tuple[str, ...],
                    overrides: dict[str, str] | None = None) -> Iterator[dict[str, str]]:
    """Yield the env vars the given servers need; clean everything up after."""
    env = dict(overrides or {})
    with ExitStack() as stack:
        if "filesystem" in server_ids and "MCP_FS_SANDBOX" not in env:
            env["MCP_FS_SANDBOX"] = str(stack.enter_context(fresh_sandbox()))
        if "sqlite" in server_ids and "MCP_SQLITE_DB" not in env:
            env["MCP_SQLITE_DB"] = str(stack.enter_context(fresh_database()))
        if "web_fetch" in server_ids and "MCP_WEB_BASE_URL" not in env:
            if os.getenv("MCP_WEB_BASE_URL"):
                env["MCP_WEB_BASE_URL"] = os.environ["MCP_WEB_BASE_URL"]
            else:
                from servers.benign.web_fetch.testsite import shared_site_url
                env["MCP_WEB_BASE_URL"] = shared_site_url()
        yield env
