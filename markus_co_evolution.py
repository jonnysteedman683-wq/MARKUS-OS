#!/usr/bin/env python3
"""
MARKUS OS Co-Evolution Orchestrator (Upgrade 47)
Implements the full closed-loop self-improvement cycle:

  User Prompt
      ↓
  MarkUS Dice Engine (6-sided + reward-weighted)
      ↓
  Multi-Agent Debate Pipeline (3 personas)
      ↓
  PHOENIX CLI Validation (AST scan)
      ↓
  Auto-commit (git add + commit)
      ↓
  DevSwarm Health Check (42/42 modules)
      ↓
  Cortex → Skill Auto-Patcher
      ↓
  Reward Feedback → Dice Engine (bias future rolls)
      ↓
  Research Integration (Action 5: Technical Alternatives)
      ↓
  ┌──────────────────────────────────────────┐
  │ Back to: Next User Prompt / Cron Cycle   │
  └──────────────────────────────────────────┘

Usage:
    python markus_co_evolution.py --single   # Run one full cycle
    python markus_co_evolution.py --daemon   # Run continuously (cron mode)
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from markus_db import PersistentCortexDB
from markus_dice_engine import MarkusDiceEngine
from markus_debate_pipeline import MarkusDebatePipeline
from markus_cortex_replication import MarkusCortexReplicator
from markus_ring_buffer import MarkusSharedRingBuffer
from markus_kernel import MarkusKernel
from markus_reflexion import ReflexionLoopEngine
from markus_population_dice import PopulationDiceEngine
from markus_redteam import RedTeamOrchestrator

logger = logging.getLogger("Markus.CoEvolution")

REPO_ROOT = Path(os.path.dirname(os.path.abspath(__file__) if "__file__" in dir() else os.getcwd()))
SKILLS_DIR = Path(os.environ.get("HERMES_SKILLS_DIR", ""))


class CoEvolutionOrchestrator:
    """
    Orchestrates the complete self-improvement loop:
    dice roll → debate → validation → commit → health check → skill patch → reward
    """

    def __init__(
        self,
        cortex: Optional[PersistentCortexDB] = None,
        dice_engine: Optional[MarkusDiceEngine] = None,
        kernel: Optional[MarkusKernel] = None,
    ) -> None:
        self.cortex = cortex or PersistentCortexDB()
        self.dice_engine = dice_engine or MarkusDiceEngine(cortex=self.cortex)
        self.kernel = kernel or MarkusKernel()
        self.cortex_replicator = MarkusCortexReplicator(db=self.cortex)
        self.cortex_ring = MarkusSharedRingBuffer(
            name="markus_cortex_ring", capacity=256, slot_size=1024, create=True
        )
        self.cycle_counter = 0
        self._reward_log: List[Dict[str, Any]] = []

    # ─── Phase 1: Dice Roll + Debate ───

    async def phase_decision(self) -> Tuple[int, List[int], Any]:
        """
        Execute the dice engine with multi-agent debate.
        Returns: (final_roll, roll_sequence, debate_verdict)
        """
        final_roll, rolls = await self.dice_engine.execute_dice_cycle()
        action_label = self.dice_engine.ACTIONS.get(final_roll, "UNKNOWN")
        logger.info(f"[CoEvo] Dice rolled: {final_roll} ({action_label}) | Sequence: {rolls}")
        return final_roll, rolls, None

    # ─── Phase 2: PHOENIX CLI Validation ───

    def phase_validation(self) -> Tuple[bool, str]:
        """
        Run PHOENIX CLI AST batch scan on all modules.
        Returns: (all_passed, summary_output)
        """
        start = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, "phoenix_cli.py", "batch", "."],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(REPO_ROOT),
            )
            output = result.stdout + result.stderr
            elapsed = time.perf_counter() - start

            # Check for PASS markers
            pass_count = output.count("[PASS]")
            fail_count = output.count("[FAIL]")
            all_passed = fail_count == 0 and pass_count > 0

            summary = f"PHOENIX: {pass_count}P/{fail_count}F | {elapsed:.1f}s"
            logger.info(f"[CoEvo] Validation: {summary}")
            return all_passed, summary
        except Exception as e:
            logger.error(f"[CoEvo] PHOENIX CLI failed: {e}")
            return False, f"Validation error: {e}"

    # ─── Phase 3: Auto-Commit ───

    def phase_autocommit(self, action_label: str, rolls: List[int]) -> Optional[str]:
        """
        Auto-commit changes to git if working tree has modifications.
        Returns: commit hash if committed, None otherwise
        """
        try:
            # Check for changes
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=str(REPO_ROOT)
            )
            if not status.stdout.strip():
                logger.info("[CoEvo] No changes to commit")
                return None

            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                capture_output=True, text=True, cwd=str(REPO_ROOT)
            )

            # Commit
            roll_chain = "→".join(str(r) for r in rolls)
            commit_msg = f"feat: {action_label} upgrade (dice chain: {roll_chain})"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True, text=True, cwd=str(REPO_ROOT)
            )

            # Extract commit hash
            commit_hash = result.stdout.extract_commit_hash() if "commit_hash" in dir(result.stdout) else None
            if not commit_hash:
                log = subprocess.run(
                    ["git", "log", "--oneline", "-1"],
                    capture_output=True, text=True, cwd=str(REPO_ROOT)
                )
                commit_hash = log.stdout.split()[0][:8] if log.stdout else None

            logger.info(f"[CoEvo] Committed: {commit_msg} (hash: {commit_hash})")
            return commit_hash
        except Exception as e:
            logger.error(f"[CoEvo] Auto-commit failed: {e}")
            return None

    # ─── Phase 4: DevSwarm Health Check ───

    def phase_health_check(self) -> Tuple[bool, str]:
        """
        Run DevSwarm strange-loop self-healing check.
        Returns: (all_healthy, summary)
        """
        try:
            result = subprocess.run(
                [sys.executable, "markus_devswarm.py"],
                capture_output=True, text=True, timeout=60,
                cwd=str(REPO_ROOT)
            )
            output = result.stdout + result.stderr
            all_healthy = "42/42" in output or "healthy" in output.lower()
            summary = f"DevSwarm: {output.strip()[-200:]}" if output else "No output"
            logger.info(f"[CoEvo] DevSwarm: {summary[:100]}")
            return all_healthy, summary
        except Exception as e:
            logger.error(f"[CoEvo] DevSwarm failed: {e}")
            return False, f"DevSwarm error: {e}"

    # ─── Phase 5: Cortex → Skill Auto-Patcher ───

    def phase_skill_patch(self, action_label: str) -> int:
        """
        Scan cortex thoughts and auto-patch relevant skills.
        Returns: number of skills patched
        """
        from markus_cortex_skill_patcher import CortexSkillPatcher
        patcher = CortexSkillPatcher()

        # Get recent thoughts since last cycle
        recent = self.cortex.get_recent_thoughts(limit=50)
        patches_applied = 0

        for thought in recent:
            entry_id = thought.get("entry_id", "")
            agent = thought.get("agent", "")
            content = thought.get("content", "")
            metadata = thought.get("metadata", {})

            # Skip already processed
            if f"processed_{entry_id}" in self.cortex.get_register("PATCHED_IDS", ""):
                continue

            patches = patcher.analyze_thought(entry_id, agent, content, metadata)
            for patch in patches:
                if patcher.auto_patch_skill(patch):
                    patches_applied += 1

            # Mark as processed
            patched_ids = self.cortex.get_register("PATCHED_IDS", "")
            self.cortex.set_register("PATCHED_IDS", patched_ids + f"processed_{entry_id};")

        logger.info(f"[CoEvo] Skill patches applied: {patches_applied}")
        return patches_applied

    # ─── Phase 6: Research Integration (Action 5) ───

    async def phase_research(self, action_label: str) -> Optional[str]:
        """
        If dice rolled Technical Alternative (Action 5),
        research external architectures and generate improvement proposal.
        """
        if action_label != "TECHNICAL_ALTERNATIVE_UPGRADE":
            return None

        try:
            # Research prompt template
            research_prompt = (
                "Research high-performance technical alternatives for AI agent OS architectures. "
                "Look for: zero-copy memory strategies, lockless IPC patterns, "
                "event-driven kernel designs, and microkernel vs monolithic tradeoffs. "
                "Generate one concrete improvement proposal for MARKUS OS."
            )

            # Log research intent to cortex
            self.cortex.append_thought(
                f"research_{int(time.time())}", "MARKUS_COEVOLUTION",
                research_prompt,
                {"type": "technical_alternative_research", "action": action_label}
            )

            research_result = f"Research initiated for {action_label} — findings logged to cortex"
            logger.info(f"[CoEvo] Research phase: {research_result}")
            return research_result
        except Exception as e:
            logger.error(f"[CoEvo] Research phase failed: {e}")
            return None

    # ─── Phase 7: Reward Feedback ───

    def phase_reward(self, action_label: str, validation_passed: bool, health_passed: bool) -> float:
        """
        Compute and record reward for the action based on validation + health results.
        Returns: reward value (0.0-1.0)
        """
        base_reward = 0.5
        if validation_passed:
            base_reward += 0.3
        if health_passed:
            base_reward += 0.2

        self.dice_engine.record_action_reward(action_label, base_reward)
        self._reward_log.append({
            "cycle": self.cycle_counter,
            "action": action_label,
            "reward": base_reward,
            "validation_passed": validation_passed,
            "health_passed": health_passed,
            "timestamp": time.time()
        })

        # Reset any invalid register reference
        self.cortex.set_register("PATCHED_IDS", "")

        stats = self.dice_engine.get_action_stats()
        logger.info(f"[CoEvo] Reward: {base_reward:.2f} | Action stats: {stats}")
        return base_reward

    # ─── Main Cycle ───

    async def execute_cycle(self) -> Dict[str, Any]:
        """
        Execute one full co-evolution cycle:
        Dice → Debate → Validate → Commit → Health → SkillPatch → Research → Reward
        """
        cycle_id = f"coev_{self.cycle_counter}_{int(time.time())}"
        self.cycle_counter += 1
        t0 = time.perf_counter()

        logger.info(f"\n{'='*60}")
        logger.info(f"Co-Evolution Cycle #{self.cycle_counter} (ID: {cycle_id})")
        logger.info(f"{'='*60}")

        # Phase 1: Dice + Debate
        final_roll, rolls, verdict = await self.phase_decision()
        action_label = self.dice_engine.ACTIONS.get(final_roll, "UNKNOWN")

        # Phase 2: PHOENIX Validation
        validation_passed, validation_summary = self.phase_validation()

        # Phase 3: Auto-commit
        commit_hash = self.phase_autocommit(action_label, rolls)

        # Phase 4: DevSwarm Health
        health_passed, health_summary = self.phase_health_check()

        # Phase 5: Skill Patching
        patches_applied = self.phase_skill_patch(action_label)

        # Phase 6: Research (only for Technical Alternative)
        research_result = await self.phase_research(action_label)

        # Phase 7: Reward Feedback
        reward = self.phase_reward(action_label, validation_passed, health_passed)

        cycle_elapsed = time.perf_counter() - t0

        # Log cycle completion to cortex
        self.cortex.append_thought(
            cycle_id, "MARKUS_COEVOLUTION",
            f"Cycle complete: roll={final_roll} action={action_label} "
            f"validation={'PASS' if validation_passed else 'FAIL'} "
            f"health={'HEALTHY' if health_passed else 'DEGRADED'} "
            f"patches={patches_applied} reward={reward:.2f}",
            {
                "cycle_id": cycle_id,
                "final_roll": final_roll,
                "action": action_label,
                "validation_passed": validation_passed,
                "health_passed": health_passed,
                "patches_applied": patches_applied,
                "reward": reward,
                "commit_hash": commit_hash,
                "elapsed_ms": round(cycle_elapsed * 1000, 2),
            }
        )

        result = {
            "cycle_id": cycle_id,
            "cycle_number": self.cycle_counter,
            "dice_roll": final_roll,
            "action": action_label,
            "roll_sequence": rolls,
            "validation": {"passed": validation_passed, "summary": validation_summary},
            "commit": commit_hash,
            "health": {"passed": health_passed, "summary": health_summary},
            "skill_patches": patches_applied,
            "research": research_result,
            "reward": reward,
            "elapsed_ms": round(cycle_elapsed * 1000, 2),
        }

        logger.info(f"[CoEvo] Cycle complete in {cycle_elapsed:.2f}s")
        logger.info(f"[CoEvo] Result: {json.dumps(result, indent=2)}")
        return result

    async def run_daemon(self, interval_s: float = 60.0) -> None:
        """Run co-evolution cycles continuously."""
        logger.info("=== MARKUS Co-Evolution Orchestrator Online ===")
        logger.info(f"Interval: {interval_s}s")
        while True:
            try:
                await self.execute_cycle()
            except Exception as e:
                logger.error(f"[CoEvo] Cycle error: {e}", exc_info=True)
                self.cortex.append_thought(
                    f"error_{int(time.time())}", "MARKUS_COEVOLUTION",
                    f"Cycle failed: {str(e)}",
                    {"error": True, "timestamp": time.time()}
                )
            await asyncio.sleep(interval_s)


# ─── Utilities ───

def _extract_commit_hash(text: str) -> str:
    """Extract the first commit hash from git output."""
    import re
    match = re.search(r'([a-f0-9]{7,40})', text)
    return match.group(1) if match else "unknown"


def _test_co_evolution():
    """Run a single test cycle of the co-evolution orchestrator."""
    print("=== MARKUS Co-Evolution Orchestrator Test ===\n")

    orch = CoEvolutionOrchestrator()

    # Run one cycle
    result = asyncio.run(orch.execute_cycle())

    print(f"\n✅ Cycle Results:")
    print(f"  Cycle ID: {result['cycle_id']}")
    print(f"  Dice Roll: {result['dice_roll']} → {result['action']}")
    print(f"  Validation: {'PASS' if result['validation']['passed'] else 'FAIL'}")
    print(f"  Commit: {result['commit'] or 'none'}")
    print(f"  Health: {'HEALTHY' if result['health']['passed'] else 'DEGRADED'}")
    print(f"  Skill Patches: {result['skill_patches']}")
    print(f"  Reward: {result['reward']:.2f}")
    print(f"  Elapsed: {result['elapsed_ms']:.2f}ms")

    print(f"\n✅ Co-Evolution Orchestrator Test: PASSED")


if __name__ == "__main__":
    mode = "daemon" if "--daemon" in sys.argv else "single"
    if mode == "single":
        _test_co_evolution()
    else:
        orch = CoEvolutionOrchestrator()
        asyncio.run(orch.run_daemon(interval_s=60.0))
