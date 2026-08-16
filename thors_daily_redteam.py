#!/usr/bin/env python3
"""Daily Thors Red Team validation script — cron job runner."""
import subprocess, sys, os
os.chdir(r"C:\Users\jonny\OneDrive\Desktop\New folder")
result = subprocess.run(
    [sys.executable, "markus_attack_simulator.py"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
if "Success rate:    100.0%" in result.stdout:
    print("SECURITY STATUS: GREEN - 17/17 attacks detected")
else:
    print("SECURITY STATUS: AMBER - detection rate below 100%")
sys.exit(result.returncode)
