#!/usr/bin/env python3
"""verify_all.py — Unified Master Verification Suite for OMNIPRIME Dual Super-Agent Architecture."""

from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

HARNESSES = [
    ("hermes_verify_router.py", "Zero-Cost Router & Adaptive Matrix Feedback"),
    ("hermes_verify_vorpal_bridge.py", "Bidirectional VORPAL Goal DAG & Telemetry Bridge"),
    ("hermes_verify_markus_brain.py", "Brain Backend & Nous Key Alignment"),
    ("markus_ui_db.py", "UI OS Database & Session Registers"),
]

def main() -> int:
    print("==========================================================")
    print("  OMNIPRIME Unified Super-Agent Verification Suite")
    print("==========================================================")

    all_passed = True
    for script, desc in HARNESSES:
        target = ROOT / script
        print(f"\n[RUNNING] {script} — {desc}")
        proc = subprocess.run([sys.executable, str(target)], capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"  [PASS] {script} verified cleanly.")
        else:
            print(f"  [FAIL] {script} returned exit code {proc.returncode}")
            if proc.stdout:
                print("  stdout tail:", proc.stdout.strip().splitlines()[-3:])
            if proc.stderr:
                print("  stderr tail:", proc.stderr.strip().splitlines()[-3:])
            all_passed = False

    print("\n----------------------------------------------------------")
    if all_passed:
        print("OVERALL SYSTEM VERIFICATION: ALL PASSED (100% GREEN)")
        return 0
    else:
        print("OVERALL SYSTEM VERIFICATION: AT LEAST ONE GATE FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
