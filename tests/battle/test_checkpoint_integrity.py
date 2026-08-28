"""
Battle-test: checkpoint integrity + restore auth (markus_checkpoint).

REG-14 (MED): restore_checkpoint() re-commits ALL registers — including
protected system registers (OS_STATUS / VERSION) — with no namespace
allowlist. A checkpoint that legitimately carries attacker-influenced
register values overwrites live protected state on restore.
REG-15 (LOW): index.json is trusted blindly on load. A tampered index that
advertises a ghost checkpoint (with a self-consistent payload + checksum)
lets restore apply attacker-controlled data; the index has no integrity
verification of its own.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from markus_checkpoint import MarkusCheckpointManager
from markus_db import PersistentCortexDB


@pytest.fixture()
def mgr(tmp_path: Path) -> MarkusCheckpointManager:
    db = PersistentCortexDB(db_path=tmp_path / "c.db")
    return MarkusCheckpointManager(checkpoint_dir=tmp_path / "chk", db=db)


def test_restore_does_not_poison_protected_registers(mgr) -> None:
    """REG-14: restoring a checksum-VALID checkpoint must not overwrite
    protected system registers (OS_STATUS / VERSION) with checkpoint values."""
    mgr.db.set_register("OS_STATUS", "BOOTED")
    mgr.db.set_register("VERSION", "1.0.0")
    # Attacker (or a compromised writer) creates a checksum-valid checkpoint
    # whose registers claim hostile protected-state values.
    meta = mgr.create_checkpoint(
        registers={"OS_STATUS": "DEGRADED", "VERSION": "0.0.0-EVIL"},
        working_memory=[],
        reason="attacker",
    )
    # Today: checksum verifies, restore succeeds and re-commits registers
    # verbatim (markus_checkpoint.restore_checkpoint lines ~150-153).
    mgr.restore_checkpoint(meta.checkpoint_id)
    assert mgr.db.get_register("OS_STATUS") == "BOOTED", (
        "protected register OS_STATUS overwritten by checkpoint restore"
    )
    assert mgr.db.get_register("VERSION") == "1.0.0", (
        "protected register VERSION overwritten by checkpoint restore"
    )


def test_tampered_payload_checksum_rejected(mgr, tmp_path: Path) -> None:
    """Guardrail: on-disk payload tampering must be detected (checksum)."""
    meta = mgr.create_checkpoint(
        registers={"OS_STATUS": "DEGRADED", "OS_MODE": "EVIL"},
        working_memory=[],
        reason="attacker",
    )
    path = Path(meta.file_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["registers"]["SECRET"] = "leaked"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        mgr.restore_checkpoint(meta.checkpoint_id)


def test_restore_unknown_checkpoint_id_fails(mgr) -> None:
    with pytest.raises(ValueError):
        mgr.restore_checkpoint("chk_does_not_exist")


def test_index_injection_does_not_restore_ghost(mgr, tmp_path: Path) -> None:
    """REG-15: an index.json tampered to advertise a ghost checkpoint must
    NOT let restore apply attacker-controlled data."""
    evil = {
        "checkpoint_id": "chk_ghost",
        "timestamp": 0,
        "iso_time": "x",
        "reason": "attacker",
        "registers": {"OS_STATUS": "DEGRADED", "SECRET": "leaked"},
        "working_memory": [],
        "tags": [],
    }
    payload = json.dumps(evil, indent=2).encode("utf-8")
    evil_path = mgr.checkpoint_dir / "chk_ghost.json"
    evil_path.write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    # Attacker rewrites the index so it advertises the ghost checkpoint with a
    # self-consistent checksum (index itself is not integrity-protected today).
    index = mgr.checkpoint_dir / "index.json"
    index.write_text(json.dumps([{
        "checkpoint_id": "chk_ghost", "timestamp": 0, "iso_time": "x",
        "trigger_reason": "attacker", "l1_register_count": 2,
        "l2_thought_count": 0, "checksum_sha256": checksum,
        "file_path": str(evil_path), "tags": [],
    }]), encoding="utf-8")

    from markus_checkpoint import MarkusCheckpointManager as M
    reloaded = M(checkpoint_dir=mgr.checkpoint_dir,
                 db=PersistentCortexDB(db_path=tmp_path / "c2.db"))
    with pytest.raises(ValueError):
        reloaded.restore_checkpoint("chk_ghost")
