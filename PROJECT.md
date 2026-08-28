# Project: OMNIPRIME Air-Gapped Offline Enhancement

## Architecture
OMNIPRIME unifies MARKUS OS, VORPAL, and HERMES into a resilient, air-gapped autonomous intelligence runtime.
- **Model Routing Subsystem**: `markus_router.py` & `markus_brain_backend.py` enforce deterministic offline gating to `custom/qwen2.5-coder:7b` when `is_offline=True` or `network_down=True`.
- **IPC Bridge Subsystem**: `markus_hermes_bridge.py` & `markus_vorpal_bridge.py` manage inter-process communication with persistent JSONL offline queueing, local telemetry spooling, and automatic reconnection synchronization.
- **Memory & Compaction Engine**: `markus_db.py` & `markus_context_pruner.py` manage persistent SQLite cortex storage with TTL pruning, FTS5 sync, database compaction (VACUUM), and AST/salience context pruning within token limits.
- **Evolution Loops**: `markus_reflexion.py`, `markus_population_dice.py`, and `markus_redteam.py` verified via `hermes_verify_evolution_loops.py`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Air-Gapped Local Model Routing Gate | Fallback gate routing to `custom/qwen2.5-coder:7b` when `is_offline=True` or network is down | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Single Source of Truth Brain Models | `TIER_MODELS["OFFLINE_LOCAL"]` mapped to `custom/qwen2.5-coder:7b` with fail-open fallback | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Hermes Offline IPC Queueing & Drain | Persistent disk-backed queue (`hermes_offline_queue.jsonl`), health probing, background flush | M2 | ORIGINAL_REQUEST §R2 |
| 4 | Vorpal Offline Telemetry Spooling | Spooling when VORPAL_ROOT absent, synchronization upon reconnect, cortex goal sync | M2 | ORIGINAL_REQUEST §R2 |
| 5 | SQLite Cortex Memory Compaction | TTL pruning, row count capping, FTS5 deletion synchronization, SQLite VACUUM optimization | M3 | ORIGINAL_REQUEST §R3 |
| 6 | AST & Salience Context Pruning | Multi-factor token importance scoring, structural invariant protection, greedy budget packing | M3 | ORIGINAL_REQUEST §R3 |
| 7 | Full Acceptance Test Suite Verification | Verify `hermes_verify_router.py`, `hermes_verify_vorpal_bridge.py`, `hermes_verify_evolution_loops.py`, and `py_compile` across all targets | M4 | ORIGINAL_REQUEST Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Offline Local Model Fallback Gate | `markus_router.py`, `markus_brain_backend.py` | none | IN_PROGRESS |
| 2 | M2: Offline IPC Bridge Synchronization | `markus_hermes_bridge.py`, `markus_vorpal_bridge.py` | M1 | PLANNED |
| 3 | M3: Local Memory & Context Compaction Engine | `markus_db.py`, `markus_context_pruner.py` | M1 | PLANNED |
| 4 | M4: Full Acceptance & Forensic Integrity Audit | End-to-end test execution, compilation, and audit across all modules | M1, M2, M3 | PLANNED |

## Interface Contracts

### Model Routing Interface (`markus_router.py` ↔ `markus_brain_backend.py`)
- `MODEL_AIRGAPPED_LOCAL = "custom/qwen2.5-coder:7b"`
- `TIER_MODELS["OFFLINE_LOCAL"] = "custom/qwen2.5-coder:7b"`
- `route_intent(prompt: str, context_tokens: int = 0, is_offline: bool = False) -> RouteDecision`
- When `is_offline=True` or `network_down=True`, return `RouteDecision(target_model="custom/qwen2.5-coder:7b", provider="custom", tier_category="OFFLINE_LOCAL", confidence=1.0)`

### Hermes IPC Interface (`markus_hermes_bridge.py`)
- `HermesBridgeConfig.private_workspace_root`: `Path`
- `enqueue_offline(payload: dict) -> bool`
- `flush_offline_queue() -> int`
- `get_pending_offline_count() -> int`
- `check_gateway_connectivity() -> bool`
- `send_to_hermes_session(session_id: str, prompt: str, is_offline: bool = False) -> bool`

### Vorpal IPC Interface (`markus_vorpal_bridge.py`)
- `write_markus_telemetry(payload: dict) -> Optional[Path]` (spools locally if VORPAL_ROOT is absent)
- `flush_spooled_telemetry() -> int`
- `parse_active_goal_dag() -> List[Dict[str, Any]]`

### Memory Cortex Compaction Interface (`markus_db.py`)
- `prune_thoughts(max_age_seconds: Optional[int] = None, max_entries: Optional[int] = None) -> int`
- `compact_cortex() -> Dict[str, Any]` (executes vacuum, analyze, and returns freed bytes / stats)
- `get_cortex_stats() -> Dict[str, Any]`

### Context Pruner Interface (`markus_context_pruner.py`)
- `prune(context_blocks: List[str], target_token_limit: int) -> PruneResult`
- `estimate_tokens(text: str) -> int`

## Code Layout
- `markus_router.py`: Intent classifier, model tier router, network intel auto-offline gate.
- `markus_brain_backend.py`: Model provider API clients, tier configuration, token cost accounting.
- `markus_hermes_bridge.py`: HERMES private workspace IPC bridge, offline queue, daemon synchronization.
- `markus_vorpal_bridge.py`: VORPAL filesystem IPC bridge, telemetry ledger, goal DAG parser.
- `markus_db.py`: SQLite persistent cortex database, FTS5 index, compaction and pruning routines.
- `markus_context_pruner.py`: Token budget optimizer, AST and regex salience scorer.
- `hermes_verify_router.py`: Verification harness for router offline fallback and adaptive matrix.
- `hermes_verify_vorpal_bridge.py`: Verification harness for Vorpal bridge and telemetry persistence.
- `hermes_verify_evolution_loops.py`: Verification harness for Reflexion, Population Dice, and RedTeam loops.
