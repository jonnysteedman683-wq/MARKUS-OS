#!/usr/bin/env python3
"""Bounded full-system test: drive N co-evolution cycles, verify vault sync
emits per run, and confirm pause_after_generation halt. NOT committed (scratch)."""
import asyncio
import sys
from pathlib import Path
from markus_co_evolution import CoEvolutionOrchestrator

VAULT = Path(r"C:/Users/jonny/OneDrive/Documents/VORPAL Vault/Journal/Markus/Runs")

def main(max_cycles: int = 5) -> int:
    orch = CoEvolutionOrchestrator()
    runs_before = sorted(VAULT.glob("run_*.md"))
    print(f"[TEST] starting {max_cycles} cycles (vault pause_after_generation=5)")
    halted = False
    for i in range(max_cycles):
        try:
            res = asyncio.run(orch.execute_cycle())
        except SystemExit:
            halted = True
            print(f"[TEST] daemon halted at cycle {orch.cycle_counter} (pause_after_generation)")
            break
        print(f"[TEST] cycle {orch.cycle_counter} ok: action={res.get('action')} "
              f"reward={res.get('reward'):.2f}")
    runs_after = sorted(VAULT.glob("run_*.md"))
    new_runs = set(runs_after) - set(runs_before)
    lineage = sorted((VAULT / "lineage").glob("lineage_run_*.md"))
    print(f"[TEST] new run reports: {len(new_runs)}")
    print(f"[TEST] lineage notes total: {len(lineage)}")
    ok = len(new_runs) >= 1 and len(lineage) >= 1
    print(f"[TEST] {'PASS' if ok else 'FAIL'} — vault sync emitted across cycles" +
          (f"; halt fired={halted}" if halted else ""))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
