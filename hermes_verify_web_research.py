#!/usr/bin/env python3
"""hermes_verify_web_research.py — standalone verification for the persistence
upgrade in markus_web_research.py (dice research slot now writes real artifacts).

AST gate + module self-test + direct persistence checks. Stdlib-only.
"""
from __future__ import annotations
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "markus_web_research.py"


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  -  {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main() -> int:
    results = []
    try:
        py_compile.compile(str(TARGET), doraise=True)
        results.append(check("py_compile markus_web_research.py", True))
    except Exception as e:  # noqa: BLE001
        results.append(check("py_compile markus_web_research.py", False, str(e)))
        print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
        return 0 if all(results) else 1

    # Module self-test (temp-path persistence, live-finding seam).
    proc = subprocess.run([sys.executable, str(TARGET)], capture_output=True, text=True)
    ok_run = proc.returncode == 0 and "PASSED" in proc.stdout
    results.append(check("module self-test passes", ok_run, "exit={}".format(proc.returncode)))
    if not ok_run:
        print(proc.stdout[-1500:])
        print(proc.stderr[-1500:])

    # Direct persistence + live-findings checks against a temp roadmap.
    sys.path.insert(0, str(HERE))
    import importlib.util
    spec = importlib.util.spec_from_file_location("wresearch", TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory() as tmp:
        rep = Path(tmp) / "roadmap.md"
        eng = mod.WebResearchEngine()
        live = ["LIVE_A", "LIVE_B"]
        r = eng.research_and_report("swarm_intelligence", live_findings=live,
                                    report_path=str(rep))  # str path must coerce
        text = rep.read_text(encoding="utf-8")
        results.append(check("writes roadmap artifact", rep.exists() and len(text) > 100))
        results.append(check("persists ALL findings incl live", "LIVE_A" in text and "LIVE_B" in text))
        results.append(check("accepts str report_path", "roadmap.md" in r["report_path"]))
        results.append(check("tags live_findings", r["live_findings"] is True))

    print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
