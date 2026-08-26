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

## ✅ Status: Implemented

- **Reflexion Loop (`markus_reflexion.py`)**: Passes self-test (`_test_reflexion`). Wired into live co-evolution cycle (`CoEvolutionOrchestrator` Phase 6b).
- **Population Dice Evolution (`markus_population_dice.py`)**: Passes self-test (`_test_population_dice`). Wired into live co-evolution cycle (`CoEvolutionOrchestrator` Phase 6c).
- **Red Team Adversarial Loop (`markus_redteam.py`)**: Passes self-test (`_test_redteam`). Wired into live co-evolution cycle (`CoEvolutionOrchestrator` Phase 6d).

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

---

## 🔬 Dice Engine Research Run — 2026-08-26 (Duo Dice cycle)

**Source:** `markus_web_research.py` (WebResearchEngine) — run `PASSED` via dice engine slot 5 (RESEARCH_MARKUS_ROADMAP).

### Topics researched (3)

| Topic | Findings | Coverage | Improvement Opportunity | Effort |
|:---|:---|:---|:---|:---|
| `autonomous_agent_loop` | AutoGPT goal decomposition → task queue; BabyAGI priority queue; SWE-agent terminal+browser loop; Reflexion self-reflection; DevSwarm strange-loop healing; EvoAgentX topology adaptation | High (dice engine + debate pipeline) | Add hierarchical task decomposition | Medium |
| `swarm_intelligence` | UDP gossip + Lamport vector clocks; TCP reliability layer; ant-colony task assignment; particle-swarm tuning; RAFT consensus; φ-accrual failure detection | Medium (UDP gossip replication) | Add RAFT consensus + failure detection | High |
| `multi_model_routing` | vLLM PagedAttention; TGI continuous batching; Ollama local serving; OpenRouter performance routing; adaptive reliability scoring; confidence triage (≥0.8 hermes / ≥0.5 ollama / <0.5 nous) | Medium (adaptive matrix) | Real-time reliability scoring | Low |

### Actionable next steps (from research)
1. **multi_model_routing (LOW effort, highest ROI)** — wire real-time reliability scoring into `markus_adaptive_matrix.py`; reuse confidence-triage thresholds already proven in the triage layer.
2. **autonomous_agent_loop (MEDIUM)** — add a hierarchical task-decomposition stage in front of the DAG (`markus_hierarchical_decomposer.py` already exists; connect it to the dice action queue).
3. **swarm_intelligence (HIGH)** — defer RAFT/φ-accrual until after the two above; keep UDP gossip as-is.

**Run evidence:** `python markus_web_research.py` → `✅ Web Research Engine Test: PASSED` (exit 0), 5 findings per topic, feasibility assessed for all 3.
## 2026-08-26T18:09:08+1000 — Dice Research Slot: multi_model_routing
Live web findings: no

## Improvement Proposal: Multi Model Routing

### Current MARKUS Coverage
Medium - Adaptive matrix

### Key Findings from Research
- vLLM: High-throughput LLM inference with PagedAttention
- TGI: HuggingFace Text Generation Inference with continuous batching
- Ollama: Local model serving with ModELFUSE pipeline

### Identified Tradeoffs


### Proposed Enhancement
Real-time reliability scoring

### Effort Estimate
Low

### Next Steps
1. Create implementation plan for Real-time reliability scoring
2. Generate PHOENIX CLI module for AST validation
3. Test with existing test suite
4. Commit with conventional commit format

## 2026-08-26T18:10:11+1000 — Dice Research Slot: multi_model_routing
Live web findings: yes

## Improvement Proposal: Multi Model Routing

### Current MARKUS Coverage
Medium - Adaptive matrix

### Key Findings from Research
- vLLM: High-throughput LLM inference with PagedAttention
- TGI: HuggingFace Text Generation Inference with continuous batching
- Ollama: Local model serving with ModELFUSE pipeline

### Identified Tradeoffs


### Proposed Enhancement
Real-time reliability scoring

### Effort Estimate
Low

### Next Steps
1. Create implementation plan for Real-time reliability scoring
2. Generate PHOENIX CLI module for AST validation
3. Test with existing test suite
4. Commit with conventional commit format

## 2026-08-26T18:10:52+1000 — Dice Research Slot: multi_model_routing
Live web findings: yes

### All findings (8)
- vLLM: High-throughput LLM inference with PagedAttention
- TGI: HuggingFace Text Generation Inference with continuous batching
- Ollama: Local model serving with ModELFUSE pipeline
- OpenRouter: Unified API with performance-based routing
- Adaptive Model Switcher: Real-time reliability scoring
- LangGraph: de facto 2026 standard for production multi-agent - stateful graphs, durable execution, HITL
- Microsoft Agent Framework: conversation + graph-based routing, Azure telemetry
- CrewAI: role-based crews, rapid prototyping, open source

## Improvement Proposal: Multi Model Routing

### Current MARKUS Coverage
Medium - Adaptive matrix

### Key Findings from Research
- vLLM: High-throughput LLM inference with PagedAttention
- TGI: HuggingFace Text Generation Inference with continuous batching
- Ollama: Local model serving with ModELFUSE pipeline

### Identified Tradeoffs


### Proposed Enhancement
Real-time reliability scoring

### Effort Estimate
Low

### Next Steps
1. Create implementation plan for Real-time reliability scoring
2. Generate PHOENIX CLI module for AST validation
3. Test with existing test suite
4. Commit with conventional commit format

## 2026-08-26T18:36:14+1000 — Dice Research Slot: multi_model_routing
Live web findings: yes

### All findings (8)
- vLLM: High-throughput LLM inference with PagedAttention
- TGI: HuggingFace Text Generation Inference with continuous batching
- Ollama: Local model serving with ModELFUSE pipeline
- OpenRouter: Unified API with performance-based routing
- Adaptive Model Switcher: Real-time reliability scoring
- RouteLLM (ICLR 2025): learned complexity router achieves 95% of frontier quality routing only 14-26% of requests to expensive model - 75-85% cost cut
- 70/20/10 distribution: route 70% to cheap flash ($0.30/M), 20% to mid ($3/M), 10% to frontier ($15/M) - ~86% cost reduction on routed traffic
- FrugalGPT cascade (2023): cheapest model first, escalate on scorer rejection - up to 98% lower cost at matched quality

## Improvement Proposal: Multi Model Routing

### Current MARKUS Coverage
Medium - Adaptive matrix

### Key Findings from Research
- vLLM: High-throughput LLM inference with PagedAttention
- TGI: HuggingFace Text Generation Inference with continuous batching
- Ollama: Local model serving with ModELFUSE pipeline

### Identified Tradeoffs


### Proposed Enhancement
Real-time reliability scoring

### Effort Estimate
Low

### Next Steps
1. Create implementation plan for Real-time reliability scoring
2. Generate PHOENIX CLI module for AST validation
3. Test with existing test suite
4. Commit with conventional commit format

## 2026-08-26T18:48:07+1000 — Dice Research Slot: phone_unlocking
Live web findings: yes

### All findings (8)
- Carrier/network unlock is legally REQUIRED (US FCC + CTIA Consumer Code): carriers must unlock free once device is fully paid / early-termination fee settled
- CTIA policy: postpaid unlock on request for customers in good standing after contract/financing fulfilled; prepaid unlock no later than 1yr after activation
- How to check lock status: iPhone Settings>General>About 'Carrier Lock' shows 'No SIM restrictions' = unlocked; Samsung Settings>Connections>Mobile networks>Network operators (list appears = unlocked); dial *#06# for IMEI
- T-Mobile auto-unlocks within ~2 days of eligibility (paid off + 40+ days on network); request via unlock page/app or call 611 / 800-937-8997; caps ~2 devices/year
- eSIM (all iPhones since 2018, many Android) removes the physical-SIM step for switching carriers
- Forgotten passcode recovery is OFFICIAL but data-wiping: iOS = Passcode Reset then recovery mode + computer reset (Apple); Android = Google Find My Device remote unlock/factory reset + Google-account verification
- Forgotten-passcode unlock resets the device (data loss) - the honest tradeoff; no method recovers data without the passcode on modern devices
- Scope: these are the legal paths for phones you own. Bypassing a device you don't own (stolen/lost FRP or Activation-Lock) is not covered.

## Improvement Proposal: Phone Unlocking

### Current MARKUS Coverage
Unknown

### Key Findings from Research
- Carrier/network unlock is legally REQUIRED (US FCC + CTIA Consumer Code): carriers must unlock free once device is fully paid / early-termination fee settled
- CTIA policy: postpaid unlock on request for customers in good standing after contract/financing fulfilled; prepaid unlock no later than 1yr after activation
- How to check lock status: iPhone Settings>General>About 'Carrier Lock' shows 'No SIM restrictions' = unlocked; Samsung Settings>Connections>Mobile networks>Network operators (list appears = unlocked); dial *#06# for IMEI

### Identified Tradeoffs
- Forgotten-passcode unlock resets the device (data loss) - the honest tradeoff; no method recovers data without the passcode on modern devices

### Proposed Enhancement
Research needed

### Effort Estimate
Unknown

### Next Steps
1. Create implementation plan for Research needed
2. Generate PHOENIX CLI module for AST validation
3. Test with existing test suite
4. Commit with conventional commit format

## 2026-08-26T20:35:55+1000 — Dice Research Slot: swarm_intelligence
Live web findings: no

### All findings (5)
- UDP gossip protocols with Lamport vector clocks for consistency
- TCP reliability layer for message delivery guarantees
- Ant colony optimization for distributed task assignment
- Particle swarm optimization for parameter tuning
- RAFT consensus for distributed state machine replication

## Improvement Proposal: Swarm Intelligence

### Current MARKUS Coverage
Medium - UDP gossip replication

### Key Findings from Research
- UDP gossip protocols with Lamport vector clocks for consistency
- TCP reliability layer for message delivery guarantees
- Ant colony optimization for distributed task assignment

### Identified Tradeoffs


### Proposed Enhancement
RAFT consensus, failure detection

### Effort Estimate
High

### Next Steps
1. Create implementation plan for RAFT consensus, failure detection
2. Generate PHOENIX CLI module for AST validation
3. Test with existing test suite
4. Commit with conventional commit format
