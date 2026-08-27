#!/usr/bin/env python3
"""hermes_verify_vorpal_bridge.py — standalone verification for the
markus_vorpal_bridge.py bidirectional MARKUS<->VORPAL intertwining.

AST gate + module self-test + direct checks on the parser (VORPAL goal DAG)
and the telemetry write path. Stdlib-only, fail-open on absent VORPAL."""
from __future__ import annotations
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "markus_vorpal_bridge.py"
VORPAL_GOALS = Path(r"C:\Users\jonny\OneDrive\Desktop\VORPAL\EVOLVE\GOALS\GOALS.md")


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  -  {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main() -> int:
    results = []
    try:
        py_compile.compile(str(TARGET), doraise=True)
        results.append(check("py_compile markus_vorpal_bridge.py", True))
    except Exception as e:  # noqa: BLE001
        results.append(check("py_compile markus_vorpal_bridge.py", False, str(e)))
        print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
        return 0 if all(results) else 1

    proc = subprocess.run([sys.executable, str(TARGET)], capture_output=True, text=True)
    ok_run = proc.returncode == 0 and "PASSED" in proc.stdout
    results.append(check("bridge self-test passes", ok_run, "exit={}".format(proc.returncode)))
    if not ok_run:
        print(proc.stdout[-1500:])
        print(proc.stderr[-1500:])

    sys.path.insert(0, str(HERE))
    import importlib.util
    spec = importlib.util.spec_from_file_location("mvbridge", TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    b = mod.MarkusVorpalBridge()

    # 1. Parser correctness against the real VORPAL GOALS.md (if present).
    if VORPAL_GOALS.exists():
        st = b.read_vorpal_status()
        results.append(check("parses real VORPAL goal DAG", st.goal_count >= 20,
                             f"goals={st.goal_count}"))
        results.append(check("goal_pulse in [0,1]", 0.0 <= st.goal_pulse <= 1.0,
                             f"pulse={st.goal_pulse}"))
        results.append(check("implemented > 0 (block-scoped parse)", st.implemented_goal_count > 0,
                             f"implemented={st.implemented_goal_count}"))
    else:
        results.append(check("VORPAL absent (skip real-DAG checks)", True))

    # 1b. Regression: child lines that only REFERENCE a goal (UNLOCKS/BLOCKED
    #     BY) must not be counted as new goal blocks. This used to inflate the
    #     count and fabricate an open goal (35 vs 33 real titles).
    with tempfile.TemporaryDirectory() as tmp:
        fake_goals = Path(tmp) / "GOALS.md"
        fake_goals.write_text(
            "- [x] **[a1->b1->t0] GOAL_1.1:** Triad State Memory Abstraction\n"
            "  - [IMPLEMENTED: state_memory_manager]\n"
            "  - [UNLOCKS: GOAL_6.1 - HIVE Integration Bridge now unblocked\n"
            "- [x] **[a6->b6->t1] GOAL_6.6:** Generational Fold Gates\n"
            "  - [IMPLEMENTED: fold_gate_monitor]\n"
            "  - [BLOCKED BY: GOAL_6.1] -> RESOLVED (roster feed)\n",
            encoding="utf-8")
        old_goals_path = mod.GOALS_PATH
        mod.GOALS_PATH = fake_goals
        try:
            t, o, i = b._parse_goals(fake_goals)
            results.append(check("UNLOCKS/BLOCKED-BY refs not counted as goals",
                                 t == 2 and o == 0 and i == 2,
                                 f"total={t} open={o} implemented={i}"))
        finally:
            mod.GOALS_PATH = old_goals_path

    # 2. Telemetry write path to a temp ledger.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_ledger = Path(tmp) / "TELEMETRY.json"
        mod.MARKUS_LEDGER_PATH = tmp_ledger
        p = b.write_markus_telemetry(matrix_state=[{"model": "x", "w": 1.0}],
                                     network_state={"has_internet": True},
                                     server_ok=True)
        results.append(check("telemetry ledger written", p is not None and p.exists()))
        if p and p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            results.append(check("telemetry payload correct", d.get("server_ok") is True))

    # 3. Fail-open when VORPAL root is absent.
    mod.VORPAL_ROOT = Path(tmp_ledger) / "does_not_exist"
    mod.GOALS_PATH = mod.VORPAL_ROOT / "GOALS.md"
    st2 = b.read_vorpal_status()
    results.append(check("fail-open on absent VORPAL", st2.goal_count == 0))

    print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
