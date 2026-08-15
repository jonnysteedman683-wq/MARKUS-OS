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
from urllib.parse import urlparse, parse_qs

repo_root = Path.cwd()
sys.path.insert(0, str(repo_root))

from markus_server import (
    kernel,
    prompt_matrix,
    Handler,
    sse_subscribers,
    sse_lock,
    broadcast_sse_event,
)

MARKUS_HOST = os.environ.get("MARKUS_HOST", "0.0.0.0")
MARKUS_HTTP_PORT = int(os.environ.get("MARKUS_PORT", "8128"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("MARKUS.OrbShell")

class OrbShellHandler(Handler):
    """Override routes to serve orb shell UI."""

    def do_GET(self):
        if self.path in ("/", "/orb"):
            self._serve_orb_html()
        elif self.path == "/api/bootstrap":
            self._send_json(200, {
                "persona": "superagent",
                "memory_layers": ["L1", "L1.5", "L2", "L3"],
                "cortex_entries": len(kernel.memory.l2_working_memory),
                "disable_orb": os.environ.get("DISABLE_ORB", "0") == "1"
            })
        elif self.path.startswith("/api/chat"):
            self._handle_chat()
        elif self.path.startswith("/api/repl"):
            self._handle_repl()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/repl"):
            self._handle_repl()
        elif self.path.startswith("/api/chat"):
            self._handle_chat_post()
        else:
            self._send_json(404, {"error": "Not Found"})

    def _handle_chat_post(self):
        """Handle POST-based chat for batch scripting."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                prompt = data.get("query", "")
            except json.JSONDecodeError:
                prompt = body.strip()
        else:
            prompt = ""

        if not prompt:
            self._send_json(400, {"error": "No query provided"})
            return

        synth_result = prompt_matrix.synthesize_prompt(user_input=prompt, persona="AUTONOMOUS_CODER")
        response = {
            "reply": prompt,
            "exemplars": len(synth_result.exemplars),
            "tokens": synth_result.token_estimate
        }
        broadcast_sse_event("chat_reply", response)
        self._send_json(200, response)

    def _serve_orb_html(self):
        filepath = repo_root / "markus_orb_shell.html"
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self._send_json(404, {"error": "Orb shell UI not found"})

    def _handle_chat(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        prompt = params.get("q", [""])[0]

        synth_result = prompt_matrix.synthesize_prompt(
            user_input=prompt,
            persona="AUTONOMOUS_CODER"
        )
        response = {
            "reply": prompt,
            "exemplars": len(synth_result.exemplars),
            "tokens": synth_result.token_estimate
        }
        broadcast_sse_event("chat_reply", response)
        self._send_json(200, response)

    def _handle_repl(self):
        """CLI batch endpoint — accepts piped input via POST body or ?q= query."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode('utf-8')
            prompt = body.strip()
        else:
            query = urlparse(self.path).query
            params = parse_qs(query)
            prompt = params.get("q", [""])[0]

        if not prompt:
            self._send_json(400, {"error": "No input provided. Use POST body or ?q=<query>"})
            return

        synth_result = prompt_matrix.synthesize_prompt(
            user_input=prompt,
            persona="AUTONOMOUS_CODER"
        )
        response = {
            "input": prompt,
            "reply": prompt,
            "exemplars": len(synth_result.exemplars),
            "tokens": synth_result.token_estimate,
            "timestamp": int(time.time())
        }
        broadcast_sse_event("repl_reply", response)
        self._send_json(200, response)

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    server = ThreadingHTTPServer((MARKUS_HOST, MARKUS_HTTP_PORT), OrbShellHandler)
    logger.info(f"MARKUS Orb Shell running at http://{MARKUS_HOST}:{MARKUS_HTTP_PORT}/orb")
    server.serve_forever()
