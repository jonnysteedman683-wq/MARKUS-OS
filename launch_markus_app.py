#!/usr/bin/env python3
"""launch_markus_app.py — Python Desktop App Launcher & Executable Packaging Utility for MARKUS OS."""

from __future__ import annotations
import os
import sys
import subprocess
import shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
ELECTRON_DIR = ROOT / "markus-os-electron"

def check_npm_installed() -> bool:
    return shutil.which("npm") is not None or shutil.which("npm.cmd") is not None

def run_npm_install():
    print("[MARKUS App Launcher] Ensuring npm dependencies in markus-os-electron...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.run([npm_cmd, "install"], cwd=str(ELECTRON_DIR), check=True)

def launch_electron_dev():
    print("[MARKUS App Launcher] Launching MARKUS OS Desktop App (Dev Mode)...")
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    subprocess.run([npx_cmd, "electron", "."], cwd=str(ELECTRON_DIR))

def build_executable_package():
    print("[MARKUS App Launcher] Packaging MARKUS OS Desktop Executable...")
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    subprocess.run([npx_cmd, "electron-builder", "--dir"], cwd=str(ELECTRON_DIR), check=True)
    print(f"[MARKUS App Launcher] Package built cleanly in: {ELECTRON_DIR / 'dist'}")

def main():
    print("==========================================================")
    print("  MARKUS OS Desktop Launcher & Packaging Utility")
    print("==========================================================")

    if not check_npm_installed():
        print("[ERROR] npm is not found in PATH. Please install Node.js.")
        sys.exit(1)

    node_modules = ELECTRON_DIR / "node_modules"
    if not node_modules.exists():
        run_npm_install()

    if "--package" in sys.argv or "--dist" in sys.argv:
        build_executable_package()
    else:
        launch_electron_dev()

if __name__ == "__main__":
    main()
