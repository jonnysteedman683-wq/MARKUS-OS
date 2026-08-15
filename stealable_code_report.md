# Stealable Code Report — Repos Scanned for MARKUS Strengthening

## Scan Date
2026-08-16 (PHOENIX iteration)

## Repos Audited (9 total)
| Repo | Language | Stealable Potential | Notes |
|------|----------|---------------------|-------|
| **HERMES-HIVE** | TypeScript | 🔥 CRITICAL | 159 files, full agent OS, task orchestration, policy engine, world model |
| **ARISE** | Python | 🔥 CRITICAL | 2D ant-farm swarm sim — brain.py (numpy NN), tasks.py, evolution engine |
| **ARGUS** | Python | 🔥 HIGH | Digital twin with time-series SQLite store, as-of queries, preference engine |
| **SUPRIME** | Python | 🔥 CRITICAL | Decentralized gossip swarm, CRDT, SWIM probing, Plumtree, Ed25519, ChaCha20 |
| **Sentinel** | TypeScript | 🔥 HIGH | "Arcane Quantum Brain" — RL agent, knowledge graph, memory consolidation |
| **Vortronor** | TypeScript | LOW | No README at /main or /master |
| **Agent-engine** | TypeScript | LOW | No README |
| **Roo-Code** | TypeScript | LOW | External fork, not Jonny's codebase |
| **Apache License 2.0** | TypeScript | LOW | Likely a license repo |

---

## Tier 1 Stealable Modules

### A. SUPRIME — `suprime/peers.py` (PeerTable + Heartbeat Failure Detector)
**Why steal:** Pure-state heartbeat failure detection with `SUSPECT`/`DEAD`/`ALIVE` states. Exactly what MARKUS needs for UDP mesh reliability.

**Key classes/patterns:**
- `PeerState` enum (ALIVE → SUSPECT → DEAD)
- `Peer` dataclass with heartbeat counter + last_update timestamp
- `PeerTable` with `merge()`, `refresh()`, `evict()`, `tick()` (staleness-based demotion)
- `suspect_after` / `dead_after` configurable timers
- Injectable `clock` for deterministic testing

**Stealable adaptation:** Drop directly into `markus_mesh.py` for UDP mesh peer tracking. The `tick()` method handles node eviction; `merge()` handles gossip piggybacking.

### B. SUPRIME — `suprime/store.py` (LWW CRDT Store)
**Why steal:** Last-writer-wins key/value store with Lamport `(timestamp, origin)` versioning. Commutative/associative/idempotent merge. Perfect for replicated MARKUS state across mesh nodes.

**Key classes:**
- `Version` dataclass (ts + origin, with `__gt__` ordering)
- `Entry` dataclass (value + version + deleted tombstone)
- `DistributedStore` with `set()`, `delete()`, `get()`, `merge()`, `digest()`, `collect_garbage()`
- Tombstone management for safe deletion propagation
- Subscriber hooks (`_notify`, `_emit_commit`) for WAL integration

**Stealable adaptation:** Replace or augment `markus_router.py`'s state sync. The CRDT convergence guarantees are stronger than naive UDP broadcast.

### C. SUPRIME — `suprime/transport.py` (Pluggable Transport Layer)
**Why steal:** TCP + InMemory transports with length-prefixed JSON, gzip compression, connection caching, and configurable timeouts. Direct upgrade for MARKUS's current UDP-only mesh.

**Key classes:**
- `Transport` abstract base
- `InMemoryTransport` (shared registry, simulated latency, single-process swarm testing)
- `TcpTransport` (4-byte length prefix, gzip over 1KB, 16MB max frame, 3s connect timeout)

**Stealable adaptation:** Wrap as `MarkusTcpTransport` — gives MARKUS TCP mesh reliability with UDP fallback (matches existing `tcp-mesh-reliability` skill).

### D. SUPRIME — `suprime/crdt.py` (CRDT Toolkit)
**Why steal:** Full CRDT toolkit — GCounter, PNCounter, ORSet, LWWMap, VectorClock, MVRegister. All with `merge()`/`digest()`/`apply_digest()` for gossip compatibility.

**Key classes:**
- `VectorClock` with causal comparison (`before`/`after`/`equal`/`concurrent`)
- `GCounter` / `PNCounter` grow-only and bidirectional
- `ORSet` with tag-based add-wins semantics
- `LWWMap` with `(ts, origin)` tie-breaking

**Stealable adaptation:** Use ORSet for distributed task ID membership; GCounter for resource accounting across mesh nodes.

### E. HERMES-HIVE — `src/server/web/policyAndAuthorizationEngine.ts` (Risk-Based Auth Engine)
**Why steal:** Multi-layer policy engine with service identity check, capability registry lookup, rate limiting, risk-level gating, and approval queues.

**Key patterns:**
- 7-rule evaluation chain (identity → availability → operation → rate limit → simulation → risk → default)
- `PolicyDecision` with DENY/ALLOW/REQUIRE_APPROVAL
- Idempotency cache
- `approvalQueue` with resolution API

**Stealable adaptation:** Port to Python as `markus_policy_engine.py` — gate the dice engine upgrades behind risk levels.

### F. HERMES-HIVE — `src/server/tasks/taskRunner.ts` (Async Task Runner)
**Why steal:** Full task lifecycle with retry policies, backoff, pending-wait resolution, and message bus integration.

**Key patterns:**
- `DEFAULT_RETRY_POLICY` (3 retries, 2x backoff, max 60s)
- `awaitResult()` with promise-map + timeout cleanup
- Message bus subscription for task completion events
- `pendingWaits` Map with `clearTimeout` on completion

**Stealable adaptation:** Direct port to `markus_task_runner.py` — gives the AI agent a production-grade async task executor with retry semantics.

### G. HERMES-HIVE — `src/server/suprime/suprimeBridge.ts` (Swarm Bridge)
**Why steal:** HTTP bridge to SUPRIME swarm nodes with health checks, swarm start/stop, task submission, and worker registration.

**Stealable adaptation:** Port to Python client for MARKUS to orchestrate SUPRIME-style gossip overlays from the dice engine.

### H. HERMES-HIVE — `src/server/middleware/requestLogger.ts` (Correlation-ID Logger)
**Why steal:** Production-grade request logging with `x-correlation-id` header propagation, aborted-request logging, and `req.__correlationId` attachment.

**Stealable adaptation:** Drop into `markus_server.py` middleware stack for cross-request tracing.

### I. HERMES-HIVE — `src/shared/types.ts` (World Model Types)
**Why steal:** Comprehensive agent/world model types — `Agent`, `AgentReputation`, `GoalStatus`, `TaskStatus`, `MissionTask`, `ResourceBudget`, `LedgerEvent`, `SwarmLearningRecord`.

**Stealable adaptation:** Use as canonical type references when extending MARKUS's agent capabilities.

---

## File Paths for Direct Grab

```
SUPRIME (Python):
  https://raw.githubusercontent.com/jonnysteedman683-wq/SUPRIME/master/suprime/peers.py
  https://raw.githubusercontent.com/jonnysteedman683-wq/SUPRIME/master/suprime/store.py
  https://raw.githubusercontent.com/jonnysteedman683-wq/SUPRIME/master/suprime/transport.py
  https://raw.githubusercontent.com/jonnysteedman683-wq/SUPRIME/master/suprime/crdt.py
  https://raw.githubusercontent.com/jonnysteedman683-wq/SUPRIME/master/suprime/node.py
  https://raw.githubusercontent.com/jonnysteedman683-wq/SUPRIME/master/suprime/security.py
  https://raw.githubusercontent.com/jonnysteedman683-wq/SUPRIME/master/suprime/__init__.py

HERMES-HIVE (TypeScript):
  https://raw.githubusercontent.com/jonnysteedman683-wq/HERMES-HIVE/main/src/server/web/policyAndAuthorizationEngine.ts
  https://raw.githubusercontent.com/jonnysteedman683-wq/HERMES-HIVE/main/src/server/tasks/taskRunner.ts
  https://raw.githubusercontent.com/jonnysteedman683-wq/HERMES-HIVE/main/src/server/suprime/suprimeBridge.ts
  https://raw.githubusercontent.com/jonnysteedman683-wq/HERMES-HIVE/main/src/server/middleware/requestLogger.ts
  https://raw.githubusercontent.com/jonnysteedman683-wq/HERMES-HIVE/main/src/shared/types.ts
```

---

## Priority Integration Queue for MARKUS

1. **SUPRIME peers.py** → `markus_mesh.py` (heartbeat failure detection)
2. **SUPRIME store.py** → `markus_router.py` (LWW CRDT for state sync)
3. **HEMES-HIVE policyAndAuthorizationEngine.ts** → `markus_policy_engine.py` (risk-gated upgrades)
4. **HERMES-HIVE taskRunner.ts** → `markus_task_runner.py` (async task execution)
5. **SUPRIME transport.py** → `markus_tcp_mesh.py` (TCP transport with UDP fallback)
6. **HERMES-HIVE requestLogger.ts** → `markus_server.py` middleware (correlation IDs)
