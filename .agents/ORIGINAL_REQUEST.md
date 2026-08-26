# Original User Request

## Initial Request — 2026-08-27T02:19:33+10:00

Enhance OMNIPRIME (MARKUS OS, VORPAL, HERMES) with air-gapped offline capability focus: local Ollama model fallback (`custom/qwen2.5-coder:7b`), offline IPC bridge synchronization, and local SQLite memory compaction.

Requirements:
- R1. Offline Local Model Fallback Gate (`markus_router.py`, `markus_brain_backend.py`)
- R2. Offline IPC Bridge Synchronization (`markus_hermes_bridge.py`, `markus_vorpal_bridge.py`)
- R3. Local Memory & Context Compaction Engine (`markus_db.py`, `markus_context_pruner.py`)

Acceptance Criteria:
- python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py
- python hermes_verify_router.py (with target_model == "custom/qwen2.5-coder:7b" when is_offline=True)
- python hermes_verify_vorpal_bridge.py (OVERALL: PASS)
- python hermes_verify_evolution_loops.py (TOTAL PASS=7 TOTAL_FAIL=0)
