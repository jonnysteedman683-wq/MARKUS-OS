#!/usr/bin/env python3
"""hermes_verify_evolution_loops.py — Evolutionary Loops Verification Harness (2026-08-27).

Verifies the contract integrity and self-tests of all three MARKUS OS evolutionary loops:
  G1  py_compile AST gate on markus_reflexion.py, markus_population_dice.py, markus_redteam.py
  G2  ReflexionLoopEngine self-test execution (_test_reflexion)
  G3  ReflexionLoopEngine contract: collect_trajectory steps carry success+latency_ms,
      generate_self_reflection returns a SelfReflection, refine_and_retry returns (bool, str),
      get_reflection_stats returns the declared schema
  G4  PopulationDiceEngine self-test execution (_test_population_dice)
  G5  PopulationDiceEngine contract: tournament selection returns a DiceGenome winner, genome
      weights mutate deterministically (100% mutation rate), evolve_generation advances a generation
  G6  RedTeamOrchestrator self-test execution (_test_redteam)
  G7  RedTeamOrchestrator contract: a RED-phase vulnerability record round-trips to cortex AND a
      BLUE-phase patch is generated AND applied to a real file
  G8  Shared reward mechanism (MarkusDiceEngine.record_action_reward) mutates action weights —
      the contract the population loop's fitness scoring and co-evolution Phase 7 reward both rely on

Stdlib-only, network-free, fail closed (non-zero exit + clear FAIL line on ANY failure).
Exit 0 = all gates pass.
"""
from __future__ import annotations

import importlib.util
import os
import py_compile
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
results: List[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}".rstrip())


def load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    reflexion_path = ROOT / "markus_reflexion.py"
    pop_path = ROOT / "markus_population_dice.py"
    redteam_path = ROOT / "markus_redteam.py"
    dice_path = ROOT / "markus_dice_engine.py"

    # G1: py_compile AST Gate
    try:
        py_compile.compile(str(reflexion_path), doraise=True)
        py_compile.compile(str(pop_path), doraise=True)
        py_compile.compile(str(redteam_path), doraise=True)
        check("G1 py_compile AST gate on all 3 evolution loop modules", True)
    except Exception as exc:
        check("G1 py_compile AST gate on all 3 evolution loop modules", False, str(exc))
        return _finish()

    # Load modules
    try:
        mod_reflexion = load("reflexion_mod", reflexion_path)
        mod_pop = load("pop_mod", pop_path)
        mod_redteam = load("redteam_mod", redteam_path)
    except Exception as exc:
        check("Module load execution", False, str(exc))
        return _finish()

    # G2: Reflexion self-test execution
    try:
        mod_reflexion._test_reflexion()
        check("G2 Reflexion self-test (_test_reflexion)", True)
    except Exception as exc:
        check("G2 Reflexion self-test (_test_reflexion)", False, str(exc))

    # G3: Reflexion contract verification
    try:
        ref_engine = mod_reflexion.ReflexionLoopEngine()
        traj = ref_engine.collect_trajectory(last_n=5)
        assert isinstance(traj, list), "collect_trajectory must return list"
        for step in traj:
            assert hasattr(step, "success"), "trajectory step missing success field"
            assert hasattr(step, "latency_ms"), "trajectory step missing latency_ms field"

        # Deterministic contract proof independent of DB contents: the dataclass itself
        # must carry success (bool) + latency_ms (float) on every step.
        step = mod_reflexion.TrajectoryStep(
            step_id="g3_contract", action="TEST", prompt="p", output="o",
            success=True, latency_ms=12.5, timestamp=0.0,
        )
        assert step.success is True, "TrajectoryStep.success must be a bool"
        assert isinstance(step.latency_ms, float), "TrajectoryStep.latency_ms must be a float"

        reflection = ref_engine.generate_self_reflection(traj)
        assert isinstance(reflection, mod_reflexion.SelfReflection), "generate_self_reflection invalid type"
        assert isinstance(reflection.issues_found, list), "reflection.issues_found must be a list"
        assert isinstance(reflection.suggested_improvements, list), "reflection.suggested_improvements must be a list"
        assert 0.0 <= reflection.confidence <= 1.0, "reflection.confidence must be in [0.0, 1.0]"
        assert isinstance(reflection.weight_adjustments, dict), "reflection.weight_adjustments must be a dict"

        success, msg = ref_engine.refine_and_retry(reflection, max_retries=1)
        assert isinstance(success, bool), "refine_and_retry invalid return type"
        assert isinstance(msg, str), "refine_and_retry message must be a str"

        stats = ref_engine.get_reflection_stats()
        assert isinstance(stats, dict), "get_reflection_stats must return a dict"
        assert "total_reflections" in stats, "get_reflection_stats missing total_reflections"
        assert "total_refinements" in stats, "get_reflection_stats missing total_refinements"
        check("G3 ReflexionLoopEngine contract verification", True)
    except Exception as exc:
        check("G3 ReflexionLoopEngine contract verification", False, str(exc))

    # G4: Population Dice self-test execution
    try:
        mod_pop._test_population_dice()
        check("G4 Population Dice self-test (_test_population_dice)", True)
    except Exception as exc:
        check("G4 Population Dice self-test (_test_population_dice)", False, str(exc))

    # G5: Population Dice contract verification
    try:
        pop_engine = mod_pop.PopulationDiceEngine(population_size=4)
        winner = pop_engine.tournament_selection(tournament_size=2)
        assert isinstance(winner, mod_pop.DiceGenome), "tournament selection invalid winner type"

        # Force 100% mutation rate so weight mutation is deterministic (no probabilistic flake).
        pop_engine.mutation_rate = 1.0
        child = pop_engine.mutate_genome(winner)
        assert isinstance(child, mod_pop.DiceGenome), "mutate_genome invalid return type"
        assert child.genome_id != winner.genome_id, "mutated genome must have distinct genome_id"
        assert child.action_weights != winner.action_weights, "mutate_genome did not mutate weights"

        # Evolve one generation: proves the loop runs end-to-end and advances generation.
        gen_before = pop_engine.generation
        res = pop_engine.evolve_generation(evaluations_per_genome=1)
        assert res["generation"] == gen_before + 1, "evolve_generation did not advance generation"
        assert res["population_size"] == 4, "evolve_generation changed population size"
        assert res["avg_fitness"] >= 0.0, "evolve_generation returned negative fitness"
        check("G5 PopulationDiceEngine contract verification", True)
    except Exception as exc:
        check("G5 PopulationDiceEngine contract verification", False, str(exc))

    # G6: RedTeam self-test execution
    try:
        mod_redteam._test_redteam()
        check("G6 RedTeam self-test (_test_redteam)", True)
    except Exception as exc:
        check("G6 RedTeam self-test (_test_redteam)", False, str(exc))

    # G7: RedTeam contract verification — RED round-trip to cortex + BLUE patch applied
    temp_path = ""
    try:
        rt_orch = mod_redteam.RedTeamOrchestrator()
        vuln = mod_redteam.Vulnerability(
            vuln_id="vuln_g7_roundtrip",
            category="correctness",
            severity="HIGH",
            file_path="markus_sandbox.py",
            line_number=42,
            description="Simulated vulnerability check",
            failing_code="eval(user_input)",
            fix_pattern="import_missing",
            confidence=0.95,
        )

        # RED phase: vulnerability record written to cortex
        rt_orch.cortex.append_thought(
            f"vuln_{vuln.vuln_id}", "MARKUS_REDTEAM",
            f"Vulnerability logged: {vuln.description} in {vuln.file_path}:{vuln.line_number}",
            {"vuln_id": vuln.vuln_id, "severity": vuln.severity},
        )

        # ROUND-TRIP: read it back from the cortex
        thoughts = rt_orch.cortex.get_recent_thoughts(limit=20)
        roundtripped = any(
            vuln.vuln_id in (str(t.get("entry_id", "")) + str(t.get("content", "")))
            for t in thoughts
        )
        assert roundtripped, "RED-phase vuln record did not round-trip to cortex"

        # BLUE phase: a patch is synthesized for the vuln
        fix_code = rt_orch.blue_agent.generate_fix(vuln)
        assert isinstance(fix_code, str) and fix_code.strip(), "generate_fix returned empty patch"

        # BLUE phase: patch actually applies to a real file (generic_fix appends a guard)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write("x = 1\n")
            temp_path = tf.name
        patch_vuln = mod_redteam.Vulnerability(
            vuln_id="vuln_g7_apply", category="correctness", severity="MEDIUM",
            file_path=temp_path, line_number=1, description="",
            failing_code="", fix_pattern="generic_fix", confidence=0.5,
        )
        patch_code = rt_orch.blue_agent.generate_fix(patch_vuln)
        applied = rt_orch.blue_agent.apply_fix(patch_vuln, patch_code)
        assert applied, "BLUE-phase patch failed to apply"
        content_after = Path(temp_path).read_text(encoding="utf-8")
        assert "# Auto-fix" in content_after, "applied patch missing from file"
        check("G7 RedTeamOrchestrator contract verification", True)
    except Exception as exc:
        check("G7 RedTeamOrchestrator contract verification", False, str(exc))
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    # G8: Shared reward mechanism — record_action_reward mutates action weights.
    # The population loop's fitness scoring is built on this (stolen from dice_engine),
    # and co-evolution Phase 7 uses it for reward feedback. The population engine itself
    # has no such method, so the contract is asserted on the shared engine it borrows from.
    try:
        dice_mod = load("dice_mod", dice_path)
        de = dice_mod.MarkusDiceEngine()
        before = de.get_action_stats()
        de.record_action_reward("UPGRADE_AI_MODEL", 0.9)
        after = de.get_action_stats()
        before_reward = before["action_rewards"].get("UPGRADE_AI_MODEL", 0.0)
        after_reward = after["action_rewards"].get("UPGRADE_AI_MODEL", 0.0)
        assert after_reward != before_reward, "record_action_reward did not mutate the action weight"
        assert after["action_counts"]["UPGRADE_AI_MODEL"] == before["action_counts"].get("UPGRADE_AI_MODEL", 0) + 1, \
            "record_action_reward did not increment the action count"
        assert 0.0 < after_reward <= 1.0, "mutated weight out of (0, 1] range"
        check("G8 record_action_reward weight-mutation contract", True)
    except Exception as exc:
        check("G8 record_action_reward weight-mutation contract", False, str(exc))

    return _finish()


def _finish() -> int:
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nTOTAL PASS={passed} TOTAL_FAIL={total - passed} (of {total})")
    if passed == total:
        print("RESULT: PASS")
        return 0
    print("RESULT: GATE FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
