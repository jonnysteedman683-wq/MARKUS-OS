# Hermes-Hive Event, Desktop, and Evaluation Adoption Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a secure event-driven Hermes↔Hive integration, an opt-in Hermes Desktop operational cockpit, and an evidence-gated skill/workflow evaluation lane without disrupting the live HERMES-HIVE deck.

**Architecture:** Treat HERMES-HIVE as the durable machine-truth/event and product layer, with Hermes as an external agent runtime. A narrow signed ingress adapter converts selected Hermes/GitHub events into validated append-only Hive events. The desktop plugin only reads a scoped Hive API and uses the Hermes SDK for host state and navigation; it never holds provider credentials. Evaluation runs occur in isolated worktrees and only promote human-reviewed artifacts that pass deterministic gates.

**Tech Stack:** Existing HERMES-HIVE Vite/Svelte/TypeScript server and SQLite state; Hermes gateway webhooks; FastAPI-style Hermes `plugin_api.py`; plain-JS ESM Desktop Plugin SDK; Vitest; curl; official Hermes A/B evaluation harness.

## Current evidence and assumptions

- `UPGRADE_PATH.md` identifies HERMES-HIVE as Vite+Svelte with server modules, SQLite state, a `/api/neurocore/*` bridge, m1 Swarm Registry, and existing Level-1/Level-2 trust/intents work. It also states that `/api/chat` remains the live fallback and that evidence must be tests/curl/visible demo.
- The current local workspace contains the approved upgrade brief but not the HERMES-HIVE checkout. Resolve the real repository path from the configured `HERMES_HIVE_REPO` environment value or clone/open `jonnysteedman683-wq/HERMES-HIVE` before changing product code. Do not guess paths.
- Hermes inbound webhooks authenticate sender signatures and provide route filters, 1-hour idempotency, payload-size limiting, and rate limits; authenticated business text remains untrusted. [4]
- Hermes Desktop plugins are renderer-side ESM with full app authority. Backend routes are scoped to `/api/plugins/<id>`; sockets are optional accelerators and every UI needs polling fallback. [5]

---

## Phase 0 — Baseline and contract freeze

### Task 1: Locate and baseline the actual HERMES-HIVE checkout

**Objective:** Establish the exact repository, branch, gates, and existing API/event ownership before adding integration code.

**Files:**
- Inspect: `<HERMES_HIVE_REPO>/package.json`
- Inspect: `<HERMES_HIVE_REPO>/src/server/apiMiddleware.*`
- Inspect: `<HERMES_HIVE_REPO>/src/server/neurocore/*`
- Inspect: `<HERMES_HIVE_REPO>/.hive/*`, `docs/*`, and existing tests
- Create: `<HERMES_HIVE_REPO>/docs/integrations/hermes-integration-contract.md`

**Step 1: Resolve the repo path without guessing**

Run:
```bash
printf '%s\n' "$HERMES_HIVE_REPO"
git -C "$HERMES_HIVE_REPO" rev-parse --show-toplevel
git -C "$HERMES_HIVE_REPO" status --short
```

Expected: a clean or explicitly understood working tree and an absolute repository root.

**Step 2: Record the existing test/lint commands from package scripts**

Run the commands declared by `package.json`; use the established gate `bun run test` rather than `bun test`.

Expected: captured baseline output; no integration changes yet.

**Step 3: Write the public integration contract**

Document:
- event schema version;
- `event_id`, `source`, `occurred_at`, `received_at`, `type`, `correlation_id`, `payload`, `trust`, `raw_ref` fields;
- which event types are accepted in v1;
- source signing and replay/idempotency rules;
- explicit rule that webhook/agent text is untrusted data, never instructions;
- storage and redaction policy;
- retry and dead-letter policy;
- no provider credential may enter Hive events or desktop plugin state.

**Step 4: Commit**

```bash
git add docs/integrations/hermes-integration-contract.md
git commit -m "docs: define Hermes Hive integration contract"
```

---

## Phase 1 — Secure Hermes → Hive event ingress

### Task 2: Add contract tests for signed, idempotent event ingestion

**Objective:** Define the narrow ingress behavior before implementation.

**Files:**
- Create: `<HERMES_HIVE_REPO>/src/server/integrations/hermesEventSchema.ts`
- Create: `<HERMES_HIVE_REPO>/src/server/integrations/hermesEventVerifier.ts`
- Create: `<HERMES_HIVE_REPO>/src/test/hermesEventIngress.test.ts`

**Step 1: Write failing tests**

Cover at least:
1. valid v2 HMAC signature + current timestamp is accepted;
2. timestamp outside the allowed replay window is rejected;
3. missing/invalid signature is rejected;
4. oversized body is rejected before JSON parse;
5. duplicate `event_id` yields an idempotent outcome and no second write;
6. unsupported `type` is rejected;
7. payload text resembling instructions is stored as inert data and never executed;
8. secret/redacted field names do not persist plaintext.

Use known HMAC test vectors and fixed clocks—no real secret in test fixtures.

**Step 2: Run test to verify failure**

```bash
bun run test src/test/hermesEventIngress.test.ts
```

Expected: FAIL because the ingress/schema modules do not exist.

**Step 3: Implement the smallest pure functions**

Implement parsing, validation, HMAC v2 checking over `<timestamp>.<body>`, allowed event types, size limit, redaction, and a storage-neutral idempotency interface. Do not make HTTP requests or call a model in this layer.

**Step 4: Run test to verify pass**

```bash
bun run test src/test/hermesEventIngress.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/server/integrations src/test/hermesEventIngress.test.ts
git commit -m "feat: validate signed Hermes event envelopes"
```

### Task 3: Persist and expose accepted events through the existing Hive repository pattern

**Objective:** Make accepted events durable machine truth and readable by the deck/plugin without creating a parallel datastore.

**Files:**
- Modify: the existing SQLite migration/repository convention
- Create: `<HERMES_HIVE_REPO>/src/server/repositories/hermesEventRepository.ts`
- Create/Modify: `<HERMES_HIVE_REPO>/src/server/services/hermesEventService.ts`
- Create: `<HERMES_HIVE_REPO>/src/test/hermesEventRepository.test.ts`

**Step 1: Write failing repository tests**

Test durable append, unique `event_id`, chronological cursor pagination, filtered read by `type`/`correlation_id`, and redacted API representation.

**Step 2: Implement schema and repository**

Use the deck’s existing migration discipline. Add a unique constraint on `event_id`; preserve raw payload only if its redaction/retention policy is satisfied. Persist a normalized, validated event separately from any raw payload pointer.

**Step 3: Run targeted and full gates**

```bash
bun run test src/test/hermesEventRepository.test.ts
bun run test
```

Expected: PASS.

**Step 4: Commit**

```bash
git add src/server/repositories src/server/services <migration-path> src/test/hermesEventRepository.test.ts
git commit -m "feat: persist normalized Hermes events"
```

### Task 4: Mount a bounded Hive ingress endpoint and read APIs

**Objective:** Wire the pure ingress to the real server while preserving `/api/chat` and neurocore behavior.

**Files:**
- Modify: `<HERMES_HIVE_REPO>/src/server/apiMiddleware.*` or its established router mount point
- Create: `<HERMES_HIVE_REPO>/src/server/routes/hermesEvents.*` (only if routes are the project convention)
- Create: `<HERMES_HIVE_REPO>/src/test/hermesEventRoutes.test.ts`

**HTTP contract:**
- `POST /api/integrations/hermes/events` — signed envelope only; returns accepted/duplicate/rejected status, never model output.
- `GET /api/integrations/hermes/events?cursor=&limit=&type=&correlation_id=` — sanitized event timeline.
- `GET /api/integrations/hermes/summary` — bounded operational summary for the desktop plugin.

**Step 1: Write failing HTTP tests**

Assert status codes for valid, invalid, stale, duplicate, and oversized requests. Assert read endpoints never return raw secrets and enforce a maximum `limit`.

**Step 2: Implement route adapters**

Keep HTTP/controller code thin: read raw bytes once, delegate validation, persist via repository, map typed errors to status. Do not interpolate event text into shell/model prompts.

**Step 3: Verify manually with curl**

Use a test-only generated secret and signed JSON fixture. Verify a duplicate call returns a duplicate status and the list endpoint has one event.

**Step 4: Run full validation and commit**

```bash
bun run test
bun run lint
```

Use the project’s actual lint command if different.

```bash
git add src/server src/test
git commit -m "feat: expose signed Hermes event ingress"
```

### Task 5: Configure a minimal Hermes webhook route only after the receiver passes tests

**Objective:** Deliver one non-destructive event class to the now-tested Hive receiver.

**Files:**
- Modify: profile-local Hermes configuration only after user-approved secret placement
- Create: a non-secret example config in `<HERMES_HIVE_REPO>/docs/integrations/hermes-webhook.example.yaml`

**Step 1: Choose v1 event types**

Start with only operationally safe events, e.g. `hive.intent.created`, `hive.intent.completed`, `hive.review.required`, `hive.cycle.summary`. Do not forward arbitrary transcript/tool-output bodies in v1.

**Step 2: Implement a sender script/service**

Use generic V2 HMAC headers with timestamp and request ID. Include a correlation ID from the existing Hive intent lifecycle.

**Step 3: Provision the Hermes route**

Use a route-specific secret—not an `INSECURE_NO_AUTH` route. Apply an allow-list filter and minimum tool permissions. If a webhook triggers an agent, disable terminal/file/outbound tools unless required; payload fields are untrusted even after HMAC verification. [4]

**Step 4: Prove end-to-end behavior**

1. `curl /health` on the gateway.
2. Send a signed fixture.
3. Confirm the Hive event exists once.
4. Replay the same request ID; confirm duplicate/no additional write.
5. Send prompt-injection-like payload text; confirm it displays as data and no action occurs.

**Step 5: Commit documentation only**

```bash
git add docs/integrations/hermes-webhook.example.yaml docs/integrations/hermes-integration-contract.md
git commit -m "docs: add secure Hermes webhook deployment guide"
```

---

## Phase 2 — Hermes Desktop “Hive Mission Room” plugin

### Task 6: Create an opt-in read-only plugin skeleton

**Objective:** Put a native Hermes desktop surface beside the conversation without forking Hermes Desktop or making it a second source of truth.

**Files:**
- Create: `$HERMES_HOME/desktop-plugins/hermes-hive-mission-room/plugin.js`
- Create: `<HERMES_HIVE_REPO>/docs/integrations/hermes-desktop-plugin.md`

**Step 1: Implement the smallest pane**

Use plain JavaScript ESM and `jsx()` (not JSX syntax). Register:
- a right-hand pane titled “Hive Mission Room”;
- an opt-in default (`defaultEnabled: false`);
- a status-bar chip for connection state;
- a palette command to focus the pane.

Use native SDK components and CSS variables only—no hardcoded backgrounds/colors. [5]

**Step 2: Display only a connection state and empty-state view**

The first render must work when Hive is offline, missing, or returns an error.

**Step 3: Reload and verify in Hermes Desktop**

Use **Reload desktop plugins** from the command palette. Verify no load-failure toast appears, the pane is draggable, and disable/enable survives reload.

### Task 7: Add the scoped plugin backend and summary/event UI

**Objective:** Fetch Hive summary data via a narrow backend—not from renderer-side credentials or arbitrary URLs.

**Files:**
- Create: `$HERMES_HOME/plugins/hermes-hive-mission-room/dashboard/manifest.json`
- Create: `$HERMES_HOME/plugins/hermes-hive-mission-room/dashboard/plugin_api.py`
- Modify: `$HERMES_HOME/desktop-plugins/hermes-hive-mission-room/plugin.js`
- Create: `<HERMES_HIVE_REPO>/src/test/hermesSummaryRoute.test.ts`

**Step 1: Write failing Hive summary endpoint tests**

Assert a bounded response that contains active swarm, intent totals by lifecycle state, recent sanitized events, and a `generated_at` timestamp. Assert no credentials/raw payloads/agent prompts are included.

**Step 2: Implement the backend proxy**

The plugin API reads the Hive base URL from plugin configuration/environment, applies a short timeout, validates the returned schema, and exposes only `/summary` and `/events` under `/api/plugins/hermes-hive-mission-room/`. Never expose a generic HTTP proxy endpoint.

**Step 3: Implement React Query data flow**

Use `ctx.rest('/summary')` with React Query. Refresh no faster than every 10–15 seconds; if using `ctx.socket`, retain polling fallback because sockets can be unavailable/drop. [5]

**Step 4: Build the v1 information architecture**

Tabs:
1. **Now** — active swarm, active intent, safety/emergency state.
2. **Timeline** — last 25 sanitized events, correlation link/copy control.
3. **Review** — needs-review intents, read-only in v1.

Use `ctx.storage` only for local UX preferences such as selected tab, never Hive state.

**Step 5: Verify Desktop and API behavior**

- start Hive;
- confirm plugin summary and timeline match `curl` exactly;
- stop Hive and observe clear error state/retry;
- reload plugin; ensure no renderer error;
- inspect network calls: all plugin backend calls must remain under `/api/plugins/hermes-hive-mission-room/*`.

### Task 8: Add constrained operator actions only after read-only acceptance

**Objective:** Allow one safe action—open intent in Hive—before any state-changing controls.

**Files:**
- Modify: plugin `plugin.js`
- Optional modify: plugin `plugin_api.py`

**Step 1: Add “Open in Hive”**

Use `ctx.os.openExternal()` with an allow-listed Hive origin and a URI-encoded intent path. On failure, show an in-app message.

**Step 2: Do not add emergency stop in the plugin yet**

The deck’s emergency stop is already a demo-critical capability. Only add plugin mutation controls after a separate explicit design/review: server-side authorization, confirmation dialog, audit event, idempotency, and an independently tested manual recovery path.

**Step 3: Commit plugin and docs in the appropriate repository**

Keep source under a versioned HERMES-HIVE integration directory, then deploy/copy it to the profile’s desktop plugin path as a release step; do not rely on unversioned profile-only source.

---

## Phase 3 — Evidence-gated skill and workflow optimization pilot

### Task 9: Create a Hive-specific evaluation dataset and promotion policy

**Objective:** Adopt the useful discipline of self-evolution without allowing auto-mutated skills or prompts into live operations.

**Files:**
- Create: `<HERMES_HIVE_REPO>/evals/hermes-skills/README.md`
- Create: `<HERMES_HIVE_REPO>/evals/hermes-skills/hive-intent-routing.golden.jsonl`
- Create: `<HERMES_HIVE_REPO>/evals/hermes-skills/rubrics/hive-intent-routing.md`
- Create: `<HERMES_HIVE_REPO>/docs/evals/promotion-policy.md`

**Step 1: Define a non-sensitive golden set**

Create 20–30 synthetic/curated scenarios covering:
- correct intent state transitions;
- malformed/unsafe input rejection;
- handoff/review state correctness;
- evidence/rationale completeness;
- no fabricated tool or external-action claims;
- concise human-readable output.

Separate train/validation/holdout sets before any optimization. Do not mine raw private conversations into a shared dataset without explicit review/redaction.

**Step 2: Define the gate before running candidates**

Candidate promotion requires all of:
- deterministic scenario success ≥ baseline;
- holdout rubric improvement ≥10% for a skill pilot, or no promotion;
- no safety/trust regression;
- no latency/cost regression beyond predefined budget;
- full Hive test suite green;
- human diff review and manual approval;
- versioned rollback available.

This follows the official project’s stated pattern of constraints, holdout evaluation, and human-reviewed promotion rather than direct deploy. [1]

**Step 3: Commit**

```bash
git add evals/hermes-skills docs/evals/promotion-policy.md
git commit -m "test: define Hive skill evaluation and promotion gates"
```

### Task 10: Adapt the tool-performance A/B method to a narrow Hive workflow

**Objective:** Benchmark operational changes using traces and programmatic outcome checks rather than model self-report.

**Files:**
- Create: `<HERMES_HIVE_REPO>/evals/toolperf/hive_intent_lifecycle.py` or project-native equivalent
- Create: `<HERMES_HIVE_REPO>/evals/toolperf/README.md`
- Create: `<HERMES_HIVE_REPO>/evals/toolperf/fixtures/*`

**Step 1: Implement three mechanical traps**

Start small and only add traps justified by real Hive pain:
1. duplicate event/inbound replay;
2. malformed intent that must be rejected before routing;
3. safe intent whose final database state and event sequence are exact.

Each task needs a strict success marker: database assertion/event count/API response—not LLM judging alone.

**Step 2: Compare only one variable**

Baseline and candidate must use the same model, same fixture, same configuration, and ≥3 repetitions. Collect: success rate, wall time, tool calls/turns where available, retries/errors, and result bytes. The official harness uses this two-arm/single-variable and trace-based pattern. [2]

**Step 3: Run baseline versus candidate in worktrees**

Never use the live profile/config as the evaluation environment. Use an isolated Hermes home and separate worktrees. Since this Windows environment uses a named profile layout, verify all paths point at the intended test profile before starting.

**Step 4: Publish results as a versioned report**

Include exact commit SHAs, model IDs, dates, fixture versions, raw runs, median/mean, and a clear no-promotion conclusion if results are noisy.

---

## Phase 4 — Rollout and operational acceptance

### Task 11: Stage rollout with kill switches and demonstration rehearsal

**Objective:** Make the new integrations demonstrably safe and reversible.

**Files:**
- Create: `<HERMES_HIVE_REPO>/docs/runbooks/hermes-hive-rollout.md`
- Create: `<HERMES_HIVE_REPO>/docs/runbooks/hermes-hive-rollback.md`

**Step 1: Feature flags**

Add independent flags for:
- Hive ingress enabled;
- event read API enabled;
- desktop plugin configured;
- evaluation lane enabled.

Flags must default off in production-like configuration until the corresponding acceptance check passes.

**Step 2: Write a rollback runbook**

Document exactly how to:
- disable the Hermes webhook route;
- stop/restart the gateway;
- disable the desktop plugin in Settings;
- disable Hive ingress without losing historical events;
- revert the specific Hive commit;
- rotate compromised route secrets.

**Step 3: Rehearse acceptance**

Demonstrate:
1. a signed event reaches Hive exactly once;
2. an invalid/replayed request is rejected or deduplicated;
3. untrusted payload text remains inert;
4. desktop pane shows the matching sanitized state;
5. Hive down → plugin degrades gracefully;
6. disable webhook/plugin and verify no further effect;
7. existing deck/neurocore tests and `/api/chat` fallback still work.

**Step 4: Commit and tag a release candidate**

```bash
git add docs/runbooks <feature-flag-files>
git commit -m "docs: add Hermes Hive integration rollout runbooks"
```

---

## Risks and decisions

| Risk | Mitigation / decision |
|---|---|
| Signed payload contains prompt injection | HMAC authenticates sender, not content. Treat all business fields as data; no privileged tool access for webhook-triggered sessions; no raw event-to-prompt interpolation. [4] |
| Duplicate/out-of-order events corrupt intent lifecycle | Unique `event_id`, idempotent route behavior, correlation IDs, and monotonic lifecycle validation. |
| Desktop plugin becomes a privileged shadow controller | Begin read-only; backend exposes two fixed endpoints, not a proxy; explicit later review for mutations. Desktop plugins have full renderer authority, so source must be versioned and reviewed. [5] |
| Hive source path absent locally | Resolve the actual checkout first; this plan intentionally does not invent file locations beyond documented seams. |
| Self-evolution creates plausible but worse instructions | Golden/holdout split, deterministic gates, fixed promotion thresholds, isolated worktrees, human review, rollback; no autonomous deploy. [1] |
| Benchmark claims based on noisy small samples | ≥3 repetitions per cell, raw trace inspection, one-variable comparison, no promotion on ambiguous deltas. [2] |
| Drift between narrative Obsidian and `.hive` machine truth | Continue current one-way render design; integrations append/reconcile machine truth first and render narrative second. |

## Expected impact and sequencing

1. **Phase 1: secure ingress** — highest operational value; enables real-time visibility and audit without granting new action authority.
2. **Phase 2: Desktop Mission Room** — highest UX value; turns Hermes into a live operational cockpit while Obsidian remains the narrative command deck.
3. **Phase 3: evaluation lane** — highest compounding value; improves only workflows demonstrated to be better.
4. **Phase 4: staged rollout** — preserves your safety-first, evidence-over-vibes standard.

## Sources

[1] Hermes Agent Self-Evolution — https://github.com/NousResearch/hermes-agent-self-evolution
[2] Hermes Tool Performance Evals — https://github.com/NousResearch/hermes-toolperf-evals
[4] Hermes webhook documentation — https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks
[5] Hermes Desktop Plugin SDK — https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
