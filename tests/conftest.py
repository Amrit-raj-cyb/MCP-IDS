"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Send every test's proxy logs to a temp dir, never to data/raw/."""
    d = tmp_path / "logs"
    monkeypatch.setenv("MCP_LOG_DIR", str(d))
    return d
