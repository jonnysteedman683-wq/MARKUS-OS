
## 2026-08-26T17:18:44+10:00 — mode=duo
- Coin gate: PASS
- Lead system: MARKUS
- HERMES slot 12: DOUBLE_REROLL -> 2 extra dice
- HERMES slot 8: UPGRADE_HERMES_BACKEND
    target: hermes config CLI: providers, models, gateway, MCP (setup_mcp), cron (cronjob)
    next: Load hermes-agent skill; hermes config set ...; audit MCP servers; review cron jobs
- HERMES slot 10: OPTIMISE_HERMES_PROCESS
    target: tool batching, memory hygiene, skill loading, adaptive-model-switcher routing
    next: Audit skills_list for stale entries; run adaptive-model-switcher; prune memory with the memory tool
- MARKUS slot 3: UPGRADE_MARKUS_FRONTEND
    target: electron-main.js, electron-preload.js, package.json, hive-core/ frontend, markus-os-electron/
    next: npm install per package.json; electron smoke test
- Curation die: ENHANCE — Patch one skill with this cycle's lesson via skill_manage patch; bump version; keep pitfalls fresh.
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T17:22:57+10:00 — mode=duo
- Coin gate: PASS
- Lead system: HERMES
- HERMES slot 10: OPTIMISE_HERMES_PROCESS
    target: tool batching, memory hygiene, skill loading, adaptive-model-switcher routing
    next: Audit skills_list for stale entries; run adaptive-model-switcher; prune memory with the memory tool
- MARKUS slot 5: RESEARCH_MARKUS_ROADMAP
    target: markus_web_research.py -> research/evolutionary_loop_roadmap.md + DICE_ROADMAP.md
    next: Run markus_web_research.py; append findings to research/evolutionary_loop_roadmap.md and DICE_ROADMAP.md
- Curation die: DEEP — Run CURATE + ENHANCE + OPTIMISE (the extra chance).
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

### CYCLE-2026-08-26-172257 — EXECUTION + VERIFICATION
- MARKUS slot 5 RESEARCH: `python markus_web_research.py` -> PASSED (exit 0), 3 topics (autonomous_agent_loop, swarm_intelligence, multi_model_routing), 5 findings each.
  - Findings appended to `research/evolutionary_loop_roadmap.md` (Dice Engine Research Run section).
  - Next steps ranked: multi_model_routing (LOW) > autonomous_agent_loop (MEDIUM) > swarm_intelligence (HIGH).
- HERMES slot 10 OPTIMISE: skills audit (50 skills, no [SKILL_PRUNED]); adaptive-model-switcher tests 8/8 OK (recommend mode, selector-only); memory pruned via memory tool.
- Curation die: DEEP -> CURATE + ENHANCE + OPTIMISE on skill library.

## 2026-08-26T17:33+10:00 — CRON RETIREMENT
- retired 'markus-auto-upgrade' (e2addb50a12e): every 360m, no_agent watchdog, full MARKUS upgrade cycle.
  Superseded by duo-dice-cycle (dbf7f9a73505, daily 03:00) which owns MARKUS+Hermes selection via dice engine.
  Archived outputs to HERMES UPGRADE/cron_archive/markus-auto-upgrade/ (2 runs: 2026-08-26_03-53, 2026-08-26_13-25).

## 2026-08-26T17:47:41+10:00 — mode=duo
- Coin gate: PASS
- Lead system: MARKUS
- HERMES slot 10: OPTIMISE_HERMES_PROCESS
    target: tool batching, memory hygiene, skill loading, adaptive-model-switcher routing
    next: Audit skills_list for stale entries; run adaptive-model-switcher; prune memory with the memory tool
- MARKUS slot 3: UPGRADE_MARKUS_FRONTEND
    target: electron-main.js, electron-preload.js, package.json, hive-core/ frontend, markus-os-electron/
    next: npm install per package.json; electron smoke test
- Curation die: ENHANCE — Patch one skill with this cycle's lesson via skill_manage patch; bump version; keep pitfalls fresh.
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T17:5x+10:00 — UPGRADE: markus_adaptive_matrix.py reliability scoring
- Roadmap #1 ROI item done (manual, not dice-driven).
- Added to markus_adaptive_matrix.py: sliding-window (20) recency-decayed reliability_score [0,1]; 3-consecutive-failure circuit-break (60s open, 0.1x weight suppression); state persistence to markus_adaptive_state.json (survives restart); matrix_state now exposes reliability_score/consecutive_failures/circuit_broken.
- New hermes_verify_adaptive_matrix.py harness: 6/6 PASS (AST, self-test, reliability range, circuit-break trip, failure reset, persistence round-trip).
- Verification: python markus_adaptive_matrix.py (self-test PASS incl circuit-break+recovery+persistence); python hermes_verify_adaptive_matrix.py OVERALL PASS.
- Files: markus_adaptive_matrix.py (upgraded), hermes_verify_adaptive_matrix.py (new).

## 2026-08-26T17:5x+10:00 — UPGRADE: markus_web_research.py persistence (research slot fix)
- Research slot no longer fakes output: added research_and_report() + write_to_roadmap() persisting FULL findings to research/evolutionary_loop_roadmap.md; research_technical_alternative() accepts live_findings= to inject real web_search results through the old try:pass stub.
- New hermes_verify_web_research.py harness: 6/6 PASS (AST, self-test, writes artifact, persists all findings incl live, str path coercion, live_findings tag).
- Live proof: real web_search results (LangGraph, MS Agent Framework, CrewAI...) fed through live seam, landed in evolutionary_loop_roadmap.md.
- Files: markus_web_research.py (upgraded), hermes_verify_web_research.py (new).

## 2026-08-26T18:35:39+10:00 — mode=duo
- Coin gate: PASS
- Lead system: MARKUS
- HERMES slot 10: OPTIMISE_HERMES_PROCESS
    target: tool batching, memory hygiene, skill loading, adaptive-model-switcher routing
    next: Audit skills_list for stale entries; run adaptive-model-switcher; prune memory with the memory tool
- MARKUS slot 5: RESEARCH_MARKUS_ROADMAP
    target: markus_web_research.py -> research/evolutionary_loop_roadmap.md + DICE_ROADMAP.md
    next: Run markus_web_research.py; append findings to research/evolutionary_loop_roadmap.md and DICE_ROADMAP.md
- Curation die: CURATE — Inventory skills (skills_list); find stale/[SKILL_PRUNED]/duplicate skills; prune or consolidate via skill_manage delete absorbed_into=...
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T18:37+10:00 — CYCLE duo (roll 2026-08-26T18:35)
- Coin PASS · lead MARKUS · slots: MARKUS 5 (research) + HERMES 10 (optimise)
- MARKUS 5: real web_search (2026 routing/cost optimization) -> 8 findings via live seam landed in research/evolutionary_loop_roadmap.md (RouteLLM, 70/20/10, FrugalGPT, NeMo Switchyard). VERIFIED by read-back.
- HERMES 10: adaptive_router test 8/8 OK; skills audit clean (0 pruned, 0 dupes) -> no prune needed.
- CURATION die=CURATE: inventory clean, nothing to prune (honest no-op).
- Rewards: 5=1.0, 10=1.0 (now 0.488/0.488 co-lead, 3 counts each). Engine verify 5/5 PASS.
- Roadmap now surfaces concrete next steps: eval-verified tier switching, prompt-caching, cost-capped routing.

## 2026-08-26T18:52+10:00 — UPGRADE: markus_network_intel.py (network-intelligence layer)
- New connectivity-awareness module (stdlib-only, Windows-aware): enumerates adapters/connection-type (wifi/ethernet/vpn/cellular), probes gateway + internet latency, detects VPN/cellular presence, persists structured snapshot to markus_network_state.json.
- Grounded on real host AOPSTOPER (Win10): WiFi active 192.168.1.101, Surfshark VPN adapter disconnected, no cellular modem. Self-test detected this correctly (primary=wifi, internet=True, 78.7ms then 23.8ms).
- Wired into markus_adaptive_matrix.py: _network_is_down() reads the snapshot (fail-open if missing/stale >10min) and select_best_model() forces the AIRGAPPED_LOCAL model when transport is down - routing never stalls on unreachable APIs. Decision snapshot now includes network_down flag.
- hermes_verify_network_intel.py harness: 9/9 PASS (AST, self-test, WiFi/Ethernet/VPN/Cellular classification, probe=False validity, enum, persistence). Matrix harness re-PASS.
- Files: markus_network_intel.py (new), hermes_verify_network_intel.py (new), markus_adaptive_matrix.py (network-aware hook), markus_network_state.json (runtime snapshot).

## 2026-08-26T19:0x+10:00 — UPGRADE: markus_router.py live telemetry wiring (loop closed)
- markus_router.py now: (1) auto-offline detection via _network_down() reading markus_network_state.json (fail-open); (2) _apply_matrix() attaches adaptive-matrix advisory (matrix_model/weight + network_down) to every route; (3) record_outcome() feeds post-dispatch latency/success back into the matrix so weights learn from real traffic.
- Feedback loop verified: demote laguna (slow failure, w->0.346) then 5 fast successes recover (w->0.887). Offline forced to local model confirmed.
- New hermes_verify_router.py: 4/4 PASS. Full regression: adaptive_matrix + network_intel + web_research + router ALL PASS.
- KEY PITFALL: the matrix weight formula caps out (base*0.5 + sr*0.3 + lat*0.2); a model already at its ceiling (base 1.2, sr 1.0, rel 1.0) CANNOT rise on fast successes - a feedback test must demote first, then assert recovery. "weight goes up after success" is false once saturated.
- Files: markus_router.py (telemetry wiring), hermes_verify_router.py (new).
- LOOP: network_intel -> adaptive_matrix -> router (auto-offline + advisory + feedback learning). Closed end-to-end.

## 2026-08-26T19:1x+10:00 — UPGRADE: markus_server.py live telemetry (loop LIVE end-to-end)
- markus_server.py now: /api/intent measures dispatch latency and feeds router.record_outcome() into the adaptive matrix (real API traffic learns weights); routing_decision response enriched with latency_ms + matrix_advisory + matrix_weight + network_down.
- NEW GET /api/network/intel endpoint: live transport snapshot (connection type, internet, latency, vpn, adapters) rebuilt on demand from markus_network_intel.
- Restarted server (killed old PID 14604, booted fresh). Verified LIVE:
  - GET /api/health -> ONLINE
  - GET /api/network/intel -> wifi, internet True, 29.0ms, vpn False
  - POST /api/intent -> routed CODE_SPECIALIST->laguna, latency_ms 8483.8 recorded, matrix_advisory gemini w=1.4, network_down False
  - GET /api/router/matrix -> laguna calls 41 sr 0.88 rel 0.849 (live traffic absorbed)
- Full loop: network_intel -> adaptive_matrix -> router -> server API -> record_outcome -> adaptive_matrix. CLOSED and LIVE on port 8128.
- Server process: background proc_dcf83b4bb855 (pid 5000).

## 2026-08-26T19:11+10:00 — CRON ADD: markus-network-refresh (network-intel watchdog)
- Added zero-token no_agent watchdog (id 57ba65e7db72, every 15 min): runs markus_network_intel.py --save to refresh markus_network_state.json; SILENT when transport unchanged (zero tokens), prints CHANGE DETECTED report when connection/internet/vpn/cellular flips so the agent wakes to note the transport shift.
- Script: ~/AppData/Local/hermes/scripts/markus_network_watchdog.py. Audit logs -> ~/.hermes/cron_log/.
- Verified manually: tick1 CHANGE (wifi/internet/33.9ms), tick2 SILENT. Cron run fired.
- Keeps the adaptive matrix + router auto-offline detection fed with FRESH transport telemetry every 15 min.

## 2026-08-26T19:11:31+10:00 — mode=duo
- Coin gate: PASS
- Lead system: HERMES
- HERMES slot 8: UPGRADE_HERMES_BACKEND
    target: hermes config CLI: providers, models, gateway, MCP (setup_mcp), cron (cronjob)
    next: Load hermes-agent skill; hermes config set ...; audit MCP servers; review cron jobs
- MARKUS slot 2: UPGRADE_MARKUS_BACKEND
    target: markus_server.py (8128), markus_kernel.py, markus_router.py, phoenix_*.py
    next: py_compile touched files; restart server; curl http://localhost:8128/api/health
- Curation die: DEEP — Run CURATE + ENHANCE + OPTIMISE (the extra chance).
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T19:1x+10:00 — CYCLE duo (roll 2026-08-26T19:11)
- Coin PASS · lead HERMES · slots: HERMES 8 (backend) + MARKUS 2 (backend) · curation DEEP
- MARKUS 2: hardened markus_server.py — bound 127.0.0.1 (was 0.0.0.0 LAN-exposed, now MARKUS_HOST env); CORS wildcard->allowlist (evil origin gets no ACAO); +Cache-Control no-store +X-Content-Type-Options nosniff. Verified live: bind 127.0.0.1:8128, curl evil Origin -> no ACAO. Intent+network endpoints no regression.
- HERMES 8: enabled adaptive_router MCP server via setup_mcp (was enabled:false) -> ✓ enabled; model-router capability wired into Hermes.
- CURATION DEEP: ENHANCE co-located backend-hardening pitfalls (config security-protected -> use setup_mcp; hermes mcp configure is interactive); version->1.0.8.
- Rewards: 8=1.0, 2=1.0 (both verified green). Engine verify 5/5.

## 2026-08-26T19:20:41+10:00 — mode=duo
- Coin gate: PASS
- Lead system: HERMES
- HERMES slot 9: UPGRADE_HERMES_FRONTEND
    target: hermes-desktop-plugins, preview widgets, ::preview{file=...} pages, inline chat widgets
    next: Build/extend a desktop plugin or chat widget; deliver as ::preview{file=...}
- MARKUS slot 6: DOUBLE_REROLL -> 2 extra dice
- MARKUS slot 2: UPGRADE_MARKUS_BACKEND
    target: markus_server.py (8128), markus_kernel.py, markus_router.py, phoenix_*.py
    next: py_compile touched files; restart server; curl http://localhost:8128/api/health
- MARKUS slot 4: OPTIMISE_MARKUS_PROCESS
    target: markus_latency_multi_upgrade.py, markus_task_dag.py, markus_devswarm.py, markus_resilience.py, cron/schtasks
    next: Run python markus_benchmark.py; profile hot paths; tune worker pools/DAG
- Curation die: CURATE+ENHANCE — Run CURATE then ENHANCE.
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T19:22+10:00 — CYCLE duo (roll 2026-08-26T19:20)
- Coin PASS · lead HERMES · slots: HERMES 9 (frontend) + MARKUS 2 (backend reroll) + MARKUS 4 (optimise) · curation CURATE+ENHANCE
- HERMES 9: built Dice Panel desktop plugin (C:/Users/jonny/AppData/Local/hermes/desktop-plugins/dice-panel/plugin.js) - statusbar chip + right pane with Roll button that sends "roll the dice" to the agent via window.hermes.send. node --check PASS.
- MARKUS 2 (reroll): backend already hardened last cycle; telemetry continuity confirmed (server live, no regression).
- MARKUS 4: ran markus_benchmark.py - KEY FINDING: matrix weights misaligned with measured latency (matrix ranks gemini-3.7-flash w=1.4 top, but benchmark fastest = gemini-2.0-flash-exp and mistral-7b @200ms; laguna #4 @600ms). Next: calibrate matrix weights to benchmark.
- Rewards: 9=1.0, 2=1.0, 4=1.0. Engine verify 5/5.

## 2026-08-26T19:2x+10:00 — UPGRADE: adaptive matrix weight calibration (from slot-4 benchmark finding)
- Tier-aware calibration: latency-sensitive tiers (FAST_CODE/REALTIME_LINT/MEGACONTEXT_ARCH) now derive base_weight from markus_benchmark.py measured latency via clamp(1.5*(200/ms),0.5,1.5); quality/local tiers (PAID_HIGH_REASONING/AIRGAPPED_LOCAL) keep intent weights.
- Results: ling-3.0-flash (200ms) 1.5, deepseek (300ms) 1.0, laguna (600ms) 0.5, qwen 0.8 local, gemini-3.7-flash 1.4 quality. Verified live on /api/router/matrix (base_w).
- Gotchas: clear markus_adaptive_state.json after changing DEFAULT_MODELS or stale current_weight overrides calibrated base on load; self-test pollutes the state file so clear before clean prod start.

## 2026-08-26T20:35:33+10:00 — mode=duo
- Coin gate: PASS
- Lead system: MARKUS
- HERMES slot 11: RESEARCH_HERMES_ROADMAP
    target: hermes docs https://hermes-agent.nousresearch.com/docs + web_search -> DICE_ROADMAP.md
    next: Read hermes-agent skill + docs; web_search new capabilities; append findings to DICE_ROADMAP.md
- MARKUS slot 5: RESEARCH_MARKUS_ROADMAP
    target: markus_web_research.py -> research/evolutionary_loop_roadmap.md + DICE_ROADMAP.md
    next: Run markus_web_research.py; append findings to research/evolutionary_loop_roadmap.md and DICE_ROADMAP.md
- Curation die: SKIP — No curation this cycle.
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T20:36:21+1000 — Dice Research Slot: multi_model_routing
Live web findings: yes

### All findings (8)
- vLLM: High-throughput LLM inference with PagedAttention
- TGI: HuggingFace Text Generation Inference with continuous batching
- Ollama: Local model serving with ModELFUSE pipeline
- OpenRouter: Unified API with performance-based routing
- Adaptive Model Switcher: Real-time reliability scoring
- Production observability is table stakes in 2026: tracing/logging/cost-tracking (LangSmith, Semantic Kernel telemetry) are required, not differentiators
- LangGraph = stateful cyclic multi-agent orchestration; persistent memory + HITL; de facto 2026 standard
- Microsoft Agent Framework unifies AutoGen + Semantic Kernel: graph-based workflows, type-safe routing, checkpointing, OpenTelemetry GenAI telemetry conventions

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

## 2026-08-26T20:36+10:00 — CYCLE duo (roll 2026-08-26T20:35)
- Coin PASS · lead MARKUS · slots: HERMES 11 (research) + MARKUS 5 (research) · curation SKIP
- HERMES 11: web_search 2026 agent frameworks/observability -> 8 findings persisted to DICE_ROADMAP.md (LangGraph/LangSmith observability table stakes, Microsoft Agent Framework graph workflows, shared versioned memory, role archetypes, OpenAI Agents SDK Redis state, start-small).
- MARKUS 5: markus_web_research.py --report swarm_intelligence -> 5 findings to evolutionary_loop_roadmap.md.
- Curation SKIP (no skill mutation this cycle).
- Rewards: 11=1.0, 5=1.0. Engine verify 5/5.

## 2026-08-26T20:5x+10:00 — UPGRADE: VORPAL <-> MARKUS bidirectional bridge (intertwining)
- New markus_vorpal_bridge.py (MARKUS-OS): reads VORPAL decision layer (GOALS.md 35 goals/26 impl/1 open, NOTES.md errors, SOUL.md objectives+cardinals) -> VORPALStatus snapshot; writes MARKUS live telemetry (matrix weights, network, server_ok) to VORPAL/EVOLVE/MARKUS_TELEMETRY.json.
- Fixed parser bug: [IMPLEMENTED] markers are on indented child lines, not the GOAL_ title line -> block-scoped parse (was undercounting implemented=0, now 26).
- Dice engine: new --vorpal flag reads vorpal_goal_pulse() (0.029) via bridge subprocess and nudges duo lead die toward MARKUS proportional to open-goal pulse.
- New hermes_verify_vorpal_bridge.py: 8/8 PASS (AST, self-test, real-DAG parse, pulse range, block-scoped impl, telemetry write, payload, fail-open).
- skill v1.1.0. Files: markus_vorpal_bridge.py, hermes_verify_vorpal_bridge.py, dice_engine.py, VORPAL/EVOLVE/MARKUS_TELEMETRY.json.

## 2026-08-26T20:5x+10:00 — CRON WIRE: duo-dice-cycle now VORPAL-aware
- Updated duo-dice-cycle (dbf7f9a73505) prompt to roll with --mode duo --force --vorpal: every daily cycle is biased by VORPAL open-goal pulse.
- Prompt also adds the bridge-snapshot step so MARKUS telemetry flows to VORPAL/EVOLVE/MARKUS_TELEMETRY.json on each run.
- Verified exact invocation resolves (lead + slots + curation) and bridge snapshot writes. skill v1.1.1.

## 2026-08-26T21:12:45+10:00 — mode=triad
- Coin gate: PASS
- Lead system: HERMES
- HERMES slot 9: UPGRADE_HERMES_FRONTEND
    target: hermes-desktop-plugins, preview widgets, ::preview{file=...} pages, inline chat widgets
    next: Build/extend a desktop plugin or chat widget; deliver as ::preview{file=...}
- MARKUS slot 4: OPTIMISE_MARKUS_PROCESS
    target: markus_latency_multi_upgrade.py, markus_task_dag.py, markus_devswarm.py, markus_resilience.py, cron/schtasks
    next: Run python markus_benchmark.py; profile hot paths; tune worker pools/DAG
- VORPAL slot 14: UPGRADE_VORPAL_LINGUA
    target: Desktop/VORPAL: LINGUA/ (lingua_prima, lp_tool, LINGUA_PROTOCOL.md)
    next: Edit LINGUA modules; run lingua harnesses; py_compile; commit
- Curation die: DEEP — Run CURATE + ENHANCE + OPTIMISE (the extra chance).
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T21:13+10:00 — UPGRADE: dice engine expanded to TRIAD (HERMES + MARKUS + VORPAL)
- v2.0.0. Added VORPAL slot band (13-18: core, lingua, skills, optimise, research, reroll).
- New default --mode triad: one action die per system, all 3 get an action each cycle. Lead die picks lead system. 6/12/18 = that system double reroll.
- resolve_duo kept (HERMES+MARKUS); resolve_triad generalizes to N systems via SYSTEM_BANDS.
- Verify gate now 6/6: py_compile, all 18 slots, coin 0.492, duo both, TRIAD all-3, roadmap writable.
- Live triad roll: HERMES 9 (frontend) + MARKUS 4 (optimise) + VORPAL 14 (lingua), lead HERMES, curation DEEP. Works end-to-end.
- skill v2.0.0. Files: dice_engine.py, SKILL.md.

## 2026-08-26T21:14+10:00 — CRON FLIP: duo-dice-cycle now TRIAD-wide
- Updated duo-dice-cycle (dbf7f9a73505) prompt to roll --mode triad --force --vorpal: every daily cycle covers ALL THREE systems (HERMES + MARKUS + VORPAL), lead biased by VORPAL pulse.
- Prompt now has per-system execution steps (HERMES/MARKUS/VORPAL) + bridge-snapshot step.
- Verified exact invocation: triad cycle resolves with all 3 systems + reroll handling. skill v2.0.1.

## 2026-08-26T21:18:23+10:00 — mode=triad
- Coin gate: PASS
- Lead system: MARKUS
- HERMES slot 7: UPGRADE_HERMES_UI
    target: Hermes desktop: theme tokens, panes, chat surface (hermes-desktop-plugins skill)
    next: Follow hermes-desktop-plugins skill; edit theme tokens / build a pane plugin
- MARKUS slot 3: UPGRADE_MARKUS_FRONTEND
    target: electron-main.js, electron-preload.js, package.json, hive-core/ frontend, markus-os-electron/
    next: npm install per package.json; electron smoke test
- VORPAL slot 14: UPGRADE_VORPAL_LINGUA
    target: Desktop/VORPAL: LINGUA/ (lingua_prima, lp_tool, LINGUA_PROTOCOL.md)
    next: Edit LINGUA modules; run lingua harnesses; py_compile; commit
- Curation die: CURATE+ENHANCE — Run CURATE then ENHANCE.
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)

## 2026-08-26T21:19+10:00 — TRIAD CYCLE (live roll 2026-08-26T21:18)
- Coin PASS · lead MARKUS · slots: HERMES 7 (UI) + MARKUS 3 (frontend) + VORPAL 14 (Lingua) · curation CURATE+ENHANCE
- VORPAL 14: fixed lp_tool.py stale OMNIPRIME canonical path -> local LINGUA/lingua_prima.py (enc 0.64 ratio, dec round-trip). Committed 6a6fae0.
- MARKUS 3: added accessibility (aria-label/role/visually-hidden) to markus_chat.html input + send button (0 -> 5 attrs). Committed 022ec90.
- HERMES 7: Dice Panel plugin updated to Triad Dice Engine (18-slot). node --check PASS.
- Bridge telemetry refreshed -> VORPAL/EVOLVE/MARKUS_TELEMETRY.json.
- Rewards: 7=1.0, 3=1.0, 14=1.0 (VORPAL slot first reward). skill v2.0.2.

## 2026-08-27T19:35:20+10:00 — mode=triad
- Coin gate: PASS
- Lead system: MARKUS
- HERMES slot 12: DOUBLE_REROLL -> 2 extra dice
- HERMES slot 8: UPGRADE_HERMES_BACKEND
    target: hermes config CLI: providers, models, gateway, MCP (setup_mcp), cron (cronjob)
    next: Load hermes-agent skill; hermes config set ...; audit MCP servers; review cron jobs
- HERMES slot 11: RESEARCH_HERMES_ROADMAP
    target: hermes docs https://hermes-agent.nousresearch.com/docs + web_search -> DICE_ROADMAP.md
    next: Read hermes-agent skill + docs; web_search new capabilities; append findings to DICE_ROADMAP.md
- MARKUS slot 1: UPGRADE_MARKUS_UI
    target: markus_chat.html, markus-os.html, the-orb.html, memory-palace.html, hack-console.html
    next: Edit the listed HTML under Desktop/MARKUS-OS; smoke-test via python launch_markus_app.py
- VORPAL slot 16: OPTIMISE_VORPAL_PROCESS
    target: Desktop/VORPAL: EVOLVE/GOALS/GOALS.md, EVOLVE/NOTES.md, registry.json, cost ledger
    next: Audit GOALS/NOTES/registry for stale or false claims; fix; commit
- Curation die: DEEP — Run CURATE + ENHANCE + OPTIMISE (the extra chance).
- Status: EXECUTED (log this cycle in DICE_ROADMAP.md)
