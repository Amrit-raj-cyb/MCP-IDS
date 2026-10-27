"""Logging setup for MCP server processes.

Called from each server's ``main()``, never at import time: other code (the
orchestrator, tests) imports server modules for their constants, and a
module-level ``logging.basicConfig`` would take over *their* logging.
Servers log to stderr only, because stdout carries the JSON-RPC protocol.
"""

from __future__ import annotations

import logging
import os
import sys


def configure_server_logging(tag: str) -> None:
    # force=True: the MCP SDK already installed its own handler when the server
    # object was created at import time; replace it so LOG_LEVEL and our format apply.
    logging.basicConfig(stream=sys.stderr, level=os.getenv("LOG_LEVEL", "INFO"), force=True,
                        format=f"%(asctime)s %(levelname)s [{tag}] %(message)s")
