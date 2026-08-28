#!/usr/bin/env python3
"""hermes_verify_adaptive_matrix.py — standalone verification for the real-time
reliability scoring upgrade in markus_adaptive_matrix.py.

Runs AST gate + the module's extended self-test and reports PASS/FAIL per the
triad epistemic-verification doctrine. Stdlib-only, no network.
"""
from __future__ import annotations
import json
import py_compile
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "markus_adaptive_matrix.py"


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  -  {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main() -> int:
    results = []

    # 1. AST gate
    try:
        py_compile.compile(str(TARGET), doraise=True)
        results.append(check("py_compile markus_adaptive_matrix.py", True))
    except Exception as e:  # noqa: BLE001
        results.append(check("py_compile markus_adaptive_matrix.py", False, str(e)))
        print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
        return 0 if all(results) else 1

    # 2. Isolate the module's own self-test via subprocess (captures stdout/exit).
    import subprocess
    proc = subprocess.run([sys.executable, str(TARGET)], capture_output=True, text=True)
    ok_run = proc.returncode == 0 and "PASSED" in proc.stdout
    results.append(check("module self-test passes", ok_run,
                         "exit={}".format(proc.returncode)))
    if not ok_run:
        print(proc.stdout[-1500:])
        print(proc.stderr[-1500:])

    # 3. Direct unit checks on the reliability / circuit-break primitives.
    sys.path.insert(0, str(HERE))
    import importlib.util
    spec = importlib.util.spec_from_file_location("amatrix", TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolves cls.__module__ via sys.modules
    spec.loader.exec_module(mod)
    mx = mod.MarkusAdaptiveWeightMatrix()
    nem = "deepseek/deepseek-v4-pro-0813"
    # reliability in [0,1] for a model with only failures
    for _ in range(3):
        mx.record_outcome(nem, latency_ms=900.0, success=False)
    rel = mx.models[nem].reliability_score
    results.append(check("reliability_score in [0,1] under failure", 0.0 <= rel <= 1.0, f"rel={rel}"))
    results.append(check("circuit-break tripped after 3 failures", not mx.circuit_ok(nem)))
    mx.record_outcome(nem, latency_ms=150.0, success=True)
    results.append(check("consecutive_failures reset on success",
                         mx.models[nem].consecutive_failures == 0))

    # 4. State persistence round-trip (fresh instance reads back telemetry).
    try:
        fresh = mod.MarkusAdaptiveWeightMatrix()
        persisted = fresh.models[nem].total_calls
        results.append(check("state persists across instances", persisted >= 4, f"total_calls={persisted}"))
    except Exception as e:  # noqa: BLE001
        results.append(check("state persists across instances", False, str(e)))

    print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
