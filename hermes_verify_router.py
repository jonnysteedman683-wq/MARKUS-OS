#!/usr/bin/env python3
"""hermes_verify_router.py — standalone verification for the markus_router.py
live-telemetry wiring (route -> matrix advisory + record_outcome feedback loop
+ auto-offline network detection). Stdlib-only."""
from __future__ import annotations
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "markus_router.py"


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  -  {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main() -> int:
    results = []
    try:
        py_compile.compile(str(TARGET), doraise=True)
        results.append(check("py_compile markus_router.py", True))
    except Exception as e:  # noqa: BLE001
        results.append(check("py_compile markus_router.py", False, str(e)))
        print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
        return 0 if all(results) else 1

    # Module self-test (benchmark + feedback loop).
    proc = subprocess.run([sys.executable, str(TARGET)], capture_output=True, text=True)
    ok_run = proc.returncode == 0 and "PASSED" in proc.stdout
    results.append(check("router self-test (benchmark + feedback loop)", ok_run,
                         "exit={}".format(proc.returncode)))
    if not ok_run:
        print(proc.stdout[-1500:])
        print(proc.stderr[-1500:])

    sys.path.insert(0, str(HERE))
    import importlib.util
    spec = importlib.util.spec_from_file_location("mrouter", TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    r = mod.MarkusIntentRouter(use_matrix=True)
    # Offline forced to local even with a fake online network snapshot.
    d = r.route_intent("check health", is_offline=True)
    results.append(check("offline -> local model", d.target_model == r.MODEL_AIRGAPPED_LOCAL))
    # Matrix advisory attached to a normal route.
    d2 = r.route_intent("optimize the AST")
    results.append(check("matrix advisory attached", d2.matrix_model is not None and d2.matrix_weight is not None))
    # record_outcome moves the matrix (feedback loop primitive).
    lag = r.MODEL_CODE_FAST
    r.record_outcome(lag, latency_ms=3000.0, success=False)
    dipped = r.matrix.models[lag].current_weight
    for _ in range(5):
        r.record_outcome(lag, latency_ms=80.0, success=True)
    rec = r.matrix.models[lag].current_weight
    results.append(check("record_outcome feedback loop moves weights", rec > dipped,
                         f"dipped={dipped:.3f}->recovered={rec:.3f}"))

    print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
