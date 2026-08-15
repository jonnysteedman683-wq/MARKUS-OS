# MARKUS OS: 10 Architectural & Capability Upgrades Roadmap

This document outlines the 10 core upgrade paths for the MARKUS Autonomous Agent Operating System.

---

### 1. Dynamic Capability Driver Subsystem (`markus_capabilities.py`)
- **Upgrade:** Create an extensible plugin interface (`MarkusCapability`) for dynamic runtime driver loading (file tools, network scanners, git tools).
- **Impact:** Decouples core kernel logic from peripheral tool definitions, allowing hot-reloading of drivers without restarting the kernel.

### 2. SQLite L3 Persistent Cortex Storage (`markus_db.py`)
- **Upgrade:** Transition the L3 audit log and L1 persistent registers from in-memory arrays to a thread-safe SQLite backend with FTS5 search.
- **Impact:** Full state durability across OS reboots and high-speed historical thought query capability.

### 3. Server-Sent Events (SSE) & WebSocket Streaming Gateway
- **Upgrade:** Replace the polling `/api/status` endpoint in `markus_server.py` with an event-driven SSE stream (`/api/stream`).
- **Impact:** 0ms latency kernel telemetry streaming directly into `markus-os.html` without CPU polling overhead.

### 4. Isolated Process Execution Sandbox (`markus_sandbox.py`)
- **Upgrade:** Implement process-level containment using Python subprocess workers with strict memory/CPU limits and execution timeouts.
- **Impact:** Prevents malformed user scripts or infinite loops from crashing the main `MarkusKernel` event loop.

### 5. Multi-Model Intent Routing Engine
- **Upgrade:** Add semantic model triage to `DeliberativePlanner`:
  - Quick tasks $\to$ `poolside/laguna-s-2.1:free`
  - High-context architecture $\to$ `nvidia/nemotron-3-ultra:free`
  - Critical logic $\to$ Local Ollama / Nous fallback.
- **Impact:** Optimizes cost, token throughput, and reasoning quality per task.

### 6. Bidirectional Kanban Bridge Driver
- **Upgrade:** Author a native Kanban task worker inside `markus_hermes_bridge.py` that claims tasks assigned to `markus` from `kanban.db`.
- **Impact:** Allows MARKUS to autonomously pick up, execute, and report back on background tasks dispatched from Hermes.

### 7. Obsidian Palace Knowledge Bridge
- **Upgrade:** Establish automatic markdown log extraction syncing MARKUS L3 thoughts to `Obsidian Vault/Journal/Markus/`.
- **Impact:** Unified knowledge visualization between the command deck and the Obsidian graph view.

### 8. Acoustic Synapse Synthesis Suite
- **Upgrade:** Expand the Web Audio engine in `markus-os.html` to generate procedural harmonic multi-tone chords for process states (Running, Blocked, Complete, Error).
- **Impact:** Ambient multi-sensory feedback allowing auditory monitoring of background swarm operations.

### 9. Self-Healing Circuit Breaker & Automatic Rollback
- **Upgrade:** Embed the `CircuitBreaker` resilience pattern from `PRIME-DIRECTIVE.md` into all outbound network and tool requests.
- **Impact:** Automatic quarantine and state rollback when external APIs or bridge routes experience cascading failures.

### 10. Swarm Mesh Node Discovery Protocol
- **Upgrade:** Implement lightweight UDP broadcast discovery enabling multiple MARKUS OS instances across desktop, laptop, and server nodes to form a unified mesh.
- **Impact:** Distributed agent swarm compute with zero-configuration clustering.

---

## Technical Feasibility & Impact Evaluation Matrix

| Upgrade ID & Component | Feasibility | Effectiveness / Leverage | Implementation Complexity | Current Status |
|---|---|---|---|---|
| **#1 Dynamic Capability Drivers** (`markus_capabilities.py`) | **High (10/10)** | **High (8/10)** | Low (Plugin ABC interface) | **Complete & Verified** |
| **#2 SQLite L3 Persistent DB** (`markus_db.py`) | **High (10/10)** | **Critical (9/10)** | Low (FTS5 SQLite engine) | **Complete & Verified** |
| **#3 Real-Time SSE Stream** (`markus_server.py`) | **High (10/10)** | **High (8.5/10)** | Low (HTTP EventStream) | **Complete & Live** |
| **#4 Isolated Process Sandbox** (`markus_sandbox.py`) | **High (10/10)** | **Critical (9.5/10)** | Medium (Async subprocess) | **Complete & Verified** |
| **#5 Multi-Model Intent Router** (`markus_router.py`) | **High (10/10)** | **High (8.5/10)** | Low (Heuristic Regex Triage) | **Complete & Verified** |
| **#6 Bidirectional Kanban Worker** (`markus_kanban_worker.py`) | **High (10/10)** | **Critical (9/10)** | Medium (SQLite claim locks) | **Complete & Verified** |
| **#7 Obsidian Palace Sync** (`markus_obsidian_sync.py`) | **High (10/10)** | **High (8/10)** | Low (Vault markdown writer) | **Next Queue** |
| **#8 Harmonic Web Audio Synth** (`markus-os.html`) | **High (10/10)** | **Medium (7/10)** | Low (Browser Web Audio API) | **Next Queue** |
| **#9 Self-Healing Circuit Breaker** (`markus_resilience.py`) | **High (9/10)** | **Critical (9.5/10)** | Medium (Stateful backoff) | **Queued** |
| **#10 Swarm Mesh UDP Discovery** (`markus_mesh.py`) | **Medium (7.5/10)** | **High (8.5/10)** | High (Cross-subnet UDP/LAN) | **Queued** |

