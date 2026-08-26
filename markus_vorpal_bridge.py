#!/usr/bin/env python3
"""
MARKUS-OS <-> VORPAL Bidirectional Bridge.

Intertwines the two projects that were previously only loosely connected
(MARKUS -> Obsidian Vault). This adds the missing return path and turns the
link into a real, state-exchanging loop:

  DOWNSTREAM (VORPAL -> MARKUS):
    Read VORPAL's decision layer into MARKUS so the dice engine / router can
    weight toward VORPAL's open goals:
      - EVOLVE/GOALS/GOALS.md  -> goal DAG (open vs implemented)
      - EVOLVE/NOTES.md        -> recent deltas / ERR entries
      - SOUL.md                -> objectives / cardinal stars
    Produces a compact VORPALStatus snapshot.

  UPSTREAM (MARKUS -> VORPAL):
    Write MARKUS's live telemetry into a VORPAL-facing ledger so VORPAL's
    decision layer can see what its body is doing:
      - adaptive-matrix weights (model routing state)
      - network-intel transport state
      - server / dice-engine health
      - offline disk-backed telemetry spooling when VORPAL_ROOT is detached

Stdlib-only, fail-open: if VORPAL is absent or unreadable, every method
degrades to empty/None or local spool rather than raising. Never blocks on VORPAL.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Markus.VorpalBridge")

# ---- Paths (overridable via env for tests / portability) ----
VORPAL_ROOT = Path(os.environ.get(
    "VORPAL_ROOT", r"C:\Users\jonny\OneDrive\Desktop\VORPAL"))
GOALS_PATH = Path(os.environ.get(
    "VORPAL_GOALS", str(VORPAL_ROOT / "EVOLVE/GOALS/GOALS.md")))
NOTES_PATH = Path(os.environ.get(
    "VORPAL_NOTES", str(VORPAL_ROOT / "EVOLVE/NOTES.md")))
SOUL_PATH = Path(os.environ.get(
    "VORPAL_SOUL", str(VORPAL_ROOT / "SOUL.md")))

# Where MARKUS writes its telemetry for VORPAL to read.
MARKUS_LEDGER_PATH = Path(os.environ.get(
    "MARKUS_LEDGER", str(VORPAL_ROOT / "EVOLVE/MARKUS_TELEMETRY.json")))

# Local offline spool buffer when VORPAL_ROOT is detached
DEFAULT_PRIVATE_ROOT = Path(os.environ.get(
    "MARKUS_PRIVATE_ROOT",
    os.environ.get("HERMES_PRIVATE_ROOT", r"C:\Users\jonny\OneDrive\Desktop\New folder\markus_private")
))
VORPAL_SPOOL_PATH = Path(os.environ.get(
    "VORPAL_SPOOL_PATH", str(DEFAULT_PRIVATE_ROOT / "ipc" / "vorpal_telemetry_spool.jsonl")))


@dataclass
class VORPALGoal:
    title: str
    status: str          # e.g. "tier_0_apex", "COMPLETE", "tier_2_stagnant"
    implemented: bool    # True if an [IMPLEMENTED: ...] marker exists
    phase: Optional[str] = None


@dataclass
class VORPALStatus:
    goal_count: int = 0
    open_goal_count: int = 0
    implemented_goal_count: int = 0
    recent_errors: List[str] = field(default_factory=list)
    objectives: List[str] = field(default_factory=list)
    cardinals: Dict[str, str] = field(default_factory=dict)
    parsed_at: float = 0.0

    @property
    def goal_pulse(self) -> float:
        """Fraction of goals that are open (not implemented/complete).
        A high pulse = lots of open work -> dice should weight toward it."""
        if self.goal_count == 0:
            return 0.0
        return round(self.open_goal_count / self.goal_count, 3)


class MarkusVorpalBridge:
    """Read VORPAL's decision layer + write MARKUS's telemetry back."""

    # ------------------------------------------------------------------
    # DOWNSTREAM: VORPAL -> MARKUS
    # ------------------------------------------------------------------
    def read_vorpal_status(self) -> VORPALStatus:
        st = VORPALStatus(parsed_at=time.time())
        try:
            if GOALS_PATH.exists():
                st.goal_count, st.open_goal_count, st.implemented_goal_count = \
                    self._parse_goals(GOALS_PATH)
        except Exception as e:  # noqa: BLE001
            logger.warning("vorpal goals parse failed: %s", e)
        try:
            if NOTES_PATH.exists():
                st.recent_errors = self._parse_recent_errors(NOTES_PATH)
        except Exception as e:  # noqa: BLE001
            logger.warning("vorpal notes parse failed: %s", e)
        try:
            if SOUL_PATH.exists():
                st.objectives, st.cardinals = self._parse_soul(SOUL_PATH)
        except Exception as e:  # noqa: BLE001
            logger.warning("vorpal soul parse failed: %s", e)
        return st

    @staticmethod
    def _parse_goals(path: Path) -> tuple:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        total = open_ct = impl = 0
        in_goal_block = False
        block_has_impl = False
        block_is_done = False
        phase = None
        for line in lines:
            if line.startswith("## "):
                phase = line[3:].strip()
                continue
            if "GOAL_" in line:
                # A new goal title starts a block.
                if in_goal_block:
                    # close the previous block
                    if block_has_impl:
                        impl += 1
                    if not block_is_done:
                        open_ct += 1
                total += 1
                in_goal_block = True
                block_has_impl = "[IMPLEMENTED" in line
                block_is_done = ("COMPLETE" in line.upper() or block_has_impl
                                 or "tier_0" in line or "tier_1" in line
                                 or "[x]" in line)
                continue
            # A non-GOAL line inside the current goal block (indented child).
            if in_goal_block:
                if "[IMPLEMENTED" in line:
                    block_has_impl = True
                    block_is_done = True
                if "COMPLETE" in line.upper() or "tier_0" in line or "tier_1" in line:
                    block_is_done = True
        # close the last block
        if in_goal_block:
            if block_has_impl:
                impl += 1
            if not block_is_done:
                open_ct += 1
        return total, open_ct, impl

    @staticmethod
    def _parse_recent_errors(path: Path) -> List[str]:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        errs = []
        for line in lines:
            m = re.search(r"\[(ERR_\w+)\]", line)
            if m:
                errs.append(line.strip())
        return errs[-10:]  # most recent 10

    @staticmethod
    def _parse_soul(path: Path) -> tuple:
        text = path.read_text(encoding="utf-8", errors="replace")
        objectives = []
        for m in re.finditer(r"^\d+\.\s+\*\*(.+?)\*\*", text, re.MULTILINE):
            if "OBJECTIVES" not in text[:text.find(m.group(0))]:
                continue
            objectives.append(m.group(1).strip())
        # cardinal stars: NORTH/SOUTH/EAST/WEST
        cardinals = {}
        for m in re.finditer(r"-\s+\*\*(NORTH|SOUTH|EAST|WEST)\*\*\s*[—–-]?\s*(.+)", text):
            cardinals[m.group(1)] = m.group(2).strip()
        return objectives[:6], cardinals

    # ------------------------------------------------------------------
    # UPSTREAM: MARKUS -> VORPAL
    # ------------------------------------------------------------------
    def write_markus_telemetry(self, matrix_state: Optional[List] = None,
                               network_state: Optional[Dict] = None,
                               server_ok: Optional[bool] = None,
                               extra: Optional[Dict] = None) -> Optional[Path]:
        """Persist MARKUS's live telemetry to the VORPAL ledger.
        When VORPAL_ROOT exists (or MARKUS_LEDGER_PATH is explicitly redirected),
        writes MARKUS_LEDGER_PATH. When VORPAL_ROOT is absent, spools to local
        offline buffer (e.g. markus_private/ipc/vorpal_telemetry_spool.jsonl)
        and returns the spooled path."""
        try:
            payload = {
                "written_at": time.time(),
                "matrix": matrix_state or [],
                "network": network_state or {},
                "server_ok": server_ok,
                "extra": extra or {},
            }
            # Check whether target ledger or VORPAL_ROOT exists
            is_vorpal_available = VORPAL_ROOT.exists()
            is_explicit_ledger = (
                MARKUS_LEDGER_PATH.parent.exists() and
                not str(MARKUS_LEDGER_PATH).startswith(str(VORPAL_ROOT))
            )
            if is_vorpal_available or is_explicit_ledger:
                MARKUS_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
                MARKUS_LEDGER_PATH.write_text(
                    json.dumps(payload, indent=2, default=str), encoding="utf-8")
                return MARKUS_LEDGER_PATH
            else:
                # Spool to local offline buffer
                VORPAL_SPOOL_PATH.parent.mkdir(parents=True, exist_ok=True)
                with VORPAL_SPOOL_PATH.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, default=str) + "\n")
                return VORPAL_SPOOL_PATH
        except Exception as e:  # noqa: BLE001
            logger.warning("markus telemetry write failed: %s", e)
            return None

    def get_spooled_telemetry_count(self) -> int:
        """Returns the number of un-flushed spooled telemetry entries."""
        if not VORPAL_SPOOL_PATH.exists():
            return 0
        try:
            lines = [l.strip() for l in VORPAL_SPOOL_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            return len(lines)
        except Exception:
            return 0

    def flush_spooled_telemetry(self, target_ledger: Optional[Path] = None) -> int:
        """Flushes local spooled telemetry records into the VORPAL ledger once available.
        Returns the number of spooled telemetry records flushed."""
        target = target_ledger or MARKUS_LEDGER_PATH
        if not VORPAL_SPOOL_PATH.exists():
            return 0
        if not (VORPAL_ROOT.exists() or target.parent.exists()):
            return 0
        try:
            lines = [l.strip() for l in VORPAL_SPOOL_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            if not lines:
                return 0
            last_payload = None
            for line in lines:
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        last_payload = payload
                except Exception:
                    continue
            if last_payload and isinstance(last_payload, dict):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(last_payload, indent=2, default=str), encoding="utf-8")
            VORPAL_SPOOL_PATH.unlink(missing_ok=True)
            return len(lines)
        except Exception as e:  # noqa: BLE001
            logger.warning("flush_spooled_telemetry failed: %s", e)
            return 0

    def sync_vorpal_to_memory(self, memory_cortex: Any) -> Dict[str, Any]:
        """Bridge helper to set VORPAL status registers on a MARKUS MemoryCortex."""
        st = self.read_vorpal_status()
        summary = {
            "goal_count": st.goal_count,
            "open_goal_count": st.open_goal_count,
            "implemented_goal_count": st.implemented_goal_count,
            "goal_pulse": st.goal_pulse,
            "recent_errors": st.recent_errors,
            "objectives": st.objectives,
            "cardinals": st.cardinals,
            "parsed_at": st.parsed_at,
        }
        if memory_cortex and hasattr(memory_cortex, "set_register"):
            memory_cortex.set_register("VORPAL_GOAL_PULSE", st.goal_pulse)
            memory_cortex.set_register("VORPAL_OPEN_GOALS", st.open_goal_count)
            memory_cortex.set_register("VORPAL_GOALS_TOTAL", st.goal_count)
            memory_cortex.set_register("VORPAL_STATUS_SUMMARY", summary)
        return summary

    # ------------------------------------------------------------------
    # Convenience: build the MARKUS telemetry payload from local modules.
    # ------------------------------------------------------------------
    def snapshot_from_markus(self) -> Dict[str, Any]:
        """Pull live state from the in-repo modules (fail-open on each)."""
        out: Dict[str, Any] = {}
        # Adaptive matrix
        try:
            import markus_adaptive_matrix as _m
            mx = _m.MarkusAdaptiveWeightMatrix()
            out["matrix"] = mx.get_matrix_state()
        except Exception as e:  # noqa: BLE001
            out["matrix_error"] = str(e)
        # Network intel
        try:
            import markus_network_intel as _n
            rep = _n.build_report(probe=False)
            out["network"] = {
                "primary_connection_type": rep.primary_connection_type,
                "has_internet": rep.has_internet,
                "vpn_active": rep.vpn_active,
            }
        except Exception as e:  # noqa: BLE001
            out["network_error"] = str(e)
        # Server health
        try:
            import urllib.request
            with urllib.request.urlopen(
                    "http://127.0.0.1:8128/api/health", timeout=2) as r:
                out["server_ok"] = r.status == 200
        except Exception:
            out["server_ok"] = False
        return out

    # ------------------------------------------------------------------
    # Dice weighting helper
    # ------------------------------------------------------------------
    def vorpal_goal_weight_bias(self) -> float:
        """How much the dice engine should bias toward VORPAL work this cycle.
        0.0 = VORPAL fully implemented (no reason to bias); higher = more open
        work available. Fail-open -> 0.0 if VORPAL unreadable."""
        st = self.read_vorpal_status()
        return st.goal_pulse


def _self_test() -> int:
    global VORPAL_ROOT, MARKUS_LEDGER_PATH, VORPAL_SPOOL_PATH
    print("=== MARKUS <-> VORPAL Bridge Test ===")
    bridge = MarkusVorpalBridge()
    st = bridge.read_vorpal_status()
    print(f"  VORPAL goals: {st.goal_count} total, {st.open_goal_count} open, "
          f"{st.implemented_goal_count} implemented (pulse={st.goal_pulse})")
    print(f"  recent errors: {len(st.recent_errors)}")
    print(f"  objectives: {st.objectives[:3]}")
    print(f"  cardinals: {st.cardinals}")

    # 1. Write telemetry to a temp ledger so we don't clobber the real one.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_ledger = Path(tmp) / "TELEMETRY.json"
        orig_ledger = MARKUS_LEDGER_PATH
        try:
            MARKUS_LEDGER_PATH = tmp_ledger
            p = bridge.write_markus_telemetry(matrix_state=[{"model": "x", "w": 1.0}],
                                              network_state={"has_internet": True},
                                              server_ok=True)
            assert p is not None and p.exists(), "telemetry ledger should be written"
            loaded = json.loads(p.read_text(encoding="utf-8"))
            assert loaded["server_ok"] is True
            print(f"  telemetry ledger written: {p} ({len(loaded)} keys)")
        finally:
            MARKUS_LEDGER_PATH = orig_ledger

    # 2. Offline telemetry spooling and drainage test
    with tempfile.TemporaryDirectory() as tmp2:
        orig_root = VORPAL_ROOT
        orig_ledger = MARKUS_LEDGER_PATH
        orig_spool = VORPAL_SPOOL_PATH
        try:
            fake_absent_root = Path(tmp2) / "absent_vorpal"
            VORPAL_ROOT = fake_absent_root
            MARKUS_LEDGER_PATH = fake_absent_root / "EVOLVE" / "MARKUS_TELEMETRY.json"
            VORPAL_SPOOL_PATH = Path(tmp2) / "ipc" / "vorpal_telemetry_spool.jsonl"

            spool_p = bridge.write_markus_telemetry(matrix_state=[{"model": "offline", "w": 0.5}],
                                                    server_ok=False)
            assert spool_p is not None and spool_p.exists(), "spool path must exist"
            assert bridge.get_spooled_telemetry_count() == 1, "spooled count should be 1"

            # Simulate VORPAL root becoming available and flush
            fake_absent_root.mkdir(parents=True, exist_ok=True)
            flushed = bridge.flush_spooled_telemetry()
            assert flushed == 1, f"expected 1 flushed, got {flushed}"
            assert MARKUS_LEDGER_PATH.exists(), "flushed ledger should exist"
            assert bridge.get_spooled_telemetry_count() == 0, "spooled count should be 0 after flush"
            print("  offline telemetry spool & flush: PASS")
        finally:
            VORPAL_ROOT = orig_root
            MARKUS_LEDGER_PATH = orig_ledger
            VORPAL_SPOOL_PATH = orig_spool

    print("[OK] Markus-Vorpal Bridge: PASSED")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="MARKUS <-> VORPAL bridge")
    ap.add_argument("--status", action="store_true", help="print VORPAL status JSON")
    ap.add_argument("--snapshot", action="store_true", help="write MARKUS telemetry to VORPAL ledger")
    args = ap.parse_args()
    if args.status:
        b = MarkusVorpalBridge()
        print(json.dumps(asdict(b.read_vorpal_status()), indent=2))
    elif args.snapshot:
        b = MarkusVorpalBridge()
        snap = b.snapshot_from_markus()
        p = b.write_markus_telemetry(
            matrix_state=snap.get("matrix"),
            network_state=snap.get("network"),
            server_ok=snap.get("server_ok"))
        print(f"wrote telemetry -> {p}")
    else:
        _self_test()
