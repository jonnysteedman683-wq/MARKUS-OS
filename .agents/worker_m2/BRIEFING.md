# BRIEFING — 2026-08-26T16:28:00Z

## Mission
Enhance `markus_hermes_bridge.py` and `markus_vorpal_bridge.py` with genuine offline IPC queueing, connectivity probing, telemetry spooling, drainage/flushing, and comprehensive self-tests while strictly preserving all existing contracts.

## 🔒 My Identity
- Archetype: implementer / qa / specialist
- Roles: implementer, qa, specialist
- Working directory: C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\.agents\worker_m2
- Original parent: 3a5c5127-8ee6-451b-9f68-7086512fa263
- Milestone: M2 Offline IPC Bridge Synchronization

## 🔒 Key Constraints
- Exclusive write ownership: `markus_hermes_bridge.py`, `markus_vorpal_bridge.py`
- DO NOT modify any other repository files.
- DO NOT CHEAT: Genuine logic only, no dummy/facade implementations or hardcoded verifications.
- 100% preservation of existing classes, functions, and interfaces for backward compatibility and `hermes_verify_vorpal_bridge.py`.

## Current Parent
- Conversation ID: 3a5c5127-8ee6-451b-9f68-7086512fa263
- Updated: not yet

## Task Summary
- **What to build**: 
  1. `markus_hermes_bridge.py`: persistent JSONL queue (`hermes_offline_queue.jsonl`), `enqueue_offline`, `flush_offline_queue`, `get_pending_offline_count`, `check_gateway_connectivity`, offline detection/spooling in `send_to_hermes_session`, connectivity polling & drainage in `bridge_daemon`, and `_self_test()`.
  2. `markus_vorpal_bridge.py`: telemetry fallback spooling to `vorpal_telemetry_spool.jsonl` when `VORPAL_ROOT` absent, `flush_spooled_telemetry()`, preserving all existing contracts so `hermes_verify_vorpal_bridge.py` passes with `OVERALL: PASS`.
- **Success criteria**: 
  - `python -m py_compile markus_hermes_bridge.py markus_vorpal_bridge.py` passes cleanly.
  - `python hermes_verify_vorpal_bridge.py` passes with `OVERALL: PASS`.
  - `python markus_hermes_bridge.py` executes self-tests cleanly.
  - `python markus_vorpal_bridge.py` executes cleanly.
- **Interface contracts**: PROJECT.md, survey_r2.md

## Change Tracker
- **Files modified**: [TBD]
- **Build status**: [TBD]
- **Pending issues**: None

## Quality Status
- **Build/test result**: [TBD]
- **Lint status**: Clean
- **Tests added/modified**: `_self_test()` in `markus_hermes_bridge.py` and verification suite runs

## Loaded Skills
- None explicitly required beyond standard python / teamwork methodology

## Artifact Index
- `.agents/worker_m2/progress.md`
- `.agents/worker_m2/handoff.md`
