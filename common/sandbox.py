"""Per-session sandbox copies.

``sandbox/`` in the repository is the *seed*: it must never change, otherwise
session N would see files written by session N-1 and the dataset would not be
reproducible. Every agent session therefore works on a fresh temporary copy
that is deleted afterwards.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from common.registry import PROJECT_ROOT

SEED_SANDBOX = PROJECT_ROOT / "sandbox"


@contextmanager
def fresh_sandbox(seed: Path = SEED_SANDBOX) -> Iterator[Path]:
    """Yield the path of a throw-away copy of the seed sandbox."""
    with tempfile.TemporaryDirectory(prefix="mcp-ids-sandbox-") as tmp:
        dest = Path(tmp) / "sandbox"
        shutil.copytree(seed, dest)
        yield dest.resolve()
