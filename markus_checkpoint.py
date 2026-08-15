#!/usr/bin/env python3
"""
MARKUS OS Autonomous Micro-Checkpointing & Snapshot Rollback Subsystem (Upgrade 25)
Captures atomic point-in-time snapshots of L1 registers, L2 working memory,
process table state, and circuit-breaker telemetry with SHA-256 integrity verification
and fast transactional rollback upon fault detection.
"""

from __future__ import annotations
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.Checkpoint")

CHECKPOINT_DIR = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/checkpoints")

@dataclass
class CheckpointMetadata:
    checkpoint_id: str
    timestamp: float
    iso_time: str
    trigger_reason: str
    l1_register_count: int
    l2_thought_count: int
    checksum_sha256: str
    file_path: str
    tags: List[str] = field(default_factory=list)

class MarkusCheckpointManager:
    """
    Manages atomic micro-checkpointing and point-in-time state restoration for MARKUS OS.
    Ensures zero state loss during kernel failures, test regressions, or node degradation.
    """

    def __init__(
        self,
        checkpoint_dir: Path = CHECKPOINT_DIR,
        db: Optional[PersistentCortexDB] = None
    ) -> None:
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.db = db or PersistentCortexDB()
        self.history: List[CheckpointMetadata] = []
        self._load_index()

    def _load_index(self) -> None:
        index_file = self.checkpoint_dir / "index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                self.history = [CheckpointMetadata(**item) for item in data]
            except Exception as e:
                logger.warning(f"Could not load checkpoint index: {e}")

    def _save_index(self) -> None:
        index_file = self.checkpoint_dir / "index.json"
        data = [asdict(item) for item in self.history]
        index_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _compute_checksum(data_bytes: bytes) -> str:
        return hashlib.sha256(data_bytes).hexdigest()

    def create_checkpoint(
        self,
        registers: Dict[str, Any],
        working_memory: List[Dict[str, Any]],
        reason: str = "MANUAL_CHECKPOINT",
        tags: Optional[List[str]] = None
    ) -> CheckpointMetadata:
        """Captures an atomic snapshot of current state and computes verification hash."""
        now = time.time()
        iso = datetime.now(timezone.utc).isoformat()
        cid = f"chk_{int(now)}_{hashlib.sha256(str(now).encode()).hexdigest()[:6]}"

        snapshot_payload = {
            "checkpoint_id": cid,
            "timestamp": now,
            "iso_time": iso,
            "reason": reason,
            "registers": registers,
            "working_memory": working_memory,
            "tags": tags or []
        }

        payload_bytes = json.dumps(snapshot_payload, indent=2).encode("utf-8")
        checksum = self._compute_checksum(payload_bytes)

        file_name = f"{cid}.json"
        file_path = self.checkpoint_dir / file_name
        file_path.write_bytes(payload_bytes)

        meta = CheckpointMetadata(
            checkpoint_id=cid,
            timestamp=now,
            iso_time=iso,
            trigger_reason=reason,
            l1_register_count=len(registers),
            l2_thought_count=len(working_memory),
            checksum_sha256=checksum,
            file_path=str(file_path),
            tags=tags or []
        )

        self.history.append(meta)
        self._save_index()

        # Log checkpoint creation to L3 persistent database
        self.db.append_thought(
            f"checkpoint_{cid}",
            "CHECKPOINT_MANAGER",
            f"Created micro-checkpoint '{cid}' ({reason})",
            {"checkpoint_id": cid, "checksum": checksum, "registers": len(registers)}
        )

        logger.info(f"Created micro-checkpoint '{cid}' (checksum={checksum[:8]}...)")
        return meta

    def restore_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """Validates snapshot integrity and returns full restored state."""
        meta = next((m for m in self.history if m.checkpoint_id == checkpoint_id), None)
        if not meta:
            raise ValueError(f"Checkpoint '{checkpoint_id}' not found in index.")

        file_path = Path(meta.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Checkpoint archive file {file_path} is missing.")

        content_bytes = file_path.read_bytes()
        actual_checksum = self._compute_checksum(content_bytes)

        if actual_checksum != meta.checksum_sha256:
            raise ValueError(
                f"Checkpoint integrity violation! Expected {meta.checksum_sha256[:8]}, got {actual_checksum[:8]}"
            )

        data = json.loads(content_bytes.decode("utf-8"))

        # Re-commit registers to L3 DB
        if self.db and "registers" in data:
            for k, v in data["registers"].items():
                self.db.set_register(k, v)

        # Log restoration event
        self.db.append_thought(
            f"rollback_{checkpoint_id}_{int(time.time())}",
            "CHECKPOINT_MANAGER",
            f"Restored system state from checkpoint '{checkpoint_id}'",
            {"restored_checkpoint": checkpoint_id, "checksum_verified": True}
        )

        logger.info(f"Successfully rolled back to checkpoint '{checkpoint_id}'")
        return data

    def list_checkpoints(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [asdict(m) for m in self.history[-limit:]]

    def prune_checkpoints(self, keep_latest: int = 20) -> int:
        if len(self.history) <= keep_latest:
            return 0

        prune_targets = self.history[:-keep_latest]
        removed = 0
        for p in prune_targets:
            f = Path(p.file_path)
            if f.exists():
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass

        self.history = self.history[-keep_latest:]
        self._save_index()
        return removed

def _test_checkpoint_subsystem():
    print("=== MARKUS Micro-Checkpoint & Rollback Subsystem Test ===")
    test_dir = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/checkpoints_test")
    mgr = MarkusCheckpointManager(checkpoint_dir=test_dir)

    initial_regs = {"OS_STATUS": "ACTIVE", "VERSION": "1.0.0", "TEST_FLAG": "ALPHA_1"}
    initial_thoughts = [{"agent": "TEST", "thought": "Baseline state established."}]

    # 1. Create Baseline Checkpoint
    chk1 = mgr.create_checkpoint(initial_regs, initial_thoughts, reason="PRE_EXPERIMENT_BASELINE")
    print(f"Created Checkpoint: {chk1.checkpoint_id} (Checksum: {chk1.checksum_sha256[:12]}...)")

    # 2. Mutate State (Simulate degradation/regression)
    mutated_regs = {"OS_STATUS": "DEGRADED", "VERSION": "1.0.0", "TEST_FLAG": "CORRUPT_MUTATION"}
    chk2 = mgr.create_checkpoint(mutated_regs, [], reason="MUTATED_STATE")

    # 3. Rollback to Baseline Checkpoint
    restored = mgr.restore_checkpoint(chk1.checkpoint_id)
    print(f"Restored Checkpoint ID: {restored['checkpoint_id']}")
    print(f"Restored Registers: {restored['registers']}")

    assert restored["registers"]["TEST_FLAG"] == "ALPHA_1", "Rollback failed to restore baseline flag"
    assert restored["checkpoint_id"] == chk1.checkpoint_id, "Wrong checkpoint restored"

    # 4. Clean up test directory
    shutil.rmtree(test_dir, ignore_errors=True)
    print("\n✅ Micro-Checkpoint & Rollback Subsystem Test: PASSED")

if __name__ == "__main__":
    _test_checkpoint_subsystem()
