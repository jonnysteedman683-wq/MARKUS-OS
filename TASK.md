# TASK: Verify, harden, and wire the three evolutionary loops into the live cycle

**Repo:** `C:/Users/jonny/OneDrive/Desktop/MARKUS-OS`
**Goal:** The three evolutionary loops from `research/evolutionary_loop_roadmap.md` are
implemented (`markus_reflexion.py`, `markus_population_dice.py`, `markus_redteam.py`) but are
NOT verified by any harness and NOT invoked by the live co-evolution cycle. Make them
production-real. Do NOT rewrite them — they pass their self-tests. Find and fix real gaps.

## Context (read these first)
- `research/evolutionary_loop_roadmap.md` — the spec (sections "3 Priority Loops" + "Ready-to-Steal Snippets Inventory").
- `markus_reflexion.py` (404 lines, self-test PASSES) — Reflexion loop: act → observe → self-reflect → refine.
- `markus_population_dice.py` (408 lines, self-test PASSES) — population of N dice engines with tournament selection.
- `markus_redteam.py` (563 lines, self-test PASSES) — RED/BLUE adversarial loop with PHOENIX validation.
- `markus_co_evolution.py` — the LIVE 7-phase cycle; `CoEvolutionOrchestrator.execute_cycle()` is the daemon.
- `markus_epoch_scheduler.py` — scheduler that references the loops.
- `markus_integration_test.py` — the 9/9 integration harness (do not break it).
- `hermes_verify_markus_brain.py` — the house style for a verification harness (stdlib-only, AST gate + module self-test, PASS/FAIL lines, exit code).

## Deliverables (all required)

### 1. Verification harness (the big one)
Create **`hermes_verify_evolution_loops.py`** in the house style, covering ALL THREE loops:
- py_compile AST gate on all three modules.
- Run each module's `_test_*` self-test and assert it passes.
- Direct checks on the loop contracts (read the code first, then assert):
  - `ReflexionLoopEngine`: `collect_trajectory()`, `generate_self_reflection()`, `refine_and_retry()`,
    `get_reflection_stats()` exist and return the declared types; trajectory steps carry
    `success` + `latency_ms`.
  - `PopulationDiceEngine` (or the population loop's engine): tournament selection returns a winner,
    weights mutate on `record_action_reward`.
  - Red team: a RED-phase vulnerability record round-trips to cortex and a BLUE-phase patch exists.
- Must be stdlib-only, no network, fail closed (non-zero exit + clear line on ANY failure).
- End with `TOTAL PASS=N TOTAL_FAIL=0` + `RESULT: PASS` and exit 0 on success.

### 2. Wire-in (do the minimal real thing)
Check how `markus_co_evolution.py` and `markus_epoch_scheduler.py` reference the loops.
`grep -rn "reflexion\|population_dice\|redteam" *.py` to map the call sites.
- If a loop is imported but never *called* in `execute_cycle()`: add ONE well-scoped invocation
  (e.g. a reflexion pass over the last cycle's trajectory in the reward/refine phase) with a clear
  `# Reflexion wiring` comment. Keep it stdlib-only and cheap — do not turn the cycle async-into-a-mess.
- If the reference is already live, document it in a brief code comment instead of changing behavior.
- The 9/9 integration test MUST still pass after your change (`python markus_integration_test.py`).

### 3. Doc truth-pass (small)
The roadmap says these loops are unimplemented ("Status: Research phase complete."). That is stale.
Add ONE short section at the top of `research/evolutionary_loop_roadmap.md` (above "Implementation Plan"):
"## ✅ Status: Implemented" — three bullets, one per loop, each stating the module name, that it
passes its self-test, and whether it is wired into the live cycle (after your step 2). Do not
rewrite the rest of the roadmap.

## Verification (must all pass before you report done)
1. `python -m py_compile markus_reflexion.py markus_population_dice.py markus_redteam.py markus_co_evolution.py`
2. `python hermes_verify_evolution_loops.py` → ALL PASS, exit 0
3. `python markus_integration_test.py` → still 9/9
4. Your three `_test_*` self-tests still PASS.

## Constraints
- Python 3.11, stdlib-only. No new dependencies, no network calls, no touching the live server
  (port 8128) or `markus_server.py`.
- Do NOT rewrite the loop modules' core logic. If you find a genuine bug, fix it minimally and
  say what + why in your summary.
- House style: follow `hermes_verify_markus_brain.py` for harness structure and message format.
- Report as plain text: what you found (real gaps), what you changed, each verification command's
  output tail, and any bugs fixed.

## Definition of done
- New harness exists, passes, exits 0.
- Loops are either wired into the live cycle OR proven already-wired (state which, with evidence).
- Roadmap truth-pass committed to the file.
- All three verification commands above green.
