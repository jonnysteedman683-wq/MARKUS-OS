#!/usr/bin/env python3
"""
MARKUS OS Autonomous Upgrade Dice Engine (formerly RNG Pilot)
Continuously monitors system state and self-triggers development actions
based on a 6-sided cryptographic dice roll:
  1 = Upgrade UI
  2 = Upgrade Backend
  3 = Upgrade AI Agent
  4 = Find Something Missing
  5 = Technical Alternative Upgrade
  6 = Re-Roll
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from markus_db import PersistentCortexDB
from markus_debate_pipeline import MarkusDebatePipeline

logger = logging.getLogger("Markus.DiceEngine")

class MarkusDiceEngine:
    """
    Autonomous Dice-driven development engine.
    Triggers self-improvement cycles based on uniform 6-sided dice rolls:
      1 = Upgrade UI
      2 = Upgrade Backend
      3 = Upgrade AI Agent
      4 = Find Something Missing
      5 = Technical Alternative Upgrade
      6 = Re-Roll
    Each trigger is logged to the L3 cortex and stored for dispatch.
    """

    ACTIONS: Dict[int, str] = {
        1: "UPGRADE_UI",
        2: "UPGRADE_BACKEND",
        3: "UPGRADE_AI_AGENT",
        4: "FIND_SOMETHING_MISSING",
        5: "TECHNICAL_ALTERNATIVE_UPGRADE",
        6: "RE_ROLL"
    }

    def __init__(self, cortex: Optional[PersistentCortexDB] = None, tick_interval_s: float = 60.0) -> None:
        self.cortex = cortex or PersistentCortexDB()
        self.tick_interval = tick_interval_s
        self._running = False
        self.trigger_log: List[Dict[str, Any]] = []
        # Reward-weighted dice
        self._action_rewards: Dict[str, float] = {}
        self._action_counts: Dict[str, int] = {}
        self._cycle_latency: List[float] = []
        self._last_cycle_start: float = 0.0

    def roll_reward_weighted_dice(self) -> int:
        """Reward-weighted dice: biases toward historically successful actions."""
        import math
        base_probs = {i: 1/6 for i in range(1, 7)}
        epsilon = 0.3  # 30% exploration
        total_count = sum(self._action_counts.values())
        if total_count > 3:
            for action_int, label in self.ACTIONS.items():
                if label in self._action_rewards:
                    reward_avg = self._action_rewards[label] / max(self._action_counts[label], 1)
                    weight = epsilon + (1 - epsilon) * reward_avg
                    base_probs[action_int] = weight
        total = sum(base_probs.values())
        normalized = {k: v / total for k, v in base_probs.items()}
        rand = secrets.randbelow(1000000) / 1000000.0
        cumulative = 0.0
        for action_int in range(1, 7):
            cumulative += normalized[action_int]
            if rand <= cumulative:
                return action_int
        return 6

    def record_action_reward(self, action_label: str, reward: float) -> None:
        """Record a reward (0.0-1.0) for a completed action to update weighting."""
        if action_label not in self._action_rewards:
            self._action_rewards[action_label] = 0.0
            self._action_counts[action_label] = 0
        alpha = 0.2  # learning rate
        self._action_rewards[action_label] = (
            (1 - alpha) * self._action_rewards[action_label] + alpha * reward
        )
        self._action_counts[action_label] += 1
        self.cortex.append_thought(
            f"reward_{int(time.time())}", "MARKUS_DICE_ENGINE",
            f"Reward recorded: {action_label} = {reward:.3f}",
            {"action": action_label, "reward": reward}
        )

    def get_action_stats(self) -> Dict[str, Any]:
        """Return reward-weighted dice statistics."""
        return {
            "action_rewards": dict(self._action_rewards),
            "action_counts": dict(self._action_counts),
            "avg_cycle_latency_ms": round(sum(self._cycle_latency) / max(len(self._cycle_latency), 1), 2) if self._cycle_latency else 0.0,
        }

    @staticmethod
    def roll_dice() -> int:
        """Returns a cryptographically secure random integer in [1, 2, 3, 4, 5, 6]."""
        return secrets.choice([1, 2, 3, 4, 5, 6])

    def format_prompt(self, choice: int, roll_history: Optional[List[int]] = None) -> str:
        label = self.ACTIONS.get(choice, "UNKNOWN")
        history_note = f" (Roll chain: {roll_history})" if roll_history and len(roll_history) > 1 else ""
        prompts: Dict[int, str] = {
            1: (
                f"ACTION: UPGRADE_UI{history_note}\n\n"
                "You are MARKUS, an autonomous AI agent operating under the Dice Engine. "
                "Target the UI layer (markus_chat.html, markus-os.html) and upgrade it with a new feature, "
                "visual telemetry stream, or responsive interaction. "
                "Produce runnable code, run `python phoenix_cli.py batch .`, and log the result."
            ),
            2: (
                f"ACTION: UPGRADE_BACKEND{history_note}\n\n"
                "You are MARKUS, an autonomous AI agent operating under the Dice Engine. "
                "Target the backend layer (markus_server.py, markus_kernel.py, markus_router.py, "
                "markus_sandbox.py, markus_resilience.py, markus_mesh.py, markus_db.py, markus_task_dag.py) "
                "and implement the next high-leverage architectural upgrade. "
                "Produce verified Python code, run the PHOENIX AST scanner, and log the result."
            ),
            3: (
                f"ACTION: UPGRADE_AI_AGENT{history_note}\n\n"
                "You are MARKUS, an autonomous AI agent operating under the Dice Engine. "
                "Review agent capabilities, skill registry, routing thresholds, or kanban worker logic "
                "(e.g., markus_router.py, markus_kanban_worker.py) and perform an enhancement or optimization. "
                "Keep explanations minimal."
            ),
            4: (
                f"ACTION: FIND_SOMETHING_MISSING{history_note}\n\n"
                "You are MARKUS, an autonomous AI agent operating under the Dice Engine. "
                "Audit the entire MARKUS OS codebase for a missing capability, unhandled edge case, "
                "security boundary, or untested workflow. "
                "Implement the missing component and log the verification proof to the L3 cortex."
            ),
            5: (
                f"ACTION: TECHNICAL_ALTERNATIVE_UPGRADE{history_note}\n\n"
                "You are MARKUS, an autonomous AI agent operating under the Dice Engine. "
                "Identify an existing component, research a high-performance technical alternative "
                "(e.g., async pipeline vs thread pool, WebSocket vs SSE, zero-copy memory vs serialization), "
                "implement the alternative upgrade path with verified benchmarks, and document the trade-offs."
            ),
            6: (
                f"ACTION: RE_ROLL{history_note}\n\n"
                "You are MARKUS, an autonomous AI agent operating under the Dice Engine. "
                "The dice landed on 6 (Re-Roll). Immediately roll the dice again, log the re-roll sequence, "
                "and execute the resulting target action."
            )
        }
        return prompts.get(choice, f"Unknown action: {choice}")

    async def execute_dice_cycle(self, max_rerolls: int = 5) -> Tuple[int, List[int]]:
        cycle_start = time.perf_counter()
        self._last_cycle_start = time.time()
        rolls: List[int] = []
        current_roll = self.roll_reward_weighted_dice()
        rolls.append(current_roll)

        reroll_count = 0
        while current_roll == 6 and reroll_count < max_rerolls:
            reroll_count += 1
            print(f"[DICE] Rolled 6 (RE_ROLL)! Re-rolling (attempt {reroll_count})...")
            current_roll = self.roll_dice()
            rolls.append(current_roll)

        action_label = self.ACTIONS.get(current_roll, "UNKNOWN")
        cycle_id = f"dice_{int(time.time())}"
        prompt = self.format_prompt(current_roll, roll_history=rolls)

        # Log the trigger event to L3 cortex
        self.cortex.append_thought(
            cycle_id, "MARKUS_DICE_ENGINE",
            f"Triggered dice cycle: {action_label} (final_roll={current_roll}, sequence={rolls})",
            {"action": action_label, "final_roll": current_roll, "rolls": rolls, "cycle_id": cycle_id}
        )

        print(f"\n[DICE] Cycle {cycle_id}: Roll Sequence = {rolls} -> Final Action = {action_label}")
        print(f"[DICE] Dispatch Prompt:\n{prompt[:250]}...\n")

        # Store dispatch payload for pickup
        dispatch_path = Path(__file__).resolve().parent / "markus_private" / "ipc" / f"dispatch_{cycle_id}.json"
        dispatch_path.parent.mkdir(parents=True, exist_ok=True)
        dispatch_payload = {
            "cycle_id": cycle_id,
            "final_roll": current_roll,
            "roll_sequence": rolls,
            "action": action_label,
            "prompt": prompt,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        dispatch_path.write_text(json.dumps(dispatch_payload, indent=2), encoding="utf-8")

        self.trigger_log.append({
            "cycle_id": cycle_id,
            "timestamp": time.time(),
            "final_roll": current_roll,
            "rolls": rolls,
            "action": action_label
        })

        self.cortex.set_register("LAST_DICE_ACTION", action_label)
        self.cortex.set_register("LAST_DICE_ROLL", current_roll)
        self.cortex.set_register("LAST_DICE_SEQUENCE", json.dumps(rolls))

        # Phase 1: Run multi-agent debate before executing any upgrade
        debate = MarkusDebatePipeline()
        verdict = await debate.conduct_debate(
            action_label=action_label,
            upgrade_prompt=prompt,
            proposed_changes=[
                f"Execute {action_label} upgrade cycle",
                f"Roll sequence: {rolls}",
                f"Dispatch prompt generated for autonomous execution"
            ],
            risk_level="MEDIUM" if current_roll in (2, 5) else "LOW"
        )

        # Log debate verdict to cortex
        self.cortex.append_thought(
            cycle_id, "MARKUS_DICE_ENGINE_DEBATE",
            f"Debate verdict: {verdict.winning_candidate} (confidence={verdict.confidence:.1%}, "
            f"consensus={'REACH' if verdict.consensus_reached else 'BLOCKED'})",
            {"cycle_id": cycle_id, "confident_proceed": verdict.consensus_reached}
        )

        print(f"[DICE] Debate verdict: {verdict.winning_candidate} | "
              f"Confidence: {verdict.confidence:.1%} | "
              f"Consensus: {'REACH' if verdict.consensus_reached else 'BLOCKED'}")

        # Track cycle latency
        cycle_elapsed = time.perf_counter() - cycle_start
        self._cycle_latency.append(cycle_elapsed)
        if len(self._cycle_latency) > 100:
            self._cycle_latency.pop(0)

        return current_roll, rolls

    async def run_daemon(self) -> None:
        self._running = True
        print("=== MARKUS Dice Engine Daemon Online ===")
        print(f"Tick Interval: {self.tick_interval}s | 6-Sided Actions: {self.ACTIONS}")
        while self._running:
            await self.execute_dice_cycle()
            print(f"[DICE] Sleeping {self.tick_interval}s until next roll...\n")
            await asyncio.sleep(self.tick_interval)

    def run_single(self) -> Tuple[int, List[int]]:
        """Run a single cycle synchronously for testing."""
        return asyncio.run(self.execute_dice_cycle())

if __name__ == "__main__":
    mode = "daemon" if "--daemon" in sys.argv else "single"
    engine = MarkusDiceEngine(tick_interval_s=60.0)
    if mode == "single":
        print("=== MARKUS Dice Engine — Single Roll Test ===")
        final, seq = engine.run_single()
        print(f"[RESULT] Final Dice Roll: {final} (Chain: {seq}) -> Action: {engine.ACTIONS[final]}")
    else:
        asyncio.run(engine.run_daemon())
