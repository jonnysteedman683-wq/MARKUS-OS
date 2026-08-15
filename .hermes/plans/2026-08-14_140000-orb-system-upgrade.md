# Orb System Upgrade — Comprehensive Implementation Plan (v1.0)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> Plan owner: Jonny · Date: 2026-08-14 · Status: READY (approved brainstorm modules A–E)

**Goal:** Evolve the Orb command deck into a self-improving, memory-first system: durable swarm control (leases), memory compression + stateful agents, a self-evolution loop with human gate, voice upgrades (wake word, speaker identity), and richer visualization — all grounded in researched, MIT/Apache-licensed patterns.

**Architecture:** Everything hangs off the existing `orb_bridge.py` + `the-orb.html` + `orb-sentry.py` trio. New subsystems are additive Python modules in `scripts/` (or `hive-core/`), new endpoints on the bridge, new panels on the orb page. Each module lands with a selftest + headless verification, following the proven watchdog/selftest/error-trap patterns already in the codebase.

**Tech Stack:** Python 3.11 (stdlib-first, uv venvs), existing faster-whisper/OpenCV/ElevenLabs stack, OpenRouter + DeepSeek API keys already in profile, supermemory SDK (venv python), .hive JSON state files.

**Research sources (all MIT/Apache-2.0 — ideas stealable, credited):**
- letta-ai/letta (24k★, Apache-2.0) — stateful agents, memory-driven behavior
- EverMind-AI/Raven (3.5k★, Apache-2.0) — self-improving harness, Evolver eval loops
- aiming-lab/SimpleMem (3.7k★, MIT) — semantic-lossless memory compression
- professorpalmer/Puppetmaster (313★, MIT) — durable-state swarm, SQLite jobs, leases, cost routing (29% lower SWE-bench spend; 91.1% NL2Repo)
- unohee/OpenSwarm (836★, MIT) — cross-agent cognitive memory
- dscripka/openWakeWord (2.6k★, MIT) — local wake word
- elizaOS/eliza (19k★, MIT) — agentic OS patterns

---

## Phase 0 — Foundation (do first, everything depends on it)

### Task 0.1: Harden the bridge against the recurring dual-process bug
**Objective:** Eliminate the stale-bridge race that caused wrong-code serving twice this session.
**Files:**
- Modify: `scripts/orb_bridge.py` (main entry — port bind + PID lock)
- Modify: `scripts/orb_bridge_watchdog.py`

**Step 1:** Add a single-instance guard: bind a second socket (or write a PID file with process check) at startup; if already running, exit with a distinct code (e.g. 75) instead of starting a second listener.
**Step 2:** In the watchdog, before restart: `taskkill` **all** PIDs bound to :8124 (via `netstat -ano`), not just the tracked one.
**Step 3:** Verify: start bridge twice → second exits 75; kill first → watchdog restores exactly one.
**Commit:** `fix: single-instance bridge guard + watchdog kills all stale listeners`

### Task 0.2: Verify all existing endpoints still pass a full regression sweep
**Objective:** Baseline before adding subsystems.
**Files:**
- Test: `scripts/test-bridge-regression.py` (create)

**Step 1:** Write a regression harness hitting: `/health /presence /briefing /heard /usage /status /swarm /hive /registry /memories /voice /palace /` (GET) and POST `/intent /heard /presence /voice /registry`.
**Step 2:** Assert each returns `200` + expected key shape.
**Step 3:** Run with the venv python; all green expected.

### Task 0.3: Shared watchdog + log conventions
**Objective:** One pattern for every long-running piece (bridge, sentry, future workers).
**Files:** Modify `scripts/orb_bridge_watchdog.py`, `scripts/orb_sentry_watchdog.py`

Add a shared `watchdog_lib.py` (probe-http, probe-heartbeat-file, restart-with-scrubbed-env, taskkill-all-on-port). Refactor both watchdogs onto it. Verify: healthy → silent; kill target → restart + alert line.

---

## Module A — Memory as a living brain

### A1. Memory compression & distillation (SimpleMem pattern)

**Goal:** Compress old/near-duplicate supermemory memories into distilled summaries; keep recent verbatim; palace + recall get cleaner/faster.

**Files:**
- Create: `scripts/orb_memory_compress.py` (the distiller)
- Create: `scripts/test_memory_compress.py`
- Modify: `scripts/orb_bridge.py` (expose `POST /memory/compress`, add to `/memory` response)

**Task A1.1 — Compressor core (pure function, TDD)**
- `tokenize(text)` → set of normalized tokens (reuse palace tokenizer logic)
- `similarity(a, b)` → cosine on token sets
- `cluster(memories, threshold=0.55)` → groups of near-duplicates (greedy)
- Tests: identical texts cluster; distinct texts don't; empty input → [].

**Task A1.2 — Distillation writer**
- For each cluster > 1 member: call the chat brain (`chat_complete`) with a system prompt: "Compress these N memory fragments into one 2-3 sentence distillation preserving facts." → produces `[ORB-DISTILL] <summary>`.
- Mark originals `kind:"raw-archived"` via supermemory metadata update (or a local `.hive/memory_archive.json` index — prefer local index to avoid mutating cloud unexpectedly).
- Idempotent: never distills the same fingerprint twice (index by cluster signature).
- Tests (mock brain): cluster of 3 → 1 distill + 3 archived; re-run → no-op.

**Task A1.3 — Wire into bridge + palace**
- `POST /memory/compress` (protected: dry-run default, `?apply=1` to write).
- `/memory` response gains `archived_count`, `distills`.
- Palace (`memory-palace.html`) renders distill nodes in a distinct hue + a "compressed from N" badge; the sidebar shows distills pinned on top.
- Verify: run compress on the 124-memory corpus → expect ~30-40% reduction in visible raw nodes.

### A2. Memory-first self-improvement (Raven pattern)

**Goal:** The orb proposes next actions *from memory* (patterns it notices), human approves.

**Files:**
- Create: `scripts/orb_reflection.py` (periodic reflection → proposals)
- Modify: `scripts/orb_bridge.py` (`GET /proposals`, `POST /proposals/{id}/apply`)
- Modify: `the-orb.html` (proposals panel in cortex)

**Task A2.1 — Reflection worker (cron 24h, no_agent)**
- Pulls recent memory (last 7d), intent history, swarm outcomes.
- Calls brain: "Given these patterns, propose 1-3 concrete system improvements."
- Writes `.hive/proposals.json` `[{id, text, source_memories, created_at, status:proposed}]`.
- Tests: with fixture memory → valid proposals JSON; empty memory → empty list (no hallucinated busywork).

**Task A2.2 — Orb proposals UI**
- Cortex gains "proposals" tab: list with [apply] [dismiss] per item.
- Apply = dispatch as intent (`/intent`) so the swarm executes it (human-gated by construction — the orb proposes, you apply).

### A3. Stateful agent core (letta pattern, trimmed)

**Goal:** The orb has a persistent "self" (thread state) beyond stateless memory injection.

**Files:**
- Create: `scripts/orb_state.py` — `.hive/orb_state.json`: `{self_summary, active_goal, mood, last_cycles, decided_facts[]}`
- Modify: `scripts/orb_bridge.py` — load orb_state into system prompt context; save notable outcomes after each /voice + /chat.

**Task A3.1 — State schema + read/write**
- `load_state()` / `save_state()` with atomic write (tmp+rename, same as registry save).
- Fields: `self_summary` (1-line), `active_goal` (from milestones), `decided_facts` (last 20 "we decided X" facts), `updated_at`.

**Task A3.2 — Inject + persist**
- chat_complete prepends a `SELF STATE` block (compact) to the system prompt.
- After each exchange where the reply contains a decision/plan, extract a `decided_fact` (regex + brain-assisted) and append.
- Tests: state survives restart; decided_fact dedupes.

---

## Module B — Swarm control plane

### B1. Durable leases (Puppetmaster pattern) — fixes the 6 heartbeat alerts

**Goal:** Agents check out intents with a lease (TTL); expiry → requeue. Kills orphaned `swarm-agent-*` dirs.

**Files:**
- Create: `scripts/orb_leases.py` — `.hive/leases.json`
- Modify: `scripts/hive-swarm.py` (checkout/checkin at agent spawn/complete)
- Modify: `scripts/swarm-heartbeat.py` (report stale leases → alert only after lease expiry, not immediately)

**Task B1.1 — Lease primitives (TDD)**
- `acquire(intent_fp, agent_id, ttl=90min)` → lease record; `release(fp)`; `expired_leases()`; `requeue_expired()`.
- Lock via file lock (atomic create). Tests: acquire/release cycle; expiry math; double-acquire rejected.

**Task B1.2 — Swarm integration**
- On agent spawn: `acquire`. On success/failure completion: `release`.
- Post-cycle: `requeue_expired()` — expired intents go back to `queued` in intents.json.
- Verify: run one swarm cycle; confirm leases file populated + released; heartbeat alert count drops (stale dirs only flagged post-expiry).

**Task B1.3 — Orb registry shows leases**
- `/registry` response gains per-swarm `active_leases`, `expired_leases`.
- Registry panel: small lease line per swarm.

### B2. Cross-agent cognitive memory (OpenSwarm pattern)

**Goal:** Agents persist learnings between cycles (survive worktree teardown).

**Files:**
- Modify: `scripts/orb_memory.py` or new `scripts/orb_agent_memory.py` — `.hive/agent_memory.json`
- Modify: `scripts/hive-swarm.py` — agents read agent_memory in warmup, write back post-task.

**Task B2.1 — Agent memory store**
- `add_agent_learning(repo, agent_id, text)`, `recall(repo, query, k=5)` (token-cosine, same as palace).
- Cap: 500 entries, LRU eviction.

**Task B2.2 — Wire into agent lifecycle**
- WARMUP prompt includes `AGENT MEMORY: <top 3 for repo>`.
- Post-task: extract "what I learned about this repo" from the agent's diff + summary → `add_agent_learning`.
- Verify over 2 cycles: cycle-2 agent sees cycle-1 learning (grep agent log).

---

## Module C — Voice upgrades

### C1. Local wake word (OpenWakeWord pattern) — optional always-transcribe alternative

**Goal:** Toggle: always-transcribe (current) OR wake-word gated (battery/privacy). Both keep "orb" trigger as command filter.

**Files:**
- Create: `scripts/orb_wakeword.py` — wraps OpenWakeWord (`pip install openwakeword`, MIT)
- Modify: `scripts/orb-sentry.py` — mode flag `--wake`; when on, audio chunks go through wake detector first; only post-wake chunks transcribe.

**Task C1.1 — Wake detector wrapper**
- `WakeDetector()` loads `hey_jarvis`/custom model; `is_wake(chunk)` bool.
- Graceful: model missing → falls back to always-transcribe + warn.
- Tests: silence → false; synthetic noise → false (no false-positive spam).

**Task C1.2 — Sentry mode integration**
- `--wake` flag → gated path; tray toggle switches mode live.
- Verify: with wake on, non-wake speech produces zero `/voice` calls (log check).

### C2. Speaker identity (voice biometrics)

**Goal:** Sentry only acts on YOUR voice (presence + identity).

**Files:**
- Create: `scripts/orb_speaker.py` — resemblyzer-class embedding + cosine threshold
- Modify: `scripts/orb-sentry.py` — enroll (first 10s of "orb" triggers = your voice), verify on each trigger.

**Task C2.1 — Embedding wrapper**
- `enroll(audio)` → speaker vector; `match(audio, enrolled, thr=0.75)` → bool.
- Persist enrolled vector to `.hive/speaker.json`.
- Graceful: no enrollment → act on anyone (opt-in feature).

**Task C2.2 — Sentry integration**
- On each `orb` trigger: verify voice; mismatch → log "unknown speaker ignored", no /voice call.
- Tray toggle: "voice-lock on/off".

---

## Module D — Self-evolution (the thesis)

### D1. Improvement proposal loop (Raven Evolver pattern)

**Goal:** After each swarm cycle, an agent writes "what should change about the system" → registry → human approves → applied. Concrete self-evolution with a human gate.

**Files:**
- Create: `scripts/orb_evolver.py` — runs post-cycle (cron or hive-swarm hook)
- Modify: `.hive/registry` or `.hive/proposals.json` (reuse A2.1 file)
- Create: `scripts/orb_evolver_apply.py` — applies approved proposals (config/roster/prompt edits)

**Task D1.1 — Evolver worker (post-cycle)**
- Inputs: last cycle quality deltas, intents resolved, agent memory, heartbeat alerts.
- Brain call: "Propose 1-3 concrete, verifiable system improvements. For each: change, file, expected effect, how to verify."
- Output → proposals.json `{status: proposed, category: config|roster|prompt|tooling, apply_plan}`.
- Tests: fixture cycle data → proposals with required fields; no data → no proposals.

**Task D1.2 — Apply engine**
- For approved proposals: apply only the **safe categories** automatically (config values, roster swaps, prompt wording) via targeted patches; **never** refactors or AGENTS.md changes without re-approval.
- Every apply writes to `.hive/evolution_log.md` (what, when, why, verification result).
- Tests: apply a roster proposal → roster file changes + log entry; apply is idempotent.

### D2. Skill self-creation

**Goal:** When the orb solves a novel multi-step problem, it writes a reusable skill.

**Files:**
- Create: `scripts/orb_skillsmith.py`
- Modify: `scripts/orb_bridge.py` (`POST /skill/create`)

**Task D2.1 — Skillsmith worker**
- Trigger: after a /voice or /chat exchange that produced ≥5 tool calls / ≥3 distinct steps and a positive outcome.
- Generates a SKILL.md (frontmatter + steps) in the orb's skills dir, credited "generated by orb".
- Human reviews before activation (written to `skills-pending/`, moved on approval).
- Tests: fixture conversation → valid SKILL.md frontmatter; short chat → no trigger.

---

## Module E — Interface & visualization

### E1. Memory time-lapse (nocturne snapshot/diff pattern)

**Goal:** Palace rewind/forward through memory creation.

**Files:**
- Modify: `memory-palace.html` (timeline scrubber)
- Modify: `scripts/orb_bridge.py` (`/memory/timeline` — memories bucketed by day)

**Task E1.1 — Timeline endpoint**
- Group memories by date; return `[{day, count, samples[]}]`.
- Tests: fixture dates → correct buckets.

**Task E1.2 — Palace scrubber**
- A timeline slider: scrub → nodes fade in by date; play button auto-advances.
- Verify: headless screenshot at t=0 vs t=max shows different node counts.

### E2. Presence → registry lifecycle (from approved voice design, unbuilt)

**Goal:** Away = swarm pauses heavy work; present = resumes.

**Files:**
- Modify: `scripts/orb_bridge.py` — on presence absent→present edges, set registry statuses (pause heavy swarms when away > 5min, resume on return)
- Modify: `scripts/hive-swarm.py` — honor `paused` registry status (skip cycle)
- Modify: `the-orb.html` — briefing card notes "swarm paused while you were away / resumed on return"

**Task E2.1 — Registry pause/resume on presence**
- In `set_presence`: absent + away_minutes ≥ 5 → registry set-status `paused` (all swarms); present → `active`.
- Guard: never pause if a cycle is mid-flight (check leases).
- Tests: simulated absent→paused; present→active; mid-flight guard holds.

**Task E2.2 — Swarm honors paused**
- `hive-swarm.py` main loop: if registry status `paused` → log + exit 0 without spawning.
- Verify: registry paused → manual cycle run does nothing (log line proves).

---

## Phase Z — Integration + battle-testing

### Task Z.1: Full regression (all modules)
- Run `test-bridge-regression.py` + every module's test file + the existing swarm integration tests.
- Expected: all green.

### Task Z.2: Two full swarm cycles with all modules live
- Cycle 1: leases acquired/released; agent memory written; evolver proposes (or not); presence pauses if applicable.
- Cycle 2: agent memory recalled; improvements visible in warmup prompts.
- Verify heartbeat alert count **drops** (stale dirs now lease-managed).

### Task Z.3: Headless visual sweep
- `?hud=1`, `?capsule=1`, palace timeline, cortex proposals tab, registry leases — all screenshot-verified, zero error-trap entries.

### Task Z.4: Update docs + memory
- Update `HERMES UPGRADE/orb-voice-presence-design.md` or new `orb-system-architecture.md` with all modules.
- Update persistent memory: modules, endpoints, cron ids.

---

## Risks / tradeoffs / open questions

- **Cost:** A1/A2/D1 add brain calls (compression, reflection, evolution). Budget: A1 ≈ 1 call/cluster, A2/D1 ≈ 1-3 calls/day. Acceptable at flash/gemma tier; monitor via existing `/usage`.
- **Cloud mutation:** A1 archives via **local index**, never deletes cloud memories without explicit `?apply=1`. Supermemory skill's forget≠delete rule respected.
- **Puppetmaster scale:** we adopt its *patterns* (leases, SQLite-style durable state), not the full framework — our swarm already exists.
- **Wake word (C1):** reverses the earlier always-transcribe decision *as an option*, not a replacement. Both modes supported.
- **Speaker ID (C2):** enrollment is sensitive (your voice vector is biometric). Stored locally only; opt-in; revocable.
- **Self-evolution safety (D1/D2):** hard human gate on apply; refactors and AGENTS.md edits always require re-approval. Never self-modifies the evolver.
- **Open question:** should E2 pause *all* swarms or only heavy-budget ones? Default: all, with a `presence_sensitive: true` per-swarm flag later.

## Execution order (recommended)
0.1 → 0.2 → 0.3 → **B1** (fixes alerts) → **E2** (cheap, ties voice in) → **A1** (cleans memory) → **A3** → **B2** → **A2** → **D1** → **D2** → **E1** → **C1** → **C2** → Phase Z.

> The user's planned **"hacking ability"** (advanced) will slot in as **Module F** — designed as an isolated subsystem with its own endpoint namespace (`/hack/*`), a hard consent gate, and no changes to existing modules; the Phase 0 single-instance + regression baseline keeps the surface clean for it.
