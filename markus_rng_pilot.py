#!/usr/bin/env python3
"""
MARKUS OS Autonomous Upgrade Dice Engine (Compatibility Wrapper)
Redirects execution to markus_dice_engine.py.
"""
from __future__ import annotations
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    dice_script = Path(__file__).resolve().parent / "markus_dice_engine.py"
    res = subprocess.run([sys.executable, str(dice_script)] + sys.argv[1:])
    sys.exit(res.returncode)
