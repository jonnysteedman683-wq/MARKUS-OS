#!/usr/bin/env python3
"""MARKUS OS Standalone Orb Shell Bootstrap
Entry point for the floating holographic orb UI."""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from http.server import ThreadingHTTPServer

repo_root = Path.cwd()
sys.path.insert(0, str(repo_root))

from markus_kernel import MarkusKernel
from markus_server import (
    MARKUS_HTTP_PORT,
    sse_subscribers,
    broadcast_sse_event,
    MarkusRequestHandler as Handler
)
from markus_prompt_matrix import MarkusPromptSynthesisMatrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MARKUS-OrbShell] %(message)s"
)

# Initialize kernel and subsystems directly in standalone mode
_kernel = MarkusKernel()
_kernel.memory.db.set_register("OS_BOOT_COUNT", _kernel.memory.db.get_register("OS_BOOT_COUNT", 0) + 1)
_kernel.memory.commit_thought(f"boot_{int(time.time())}", "OrbShell", "Standalone kernel initialized", {"boot_phase": "standalone"})

prompt_matrix = MarkusPromptSynthesisMatrix(db=_kernel.memory.db)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", MARKUS_HTTP_PORT), Handler)
    logging.info(f"MARKUS Orb Shell running at http://localhost:{MARKUS_HTTP_PORT}/orb")
    server.serve_forever()
