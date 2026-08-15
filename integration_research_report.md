# Integration Research Report: Stealable Code For MARKUS Strengthening

## Research Date
2026-08-16 (PHOENIX iteration #2)

## Executive Summary

Three repos yield actionable code patterns for MARKUS OS enhancement:

1. **SUPRIME** — Pure-Python gossip swarm with heartbeat failure detection, CRDT store, pluggable TCP transport
2. **HERMES-HIVE** — TypeScript agent OS with policy engine, task runner, correlation-ID logging, comprehensive type model
3. **ARISE** — Python neural brain with Q-learning, ICM curiosity module, Hebbian learning, social edge networking

---

## A. SUPRIME → MARKUS Integration Patterns

### A1: `suprime/peers.py` → `markus_mesh.py`
**Pattern**: Heartbeat-based failure detection with `SUSPECT`/`DEAD`/`ALIVE` states

```python
# Current MARKUS mesh likely uses simple timeout/ping
# SUPRIME adds:
# - Graceful SUSPECT → DEAD transition (no false positives)
# - Configurable timers (suspect_after=3s, dead_after=6s)
# - Injectable clock for testing
# - merge() for gossip piggybacking
```

**Integration**: Replace ad-hoc peer tracking in `markus_mesh.py` with `PeerTable` class. The `tick()` method handles eviction; `merge()` handles incoming gossip data. Pure-state (no I/O) → drop-in compatible.

### A2: `suprime/store.py` → `markus_router.py`
**Pattern**: Last-writer-wins CRDT with Lamport `(timestamp, origin)` versioning

```python
# Current MARKUS router likely uses naive UDP broadcast for state sync
# SUPRIME provides:
# - Commutative/associative/idempotent merge (converges regardless of message order)
# - Tombstones for safe deletion propagation
# - WAL hooks (on_commit callbacks)
# - Garbage collection for tombstones
```

**Integration**: Port `DistributedStore` as `MarkusCRDTStore`. Use `merge_entry()` in mesh message handler. The `digest()`/`apply_digest()` pattern maps directly to UDP packet payloads.

### A3: `suprime/transport.py` → `markus_tcp_mesh.py`
**Pattern**: Length-prefixed JSON over asyncio TCP with gzip + connection caching

```python
# 4-byte framing: struct.Struct(">I").pack(len(payload)) + payload
# Flags: 0x01 = gzip compressed (over 1KB threshold)
# Connection caching per peer address
# Configurable timeouts (3s connect, 16MB max frame)
```

**Integration**: Create `MarkusTcpTransport` wrapping `TcpTransport` with UDP fallback layer.

---

## B. HERMES-HIVE → MARKUS Integration Patterns

### B1: `policyAndAuthorizationEngine.ts` → `markus_policy_engine.py`
**Pattern**: 7-rule risk assessment chain with approval queues

```typescript
// Rule chain:
// 1. Service Identity Check (must be 'hermes-hive')
// 2. Capability Existence & Availability
// 3. Operation Support Validation
// 4. Rate Limit Check (per capability, 60s window)
// 5. Simulation Mode (always allowed)
// 6. Risk Level → REQUIRE_APPROVAL for HIGH/CRITICAL
// 7. Default ALLOW for LOW/MEDIUM
```

**Integration**: Port as `MarkovPolicyEngine` — gate dice engine upgrades:
- Dice Roll 1 (UI) → LOW → auto-approve
- Dice Roll 2 (Backend) → MEDIUM → auto-approve  
- Dice Roll 3 (AI Agent) → HIGH → REQUIRE_APPROVAL
- Dice Roll 4 (Missing) → HIGH → REQUIRE_APPROVAL
- Dice Roll 5 (Tech Alt) → MEDIUM → auto-approve

### B2: `taskRunner.ts` → `markus_task_runner.py`
**Pattern**: Async task lifecycle with retry + backoff

```typescript
// DEFAULT_RETRY_POLICY:
//   maxRetries: 3
//   backoffMs: 5000
//   backoffMultiplier: 2
//   maxBackoffMs: 60000
```

**Integration**: Use for AI agent task execution with exponential backoff. The `pendingWaits` Map pattern resolves via message bus events.

### B3: `requestLogger.ts` → `markus_server.py` middleware
**Pattern**: `x-correlation-id` header propagation + aborted request logging

```typescript
// On every request:
// 1. Read or generate correlation ID
// 2. Attach to req.__correlationId
// 3. Echo back in response header
// 4. Log method + URL + status + duration
```

**Integration**: Drop into `markus_server.py` ThreadingHTTPServer. Add `correlation_id` to all log lines. Cross-reference with ARISE agent IDs for traceability.

---

## C. ARISE → MARKUS Integration Patterns

### C1: `arise/brain.py` → MARKUS AI Agent Brain
**Pattern**: Q-learning + ICM (Intrinsic Curiosity Module)

```python
# QNetwork: fc1(ReLU) → fc2(ReLU) → out(linear)
# ICM: Encoder + ForwardModel + InverseModel
# Intrinsic reward = forward model prediction error (drives novelty exploration)
```

**Integration**: The `Dense` layer class with SGD backprop is directly portable to Python/NumPy. The `ICM.compute_curiosity()` method can replace random exploration in MARKUS's AI agent with curiosity-driven behavior.

### C2: `arise/agent.py` → MARKUS Agent Architecture
**Pattern**: Multi-brain support (qnet + hebbnet), social learning edges

```python
# Agent has:
# - brain: Brain | HebbNet (switchable)
# - social_edges: dict[int, SocialEdge] (Hebbian-inspired connections)
# - affinities: np.random.dirichlet([2]*6) (task specialization)
# - memory: AgentMemory (separate from brain weights)
```

**Integration**: The `SocialEdge` dataclass (trace strength 0-1, last_contact tick) can be added to MARKUS agents for emergent collaboration. The `affinities` pattern gives agents natural task preferences.

### C3: `arise/config.py` → MARKUS Tuning Constants
**Pattern**: All hyperparameters in one file with clear balancing rationale

```python
# Key tunable: MUTATION_RATE = 0.15, MUTATION_DECAY = 0.999
# HUNGER_PER_TICK = 0.008 (survival pressure)
# TASK_BASE_SUCCESS = 0.65 (task difficulty)
```

**Integration**: Reference for MARKUS dice engine balance — what should the "Technical Alternative Upgrade" (Dice 5) cost in terms of system pressure?

---

## D. Cross-Repo Architecture Patterns

### World Model (HERMES-HIVE types.ts + ARISE agent.py)
```
HERMES-HIVE: WorldEntity { id, name, type, state, createdAt, updatedAt }
          WorldRelationship { sourceEntityId, targetEntityId, relationType }

ARISE: Agent { sensory_input → brain → actions → reward }
      SocialEdge { target_id, trace_strength, last_contact }
```
**Pattern**: Both repos use entity-relationship modeling for their domain. MARKUS could adopt `WorldEntity`/`WorldRelationship` for tracking mesh peers + AI agents + tasks.

### Event System (HERMES-HIVE HiveEventType)
```
'PING' | 'TASK_ASSIGNMENT' | 'TASK_RESULT' | 'AGENT_HEARTBEAT' |
'HEALING_ACTION' | 'RISK_ASSESSED' | 'VERIFICATION_RESULT' | ...
```
**Pattern**: Comprehensive event taxonomy. MARKUS should adopt similar `HiveEventType` constants for its own event bus.

### Risk Model (HERMES-HIVE RiskAssessment)
```
riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
factors: { impact, uncertainty, reversibility, privilege, externality, securitySensitivity, resourceCost }
requiredApproval: 'AUTONOMOUS' | 'VERIFICATION_REQUIRED' | 'MULTI_AGENT_APPROVAL' | 'EXPLICIT_HUMAN_AUTHORIZATION'
```
**Pattern**: Factor-based risk scoring. Perfect for gating MARKUS dice engine upgrades.

---

## Priority Integration Plan

| Priority | Module | Source Repo | Target MARKUS File | Complexity |
|----------|--------|-------------|-------------------|------------|
| 1 | PeerTable (heartbeat failure detection) | SUPRIME | `markus_mesh.py` | LOW |
| 2 | DistributedStore (LWW CRDT) | SUPRIME | `markus_router.py` | MEDIUM |
| 3 | Policy Engine (7-rule risk chain) | HERMES-HIVE | `markus_policy_engine.py` | MEDIUM |
| 4 | TaskRunner (retry + backoff) | HERMES-HIVE | `markus_task_runner.py` | MEDIUM |
| 5 | QNetwork + ICM (curiosity) | ARISE | `markus_brain.py` | HIGH |
| 6 | Correlation-ID logging | HERMES-HIVE | `markus_server.py` | LOW |
| 7 | SocialEdge (Hebbian connections) | ARISE | `markus_agent.py` | MEDIUM |
