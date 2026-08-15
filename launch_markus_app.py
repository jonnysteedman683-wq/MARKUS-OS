#!/usr/bin/env python3
"""
MARKUS OS Electron Application Launcher
Launches the Electron wrapper for the MARKUS OS Holographic Command Deck.
Usage: python launch_markus_app.py [--dev] [--packaged]
"""

from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path

ELECTRON_DIR = Path(sys.argv[0]).resolve().parent / "markus-os-electron"

def main() -> int:
    parser = argparse.ArgumentParser(description="Launch MARKUS OS Electron Desktop App")
    parser.add_argument("--dev", action="store_true", help="Run via npm start (development)")
    parser.add_argument("--packaged", action="store_true", help="Build packaged installer")
    args = parser.parse_args()

    os.chdir(ELECTRON_DIR)

    if not (ELECTRON_DIR / "node_modules").exists():
        print("Installing Electron dependencies...")
        subprocess.run(["npm", "install"], cwd=str(ELECTRON_DIR), check=True)

    if args.packaged:
        print("Building packaged Electron application...")
        subprocess.run(["npm", "run", "dist"], cwd=str(ELECTRON_DIR), check=True)
    else:
        print("Starting MARKUS OS in Electron development mode...")
        subprocess.run(["npm", "start"], cwd=str(ELECTRON_DIR), check=True)

    return 0

if __name__ == "__main__":
    sys.exit(main())
