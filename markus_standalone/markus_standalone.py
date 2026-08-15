#!/usr/bin/env python3
"""Orb shell bootstrap — serves floating orb UI + chat terminal."""

import asyncio
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

from markus_kernel import MarkusKernel
from markus_hermes_bridge import MarkusHermesBridge
from markus_sandbox import MarkusProcessSandbox
from markus_router import MarkusIntentRouter
from markus_task_dag import TaskDAG
from markus_dice_engine import MarkusDiceEngine
from markus_cortex_replication import MarkusCortexReplicator
from markus_ring_buffer import MarkusSharedRingBuffer
from markus_context_pruner import MarkusContextPruner
from markus_consensus import MarkusConsensusArbiter
from markus_adaptive_matrix import MarkusAdaptiveWeightMatrix
from markus_checkpoint import MarkusCheckpointManager
from markus_acoustic_synapse import MarkusAcousticSynapse
from markus_complexity_governor import MarkusComplexityGovernor
from markus_speculative_cache import MarkusSpeculativeCache
from markus_prompt_matrix import MarkusPromptSynthesisMatrix
from markus_capabilities import CapabilityRegistry
from markus_capability_synthesizer import MarkusCapabilitySynthesizer

MARKUS_HTTP_PORT = 8128

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("MARKUS.OrbShell")

# Initialize subsystems
kernel = MarkusKernel()
bridge = MarkusHermesBridge(kernel)
bridge.init_private_infra()
sandbox = MarkusProcessSandbox()
router = MarkusIntentRouter()
dice_engine = MarkusDiceEngine(cortex=kernel.memory.db)
cortex_replicator = MarkusCortexReplicator(db=kernel.memory.db)
cortex_replicator.start()
cortex_ring = MarkusSharedRingBuffer(name="markus_cortex_ring", capacity=256, slot_size=1024, create=True)
context_pruner = MarkusContextPruner()
consensus_arbiter = MarkusConsensusArbiter(sandbox=sandbox)
adaptive_matrix = MarkusAdaptiveWeightMatrix()
checkpoint_mgr = MarkusCheckpointManager(db=kernel.memory.db)
acoustic_synapse = MarkusAcousticSynapse()
complexity_governor = MarkusComplexityGovernor()
speculative_cache = MarkusSpeculativeCache()
prompt_matrix = MarkusPromptSynthesisMatrix(db=kernel.memory.db)
capability_registry = CapabilityRegistry()
capability_synthesizer = MarkusCapabilitySynthesizer(registry=capability_registry, sandbox=sandbox)

# Shared SSE infrastructure
sse_subscribers = {}
sse_lock = __import__('threading').Lock()

def broadcast_sse_event(event_type, data):
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with sse_lock:
        for q in list(sse_subscribers.values()):
            try:
                q.put_nowait(payload)
            except Exception:
                pass

class OrbShellHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(format % args)

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/orb"):
            self._serve_orb_html()
        elif self.path == "/api/bootstrap":
            self._send_json(200, {
                "persona": "superagent",
                "memory_layers": ["L1", "L1.5", "L2", "L3"],
                "cortex_entries": len(kernel.memory.l2_working_memory)
            })
        elif self.path.startswith("/api/chat"):
            self._handle_chat()
        elif self.path.startswith("/api/stream"):
            self._handle_sse()
        else:
            self._send_json(404, {"error": "Not Found"})

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

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        import queue
        client_q = queue.Queue()
        with sse_lock:
            sse_subscribers[id(self)] = client_q

        try:
            while True:
                data = client_q.get(timeout=60)
                self.wfile.write(data.encode('utf-8'))
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with sse_lock:
                sse_subscribers.pop(id(self), None)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", MARKUS_HTTP_PORT), OrbShellHandler)
    logger.info(f"MARKUS Orb Shell running at http://localhost:{MARKUS_HTTP_PORT}/orb")
    server.serve_forever()
