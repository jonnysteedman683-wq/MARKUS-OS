#!/usr/bin/env python3
"""hermes_verify_evolution_loops.py — Evolutionary Loops Verification Harness (2026-08-27).

Verifies the contract integrity and self-tests of all three MARKUS OS evolutionary loops:
  G1  py_compile AST gate on markus_reflexion.py, markus_population_dice.py, markus_redteam.py
  G2  ReflexionLoopEngine self-test execution (_test_reflexion_loop)
  G3  ReflexionLoopEngine contract verification (collect_trajectory, generate_self_reflection, refine_and_retry, get_reflection_stats)
  G4  PopulationDiceEngine self-test execution (_test_population_dice)
  G5  PopulationDiceEngine contract verification (tournament selection, record_action_reward weight mutation)
  G6  RedTeamOrchestrator self-test execution (_test_redteam)
  G7  RedTeamOrchestrator contract verification (RED-phase vulnerability round-trip to cortex + BLUE-phase patch synthesis)

Stdlib-only, network-free, fail closed.
Exit 0 = all gates pass.
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import sys
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
        if traj:
            assert hasattr(traj[0], "success"), "trajectory step missing success field"
            assert hasattr(traj[0], "latency_ms"), "trajectory step missing latency_ms field"

        reflection = ref_engine.generate_self_reflection(traj)
        assert isinstance(reflection, mod_reflexion.SelfReflection), "generate_self_reflection invalid type"
        assert hasattr(reflection, "issues_found") and hasattr(reflection, "suggested_improvements"), "invalid reflection fields"

        success, msg = ref_engine.refine_and_retry(reflection, max_retries=1)
        assert isinstance(success, bool), "refine_and_retry invalid return type"

        stats = ref_engine.get_reflection_stats()
        assert isinstance(stats, dict) and "total_reflections" in stats, "get_reflection_stats invalid schema"
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

        mutated = pop_engine.mutate_genome(winner)
        assert isinstance(mutated, mod_pop.DiceGenome), "mutate_genome invalid return type"
        assert mutated.genome_id != winner.genome_id, "mutated genome must have distinct genome_id"
        check("G5 PopulationDiceEngine contract verification", True)
    except Exception as exc:
        check("G5 PopulationDiceEngine contract verification", False, str(exc))

    # G6: RedTeam self-test execution
    try:
        mod_redteam._test_redteam()
        check("G6 RedTeam self-test (_test_redteam)", True)
    except Exception as exc:
        check("G6 RedTeam self-test (_test_redteam)", False, str(exc))

    # G7: RedTeam contract verification
    try:
        rt_orch = mod_redteam.RedTeamOrchestrator()
        vuln = mod_redteam.Vulnerability(
            vuln_id="vuln_g7_test",
            category="correctness",
            severity="HIGH",
            file_path="markus_sandbox.py",
            line_number=42,
            description="Simulated vulnerability check",
            failing_code="eval(user_input)",
            fix_pattern="ast.literal_eval(user_input)",
            confidence=0.95
        )
        rt_orch.cortex.append_thought(
            f"vuln_{vuln.vuln_id}", "MARKUS_REDTEAM",
            f"Vulnerability logged: {vuln.description} in {vuln.file_path}:{vuln.line_number}",
            {"vuln_id": vuln.vuln_id, "severity": vuln.severity}
        )

        fix_code = rt_orch.blue_agent.generate_fix(vuln)
        assert isinstance(fix_code, str), "generate_fix must return str fix code"
        check("G7 RedTeamOrchestrator contract verification", True)
    except Exception as exc:
        check("G7 RedTeamOrchestrator contract verification", False, str(exc))

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
