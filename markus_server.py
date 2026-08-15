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
from markus_capabilities import CapabilityRegistry
from markus_capability_synthesizer import MarkusCapabilitySynthesizer

logger = logging.getLogger("Markus.Server")

# Global instances
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
capability_synthesizer = MarkusCapabilitySynthesizer(registry=CapabilityRegistry(), sandbox=sandbox)

active_dags: Dict[str, TaskDAG] = {
    "default_dag": TaskDAG("default_dag")
}

# Public alias for request handler (used by standalone bootstrap)
Handler = MarkusRequestHandler

# SSE event broadcast listeners
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

class MarkusRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(200)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/ui" or self.path == "/nexus" or self.path == "/markus_nexus.html":
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body) if body else {}
                intent_text = data.get("intent", "")
                action = data.get("action", "UNKNOWN")
                
                # Generate hash based on current kernel context
                ihash = speculative_cache.generate_intent_hash(
                    intent_text, 
                    {"kernel_state": kernel.kernel_state, "active_mode": kernel.mode}
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
        if self.path == "/api/intent":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
                routed = router.route_intent(prompt)
                response_text = f"Dispatched intent to {routed.model_provider} [{routed.tier_category}]. Logged to L3 cortex."

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
                        "model": routed.model_provider,
                        "tier": routed.tier_category,
                        "confidence": routed.confidence_score,
                        "reason": routed.reasoning
                    }
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

        elif self.path == "/api/sandbox/eval":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
                final_roll, rolls = dice_engine.run_single()
                action_label = dice_engine.ACTIONS.get(final_roll, "UNKNOWN")
                prompt = dice_engine.format_prompt(final_roll, roll_history=rolls)

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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
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
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

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
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, MarkusRequestHandler)
    print(f"[MARKUS-OS] Live API & SSE Stream Server listening on http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[MARKUS-OS] API Server stopped cleanly.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
