"""
MARKUS OS Live API, Server-Sent Events (SSE) & WebSocket Telemetry Server (Upgrade 3)
Provides zero-latency real-time thought/process streaming directly to markus-os.html.
Port: 8128
"""

from __future__ import annotations
import asyncio
import json
import logging
import queue
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

from markus_kernel import MarkusKernel, KernelMessage, TaskPriority
from markus_brain_backend import ask_brain, route_brain_model
from markus_hermes_bridge import MarkusHermesBridge
from markus_sandbox import MarkusProcessSandbox
from markus_router import MarkusIntentRouter
from markus_task_dag import TaskDAG, TaskNode, NodeState
from markus_dice_engine import MarkusDiceEngine
from markus_cortex_replication import MarkusCortexReplicator
from markus_ring_buffer import MarkusSharedRingBuffer
from markus_context_pruner import MarkusContextPruner
from markus_consensus import MarkusConsensusArbiter, ModelCandidate
from markus_adaptive_matrix import MarkusAdaptiveWeightMatrix
from markus_checkpoint import MarkusCheckpointManager
from markus_acoustic_synapse import MarkusAcousticSynapse
from markus_complexity_governor import MarkusComplexityGovernor
from markus_speculative_cache import MarkusSpeculativeCache
from markus_prompt_matrix import MarkusPromptSynthesisMatrix
from markus_obsidian_sync import MarkusObsidianSync
from markus_capabilities import CapabilityRegistry
from markus_capability_synthesizer import MarkusCapabilitySynthesizer
from markus_thors import ThorsEngine, create_thors_tables
from markus_ui_db import MarkusUIDatabase
from markus_resilience import CircuitBreakerManager
from markus_co_evolution import CoEvolutionOrchestrator

logger = logging.getLogger("Markus.Server")

def _ask_markus_brain(prompt: str, tier_category: str = "DEFAULT_BALANCED", timeout_s: float = 60.0) -> str:
    """Direct Nous API brain call — Hermes-independent (Hermes shell-out retired 2026-08-26)."""
    return ask_brain(prompt, model=route_brain_model(tier_category), timeout_s=timeout_s, tier=tier_category)
# Global instances
kernel = MarkusKernel()
ui_db = MarkusUIDatabase()
circuit_breaker = CircuitBreakerManager()
bridge = MarkusHermesBridge(kernel)
bridge.init_private_infra()
kernel.memory.set_register("OS_STATUS", "BOOTED")  # server up == OS online
obsidian_sync = MarkusObsidianSync(db=kernel.memory.db)  # L3 -> VORPAL Vault narrative bridge
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
capability_synthesizer = MarkusCapabilitySynthesizer(registry=CapabilityRegistry(), sandbox=sandbox)
thors_engine = ThorsEngine(cortex_db=kernel.memory.db)
create_thors_tables(kernel.memory.db)

active_dags: Dict[str, TaskDAG] = {
    "default_dag": TaskDAG("default_dag")
}

# Public aliases for SSE infrastructure
sse_subscribers: List[queue.Queue] = []
sse_lock = threading.Lock()

def broadcast_sse_event(event_type: str, data: Dict[str, Any]) -> None:
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with sse_lock:
        for q in list(sse_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                sse_subscribers.remove(q)

def _read_body(self) -> str:
    """Read request body once. Safe for multiple calls (returns cached)."""
    if not hasattr(self, '_thors_body_read'):
        content_length = int(self.headers.get("Content-Length", 0))
        self._thors_body_read = self.rfile.read(content_length).decode("utf-8") if content_length else ""
    return self._thors_body_read


def _readBody(self) -> str:
    """Read request body once. Safe for multiple calls (returns cached)."""
    return _read_body(self)


class MarkusRequestHandler(BaseHTTPRequestHandler):
    # CORS allowlist (loopback + local deck/UI origins). Requests from any
    # other Origin are served WITHOUT the ACAO header, so browsers block the
    # cross-origin read. Keeps local-first while dropping the wildcard "*".
    _ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000",
                        "http://localhost:8128", "http://127.0.0.1:8128",
                        "http://localhost:8080", "http://127.0.0.1:8080",
                        "null")

    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        origin = self.headers.get("Origin", "")
        if origin in self._ALLOWED_ORIGINS or not origin:
            # No Origin (curl / same-origin) or a trusted origin -> allow.
            self.send_header("Access-Control-Allow-Origin", origin or "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(200)

    def do_GET(self) -> None:
        # [THORS] Security gate: detect and retaliate against attackers
        client_ip = self.client_address[0]
        if thors_engine.is_blocked(client_ip):
            verdict = thors_engine.analyze_request("GET", self.path, dict(self.headers), None, client_ip)
            thors_engine.retaliate(verdict, self)
            return
        verdict = thors_engine.analyze_request("GET", self.path, dict(self.headers), None, client_ip)
        if verdict.threat_level > 0:
            thors_engine.retaliate(verdict, self)
            return
        # [END THORS]

        if self.path == "/" or self.path == "/ui-os" or self.path == "/markus_ui_os.html":
            html_path = Path(__file__).parent / "markus_ui_os.html"
            if html_path.exists():
                content = html_path.read_bytes()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content)
            else:
                self._set_headers(404)
                self.wfile.write(b"<h1>404 - markus_ui_os.html not found</h1>")
        elif self.path == "/nexus" or self.path == "/markus_nexus.html":
            html_path = Path(__file__).parent / "markus_nexus.html"
            if html_path.exists():
                content = html_path.read_bytes()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content)
            else:
                self._set_headers(404)
                self.wfile.write(b"<h1>404 - markus_nexus.html not found</h1>")
        elif self.path == "/chat" or self.path == "/markus-chat.html":
            html_path = Path(__file__).parent / "markus_chat.html"
            if html_path.exists():
                content = html_path.read_bytes()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content)
            else:
                self._set_headers(404)
                self.wfile.write(b"<h1>404 - markus_chat.html not found</h1>")
        elif self.path == "/command-deck" or self.path == "/orb" or self.path == "/markus-os.html":
            html_path = Path(__file__).parent / "markus-os.html"
            if html_path.exists():
                content = html_path.read_bytes()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content)
            else:
                self._set_headers(404)
                self.wfile.write(b"<h1>404 - markus-os.html not found</h1>")
        elif self.path == "/api/ui/state":
            components = [c.__dict__ for c in ui_db.list_components()]
            unreads = [n.__dict__ for n in ui_db.get_unread_notifications()]
            commands = ui_db.get_recent_commands(limit=10)
            res = {
                "status": "OK",
                "components": components,
                "unread_notifications": unreads,
                "recent_commands": commands
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path.startswith("/api/cortex/search"):
            import urllib.parse
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            q = params.get("q", [""])[0].strip()
            limit = int(params.get("limit", [20])[0])
            if q:
                results = kernel.memory.db.search_thoughts(q, limit=limit)
            else:
                results = kernel.memory.db.get_recent_thoughts(limit=limit)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "OK", "query": q, "count": len(results), "results": results}).encode("utf-8"))
        elif self.path == "/api/stream":
            # Server-Sent Events (SSE) Stream
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            client_queue: queue.Queue = queue.Queue(maxsize=100)
            with sse_lock:
                sse_subscribers.append(client_queue)

            try:
                # Initial handshake event
                self.wfile.write(b"event: handshake\ndata: {\"status\": \"STREAM_CONNECTED\"}\n\n")
                self.wfile.flush()

                while True:
                    try:
                        msg = client_queue.get(timeout=1.0)
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive heartbeat ping
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                with sse_lock:
                    if client_queue in sse_subscribers:
                        sse_subscribers.remove(client_queue)

        elif self.path == "/api/prompt/personas":
            res = prompt_matrix.list_personas()
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path.startswith("/api/dag/spec"):
            dag_id = "default_dag"
            if "?" in self.path:
                query = self.path.split("?")[1]
                for param in query.split("&"):
                    if param.startswith("dag_id="):
                        dag_id = param.split("=")[1]
            
            dag = active_dags.get(dag_id)
            if not dag:
                dag = TaskDAG(dag_id)
                active_dags[dag_id] = dag

            self._set_headers(200)
            self.wfile.write(json.dumps(dag.to_spec()).encode("utf-8"))

        elif self.path == "/api/cortex/hot":
            count = 10
            thoughts = kernel.memory.get_recent_hot_thoughts(count=count)
            res = {
                "hot_thoughts": thoughts,
                "count": len(thoughts),
                "has_ring_buffer": kernel.memory.hot_ring is not None,
                "timestamp": time.time()
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/speculation/precompute":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                intent_text = data.get("intent", "")
                action = data.get("action", "UNKNOWN")
                
                # Generate hash based on current kernel context
                ihash = speculative_cache.generate_intent_hash(
                    intent_text, 
                    {"kernel_state": kernel.memory.get_register("OS_STATUS", "ACTIVE"), "active_mode": "EVOLVE"}
                )
                
                speculative_cache.precompute_candidate(
                    intent_hash=ihash,
                    action=action,
                    ast_hint=data.get("ast_hint"),
                    confidence=data.get("confidence", 0.5),
                    cost_est=data.get("cost_est", 0.0)
                )
                
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "PRECOMPUTED", "intent_hash": ihash}).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/governor/audit":
            audits, summary = complexity_governor.audit_workspace()
            res = {
                "summary": summary,
                "audits": [
                    {
                        "module_name": a.module_name,
                        "total_loc": a.total_loc,
                        "average_cyclomatic": a.average_cyclomatic,
                        "maintainability_index": a.maintainability_index,
                        "status": a.status,
                        "functions_flagged": len([f for f in a.functions if f.status != "OPTIMAL"])
                    }
                    for a in audits
                ],
                "timestamp": time.time()
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/audio/neural-matrix":
            res = acoustic_synapse.get_neural_matrix()
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/checkpoints":
            res = {
                "checkpoints": checkpoint_mgr.list_checkpoints(),
                "timestamp": time.time()
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/router/matrix":
            res = {
                "matrix": adaptive_matrix.get_matrix_state(),
                "timestamp": time.time()
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/network/intel":
            # Live transport snapshot from markus_network_intel (rebuild on demand).
            try:
                import markus_network_intel as _nintel
                rep = _nintel.build_report(probe=True)
                res = {
                    "hostname": rep.hostname,
                    "primary_connection_type": rep.primary_connection_type,
                    "has_internet": rep.has_internet,
                    "internet_latency_ms": rep.internet_latency_ms,
                    "vpn_active": rep.vpn_active,
                    "cellular_present": rep.cellular_present,
                    "gateway_reachable": rep.gateway_reachable,
                    "active_adapters": [
                        {"name": a.name, "type": a.connection_type,
                         "ipv4": a.ipv4, "gateway": a.gateway}
                        for a in rep.active_adapters
                    ],
                    "timestamp": time.time()
                }
            except Exception as exc:
                res = {"status": "ERROR", "error": str(exc)}
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/vault/sync":
            # Obsidian Palace Bridge — on-demand L3 -> vault flush
            try:
                digest = obsidian_sync.sync_daily_digest(limit=50)
                live = obsidian_sync.append_new_thoughts()
                res = {
                    "status": "OK",
                    "vault": str(obsidian_sync.vault_path),
                    "digest": digest,
                    "live": live,
                }
            except Exception as exc:
                res = {"status": "ERROR", "error": str(exc)}
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/goals":
            # VORPAL goal DAG -> live route. Parsed on demand from
            # EVOLVE/GOALS/GOALS.md via markus_vorpal_bridge; goal-state
            # becomes a live surface instead of a client-tree fiction.
            try:
                import markus_vorpal_bridge as _vbridge
                st = _vbridge.MarkusVorpalBridge().read_vorpal_status()
                res = {
                    "status": "OK",
                    "goal_count": st.goal_count,
                    "open_goal_count": st.open_goal_count,
                    "implemented_goal_count": st.implemented_goal_count,
                    "goal_pulse": st.goal_pulse,
                    "source": str(_vbridge.GOALS_PATH),
                    "parsed_at": st.parsed_at,
                    "timestamp": time.time(),
                }
            except Exception as exc:
                res = {"status": "ERROR", "error": str(exc)}
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/health" or self.path == "/api/status":
            procs = [
                {"pid": p.pid, "name": p.name, "state": p.state.value, "priority": p.priority.name}
                for p in kernel.process_table.values()
            ]
            response = {
                "status": "ONLINE",
                "kernel_state": kernel.memory.get_register("OS_STATUS", "ACTIVE"),
                "version": kernel.memory.get_register("VERSION", "1.0.0-ALPHA"),
                "processes": procs,
                "memory_cortex": {
                    "registers": kernel.memory.l1_registers,
                    "working_memory_count": len(kernel.memory.l2_working_memory),
                    "recent_thoughts": kernel.memory.l2_working_memory[-5:]
                }
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not Found"}')

    def do_POST(self) -> None:
        # [THORS] Security gate: read body once, detect and retaliate against attackers
        client_ip = self.client_address[0]
        body = _read_body(self)
        if thors_engine.is_blocked(client_ip):
            verdict = thors_engine.analyze_request("POST", self.path, dict(self.headers), body, client_ip)
            thors_engine.retaliate(verdict, self)
            return
        verdict = thors_engine.analyze_request("POST", self.path, dict(self.headers), body, client_ip)
        if verdict.threat_level > 0:
            thors_engine.retaliate(verdict, self)
            return
        # [END THORS]

        if self.path == "/api/intent":
            # body already read by Thors security gate above
            try:
                data = json.loads(body) if body else {}
                prompt = data.get("prompt", "")

                # Commit thought to kernel
                kernel.memory.commit_thought(
                    agent="REST_GATEWAY",
                    content=f"Received user intent: {prompt}",
                    metadata={"source": "markus_chat.html"}
                )

                # Broadcast freshly committed thought to peer swarm via UDP replication
                try:
                    cortex_replicator.broadcast_thought(
                        f"intent_{int(time.time())}",
                        "REST_GATEWAY",
                        f"User Intent: {prompt}",
                        {"source": "markus_chat.html"}
                    )
                except Exception as repl_err:
                    logger.debug(f"Peer replication error: {repl_err}")

                # Stream thought to Shared Memory Ring Buffer for microsecond local process ingestion
                try:
                    cortex_ring.push({
                        "entry_id": f"intent_{int(time.time())}",
                        "agent": "REST_GATEWAY",
                        "content": prompt,
                        "timestamp": time.time()
                    })
                except Exception as ring_err:
                    logger.debug(f"Ring buffer push error: {ring_err}")

                # Route intent and build response
                _t0 = time.time()
                routed = router.route_intent(prompt)
                response_text = _ask_markus_brain(prompt, tier_category=routed.tier_category)
                _latency_ms = round((time.time() - _t0) * 1000.0, 1)
                # Feed post-dispatch telemetry back into the adaptive matrix so
                # routing weights learn from real API traffic.
                try:
                    router.record_outcome(routed.target_model, _latency_ms,
                                          success=bool(response_text))
                except Exception as tel_err:
                    logger.debug(f"Telemetry record error: {tel_err}")

                # Broadcast real-time SSE event to all connected UI surfaces
                broadcast_sse_event("intent", {
                    "prompt": prompt,
                    "timestamp": time.time(),
                    "agent": "MARKUS-KERNEL"
                })

                res = {
                    "status": "ACCEPTED",
                    "prompt": prompt,
                    "kernel_response": response_text,
                    "routing_decision": {
                        "model": routed.target_model,
                        "tier": routed.tier_category,
                        "confidence": routed.confidence,
                        "reason": routed.reason,
                        "latency_ms": _latency_ms,
                        "matrix_advisory": routed.matrix_model,
                        "matrix_weight": routed.matrix_weight,
                        "network_down": routed.network_down
                    }
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/sandbox/eval":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                code = data.get("code", "")
                timeout = float(data.get("timeout_s", 5.0))

                # Execute in isolated sandbox
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(sandbox.execute_python_code(code, timeout_s=timeout))
                loop.close()

                res_data = {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                    "runtime_ms": result.runtime_ms,
                    "timed_out": result.timed_out
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res_data).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/prompt/synthesize":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                user_input = data.get("prompt", "")
                persona = data.get("persona", "AUTONOMOUS_CODER")
                include_ex = data.get("include_exemplars", True)
                max_ex = data.get("max_exemplars", 3)

                synth = prompt_matrix.synthesize_prompt(
                    user_input=user_input,
                    persona=persona,
                    include_exemplars=include_ex,
                    max_exemplars=max_ex,
                    context_registers=kernel.memory.l1_registers
                )

                res = {
                    "persona": synth.persona_name,
                    "system_prompt": synth.system_prompt,
                    "user_prompt": synth.user_prompt,
                    "token_estimate": synth.token_estimate,
                    "exemplars": synth.exemplars,
                    "metadata": synth.metadata
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/audio/synthesize":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                preset = data.get("preset", "INTENT_DISPATCH")
                syn_res = acoustic_synapse.synthesize_preset(preset)

                res = {
                    "preset": syn_res.preset_name,
                    "sample_rate": syn_res.sample_rate,
                    "duration_s": syn_res.duration_s,
                    "frequencies": syn_res.frequencies,
                    "wav_base64": syn_res.wav_bytes_base64,
                    "web_audio_matrix": syn_res.web_audio_matrix,
                    "elapsed_ms": syn_res.elapsed_ms
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/checkpoints/create":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                reason = data.get("reason", "API_TRIGGERED")
                tags = data.get("tags", [])

                chk = checkpoint_mgr.create_checkpoint(
                    registers=kernel.memory.l1_registers,
                    working_memory=kernel.memory.l2_working_memory,
                    reason=reason,
                    tags=tags
                )
                res = {
                    "checkpoint_id": chk.checkpoint_id,
                    "timestamp": chk.timestamp,
                    "checksum_sha256": chk.checksum_sha256,
                    "reason": chk.trigger_reason,
                    "file_path": chk.file_path
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/checkpoints/restore":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                cid = data.get("checkpoint_id")
                if not cid:
                    raise ValueError("checkpoint_id is required")

                restored = checkpoint_mgr.restore_checkpoint(cid)
                # Apply restored state into active kernel memory cortex
                kernel.memory.l1_registers = restored.get("registers", {})
                kernel.memory.l2_working_memory = restored.get("working_memory", [])

                res = {
                    "status": "RESTORED",
                    "checkpoint_id": cid,
                    "registers_restored": len(kernel.memory.l1_registers),
                    "thoughts_restored": len(kernel.memory.l2_working_memory)
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/consensus/arbitrate":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                raw_cands = data.get("candidates", [])
                test_harness = data.get("test_harness", None)
                timeout_s = float(data.get("timeout_s", 5.0))

                cands = [
                    ModelCandidate(
                        candidate_id=c.get("candidate_id", f"cand_{i}"),
                        model_name=c.get("model_name", "unknown_model"),
                        code=c.get("code", ""),
                        reasoning=c.get("reasoning", "")
                    )
                    for i, c in enumerate(raw_cands)
                ]

                loop = asyncio.new_event_loop()
                verdict = loop.run_until_complete(consensus_arbiter.arbitrate(cands, test_harness_code=test_harness, timeout_s=timeout_s))
                loop.close()

                res = {
                    "winning_candidate_id": verdict.winning_candidate_id,
                    "winning_model": verdict.winning_model,
                    "winning_code": verdict.winning_code,
                    "consensus_confidence": verdict.consensus_confidence,
                    "total_candidates": verdict.total_candidates,
                    "elapsed_ms": verdict.elapsed_ms,
                    "evaluations": [
                        {
                            "candidate_id": e.candidate_id,
                            "model_name": e.model_name,
                            "ast_valid": e.ast_valid,
                            "sandbox_passed": e.sandbox_passed,
                            "similarity_to_peers": e.similarity_to_peers,
                            "composite_score": e.composite_score,
                            "error": e.error
                        }
                        for e in verdict.evaluations
                    ]
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/context/prune":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                raw_context = data.get("context", "")
                max_tokens = int(data.get("max_tokens", 1000))
                query = data.get("query", None)

                pruned = context_pruner.prune(raw_context, max_tokens=max_tokens, query=query)
                res = {
                    "original_tokens": pruned.original_tokens,
                    "pruned_tokens": pruned.pruned_tokens,
                    "compression_ratio": pruned.compression_ratio,
                    "retained_segments": pruned.retained_segments,
                    "total_segments": pruned.total_segments,
                    "pruned_text": pruned.text,
                    "elapsed_ms": pruned.elapsed_ms
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/dice/roll":
            try:
                final_roll = dice_engine.roll_cryptographic_dice()
                d1, d2 = dice_engine.roll_dice_pair()
                rolls = [d1, d2, final_roll]
                action_label = dice_engine.get_action_label(final_roll)
                prompt = f"MARKUS DICE: rolled {final_roll} -> {action_label} (sequence: {rolls})"

                broadcast_sse_event("dice_roll", {
                    "final_roll": final_roll,
                    "roll_sequence": rolls,
                    "action": action_label,
                    "timestamp": time.time()
                })

                res = {
                    "status": "ROLLED",
                    "final_roll": final_roll,
                    "roll_sequence": rolls,
                    "action": action_label,
                    "prompt": prompt
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/dag/step":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                dag_id = data.get("dag_id", "default_dag")
                node_id = data.get("node_id")
                if not node_id:
                    raise ValueError("node_id is required for stepping")

                dag = active_dags.get(dag_id)
                if not dag or node_id not in dag.nodes:
                    raise ValueError(f"DAG '{dag_id}' or node '{node_id}' not found")

                loop = asyncio.new_event_loop()
                step_res = loop.run_until_complete(dag.step_node(node_id, context=data.get("context")))
                loop.close()

                broadcast_sse_event("dag_node_stepped", {
                    "dag_id": dag_id,
                    "node": step_res
                })

                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "STEPPED", "node": step_res}).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/dag/execute":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)
            try:
                data = json.loads(body) if body else {}
                dag_id = data.get("dag_id", f"dag_{int(time.time())}")
                nodes_spec = data.get("nodes", [])

                dag = active_dags.get(dag_id)
                if not dag:
                    dag = TaskDAG(dag_id)
                    active_dags[dag_id] = dag
                else:
                    dag.nodes.clear()

                for n_spec in nodes_spec:
                    nid = n_spec["id"]
                    name = n_spec.get("name", nid)
                    deps = set(n_spec.get("dependencies", []))
                    code_snippet = n_spec.get("code", "return {}")

                    async def _make_action(c_code):
                        async def _act(ctx):
                            c_str = f"import json\nctx = {json.dumps(ctx)}\n{c_code}\n"
                            res = await sandbox.execute_python_code(c_str, timeout_s=5.0)
                            return {"stdout": res.stdout, "exit_code": res.exit_code}
                        return _act

                    # Bind action
                    action_fn = asyncio.run(_make_action(code_snippet)) if not asyncio.iscoroutinefunction(_make_action) else None
                    
                    async def _run_code(ctx, c=code_snippet):
                        c_str = f"import json\nctx = {json.dumps(ctx)}\n{c}\n"
                        res = await sandbox.execute_python_code(c_str, timeout_s=5.0)
                        return {"stdout": res.stdout, "exit_code": res.exit_code}

                    dag.add_node(nid, name, _run_code, dependencies=deps)

                loop = asyncio.new_event_loop()
                dag_result = loop.run_until_complete(dag.execute())
                loop.close()

                # Broadcast DAG execution event
                broadcast_sse_event("dag_completed", {
                    "dag_id": dag_id,
                    "success": dag_result["success"],
                    "elapsed_ms": dag_result["elapsed_ms"]
                })

                self._set_headers(200)
                self.wfile.write(json.dumps(dag_result).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/cron":
            body = self._thors_body_read if hasattr(self, '_thors_body_read') else _read_body(self)

            try:
                data = json.loads(body) if body else {}
                task_id = data.get("task_id", "unknown")
                cron_prompt = data.get("prompt", f"Execute cron task {task_id}")
                source = data.get("source", "rest_dispatch")

                # Quick synchronous response — log dispatch details
                routed = router.route_intent(cron_prompt)

                # Fire-and-forget async cortex log + SSE broadcast (non-blocking)
                def _async_log():
                    try:
                        if hasattr(kernel.memory, 'db') and kernel.memory.db:
                            kernel.memory.db.append_thought(
                                f"cron_dispatch_{task_id}_{int(time.time())}",
                                "REST_CRON_DISPATCHER",
                                cron_prompt,
                                {"source": source, "task_id": task_id, "routing": routed.provider}
                            )
                        else:
                            kernel.memory.commit_thought(
                                "REST_CRON_DISPATCHER",
                                cron_prompt,
                                {"source": source, "task_id": task_id, "routing": routed.provider}
                            )
                    except Exception as log_err:
                        logger.error(f"Failed to log cron dispatch: {log_err}")

                threading.Thread(target=_async_log, daemon=True).start()

                # Broadcast SSE event (non-blocking)
                broadcast_sse_event("cron_dispatch", {
                    "task_id": task_id,
                    "prompt": cron_prompt,
                    "model": routed.provider,
                    "tier": routed.tier_category,
                    "timestamp": time.time()
                })

                res = {
                    "status": "DISPATCHED",
                    "task_id": task_id,
                    "routing": {
                        "model": routed.provider,
                        "tier": routed.tier_category,
                        "confidence": routed.confidence
                    },
                    "message": f"Cron task '{task_id}' dispatched and logged to L3 cortex."
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not Found"}')

    def log_message(self, format: str, *args: Any) -> None:
        pass

def run_server(port: int = 8128) -> None:
    # Bind loopback only: the MARKUS API + SSE stream is a local-first control
    # plane. An empty host ("") binds 0.0.0.0 (all interfaces), exposing it to
    # the LAN. Override with MARKUS_HOST for intentional remote access.
    import os as _os
    host = _os.environ.get("MARKUS_HOST", "127.0.0.1")
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, MarkusRequestHandler)
    print(f"[MARKUS-OS] Live API & SSE Stream Server listening on http://{host}:{port}")
    print(f"[MARKUS-OS] Obsidian Palace Bridge -> {obsidian_sync.vault_path}")

    def _auto_vault_sync(interval_s: float = 300.0) -> None:
        """Append new L3 thoughts to the VORPAL Vault journal and generate Canvas graphs periodically."""
        try:
            obsidian_sync.append_new_thoughts()  # immediate catch-up on boot
            obsidian_sync.generate_canvas_graph()
        except Exception as exc:
            logger.warning(f"Vault boot sync failed: {exc}")
        while True:
            time.sleep(interval_s)
            try:
                obsidian_sync.append_new_thoughts()
                obsidian_sync.generate_canvas_graph()
            except Exception as exc:
                logger.warning(f"Vault auto-sync failed: {exc}")

    def _auto_co_evolution_daemon(interval_s: float = 300.0) -> None:
        """Execute autonomous 7-phase co-evolution cycle periodically."""
        co_evo = CoEvolutionOrchestrator(cortex=kernel.memory.db, dice_engine=dice_engine, kernel=kernel)
        while True:
            time.sleep(interval_s)
            try:
                asyncio.run(co_evo.execute_cycle())
                broadcast_sse_event("co_evolution", {
                    "status": "CYCLE_COMPLETE",
                    "message": "Background co-evolution cycle executed successfully.",
                    "timestamp": time.time()
                })
            except Exception as exc:
                logger.warning(f"Co-evolution daemon cycle error: {exc}")

    threading.Thread(target=_auto_vault_sync, daemon=True, name="VaultSyncDaemon").start()
    threading.Thread(target=_auto_co_evolution_daemon, daemon=True, name="CoEvoDaemon").start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[MARKUS-OS] API Server stopped cleanly.")
        httpd.server_close()

# Public aliases
Handler = MarkusRequestHandler
SseSubscribers = sse_subscribers

if __name__ == "__main__":
    run_server()
