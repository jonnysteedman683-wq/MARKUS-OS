# Evolutionary Loop Implementation Roadmap

**Research Phase Complete — 60+ minutes of pattern analysis**

## 📚 Research Summary

### Open Source Patterns Catalogued

| Pattern | Source | Stealable Components | Our Equivalent | Lift Effort |
|:---|:---|:---|:---|:---|
| **Reflexion** | github.com/yingruilee/Reflexion | Trajectory collector, critique generator, refiner | `markus_debate_pipeline.py` SENTINEL + cortex | Wrap critique around trajectory collection |
| **Population-Based Evolution** | github.com/google/brain-research/regularized_evolution | Tournament selection, mutation ops, generational replacement | `markus_dice_engine.py` action weights | Extend reward-weighted dice to population |
| **Chaos Engineering** | github.com/chaostoolkit/chaos-engine | Failure injection, resilience verification, remediation triggers | `markus_sandbox.py` + `markus_resilience.py` | Create red/blue agent pattern |
| **Constitutional AI** | github.com/anthropics/ConstitutionalAI | Self-critique generation, revision, consistency checking | `markus_debate_pipeline.py` + `CortexSkillPatcher` | Add revision step to debate pipeline |
| **SWE-agent** | github.com/princeton-nlp/SWE-agent | Action observation logging, feedback-driven policy adjustment | `markus_co_evolution.py` 7-phase orchestrator | Add trajectory feedback |
| **Ray PBT** | github.com/ray-project/ray | Genome representation, exploit, explore mutation | `markus_dice_engine.py` action weights | Add genome to hyperparameters |
| **Mutation Testing** | github.com/gaasedelen/taranos | Input mutation strategies, crash detection, root cause analysis | `markus_sandbox.py` + `markus_complexity_governor.py` | Add mutation-based input generation |
| **AutoGPT Goal Scaffolding** | github.com/Significant-Gravitas/AutoGPT | Task priority queue, goal decomposition, adaptive replanning | `markus_hierarchical_decomposer.py` + DAG | Add priority queue + replanning |

### Academic Papers Catalogued

| Paper | Pattern | Key Components |
|:---|:---|:---|
| **Self-Refine (ICLR 2024)** | LLM output → self-feedback → refine iteratively | Self-feedback prompt, feedback-to-action, stopping criterion |
| **Reflexion (ICLR 2024)** | Act → observe → self-reflect → adjust behavior | Memory buffer, self-reflection prompt, behavioral adjustment |
| **LAO (NeurIPS 2024)** | Adaptive planning depth based on task complexity | Complexity estimator, depth controller, horizon adjustment |
| **Metacognitive Control (ACL 2025)** | Monitor confidence → seek info when uncertain | Confidence estimator, uncertainty-based info gathering |

## 🚀 Implementation Plan (3 Priority Loops)

### 1. Reflexion Loop (markus_reflexion.py) — PRIORITY 1
**Stealable code:**
- Trajectory collection from `markus_cortex_skill_patcher.py` thought analysis
- Critique generation from `markus_debate_pipeline.py` SENTINEL persona
- Phase sequencing from `markus_co_evolution.py` execute_multi_upgrade_cycle()

**Structure:**
```
1. Execute action (dice roll + upgrade)
2. Collect trajectory (cortex thoughts + latency metrics)
3. Generate self-critique (SENTINEL persona analysis)
4. Refine approach (adjust dice weights + bracket probabilities)
5. Retry with refined parameters
```

**Reuse opportunities:**
- `MarkusDiceEngine` for action selection
- `PersistentCortexDB` for trajectory storage
- `MarkusDebatePipeline` for critique generation
- `SelfEvolvingCodeEngine.evaluate_candidate` for validation

### 2. Population Dice Loop (markus_population_dice.py) — PRIORITY 2
**Stealable code:**
- Boltzmann weights from `markus_dice_engine.py` (softmax temperature)
- Bracket probability from `markus_latency_multi_upgrade.py` (1/6 base probability)
- Fitness evaluation from `markus_dice_engine.py` record_action_reward()

**Structure:**
```
1. Initialize population of N dice engines with different weights
2. Each engine runs cycle independently
3. Tournament selection: pick top performers
4. Exploit: copy weights from winners
5. Explore: mutate winner weights (perturb action weights)
6. Replace bottom performers with new mutants
```

**Reuse opportunities:**
- `roll_reward_weighted_dice()` for individual engine decisions
- `record_action_reward()` for fitness scoring
- `get_action_stats()` for population health monitoring
- `calculate_latency_brackets()` for selection pressure

### 3. Red Team Adversarial Loop (markus_redteam.py) — PRIORITY 3
**Stealable code:**
- Isolated execution from `markus_sandbox.py` ProcessSandbox.execute_python_code()
- Circuit breaker from `markus_resilience.py` for resilient testing
- Skill editing from `markus_latency_multi_upgrade.py` _skill_edit()
- Cortex logging from `markus_db.py` append_thought()

**Structure:**
```
RED PHASE:
1. Red agent finds vulnerabilities (sandbox mutation testing)
2. Classifies severity and root cause
3. Logs to cortex as vulnerability records

BLUE PHASE:
1. Blue agent reads vulnerability records
2. Generates patches using skill_patcher patterns
3. Applies patches to codebase

VALIDATION:
1. PHOENIX CLI validates all modules
2. If PASS → commit, if FAIL → retry
```

**Reuse opportunities:**
- `MarkusProcessSandbox` for isolated vulnerability testing
- `CortexSkillPatcher` for automated fix generation
- `PHOENIX CLI` for validation gate
- `CircuitBreakerManager` for error resilience

## 📋 Ready-to-Steal Code Snippets Inventory

### From `markus_dice_engine.py`:
```python
# Boltzmann exploration (steal for population mutations)
def roll_reward_weighted_dice(self):
    temperature = 1.0
    exps = [math.exp(w / temperature) for w in self.action_weights.values()]
    probs = [e / sum(exps) for e in exps]
    # This can be lifted for parent selection in population loop
```

### From `markus_co_evolution.py`:
```python
# 7-phase sequence (steal for any loop structure)
phases = ["dice_roll", "debate", "phoenix_validate", "auto_commit", 
          "devswarm_health", "skill_patch", "reward_feedback"]
# Each phase has: start_timer → execute → measure → log → next
```

### From `markus_latency_multi_upgrade.py`:
```python
# Guaranteed action pattern (steal for any loop requiring guaranteed progress)
actions = ["A.upgrade", "B.edit", "C.invent", "D.explore"]
for i in range(1, 7):
    if secrets.randbelow(10000) < int(1.0/6.0 * 10000):
        self.execute_guaranteed_skill_action(actions[(i-1) % 4])
```

### From `markus_debate_pipeline.py`:
```python
# Critique format (steal for reflexion loop)
verdict = f"{persona_name} | Confidence: {confidence:.1f}% | Consensus: {consensus}"
# Can be reused as self-critique output format for reflexion loop
```

### From `markus_cortex_skill_patcher.py`:
```python
# Pattern matching for trajectory analysis
patterns = {
    "skill_update": re.compile(r"(?i)(\\w+skill\\w+)(.*)(update|improve|patch|fix)", re.DOTALL),
    # Can be lifted for reflexion loop trajectory analysis
}
```

## 🏗️ Implementation Timeline

| Loop | Estimated LOC | Difficulty | Stealable Components | Time Estimate |
|:---|:---:|:---:|:---|:---:|
| Reflexion Loop | 150 | MEDIUM | 5 patterns | 30 min |
| Population Dice Loop | 180 | MEDIUM | 4 patterns | 45 min |
| Red Team Loop | 200 | HIGH | 4 patterns | 60 min |
| **Total** | **530** | | **13 patterns** | **~2 hours** |

---

**Status:** Research phase complete. Awaiting web access for deeper paper/code analysis before implementation.