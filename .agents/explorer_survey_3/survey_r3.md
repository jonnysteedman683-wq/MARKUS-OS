# Comprehensive Survey Report: Requirement R3 & Evolution Loops Verification
**OMNIPRIME Offline Air-Gapped Enhancement**
**Explorer 3 Survey Investigation**
**Date**: 2026-08-27
**Target Directory**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS`

---

## 1. Executive Summary

This survey report provides an in-depth architectural and operational investigation for **Requirement R3: Local Memory & Context Compaction Engine** (`markus_db.py`, `markus_context_pruner.py`) and validates the **Acceptance Criteria**:
1. `python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py`
2. `python hermes_verify_evolution_loops.py` (TOTAL PASS=7 TOTAL_FAIL=0)

### Key Survey Conclusions:
1. **Evolution Loops Verification Harness (`hermes_verify_evolution_loops.py`)**:
   - Status: **100% Passing (7/7 Gates Passed)**.
   - All three evolutionary loop engines (`markus_reflexion.py`, `markus_population_dice.py`, `markus_redteam.py`) successfully pass compilation, self-tests, and strict contract verifications.
2. **Core Python Compilation Gate**:
   - Status: **100% Passing (0 Syntax/Import Errors)** across all 5 core modules (`markus_router.py`, `markus_brain_backend.py`, `markus_hermes_bridge.py`, `markus_db.py`, `markus_context_pruner.py`).
3. **Local Memory Storage Subsystem (`markus_db.py`)**:
   - Current State: Thread-safe SQLite storage engine (`PersistentCortexDB`) backing L3 memory with three primary structures: key-value `registers`, chronological `thoughts`, and an FTS5 virtual table `thoughts_fts` with Porter stemmer tokenization.
   - Compaction Gap: Lacks built-in retention expiration, vacuum routines, FTS index compaction, and token-aware thought pruning methods needed for long-running air-gapped / offline deployments.
4. **Context Compaction Engine (`markus_context_pruner.py`)**:
   - Current State: Multi-factor token importance scoring engine (`MarkusContextPruner`) with density scoring, query salience, code/AST priority boosts, temporal recency decay, and AST/error invariant protection.
   - Integration Opportunity: Can be directly leveraged to prune memory thoughts and LLM conversational context to enforce tight token budgets while running offline local models (such as `custom/qwen2.5-coder:7b`).

---

## 2. Deep Dive: `markus_db.py` (L3 Persistent Cortex DB)

### 2.1 Storage Architecture & Schema

`markus_db.py` implements the `PersistentCortexDB` class located at `C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/vault/markus_cortex.db` (by default).

```sql
-- 1. L1 Persistent Registers Table
CREATE TABLE IF NOT EXISTS registers (
    key TEXT PRIMARY KEY,
    val_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);

-- 2. L3 Memory Thoughts Table
CREATE TABLE IF NOT EXISTS thoughts (
    entry_id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- 3. FTS5 Virtual Table for Fast Semantic Keyword Search
CREATE VIRTUAL TABLE IF NOT EXISTS thoughts_fts USING fts5(
    entry_id UNINDEXED,
    agent,
    content,
    tokenize='porter unicode61'
);
```

### 2.2 Functional Methods & Behavior

| Method | Signature | Description |
|---|---|---|
| `set_register` | `(key: str, value: Any) -> None` | Serializes value to JSON and performs `INSERT ... ON CONFLICT(key) DO UPDATE` with timestamp. |
| `get_register` | `(key: str, default: Any = None) -> Any` | Fetches and deserializes JSON value by key. |
| `append_thought` | `(entry_id: str, agent: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None` | Atomic insert/replace into both `thoughts` and `thoughts_fts`. |
| `search_thoughts` | `(query: str, limit: int = 10) -> List[Dict[str, Any]]` | FTS5 BM25 rank-ordered search joining `thoughts_fts` with `thoughts`. |
| `cortex_execute` | `(sql: str, params: tuple = ()) -> None` | Raw SQL execution hook for external subsystems (e.g., ThorsEngine). |
| `get_recent_thoughts` | `(limit: int = 10) -> List[Dict[str, Any]]` | Reverse-chronological query on `thoughts` table ordered by `created_at DESC`. |

### 2.3 Air-Gapped & Offline Memory Compaction Gaps
In an air-gapped offline environment with high autonomous throughput, the following memory compaction features are essential:
1. **Thought Retention & Pruning (`prune_thoughts`)**:
   - Ability to prune thoughts older than a certain retention duration (TTL) or enforce a maximum row cap (e.g. keeping top 10,000 thoughts).
   - Deletions from `thoughts` must automatically synchronize deletions from `thoughts_fts` (`DELETE FROM thoughts_fts WHERE entry_id IN (...)`).
2. **Database Maintenance & Compaction (`compact_db`)**:
   - Execution of SQLite `VACUUM` to reclaim disk pages after deletions.
   - Execution of FTS5 optimize command: `INSERT INTO thoughts_fts(thoughts_fts) VALUES('optimize')`.
   - Execution of SQLite `PRAGMA wal_checkpoint(TRUNCATE)` and `PRAGMA optimize`.
3. **Compacted Summary Archive**:
   - Integration with `markus_context_pruner.py` to compress old thought sequences into concise summary thoughts before pruning raw logs.

---

## 3. Deep Dive: `markus_context_pruner.py` (Context Compaction Engine)

### 3.1 Scoring Formulation

`MarkusContextPruner` computes token importance per segment based on a 4-factor composite weighting model:

$$\text{Composite Score} = (0.25 \times \text{Density}) + (0.35 \times \text{Salience}) + (0.30 \times \text{PriorityBoost}) + (0.10 \times \text{Recency})$$

1. **Information Density ($w_1 = 0.25$)**:
   - Ratio of non-stop words to total words: $\frac{|\text{words} \setminus \text{STOP\_WORDS}|}{\max(1, |\text{words}|)}$.
2. **Query Salience ($w_2 = 0.35$)**:
   - Overlap between segment tokens and user query terms: $\min(1.0, |\text{query hits}| \times 0.25)$.
3. **Code / Error Priority Boost ($w_3 = 0.30$)**:
   - Matched against `PRIORITY_PATTERNS` (AST keywords: `def`, `class`, `async`, `await`, `import`; Error markers: `Traceback`, `Error`, `FAIL`, `PASS`, `CRITICAL`; identifiers, function calls, URLs): $\min(1.0, |\text{priority hits}| \times 0.2)$.
4. **Recency Bias ($w_4 = 0.10$)**:
   - Linear temporal decay favoring recent entries: $\max(0.2, \min(1.0, 1.0 - \text{decay\_factor} \times (\text{total} - 1 - \text{index})))$.

### 3.2 Invariant Structural Protection

Segments matching critical invariants are marked `is_protected = True`:
- Contains error signatures or core directives: `\b(Traceback|SyntaxError|AssertionError|PRIME-DIRECTIVE)\b`.
- Or composite score exceeds `protected_threshold` (default `0.85`).

### 3.3 Token Estimation & Pruning Workflow

1. **Heuristic Token Estimation**: `max(1, len(text) // 4)` (~4 characters per token).
2. **Greedy Budget Packing**: Sorts candidate segments by `(is_protected, score)` descending, packing segments until `max_tokens` is reached.
3. **Chronological Reconstruction**: Reorders selected segments by their original segment index to maintain narrative and logical coherence.
4. **Output Metrics (`PruneResult`)**:
   - `original_tokens`: Original token count.
   - `pruned_tokens`: Compressed token count.
   - `compression_ratio`: Ratio of compressed to original tokens.
   - `retained_segments` / `total_segments`: Line/block preservation stats.
   - `elapsed_ms`: Wall-clock execution latency.

---

## 4. Full MARKUS Memory Hierarchy Mapping

| Layer | Subsystem | Storage Medium | Lifecycle / Capacity |
|---|---|---|---|
| **L1** | Volatile Registers | In-memory `dict` (`kernel.memory.l1_registers`) | Real-time key-value cache; synced on write to L3 SQLite. |
| **L1.5** | Hot-Thought Ring | Shared Memory Circular Buffer (`markus_cortex_hot`) | Capacity: 256 slots (1024 bytes each); microsecond IPC lock-free ring. |
| **L2** | Working Memory | In-memory `list` (`kernel.memory.l2_working_memory`) | Sliding window capped at 100 recent thought dicts. |
| **L3** | Persistent Cortex Vault | SQLite Database (`markus_cortex.db`) | Durable FTS5-indexed persistent storage for thoughts, registers, and audit log. |
| **Snapshots** | Micro-Checkpoints | JSON Files with SHA-256 (`markus_checkpoint.py`) | Point-in-time state snapshots with rollback and prune history. |

---

## 5. Verification Harness Analysis: `hermes_verify_evolution_loops.py`

### 5.1 Verification Gate Results

Verification command executed: `python hermes_verify_evolution_loops.py`

```
  [PASS] G1 py_compile AST gate on all 3 evolution loop modules
  [PASS] G2 Reflexion self-test (_test_reflexion)
  [PASS] G3 ReflexionLoopEngine contract verification
  [PASS] G4 Population Dice self-test (_test_population_dice)
  [PASS] G5 PopulationDiceEngine contract verification
  [PASS] G6 RedTeam self-test (_test_redteam)
  [PASS] G7 RedTeamOrchestrator contract verification

TOTAL PASS=7 TOTAL_FAIL=0 (of 7)
RESULT: PASS
```

### 5.2 Breakdown of Individual Gates

1. **Gate 1 (G1)**: `py_compile.compile` on `markus_reflexion.py`, `markus_population_dice.py`, `markus_redteam.py`. Verified AST valid and no syntax errors.
2. **Gate 2 (G2)**: Invocation of `ReflexionLoopEngine.run_reflexion_cycle(max_retries=3)`. Verified Act-Observe-Reflect-Refine cycle with PHOENIX code validation.
3. **Gate 3 (G3)**: Verifies `collect_trajectory(last_n=5)` returns list with `success` and `latency_ms` attributes, `generate_self_reflection()` returns `SelfReflection` with `issues_found` and `suggested_improvements`, `refine_and_retry()` returns `(bool, str)`, and `get_reflection_stats()` returns valid statistics dict.
4. **Gate 4 (G4)**: Invocation of `PopulationDiceEngine.evolve_generation()` across 5 generations. Verified tournament selection, mutation rate, elite preservation, and population stats tracking.
5. **Gate 5 (G5)**: Verifies `tournament_selection(tournament_size=2)` returns a `DiceGenome`, and `mutate_genome(winner)` produces a mutated child genome with distinct `genome_id` and mutated action weight distributions.
6. **Gate 6 (G6)**: Invocation of `RedTeamOrchestrator.run_redteam_cycle()`. Scanned Python files, injected mutation operators (`insert_exception`, `modify_condition`, `delete_statement`, `skip_iterations`, `negate_return`, `change_operator`), ran sandbox AST evaluation, detected crashes, generated blue team fixes, and logged results to cortex DB.
7. **Gate 7 (G7)**: Verifies `Vulnerability` record logging to `PersistentCortexDB` via `append_thought` and verified `BlueTeamAgent.generate_fix(vuln)` produces valid fix code template.

---

## 6. Acceptance Criteria: Python Compilation Verification

Verification command executed:
`python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py`

- **Exit Code**: `0`
- **Standard Output**: (Clean / No errors)
- **Standard Error**: (Clean / No errors)
- **Status**: **PASS**

---

## 7. Actionable Recommendations for Implementation Phase (R3)

To deliver a production-grade local memory compaction engine for air-gapped / offline deployments:

1. **Add Thought Pruning & Compaction Methods to `markus_db.py`**:
   - `prune_thoughts(max_retained: int = 5000, max_age_seconds: Optional[float] = None) -> int`: Delete excess/expired entries from `thoughts` and synchronize deletions with `thoughts_fts`.
   - `compact_cortex() -> Dict[str, Any]`: Run `PRAGMA wal_checkpoint(TRUNCATE)`, `INSERT INTO thoughts_fts(thoughts_fts) VALUES('optimize')`, and `VACUUM` to reclaim physical disk space.
   - `get_cortex_stats() -> Dict[str, Any]`: Expose total thought count, register count, database file size in bytes, and table metrics.
2. **Wire Context Pruner into Database Thought Compaction**:
   - Add a method in `markus_context_pruner.py` or a helper `compact_thought_history(thoughts: List[Dict[str, Any]], max_tokens: int = 1500)` that accepts raw cortex thought streams, prioritizes critical failure/recovery logs, and compresses them for downstream local LLM prompt injection.
3. **Verify Zero Regressions on Existing Test Harnesses**:
   - Ensure all existing verifications (`hermes_verify_evolution_loops.py`, `hermes_verify_router.py`, `hermes_verify_vorpal_bridge.py`, `markus_integration_test.py`) remain completely green (TOTAL PASS=7, OVERALL PASS).
