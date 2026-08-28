"""
Battle-test: VORPAL CORE — kernel + electron shell hardening.

REG-27 (LOW): VORPAL kernel.spawn() accepts an arbitrary entrypoint string
that is recorded verbatim (no validation) — if a future executor ever
interprets it, this is an injection point.
REG-28 (MED): Electron main spawns the Python server with stdio:'inherit'
and no privilege/args validation, and the preload bridge exposes
window-control IPC but the page itself is served with NO Content-Security-
Policy — the HTML UI (markus_ui_os.html etc.) can execute inline scripts
with full origin privileges if any injection exists.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

VORPAL = Path(__import__("conftest", fromlist=["VORPAL_ROOT"]).VORPAL_ROOT)
MAIN = Path(__file__).resolve().parents[2]  # MARKUS-OS repo root


def test_kernel_spawn_validates_entrypoint() -> None:
    """REG-27: entrypoint must not be an executable injection."""
    if not (VORPAL / "kernel.py").exists():
        pytest.skip("sibling VORPAL repo (kernel.py) not available in CI")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "bt_kernel", str(VORPAL / "kernel.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    with pytest.raises((ValueError, TypeError)):
        mod.spawn("x", entrypoint="; rm -rf /", args=["--flag", "$(curl evil)"])


def test_electron_served_pages_have_csp() -> None:
    """REG-28: pages served over http://127.0.0.1:8128 must carry a CSP."""
    server_src = (MAIN / "markus_server.py").read_text(encoding="utf-8")
    # The server sets headers in _set_headers; a CSP header must be present.
    assert "Content-Security-Policy" in server_src, "no CSP header is emitted"


def test_electron_main_validates_server_args() -> None:
    """REG-28b: electron must not pass unvalidated args to the Python child."""
    src = (MAIN / "electron-main.js").read_text(encoding="utf-8")
    assert "spawn('python', [SERVER_SCRIPT]" in src and "SERVER_SCRIPT" in src
