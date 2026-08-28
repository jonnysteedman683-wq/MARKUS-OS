## 2026-08-26T21:41:15Z
<USER_REQUEST>
You are worker_m4_flash.
Working directory: C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\.agents\worker_m4_flash

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results or create dummy implementations.

Follow these exact steps directly:
1. In `markus_hermes_bridge.py`, in `flush_offline_queue`, add `if not isinstance(record, dict): continue` after parsing `record = json.loads(line)`.
2. In `markus_vorpal_bridge.py`, in `flush_spooled_telemetry`, ensure only `if isinstance(payload, dict): last_payload = payload` is used, and check `if last_payload and isinstance(last_payload, dict):` before writing to `target`.
3. Run the verification commands using `run_command`:
   `python .agents/challenger_1/test_fix_validation.py`
   `python .agents/challenger_1/stress_test_harness.py`
   `python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_vorpal_bridge.py markus_db.py markus_context_pruner.py`
   `python hermes_verify_router.py`
   `python hermes_verify_vorpal_bridge.py`
   `python hermes_verify_evolution_loops.py`
   `python markus_hermes_bridge.py`
   `python markus_vorpal_bridge.py`
   `python markus_db.py`
   `python markus_context_pruner.py`
4. Write your handoff report to `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\.agents\worker_m4_flash\handoff.md`.
5. Send a message to parent with your verdict and test outputs.
</USER_REQUEST>
