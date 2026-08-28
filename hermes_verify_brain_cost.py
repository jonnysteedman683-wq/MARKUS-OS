#!/usr/bin/env python3
"""hermes_verify_brain_cost.py — MARKUS per-call cost ledger gate (c52).

Proves the cost accounting added to markus_brain_backend.py:

  G1  backend py_compile clean + imports
  G2  cost math: free model = 0; paid model priced from the verified table
      (deepseek-v4-pro-0813 prompt $0.8976/M, completion $0.0026928/tok)
  G3  record_cost() appends a JSONL entry + cost_summary() reads it back
  G4  ledger tolerates corrupt lines (skipped, not fatal)
  G5  estimate_cost on unknown model falls back to zero (fail-safe, never
      over-charges)
  G6  (opt-in, MARKUS_BRAIN_LIVE_PROBE=1) live ask_brain writes a ledger
      entry — laguna-s-2.1:free costs $0 so this is safe

Exit 0 = all gates pass. Fail-token hygiene: no bare "[FAIL]" literals.
"""
from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}".rstrip())


def main() -> int:
    brain_path = ROOT / "markus_brain_backend.py"
    try:
        py_compile.compile(str(brain_path), doraise=True)
        check("G1 brain backend compiles", True)
    except py_compile.PyCompileError as exc:
        check("G1 brain backend compiles", False, str(exc))
        return _finish()

    spec = importlib.util.spec_from_file_location("brain_uut", str(brain_path))
    bb = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bb
    spec.loader.exec_module(bb)

    # G2 cost math
    free = bb.estimate_cost("poolside/laguna-s-2.1:free", 1000, 500)
    paid = bb.estimate_cost("deepseek/deepseek-v4-pro-0813", 1000, 500)
    # 1000 * 0.0000008976 + 500 * 0.0000026928 = 0.0008976 + 0.0013464 = 0.002244
    check(
        "G2 cost math",
        free == 0.0 and abs(paid - 0.002244) < 1e-12,
        f"free={free}, paid={paid:.12f}",
    )

    # G3 append + readback against a temp ledger
    with tempfile.TemporaryDirectory() as tmp:
        bb.COST_LEDGER = Path(tmp) / "ledger.jsonl"
        c1 = bb.record_cost("deepseek/deepseek-v4-flash", 200, 50, 123.4, "DEFAULT_BALANCED")
        c2 = bb.record_cost("poolside/laguna-s-2.1:free", 100, 10, 55.0, "CODE_SPECIALIST")
        summ = bb.cost_summary()
        expected1 = 200 * 0.0000000709 + 50 * 0.0000001418  # = 0.00001418 + 0.00000709
        ok3 = (
            abs(c1 - expected1) < 1e-12
            and c2 == 0.0
            and summ["calls"] == 2
            and "deepseek/deepseek-v4-flash" in summ["per_model"]
        )
        check("G3 record + summary", ok3, f"calls={summ['calls']} per_model={summ['per_model']}")

        # G4 corrupt line tolerance
        led = Path(tmp) / "ledger.jsonl"
        with open(led, "a", encoding="utf-8") as f:
            f.write("NOT_JSON\n")
        summ2 = bb.cost_summary()
        check("G4 corrupt-line tolerance", summ2["calls"] == 2, f"calls={summ2['calls']}")

    # G5 unknown model fail-safe
    check(
        "G5 unknown model = $0",
        bb.estimate_cost("does/not-exist", 999, 999) == 0.0,
        "",
    )

    # G6 optional live probe
    if os.environ.get("MARKUS_BRAIN_LIVE_PROBE") == "1":
        with tempfile.TemporaryDirectory() as tmp:
            bb.COST_LEDGER = Path(tmp) / "live.jsonl"
            reply = bb.ask_brain("Reply with exactly: BRAIN_LIVE")
            summ3 = bb.cost_summary()
            check(
                "G6 live probe ledgered",
                "BRAIN_LIVE" in reply and summ3["calls"] == 1,
                f"reply={reply[:30]!r} calls={summ3['calls']}",
            )
    else:
        check("G6 live probe (opt-in)", True, "skipped (MARKUS_BRAIN_LIVE_PROBE=1 to enable)")

    return _finish()


def _finish() -> int:
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nTOTAL PASS={passed} TOTAL_FAIL={total - passed} (of {total})")
    if passed == total:
        print("RESULT: PASS")
        return 0
    print("RESULT: GATE FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
