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
from markus_capability_synthesizer import MarkusCapabilitySynthesizer, DriverSynthesisResult

MARKUS_HTTP_PORT = 8128

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MARKUS-OrbShell] %(message)s"
)

# Initialize all subsystems directly in standalone mode
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

# Import server handler and shared infrastructure
from markus_server import (
    sse_subscribers,
    sse_lock,
    broadcast_sse_event,
    active_dags,
    Handler as ServerHandler
)

prompt_matrix = prompt_matrix

logging.info(f"MARKUS Orb Shell standalone initialized — port {MARKUS_HTTP_PORT}")

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", MARKUS_HTTP_PORT), ServerHandler)
    logging.info(f"MARKUS Orb Shell running at http://localhost:{MARKUS_HTTP_PORT}/orb")
    server.serve_forever()
