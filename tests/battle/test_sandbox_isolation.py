"""
Battle-test: sandbox isolation (markus_sandbox.MarkusProcessSandbox).

REG-01 (CRITICAL): the "sandbox" is a plain subprocess with full host
privileges. It must NOT be able to write files outside its root, read the
host auth.json (Nous API key), or reach the network. Currently it can do all
three — these tests are RED.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from markus_sandbox import MarkusProcessSandbox


@pytest.fixture()
def sandbox_root(tmp_path: Path) -> Path:
    return tmp_path / "sandbox_ws"


@pytest.fixture()
def sb(sandbox_root: Path) -> MarkusProcessSandbox:
    return MarkusProcessSandbox(sandbox_root=sandbox_root, default_timeout_s=5.0)


def _run(sb: MarkusProcessSandbox, code: str, timeout_s: float = 5.0):
    return asyncio.run(sb.execute_python_code(code, timeout_s=timeout_s))


def test_cannot_write_outside_sandbox_root(sb, tmp_path: Path) -> None:
    """REG-01: sandboxed code must not write to the host filesystem."""
    target = tmp_path / "ESCAPED.txt"
    code = f"open({str(target)!r}, 'w').write('pwned')"
    res = _run(sb, code)
    assert res.exit_code != 0, "sandboxed code succeeded in writing outside root"
    assert not target.exists(), "host file was created by sandboxed code"


def test_cannot_read_host_secrets(sb, tmp_path: Path) -> None:
    """REG-02: sandboxed code must not be able to read the Nous API key."""
    fake_auth = tmp_path / "auth.json"
    fake_auth.write_text('{"providers": {"nous": {"agent_key": "SUPER_SECRET_KEY_XYZ"}}}')
    code = f"print(open({str(fake_auth)!r}).read())"
    res = _run(sb, code)
    assert res.exit_code != 0, "sandboxed code read a host secret file"
    assert "SUPER_SECRET_KEY_XYZ" not in res.stdout


def test_cannot_exfiltrate_via_network(sb) -> None:
    """REG-03: sandboxed code must not be able to open sockets (exfil path)."""
    code = (
        "import socket\n"
        "s = socket.socket(); s.connect(('127.0.0.1', 9))\n"
        "print('NETWORK_OK')"
    )
    res = _run(sb, code, timeout_s=3.0)
    assert res.exit_code != 0, "sandboxed code opened a network socket"
    assert "NETWORK_OK" not in res.stdout


def test_timeout_kills_process_tree(sb, tmp_path: Path) -> None:
    """REG-04: a runaway sandbox must be killed within timeout (no orphan)."""
    code = "import time\nwhile True:\n    time.sleep(1)\n"
    t0 = asyncio.get_event_loop().time()
    res = _run(sb, code, timeout_s=1.0)
    elapsed = asyncio.get_event_loop().time() - t0
    assert res.timed_out is True
    assert elapsed < 5.0, "sandbox did not terminate within a bounded window"
