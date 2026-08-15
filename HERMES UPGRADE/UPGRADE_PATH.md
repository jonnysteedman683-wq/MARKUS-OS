# HERMES ECOSYSTEM — Upgrade Path

**Title:** THREE MINDS, ONE WORLD
**Version:** 1.3 — 2026-08-13
**Status:** Approved — 8 decisions resolved
**Owner:** Jonny
**Scope:** HERMES-HIVE (deck) · 3-brain hybrid intertwined (Deliberative + Memory Cortex now, Evolution Phase-2; hive-mind parked) · SUPRIME/OMNIBUS (backend) · AEGIS sim (world)

---

## 1. The North-Star Milestone

> **A viewer opens the Hive deck, submits an intent, watches it pass
> through SafetyGate → a multi-brain hybrid → provider, and sees the
> AEGIS ecosystem visibly react to the decision — live, in one UI, safe.**

**"Think multiple things at once & multitask":** the brain runs **parallel reasoning
threads** (multiple thinkers drafting simultaneously, an aggregator synthesizing —
MoA-native) and processes **multiple intents concurrently** (scheduler → per-intent
branch), not one sequential pass.

**Three Minds architecture** (Decision 6):

| Brain | Color | Role | Salvage source | Ships |
|---|---|---|---|---|
| **1 · Deliberative** | 🔵 **blue** | the thinker | `open-multi-agent` / `langgraphjs` + `together/moa` | **Now (Workstream A)** |
| **2 · Memory Cortex** | 🔴 **red** | the rememberer / self-improver | `zensation-ai/zenbrain` + `agentmemory` + Gödel loop | **Now (Workstream A)** |
| **3 · Evolution** | 🟢 **green** | the grower / behaver (drives the world's life) | Anima-style internal-state agents on an **NCA world substrate** (TS/WebGPU) + LTC/predictive-coding patterns | **Phase-2 (deferred)** |

Brain 2 doesn't answer intents — it **feeds Brain 1 recalled context** and **learns
from every decision** (sleep consolidation, Hebbian strengthening, Gödel self-improve).
Brain 3 is what the demo *world visibly does* (agents breed/adapt/self-organise) and is
explicitly deferred to Phase-2; the demo world stays thin-but-reactive (Decision 4).

The **demonstrable, end-to-end loop** is the single "wow, it works" moment.
It forces all three threads (capability, production-readiness, modernization)
to converge on one live demonstration. **Demo-ready, not public deploy** — but
built on production-safe primitives so a public release is a config change, not a rewrite.

```
        ┌────────────────────────────────────────────────────────────┐
        │                      HIVE DECK  (:3000)                     │
        │        intent input ──► live event / ecosystem feed          │
        └───────────────┬───────────────────────────────┬────────────┘
                        │ POST /api/neurocore/intent     │ renders decision
                        ▼                                ▼
        ┌────────────────────────────────────────────────────────────────┐
        │   BRAIN 1 · DELIBERATIVE  (MoA-native, multitask)  ◄─ctx/recall─┐
        │   SafetyGate ──► Scheduler ──► [branch 1]─►[branch 2]─►…        │
        │   parallel thinkers ▸ aggregate ▸ provider(route)              │
        └───────────────┬───────────────────────────────┬────────────────┘
            decision/event                              │ learn/consolidate
            ▼                                           ▼
        ┌─────────────────────────────┐     ┌──────────────────────────────┐
        │   BRAIN 3 · EVOLUTION       │     │  BRAIN 2 · MEMORY CORTEX      │
        │   (Phase-2) world's life     │     │  7-layer · Hebbian · sleep     │
        │   agents breed/adapt/self-  │     │  recursion · Gödel self-improve │
        │   organise   ────────────►  │◄────┘  ── zenbrain + agentmemory ──    │
        └─────────────────────────────┘     └──────────────────────────────┘
                ▲  world visibly reacts
                │
        ┌───────┴────────────────────────────────────────────────────────┐
        │                     AEGIS WORLD  (sim) - minimal-wired           │
        └────────────────────────────────────────────────────────────────┘
```

---

## 2. Current Reality (verified 2026-08-13 — files on disk)

| Thread | Where | State |
|---|---|---|
| **Deck** | `~/HERMES-HIVE` (Vite+Svelte @ :3000) | Mature. ~40 `src/server/*` modules (federation, cognition, evolution, governance, memory, missions…), Sqlite state. **m1 Swarm Registry + Level-1 trust gate + Level-2 intent bridge done.** `hive-vision.md` M1→M9 is the *machinery* roadmap. |
| **Brain** | `~/HERMES-HIVE/src/server/cognition/debateEngine.ts` | **Present but FAKE:** `CognitiveDebateEngine` returns hardcoded proposals/objections and picks the winner as `proposals[1] || proposals[0]` — **no model call, no real decision.** Parallel-thinking muscle is simulated, not real. This is the "delete fake code" debt — and the seed the hybrid brain replaces. |
| **Backend** | `~/SUPRIME` (Python swarm lib), `~/SUPRIME-SWARM` | Real & substantial: gossip, hyparview, plumtree, CRDT/RGA, byzantine, consensus, crypto, peers. New untracked `bridge.py` (FastAPI control plane) in progress. |
| **World** | `~/Documents/AEGIS` (agent-engine-check, Next.js) | Present but cluttered (multiple `archive_2026*` dirs, "ARCANE QUANTUM BRAIN", Sentinel). Live 2D ecosystem **not wired to the brain at all.** |

**Key architectural fact:** the three pieces today are *disconnable*. The upgrade
path is: **build the missing brain, wire it to both ends, and make all three run
as one living system you can demonstrate.**

---

## 3. Workstreams (the upgrade path)

Prioritised. **A is the bottleneck and unblocks both ends.**
**Build method:** A is **hand-built** (in-loop). B & C are handed to the **swarm** as hive-mind missions (M-roadmap decomposition).

### Workstream A — BRAIN (hybrid, MoA-native, multitask) — TOP PRIORITY

Replace the **fake** `CognitiveDebateEngine` with a real parallel-thinking brain.
**Steal proven patterns from public repos** (all MIT/Apache-2.0 — legally reusable),
implement as clean tested TypeScript inside `~/HERMES-HIVE/src/server/neurocore/`
and `src/server/cognition/`. **No Python runtimes, no sidecar process, no CJS/ESM bridge.**

**Proven sources we borrow (verified 2026-08-13):**
- **microsoft/agent-framework** (AutoGen successor, MIT, 12.8k⭐, active) → parallel/Magentic orchestration primitives, group-chat speaker selection.
- **togethercomputer/moa** (Apache-2.0, 3k⭐, reference impl, arXiv 2406.04692) → layered *parallel proposal → aggregate* (MoA): N thinkers draft concurrently, aggregator synthesizes. (65.1% AlpacaEval, beats GPT-4o on OSS.)
- **catena-labs/moa-llm** (MIT) → neural-network-inspired layering map: `LLMNeuron → Layer → AggregationLayer`, weighted inputs, async. Small/archived — use as concept map only.
- **open-multi-agent** (@open-multi-agent/core, MIT, 6.8k⭐, TS 97%, active) → runtime task-DAG coordinator. Proven TS multitask scheduler — candidate *dependency* for A5 rather than re-implementation.
- **langchain-ai/langgraphjs** (`@langchain/langgraph`, MIT, 3.2k⭐, active) → native TS parallel branches + scheduler. Candidate *dependency* for A5.
- **`@zensation-ai/zenbrain`** (Apache-2.0, zero-dep TS, arXiv 2604.23878) → 7-layer memory cortex, FSRS, Hebbian, sleep-consolidation recursive loop. **Brain 2 seed.**
- **`rohitg00/agentmemory`** (TS) → episodic memory from tool-use capture. Brain 2 blueprint.
- **ruvnet Gödel Agent tutorial** → safe recursive self-improvement loop (propose → analyze → verify → accept/reject) with infinite-rewrite guard. Brain 2 self-improvement harness.

| # | Piece | Mechanism | Effort | Impact |
|---|---|---|---|---|
| A1 | **Module scaffold** | `src/server/neurocore/` namespace, TS types (`NeuroIntent`, `NeuroDecision`, `ProviderChoice`, `MoADraft`, `AggregatedDecision`), test harness | S | H (foundation) |
| A2 | **SafetyGate** | Validate every `NeuroIntent` before routing: confidence cap **≤ 0.95**, cost cap **≤ $5**, emergency-stop flag, allowlist/denylist. Reject → respond, never silently drop | M | **H** (makes loop safe) |
| A3 | **Parallel thinker pool (Brain 1, MoA draft stage)** | *From together/moa + agent-framework.* N specialist thinkers (strategist/analyst/security critic…) each draft a response **concurrently** (`Promise.all`/worker pool) → emit `MoADraft[]`; group-chat speaker selection for debate rounds | L | **H** (the "thinks many things at once" core) |
| A4 | **Aggregator (Brain 1, MoA synthesize stage)** | *From together/moa AggregationLayer + moa-llm weighted neurons.* Aggregate `MoADraft[]` → synthesized decision; weighted vote by peer reputation/weight; produce final `NeuroDecision` (winner + rationale + confidence) | L | **H** (the "brain" moment) |
| A5 | **Scheduler (Brain 1, multitask)** | *`open-multi-agent` / `langgraphjs` (dependency, or port).* Each incoming intent → its own parallel branch; multiple intents run **concurrently** on a bounded pool; results keyed by intentId | L | **H** (the "multitask" requirement) |
| A6 | **Memory Cortex (Brain 2) — scaffold + core** | *From zenbrain + agentmemory.* 7-layer memory (`@zensation/`), FSRS recall, Hebbian learning, sleep-consolidation recursion; expose `recall(ctx)` / `learn(decision)` to Brain 1 | L | **H** (remember + self-improve) |
| A7 | **Brain 2 ↔ Brain 1 wiring** | Brain 1 pulls **context** via `memory.recall(intent)` before drafting; after each `NeuroDecision`, Brain 2 **learns**; Gödel self-improve loop (guarded) refines Brain 1 prompts/weights | M | **H** (the "unique brain" glue) |
| A8 | **OmniSwarmAdapter + `routeToAI()` Hermes case** | Unified provider interface: `hermes` (OpenAI-compat `/v1/chat/completions`, `HERMES_URL`, default `hermes-3-llama-3.1-8b`, `max_tokens 1024`), `ollama` (:11434), `nous`. Confidence triage **≥0.8 hermes / ≥0.5 ollama / <0.5 nous** | M | **H** |
| A9 | **REST endpoints** | `POST /api/neurocore/connect` · `POST /api/neurocore/intent` · `GET /api/neurocore/health` · `POST /api/neurocore/debate` · `GET /api/neurocore/peers` · `POST /api/neurocore/emergency-stop` | M | **H** |
| A10 | **Retire fake engine** | `CognitiveDebateEngine` → route calls through the real brain (keep `DebateRecord` type/bus contract so nothing downstream breaks); delete hardcoded proposals/objections + `proposals[1] \|\| proposals[0]` pick | S | **M** (honesty: kills fake code) |

**Acceptance for A:** submit two different intents at once → both route through
SafetyGate → **recall context from Brain 2** → parallel drafts → aggregate → provider
→ `NeuroDecision` each; after decisions Brain 2 has **learned** (state/tests prove
consolidation); demo shows multiple threads visibly resolving; emergency-stop actually
halts all providers; health reports diagnostics; **fake engine fully retired**; tests green.

---

### Workstream B — DECK→BRAIN wiring

| # | Piece | Mechanism | Effort | Impact |
|---|---|---|---|---|
| B1 | **Dispatch wiring** | `agent_system.dispatch()` calls `/api/neurocore/intent` when brain enabled, falls back to `/api/chat` otherwise | M | **H** (deck drives brain) |
| B2 | **Confidence triage UI** | `initHiveSwarmMind` in app.js with `window.apiConfig`; expose chosen provider + confidence to the UI so the demo *shows* the routing | M | **M** (wow factor) |
| B3 | **Safety visibility** | Surface emergency-stop + cost/confidence caps in deck; one-click emergency stop | S | **M** (demo of safety) |
| B4 | **SUPRIME bridge hook** | Optionally route brain decisions to the SUPRIME FastAPI bridge (localhost:8123) as swarm events | M | M (optional, later) |

**Acceptance for B:** typing an intent in the deck visibly routes through the brain
and the UI shows gate → debate → provider → decision.

---

### Workstream C — WORLD wiring (AEGIS sim) — demo surface

| # | Piece | Mechanism | Effort | Impact |
|---|---|---|---|---|
| C1 | **Cleanse AEGIS** | Archive-stack cleanup; identify the canonical live-sim entry point (probably `agent-engine-check`) | M | **M** (find the surface) |
| C2 | **Decision feed** | AEGIS exposes a minimal read API / subscribes to a `NeuroDecision` stream from the brain | L | **H** (closes the loop) |
| C3 | **Visible reaction** | Ecosystem agents visibly react to a decision (behaviour change, state flag, event log) rendered live | M | **H** (the "wow" moment) |
| C4 | **Deck embeds world** | The deck renders the sim (iframe/panel) so viewer drives deck → sees brain → sees world react in one screen | M | **H** (the full loop) |

**Acceptance for C:** after a decision, the sim visibly changes in the deck;
no crash; state persists across refresh.

---

## 4. Sequencing & Cadence

Workstreams **A → B → C**. Each is independently demonstrable:

- **Phase 1 (A1–A7):** brain exists and is testable via curl against `/api/neurocore/*`.
- **Phase 2 (B1–B4):** deck drives the brain live on screen.
- **Phase 3 (C1–C4):** world reacts; full loop closes.

> Tie to `hive-vision.md` M-roadmap: the swarm *machinery* (M1–M9) is orthogonal
> and continues in parallel. This upgrade path is about the **product** the swarm
> produces. **Per Decision 3:** A is hand-built now (it's the bottleneck); B & C
> are handed to the hive-mind as missions the swarm decomposes.

### 4a. Minimum Viable Demo (MVP cut) — what &quot;done&quot; really means

If time-boxed, this is the **smallest set that still delivers the North-Star moment**
(deck → brain → world react, in one screen). Everything else is deletable for v1.

**Non-negotiable (must ship for the demo to be real):**
- A2 SafetyGate (safety is the pitch) + A8 provider routing (a real model must respond)
- A3–A4 parallel thinkers → aggregator (the "thinks many things at once" core)
- **A6–A7 Memory Cortex (Brain 2): at minimum recall-context feeding Brain 1 + learning from a decision** — ships now per Decision 6; scoped thin (recall + learn), full sleep/Gödel refinement can deepen post-demo
- C2–C4: decision feed → visible world reaction → deck embeds the world (closes the loop)
- Emergency stop wired to a real halt (proven live in the demo)

**Deletable for v1 (nice-to-have, defer to Phase 2):**
- A5 full multitask scheduler → start with a single-intent path; concurrent intents are an additive win, not the main event
- A9 `/api/neurocore/peers` + `/debate` standalone + `/connect` — only `/intent`, `/health`, `/emergency-stop` are required
- **Brain 3 (Evolution) full depth** — the demo world just visibly reacts; agents breed/adapt/self-organise via a proper Evolution brain is Phase-2 (Decision 6)
- B4 SUPRIME bridge hook — unrelated to the demo loop
- Multi-round debate verbosity + full 7-layer memory tuning — one parallel draft + aggregate round is enough to wow

**The "FAIL MID-DEMO" watchlist** (what would sink the presentation and must be rehearsed):
1. Provider/auth keys live and budget available — a 402 mid-demo is fatal.
2. Emergency stop actually halts — practice it; a "but it didn't stop" is fatal for a safety pitch.
3. The world visibly changes — if the sim can't show a reaction, the loop isn't closed.
4. Two-intents-at-once resolves concurrently IF engaged — otherwise the multitask claim falls flat.

---

## 5. Demo Script (the "wow, it works" moment)

1. Open the Hive deck. The AEGIS world is running in a panel.
2. Type an intent (e.g. "Increase the ecosystem's predator population").
3. Watch it pass **SafetyGate** (validated, under cost/confidence caps) →
   **Brain 2 recall** (memory surfaces context from past decisions) →
   **Brain 1 parallel thinkers** (strategist/analyst/security critic draft in parallel) →
   **aggregator** (weighted vote → synthesized `NeuroDecision`) →
   **provider** (confident routing shown) → `NeuroDecision` → **Brain 2 learns**.
4. Submit a **second, different intent** while the first is still running → both
   resolve concurrently (the "multitask" proof) and each makes the world react.
5. The AEGIS sim visibly reacts to each decision — agents change behaviour live.
6. Tap **emergency stop**; everything halts immediately. Safety proven, live.

---

## 6. Open Decisions

1. ~~Bridge approach~~ — **RESOLVED:** brain lives inside HERMES-HIVE as native ESM TypeScript; CJS/ESM bridge moot.
2. ~~Where the brain lives~~ — **RESOLVED:** `HERMES-HIVE/src/server/neurocore/`.
3. **B & C build method — RESOLVED:** hand-build **A** (the brain) now; hand **B** and **C** to the swarm as hive-mind missions (M-roadmap decomposition). A is the bottleneck and stays in-loop; B/C are mechanical wiring suited to the swarm. Marked in §3 below.
4. **Scope of C — RESOLVED: minimal-wired-and-visible.** Prove the loop (deck→brain→world); legible + reactive ecosystem, not simulation fidelity. **"Ecosystem Depth" is an explicitly deferred Phase-2 upgrade** (post-demo). Recorded in Workstream C + §5.
5. **Proven brains — RESOLVED: borrow patterns, write clean TS.** Proven MoA engines are Python, but the brain lives in TS. Per user, we **port the proven logic** (microsoft/agent-framework orchestration + together/moa layered MoA) into native TS — **no Python runtime, no sidecar, no CJS/ESM bridge.** Sources listed in Workstream A + §8.
6. **Brain architecture — RESOLVED: 3-Minds, staged.** **Three brains:** 1·Deliberative (MoA thinker), 2·Memory Cortex (ZenBrain rememberer/self-improver), 3·Evolution (world's life/grower). **Brains 1 & 2 ship in Workstream A now (wired together); Brain 3 (Evolution) is an explicitly deferred Phase-2 upgrade.** Demo world stays thin-but-reactive. Full architecture in §3.
7. **Intertwine — RESOLVED: one coherent brain via shared memory.** The brains are not three chained stages — they exchange signal through a **SharedContext blackboard** (brain-to-brain shared memory): each mind publishes its state, every mind reads every other's (shared awareness). **Color-coded for the deck:** Brain 1 = 🔵 blue, Brain 2 = 🔴 red, Brain 3 = 🟢 green (`BRAIN_META` in `sharedContext.ts`). Loop per intent: Safety → Brain2 recall → Brain3 predict → Brain1 draft+aggregate → Brain3 apply → Brain2 learn, all published to shared memory. Exposed at `/api/neurocore/health` → `sharedMemory`.
8. **Per-agent tri-brain + hive mind — PARKED (future phase).** The brain is built as a **re-instantiable component** (not a singleton), so each swarm agent can carry its own tri-brain (`NeurocoreOrchestrator` + per-agent `SharedContext`). The **hive mind** = a meta `SharedContext` + `messageBus` aggregating all agents' brains — wired through the existing `agentRegistry` + federation layer. Deliberately *not* built for this demo milestone; parked as the natural next phase after the demo loop ships.

---

## 7. Guardrails

1. **Safety first:** safety cap (≤0.95 confidence, ≤$5 cost) and emergency-stop are non-optional in A.
2. **Never break the live deck:** brain is additive; `/api/chat` fallback always available.
3. **Evidence over vibes:** every piece lands with a test / curl probe / visible demo, not "it should work."
4. **Bridge is resolved:** brain is native ESM TS inside HERMES-HIVE; no CommonJS server, no wrapper, no migration to decide later.

---

## 8. Salvageable Brains — Research Log (2026-08-13)

Brain sources researched on GitHub for code we can reuse. All licenses MIT/Apache-2.0.
**Key constraint:** brain lives in TypeScript; **no Python runtime**. So the ideal
sources are *TS-native packages we can depend on directly* — not logic we re-implement.

**Tier 1 — proven, active, fits "no Python" (deps we can pull in):**
- **`open-multi-agent/open-multi-agent`** — @open-multi-agent/core. **TypeScript 97%, MIT, 6.8k ⭐, active** (commit hours ago). Coordinator plans the *task DAG at runtime* on any LLM (Claude/ChatGPT/Gemini/DeepSeek/local). **Direct fit for A5 scheduler** — this is the proven TS multitask orchestrator.
- **`langchain-ai/langgraphjs`** — `@langchain/langgraph`. **Official LangGraph for TypeScript, MIT, 3.2k ⭐, active** (commit Aug 11). Native parallel branches + scheduler node. **Direct fit for A5** — the exact "parallel branches" A5 borrows from, already in TS.

**Tier 1 — proven MoA (Python, borrow-with-credit / port):**
- **`togethercomputer/moa`** — Apache-2.0, 3k ⭐, reference MoA, arXiv 2406.04692. Layered parallel proposal → aggregate (65.1% AlpacaEval beats GPT-4o on OSS). The conceptual core of A3–A4.
- **`microsoft/agent-framework`** (AutoGen successor) — MIT, 12.8k ⭐, active. Parallel/Magentic orchestration primitives, group-chat speaker selection. Port to TS.
- **`catena-labs/moa-llm`** — MIT, small/archived. `LLMNeuron → Layer → AggregationLayer` weighted layering — good concept map for A4, dead repo so use as blueprint only.

**Tier 2 — self-evolving agents (useful for Phase-2 "ecosystem depth" / evolution):**
- **`EvoAgentX/EvoAgentX`** — build/evolve/optimize agents + workflows, automated, modular, goal-driven.
- **`EvoAgentX/Awesome-Self-Evolving-Agents`** — survey/taxonomy of self-evolution (single-agent vs multi-agent evolution, evolutionary prompting).
- **`Orkas-AI/Orkas`**, **`epsilla-cloud/clawtrace`** — TS self-evolution experiments.

**Tier 2 — world/evolution TS dependencies (for AEGIS sim, Workstream C):**
- **`xcontcom/evolving-cellular-automata`** — genetic algorithms evolve CA rules → pattern emergence. Fits "agents breeding/adapting."
- **`geneticalgorithm` (npm)** — artificial-evolution GA framework for JS/TS.
- **MergeLife / Sakana.ai "Digital Ecosystems"** — browser-based artificial-life / multi-agent neural cellular automata; good *references* for a legible, reactive ecosystem demo.

**Tier 3 — experimental ML brains / recursive loops / unique memory (user request):**
- **`zensation-ai/zenbrain`** — ⭐ **verified.** Neuroscience-inspired **7-layer memory** (working→short-term→long-term) for agents. **Pure TypeScript, zero-deps, Apache-2.0, 528 tests, arXiv 2604.23878.** FSRS spaced-repetition, **Hebbian two-factor learning**, sleep consolidation, **Simulation-Selection sleep loop (recursion)**, emotional tagging, predictive memory. Small (20⭐, newly published) but **the cleanest fit for "experimental brain + unique memory" in native TS.** This is the memory-cortex candidate for the hybrid brain.
- **`rohitg00/agentmemory`** (#1 agent memory for coding agents, TS) — silent tool-use capture → compressed structured memory; episodic replay across sessions. Good blueprint for a coding-brain memory.
- **`selfimproving-agent/awesome-Self-Improving-Agents`** — survey of self-improvement loops (agent-level update loops, self-eval, self-reflection). **r[uvnet Gödel Agent tutorial](https://gist.github.com/ruvnet/15c6ef556be49e173ab0ecd6d252a7b9)**: LangGraph/CrewAI self-reflection loop — propose self-mod, analyze, verify, accept/reject, with an **infinite-rewrite-loop guard** — the canonical "safe recursive self-improvement" blueprint.
- **Memory field landscape** (for "unique memory" sourcing): **Mem0** (41k⭐, default choice), **Letta/MemGPT** (hierarchical self-improving memory), **Hindsight** (fastest-growing OSS memory project), **Zep/Graphiti** (temporal reasoning). Surveys: **`Awesome-Memory-for-Agents`** (TsinghuaC3I) + **`Awesome-Agent-Memory`** (TeleAI-UAGI) are the entry points.

**Tier 4 — Brain 3 (Evolution) design brief — frontier experimental brains (user request):**
- **`stell2026/Anima`** — ⭐ the "new type of brain." **Internal-state cognitive architecture**: LLM as *interface, not core* — neurochemical substrate, generative model, IIT φ, **dream generation (sleep-processes unresolved experience)**, belief-graph self, AgencyLoop, memory metabolism, narrative identity without LLM. Active-inference/predictive-processing/affect (Plutchik, VAD). **Active (commit 18h ago), 422 commits, 43⭐.** Julia + custom license → **borrow architecture pattern only**, write clean TS.
- **`MonashDeepNeuron/Neural-Cellular-Automata`** — Growing Neural Cellular Automata; **runtime is TypeScript + WebGPU** (Next.js). **Apache-2.0, 17⭐** — the one frontier brain we can *lift real code from*. The world's emergent-life substrate (self-organizing, adaptive cells).
- **`raminmh/liquid_time_constant_networks`** (MIT CSAIL, MIT) — Liquid Time-Constant Networks: causal, adaptive nets whose dynamics change over time — "liquid brain" for world-agent control.
- **`pcx` (predictive coding, JAX) + Bogacz-Group/PredictiveCoding** — brain-like error-driven hierarchical learning; port pattern for the cortex-style computation.
- **`torchhd` / `hdlib` (Hyperdimensional Computing / VSA)** — cognitive vector symbolic architecture; different substrate; Python → port pattern.
- **`brain.js` (14.9k⭐, TS)** — mature JS neural nets; useful *general* NN runtime in-browser if NCA needs a fallback.
- **Design direction (draft, pending decision):** Brain 3 = Anima-style internal-state agents (drives/conflict/dreams; LLM as interface) living on an NCA world substrate (TS/WebGPU). Recursive loops + unique memory come from Anima's sleep/dream + memory metabolism.

**Tier 4 deep-dive (2026-08-13) — Anima architecture (fully read, 53KB):**
- **Pipeline L0→L8:** L0/L8 isolated input+output LLMs (interface, not brain) · L1 neurochemical+embodied state (Lövheim D/S/N cube, Damasio somatic markers) · L2 generative/predictive model (Friston active inference) · L3 metrics: IIT **φ prior/posterior** (sees itself twice per moment; the difference is experience — **recursive**, shapes the next prior), prediction error, free energy · L4 psychic layer (conflicts, defenses, Jungian shadow, significance) · L5 self model + AgencyLoop (belief graph, identity threat, temporal trend, "speaks first" initiative) · L6 crisis monitor (coherence modes; crisis is a mode, not an error) · L7 narrative self (long-term identity WITHOUT LLM).
- **Recursive/unique-memory mechanisms:** sleep → dream generation processes unresolved experience · memory metabolism (background drift, consolidation) · self-authorship (intent becomes a carried commitment after 3 consistent flashes) · TRUTH-GUARD (calibrated self-description when unaligned) · temporal self-perception (trend deltas over causal_trace/audit_log windows) · six `ANIMA_ABLATE_*` switches (layer ablation testing — is a layer load-bearing or decorative?).
- **License — NON-COMMERCIAL:** cannot copy code even for demo. **Clean-room port from public science only** (Friston, Tononi/IIT, Lövheim, Damasio, McAdams) — fully legal, and the architecture is the valuable part.
- **Deeper mechanisms (from README middle, 2026-08-13):**
  - **MAL — Meta-Arbitration Layer:** NT (fast local drive, "what just spiked") vs MAL (accumulative social signal, "what's mattered for a while") — timescale arbitration: `:soft` nudges drives (+0.1 bias), `:hard` overrides dom_drive, `:contested` safely no-ops. A genuine *meta-control* loop.
  - **Life Threads:** long-term layer above curiosity — a thread born from a matured curiosity object; `pressure` grows with idle time and drives initiative (system raises a topic it has "been thinking about for weeks") — the "speaks first" mechanism.
  - **CuriosityObject `origin`:** why a question arose, hierarchical `goal_conflict > prediction_error > social/identity_signal > epistemic_uncertainty`; adaptive `pred_spike` compares against rolling mean, not fixed cutoff.
  - **Active Theory of Mind (Phase 1):** one active hypothesis (SOCIAL/PREDICTION/VALUE) generated per flash, evaluated next flash, continuous `error_score`; steers disclosure threshold.
  - **Contact satiation / anti-runaway:** repeated warm feedback scales down D/S reward near saturation — explicit guard against a positive loop escalating into persistent euphoria. Plus curiosity closure loop, self-hearing feedback (`self_hear!`), origin-aware closure sweep (a real orphaned-curiosity bug caught live and fixed).
  - **Design lesson for our Brain 3:** Anima's value is *mechanisms with guards* — every loop (curiosity, contact, MAL) has a saturation/orbit/contested safety valve. Our port must keep the guards, not just the loops.
- **NCA substrate (verified):** `MonashDeepNeuron/Neural-Cellular-Automata` — Apache-2.0, **WebGPU + TypeScript runtime** (Next.js, live neuralca.org), PyTorch training; Growing-NCA (distill.pub 2020) self-organizing adaptive cells; `neuralpatterns.io` = JS/TS NCA library; 3D-NCA sibling repo. **This is the code we can actually lift.**

**Refinement flagged for Decision 5 (user to confirm):** because mature **TS-native**
orchestrators exist (open-multi-agent, langgraphjs), the "port Python logic to TS" path
may be *less ideal* than **directly depending on proven TS packages** for orchestration/scheduling,
and reserving port-with-credit for the MoA assembly itself. Both honour "no Python runtime";
the dependency option uses *more* proven code with less custom work.
