"""
Battle-test: VORPAL CORE — ARK sandbox escapes (ark_sandbox.Sandbox).

REG-21 (CRITICAL): tier-1 AST "sandbox" runs code via exec() with a custom
globals dict, but the classic CPython escape
().__class__.__base__.__subclasses__() reaches _wrap_close -> sys -> os,
and importlib.import_module('os') is not blocked either. Arbitrary host
code runs with full privileges.
REG-22 (CRITICAL): the tier-2 subprocess wrapper defines _safe_open and
_blocked_socket but NEVER applies them (no `open = _safe_open` /
`socket.socket = _blocked_socket`), so the fallback path has unrestricted
file + network access. The wrapper is decorative.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# The sibling VORPAL repo is local-only (no remote; not published), so in CI it
# is absent and these tests skip with a clear reason.
_ark = pytest.importorskip(
    "ark_sandbox",
    reason="sibling VORPAL repo (ark_sandbox) not available in CI",
)
Sandbox = _ark.Sandbox

# VORPAL repo root (injected by conftest via BATTLE_TEST_VORPAL_ROOT)
VORPAL_ROOT = Path(__import__("conftest", fromlist=["VORPAL_ROOT"]).VORPAL_ROOT)


@pytest.fixture()
def sb() -> Sandbox:
    return Sandbox(timeout=5)


def test_classic_subclasses_escape_blocked(sb) -> None:
    """REG-21: __class__.__base__.__subclasses__() escape must be blocked."""
    code = (
        "[c for c in ().__class__.__base__.__subclasses__() "
        "if c.__name__=='_wrap_close'][0]"
        ".__init__.__globals__['sys'].modules['os'].system('echo PWNED')"
    )
    r = sb.execute(code)
    assert not r["success"], f"subclasses escape succeeded: {r.get('output')!r}"


def test_importlib_escape_blocked(sb) -> None:
    code = "import importlib\nimportlib.import_module('os').system('echo PWNED')"
    r = sb.execute(code)
    assert not r["success"], f"importlib escape succeeded: {r.get('output')!r}"


def test_tier2_wrapper_actually_applies_isolation() -> None:
    """REG-22: the subprocess wrapper must really rebind open/socket."""
    src_path = VORPAL_ROOT / "CORE" / "ark_sandbox.py"
    src = src_path.read_text(encoding="utf-8")
    assert "open = _safe_open" in src, "tier-2 wrapper never rebinds open()"
    assert "socket.socket = _blocked_socket" in src, (
        "tier-2 wrapper never rebinds socket.socket"
    )


def test_tier1_open_escape_blocked(sb, tmp_path: Path) -> None:
    """REG-23: even reachable builtins like open() must not touch host FS."""
    target = tmp_path / "OUTSIDE.txt"
    code = f"open({str(target)!r}, 'w').write('pwned')"
    r = sb.execute(code)
    assert not r["success"], "open() escape succeeded"
    assert not target.exists()
