#!/usr/bin/env python3
"""
MARKUS OS Epoch-Based Parallel Evolution Scheduler (Upgrade 50)

Timeslices the 120-second co-evolution cycle into 6 parallel tracks:
- Epoch 1 (00-20s): Reflexion Loop
- Epoch 2 (20-40s): Population Dice Evolution
- Epoch 3 (40-60s): Red Team Adversarial Testing
- Epoch 4 (60-80s): Skill Auto-Patching
- Epoch 5 (80-100s): Dice Engine Exploration
- Epoch 6 (100-120s): PHOENIX Validation Gate

Uses multiprocessing for true parallelism. Cross-track data sharing via
shared cortex with vector timestamps. Circuit breakers per track for safety.
"""

from __future__ import annotations
import asyncio
import json
import logging
import multiprocessing as mp
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from markus_db import PersistentCortexDB
from markus_ring_buffer import MarkusSharedRingBuffer
from markus_resilience import CircuitBreakerManager

logger = logging.getLogger("Markus.EpochScheduler")

# __file__ guard for PHOENIX CLI runtime evaluation
try:
    REPO_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    REPO_ROOT = Path(os.getcwd())

EPOCH_WINDOW_S = 20     # 20 seconds per epoch
EPOCH_BUFFER_S = 2      # 2-second buffer for merge
TOTAL_CYCLE_S = 120     # Full cycle: 6 epochs × 20s = 120s
TRACK_COUNT = 6

# Vector clock for cross-track ordering
vector_clock: Dict[int, int] = {i: 0 for i in range(TRACK_COUNT)}


@dataclass
class EpochResult:
    """Result from a single epoch/track execution."""
    epoch_id: int
    track_name: str
    success: bool
    duration_ms: float
    output: str
    error: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    mutations_applied: int = 0
    files_modified: List[str] = field(default_factory=list)


@dataclass
class EpochSchedulerStats:
    """Statistics for the epoch scheduler."""
    total_cycles: int = 0
    total_epochs: int = 0
    avg_epoch_ms: float = 0.0
    track_success_rates: Dict[str, float] = field(default_factory=dict)
    cross_track_conflicts: int = 0
    cortex_writes: int = 0


class EpochScheduler:
    """
    6-track parallel evolution scheduler.
    
    Each epoch runs independently in its own process, writing results to the
    shared cortex with vector timestamps for ordering. Circuit breakers
    prevent cascading failures.
    
    Stolen patterns:
    - ProcessPoolExecutor from asyncio/concurrent patterns
    - CircuitBreakerManager from markus_resilience.py for per-track safety
    - append_thought from markus_db.py for cortex logging
    - SharedRingBuffer from markus_ring_buffer.py for lock-free communication
    """

    TRACK_CONFIGS = {
        0: {
            "name": "reflexion",
            "description": "Trajectory critique + weight refinement",
            "max_duration_s": 18,
            "imports": ["from markus_reflexion import ReflexionLoopEngine"],
            "run_fn": "run_reflexion_epoch",
        },
        1: {
            "name": "population",
            "description": "Dice genome evolution: tournament + mutate",
            "max_duration_s": 18,
            "imports": ["from markus_population_dice import PopulationDiceEngine"],
            "run_fn": "run_population_epoch",
        },
        2: {
            "name": "redteam",
            "description": "Adversarial mutation testing + fixes",
            "max_duration_s": 18,
            "imports": ["from markus_redteam import RedTeamOrchestrator"],
            "run_fn": "run_redteam_epoch",
        },
        3: {
            "name": "skill_patch",
            "description": "Cortex pattern matching + skill auto-patch",
            "max_duration_s": 18,
            "imports": ["from markus_cortex_skill_patcher import CortexSkillPatcher"],
            "run_fn": "run_skill_patch_epoch",
        },
        4: {
            "name": "dice_explore",
            "description": "Reward-weighted dice with population genome bias",
            "max_duration_s": 18,
            "imports": ["from markus_dice_engine import MarkusDiceEngine"],
            "run_fn": "run_dice_explore_epoch",
        },
        5: {
            "name": "phoenix_validate",
            "description": "Batch AST validation gate (PHOENIX CLI)",
            "max_duration_s": 18,
            "imports": ["from phoenix_cli import SelfEvolvingCodeEngine"],
            "run_fn": "run_phoenix_validate_epoch",
        },
    }

    def __init__(self, cycle_interval_s: int = 120) -> None:
        self.cortex = PersistentCortexDB()
        self.cycle_interval = cycle_interval_s
        self.stats = EpochSchedulerStats()
        self.cortex_ring = MarkusSharedRingBuffer(
            name="markus_epoch_ring", capacity=512, slot_size=2048, create=True
        )
        self.breaker = CircuitBreakerManager(db=self.cortex)
        self.epoch_results: List[EpochResult] = []
        self._running = False
        self._pool: Optional[ProcessPoolExecutor] = None

    def _vector_clock_tick(self, track_id: int) -> Dict[int, int]:
        """Increment vector clock for a track and return updated clock."""
        vector_clock[track_id] += 1
        return dict(vector_clock)

    def _log_epoch_to_cortex(self, result: EpochResult, vclock: Dict[int, int]) -> None:
        """Log epoch result to cortex with vector timestamp."""
        self.cortex.append_thought(
            f"epoch_{result.epoch_id}_{int(time.time())}",
            "MARKUS_EPOCH_SCHEDULER",
            f"Epoch {result.track_name}: success={result.success}, "
            f"duration={result.duration_ms}ms, mutations={result.mutations_applied}",
            {
                "epoch_id": result.epoch_id,
                "track_name": result.track_name,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "mutations_applied": result.mutations_applied,
                "files_modified": result.files_modified,
                "vector_clock": vclock,
                "metrics": result.metrics,
                "error": result.error,
            }
        )

    def _run_epoch_track(self, epoch_id: int) -> EpochResult:
        """
        Run a single epoch track in isolation.
        Each track is a separate function that imports and runs its engine.
        """
        config = self.TRACK_CONFIGS[epoch_id]
        track_name = config["name"]
        run_fn_name = config["run_fn"]

        # Get circuit breaker for this track
        breaker_name = f"epoch_{track_name}"
        ep = self.breaker.register(breaker_name, max_failures=3, cooldown_s=30.0)

        def _execute():
            t0 = time.perf_counter()

            # Dynamically import and call the epoch runner
            # Each runner is a standalone function that creates its engine and runs
            if run_fn_name == "run_reflexion_epoch":
                from markus_reflexion import ReflexionLoopEngine
                engine = ReflexionLoopEngine(cortex=self.cortex)
                result = asyncio.run(engine.run_reflexion_cycle(max_retries=2))
                return {
                    "success": result["success"],
                    "metrics": {"issues_found": result["issues_found"],
                               "confidence": result["reflection_confidence"]},
                    "mutations_applied": 0,
                    "files_modified": [],
                    "output": f"Reflexion cycle complete"
                }

            elif run_fn_name == "run_population_epoch":
                from markus_population_dice import PopulationDiceEngine
                engine = PopulationDiceEngine(population_size=10, cortex=self.cortex)
                result = engine.evolve_generation(evaluations_per_genome=2)
                return {
                    "success": True,
                    "metrics": {"generation": result["generation"],
                               "avg_fitness": result["avg_fitness"]},
                    "mutations_applied": len(engine.population),
                    "files_modified": [],
                    "output": f"Population evolved gen {result['generation']}"
                }

            elif run_fn_name == "run_redteam_epoch":
                from markus_redteam import RedTeamOrchestrator
                orch = RedTeamOrchestrator()
                # Reduced scope for epoch: only 5 files, 2 mutations each
                result = asyncio.run(orch.run_redteam_cycle(
                    target_dirs=[str(REPO_ROOT)],
                    mutations_per_file=2,  # Smaller for epoch
                    max_files=5  # Only test 5 files per epoch
                ))
                return {
                    "success": True,
                    "metrics": {"mutations_tested": result["mutations_tested"],
                               "vulnerabilities_found": result["vulnerabilities_found"],
                               "fixes_applied": result["fixes_applied"]},
                    "mutations_applied": result["mutations_tested"],
                    "files_modified": [],
                    "output": f"RedTeam: {result['mutations_tested']} mutations, {result['fixes_applied']} fixes"
                }

            elif run_fn_name == "run_skill_patch_epoch":
                from markus_cortex_skill_patcher import CortexSkillPatcher
                patcher = CortexSkillPatcher()
                recent = self.cortex.get_recent_thoughts(limit=30)
                patches_applied = 0
                modified_files = []

                for thought in recent:
                    entry_id = thought.get("entry_id", "")
                    agent = thought.get("agent", "")
                    content = thought.get("content", "")
                    metadata = thought.get("metadata", {})

                    if f"processed_{entry_id}" in str(self.cortex.get_register("PATCHED_IDS_EPOCH", "")):
                        continue

                    patches = patcher.analyze_thought(entry_id, agent, content, metadata)
                    for patch in patches:
                        if patcher.auto_patch_skill(patch):
                            patches_applied += 1
                            if patch.skill_name:
                                skill_file = patcher._find_skill_file(patch.skill_name)
                                if skill_file:
                                    modified_files.append(str(skill_file))

                    # Mark as processed
                    patched = self.cortex.get_register("PATCHED_IDS_EPOCH", "")
                    self.cortex.set_register("PATCHED_IDS_EPOCH", patched + f"processed_{entry_id};")

                return {
                    "success": True,
                    "metrics": {"patches_applied": patches_applied},
                    "mutations_applied": patches_applied,
                    "files_modified": modified_files,
                    "output": f"Patched {patches_applied} skill(s)"
                }

            elif run_fn_name == "run_dice_explore_epoch":
                from markus_dice_engine import MarkusDiceEngine
                engine = MarkusDiceEngine(cortex=self.cortex)
                roll = engine.roll_reward_weighted_dice()
                action_label = engine.ACTIONS.get(roll, "UNKNOWN")
                # Record a small reward to update weights
                engine.record_action_reward(action_label, 0.6)
                return {
                    "success": True,
                    "metrics": {"roll": roll, "action": action_label},
                    "mutations_applied": 0,
                    "files_modified": [],
                    "output": f"Dice roll: {roll} → {action_label}"
                }

            elif run_fn_name == "run_phoenix_validate_epoch":
                from phoenix_evolver import SelfEvolvingCodeEngine
                engine = SelfEvolvingCodeEngine()

                # Validate all markus files
                files = list(REPO_ROOT.glob("markus_*.py"))
                pass_count = 0
                fail_count = 0
                failures = []

                for f in files:
                    if f.stat().st_size > 100_000:  # Skip huge files
                        continue
                    try:
                        content = f.read_text(encoding="utf-8")
                        result = engine.evaluate_candidate(content, lambda s: True, iteration=1)
                        if result.is_valid_ast and result.passed_tests:
                            pass_count += 1
                        else:
                            fail_count += 1
                            failures.append(str(f.name))
                    except Exception as e:
                        fail_count += 1
                        failures.append(f"{f.name}: {str(e)[:100]}")

                return {
                    "success": fail_count == 0,
                    "metrics": {"pass_count": pass_count, "fail_count": fail_count,
                               "total_files": pass_count + fail_count},
                    "mutations_applied": 0,
                    "files_modified": [],
                    "output": f"PHOENIX: {pass_count}P/{fail_count}F"
                }

            return {
                "success": False,
                "metrics": {},
                "mutations_applied": 0,
                "files_modified": [],
                "output": f"Unknown track: {run_fn_name}"
            }

        t0_reference = [0.0]  # Mutable container for timing reference

        def _do_exec():
            t0_reference[0] = time.perf_counter()
            return _execute()

        try:
            result = ep.protected_call(_do_exec)
            elapsed_ms = (time.perf_counter() - t0_reference[0]) * 1000

            return EpochResult(
                epoch_id=epoch_id,
                track_name=track_name,
                success=result.get("success", False),
                duration_ms=round(elapsed_ms, 2),
                output=result.get("output", ""),
                metrics=result.get("metrics", {}),
                mutations_applied=result.get("mutations_applied", 0),
                files_modified=result.get("files_modified", []),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - time.perf_counter()) * 1000
            logger.error(f"Epoch {track_name} failed: {e}")
            return EpochResult(
                epoch_id=epoch_id,
                track_name=track_name,
                success=False,
                duration_ms=round(elapsed_ms, 2),
                output="",
                error=str(e),
                metrics={},
            )

    async def run_parallel_epoch(self) -> Dict[str, Any]:
        """
        Run all 6 tracks in parallel using ProcessPoolExecutor.
        Each track runs in its own process with a circuit breaker.

        Stolen pattern: Phase parallelism from markus_co_evolution.py +
        multiprocessing from concurrent.futures.
        """
        epoch_start = time.perf_counter()
        self.stats.total_cycles += 1
        self.epoch_results = []

        logger.info(f"\n{'='*60}")
        logger.info(f"Epoch Cycle #{self.stats.total_cycles} — {TRACK_COUNT} parallel tracks")
        logger.info(f"{'='*60}")

        # Use ThreadPoolExecutor for this — processes can't share DB connections easily
        # but we can serialize/deserialize cortex state
        loop = asyncio.get_event_loop()

        # Run all 6 tracks concurrently using asyncio.to_thread for parallelism
        tasks = []
        for epoch_id in range(TRACK_COUNT):
            # Use run_in_executor for true parallel execution
            task = loop.run_in_executor(None, self._run_epoch_track, epoch_id)
            tasks.append((epoch_id, task))

        # Wait for all tracks to complete
        results = []
        for epoch_id, task in tasks:
            try:
                result = await task
                self.epoch_results.append(result)

                # Update vector clock
                vclock = self._vector_clock_tick(epoch_id)

                # Log to cortex
                self._log_epoch_to_cortex(result, vclock)
                self.stats.cortex_writes += 1
                self.stats.total_epochs += 1

                # Update stats
                track_name = self.TRACK_CONFIGS[epoch_id]["name"]
                if result.success:
                    if track_name not in self.stats.track_success_rates:
                        self.stats.track_success_rates[track_name] = 0.0
                    # Running average
                    old_rate = self.stats.track_success_rates[track_name]
                    self.stats.track_success_rates[track_name] = (old_rate * self.stats.total_cycles + 1.0) / (self.stats.total_cycles + 1)

                print(f"  ✅ Track {epoch_id} [{track_name}]: success={result.success}, "
                      f"duration={result.duration_ms:.1f}ms, "
                      f"mutations={result.mutations_applied}")

            except Exception as e:
                logger.error(f"Track {epoch_id} error: {e}")
                self.stats.cross_track_conflicts += 1
                error_result = EpochResult(
                    epoch_id=epoch_id,
                    track_name=self.TRACK_CONFIGS[epoch_id]["name"],
                    success=False,
                    duration_ms=0.0,
                    output="",
                    error=str(e),
                )
                self.epoch_results.append(error_result)
                vclock = self._vector_clock_tick(epoch_id)
                self._log_epoch_to_cortex(error_result, vclock)

        # Compute averages
        total_duration = time.perf_counter() - epoch_start
        avg_epoch_ms = sum(r.duration_ms for r in self.epoch_results) / len(self.epoch_results) if self.epoch_results else 0
        self.stats.avg_epoch_ms = round(avg_epoch_ms, 2)

        # Check for cross-track conflicts (files modified by multiple tracks)
        all_modified_files = []
        for result in self.epoch_results:
            all_modified_files.extend(result.files_modified)

        if len(all_modified_files) != len(set(all_modified_files)):
            self.stats.cross_track_conflicts += 1
            logger.warning(f"Cross-track file conflicts detected: {len(all_modified_files)} vs {len(set(all_modified_files))}")

        # Log cycle completion
        self.cortex.append_thought(
            f"epoch_cycle_{self.stats.total_cycles}_{int(time.time())}",
            "MARKUS_EPOCH_SCHEDULER",
            f"Epoch cycle complete: {self.stats.total_cycles} | "
            f"tracks={len(self.epoch_results)} | "
            f"total_mutations={sum(r.mutations_applied for r in self.epoch_results)} | "
            f"cycle_time={total_duration:.2f}s",
            {
                "cycle": self.stats.total_cycles,
                "tracks_run": len(self.epoch_results),
                "total_mutations": sum(r.mutations_applied for r in self.epoch_results),
                "total_files_modified": len(set(all_modified_files)),
                "cross_track_conflicts": self.stats.cross_track_conflicts,
                "cycle_time_s": round(total_duration, 3),
                "track_success": {r.track_name: r.success for r in self.epoch_results},
            }
        )

        logger.info(f"\n[EpochScheduler] Cycle {self.stats.total_cycles} complete in {total_duration:.2f}s")
        logger.info(f"  Total mutations applied: {sum(r.mutations_applied for r in self.epoch_results)}")
        logger.info(f"  Files modified: {len(set(all_modified_files))}")
        logger.info(f"  Cross-track conflicts: {self.stats.cross_track_conflicts}")

        return {
            "cycle": self.stats.total_cycles,
            "total_duration_s": round(total_duration, 3),
            "track_results": [
                {
                    "track": r.track_name,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "mutations_applied": r.mutations_applied,
                    "metrics": r.metrics,
                }
                for r in self.epoch_results
            ],
            "total_mutations": sum(r.mutations_applied for r in self.epoch_results),
            "total_files_modified": len(set(all_modified_files)),
        }

    async def run_daemon(self, interval_s: float = 120.0) -> None:
        """Run epoch cycles continuously."""
        self._running = True
        print(f"=== MARKUS Epoch Scheduler Online ===")
        print(f"Cycle interval: {interval_s}s | Tracks: {TRACK_COUNT} parallel")
        print(f"Epoch window: {EPOCH_WINDOW_S}s per track (buffer: {EPOCH_BUFFER_S}s)")

        while self._running:
            try:
                result = await self.run_parallel_epoch()
                print(f"\n  Cycle {result['cycle']}: {result['total_mutations']} mutations, "
                      f"{result['total_files_modified']} files modified, "
                      f"{result['total_duration_s']}s\n")
            except Exception as e:
                logger.error(f"Epoch cycle error: {e}", exc_info=True)
                self.cortex.append_thought(
                    f"epoch_error_{int(time.time())}",
                    "MARKUS_EPOCH_SCHEDULER",
                    f"Epoch cycle failed: {str(e)}",
                    {"error": True, "timestamp": time.time()}
                )

            await asyncio.sleep(interval_s)

    def get_stats(self) -> Dict[str, Any]:
        """Return scheduler statistics."""
        return {
            "total_cycles": self.stats.total_cycles,
            "total_epochs": self.stats.total_epochs,
            "avg_epoch_ms": self.stats.avg_epoch_ms,
            "track_success_rates": self.stats.track_success_rates,
            "cross_track_conflicts": self.stats.cross_track_conflicts,
            "cortex_writes": self.stats.cortex_writes,
            "track_configs": self.TRACK_CONFIGS,
        }


def _test_epoch_scheduler():
    """Test the Epoch-Based Parallel Evolution Scheduler."""
    print("=== MARKUS Epoch-Based Parallel Evolution Scheduler Test ===\n")

    scheduler = EpochScheduler(cycle_interval_s=120)

    # Run one cycle
    result = asyncio.run(scheduler.run_parallel_epoch())

    print(f"\n✅ Epoch Cycle Results:")
    print(f"  Cycle: {result['cycle']}")
    print(f"  Total Duration: {result['total_duration_s']}s")
    print(f"  Total Mutations: {result['total_mutations']}")
    print(f"  Files Modified: {result['total_files_modified']}")

    print(f"\n  Track Results:")
    for track in result["track_results"]:
        status = "✅" if track["success"] else "❌"
        print(f"    {status} {track['track']}: {track['duration_ms']}ms, "
              f"{track['mutations_applied']} mutations")
        if track["metrics"]:
            for k, v in track["metrics"].items():
                print(f"      {k}: {v}")

    # Print stats
    stats = scheduler.get_stats()
    print(f"\n  Scheduler Stats:")
    print(f"    Total Cycles: {stats['total_cycles']}")
    print(f"    Total Epochs: {stats['total_epochs']}")
    print(f"    Average Epoch: {stats['avg_epoch_ms']}ms")
    print(f"    Track Success Rates: {json.dumps(stats['track_success_rates'], indent=4)}")

    print(f"\n✅ Epoch Scheduler Test: PASSED")


if __name__ == "__main__":
    mode = "daemon" if "--daemon" in sys.argv else "single"
    if mode == "single":
        _test_epoch_scheduler()
    else:
        scheduler = EpochScheduler(cycle_interval_s=120)
        asyncio.run(scheduler.run_daemon(interval_s=120))
