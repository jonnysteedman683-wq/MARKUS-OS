#!/usr/bin/env bash
# MARKUS OS Debugging & Hardening Run (Upgrade 9 Companion Script)
# Executes the full hardening checklist and writes a verdict to the L3 cortex.

python -m py_compile markus_resilience.py markus_server.py markus_rng_pilot.py markus_kernel.py && echo "[1/6] AST syntax check: PASS"
python phoenix_cli.py batch . && echo "[2/6] Batch AST evolution scan: PASS"
python markus_integration_test.py > /tmp/markus_itg.log 2>&1 && echo "[3/6] Integration test: PASS" || echo "[3/6] Integration test: FAIL"
python markus_resilience.py && echo "[4/6] Circuit breaker self-test: PASS"
python markus_obsidian_sync.py > /tmp/markus_sync.log 2>&1 && echo "[5/6] Obsidian Palace sync: PASS" || echo "[5/6] Obsidian Palace sync: FAIL"
python markus_rng_pilot.py > /tmp/markus_rng.log 2>&1 && echo "[6/6] RNG pilot cycle: PASS" || echo "[6/6] RNG pilot cycle: FAIL"

echo "=== MARKUS Hardening Run Complete ==="
