#!/usr/bin/env python3
"""MARKUS OS Standalone Orb Shell Bootstrap
Entry point for the floating holographic orb UI."""

import json
import logging
import os
import sys
import time
from pathlib import Path
from http.server import ThreadingHTTPServer

repo_root = Path.cwd()
sys.path.insert(0, str(repo_root))

import markus_kernel  # This initializes `kernel` as module-level variable
_kernel = markus_kernel.kernel  # Access the initialized kernel instance

from markus_server import (
    MARKUS_HTTP_PORT,
    sse_subscribers,
    broadcast_sse_event,
    Handler
)
from markus_prompt_matrix import MarkusPromptSynthesisMatrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MARKUS-OrbShell] %(message)s"
)

prompt_matrix = MarkusPromptSynthesisMatrix(db=_kernel.memory.db)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", MARKUS_HTTP_PORT), Handler)
    logging.info(f"MARKUS Orb Shell running at http://localhost:{MARKUS_HTTP_PORT}/orb")
    server.serve_forever()
