# MARKUS VORPAL — Adversarial Battle-Test Report

**Repo:** `MARKUS-OS` (with sibling `VORPAL` cross-repo imports for the ARK sandbox / syscall / kernel surface)
**Date:** 2026-08-28
**Method:** Adversarial review + TDD. Attack surface mapped, malformed/overflow/unexpected inputs
fed at every boundary, auth/access-control reviewed, security weaknesses hunted, and a RED
regression test written for each weakness. All tests target the **current unpatched code**.

## Execution summary

Every failing test is a live reproduction of a real weakness in the current code —
none of the failures is a harness/import problem. The passing tests are included
deliberately to prove the suite is honest (not everything fails) and to lock in
controls that already hold.

**Three configurations were exercised** (all against the *current unpatched code*):

| Config | Total (pytest) | Failed (RED) | Passed | Skipped |
|--------|----------------|--------------|--------|---------|
| A. Full local stack (MARKUS-OS local master + sibling VORPAL) | 54 | **45** | 9 | 0 |
| B. PR baseline (this branch = `origin/master` + sibling VORPAL; `markus_run_ledger` local-only) | 50 | **38** | 11 | 1 |
| C. CI simulation (clean `origin/master`, no sibling VORPAL) | 45 | **31** | 10 | 4 |

*(In B and C the "total" includes module-level skips exactly as pytest counts them: a skipped
module is reported once even though its individual tests are not collected.)*

- Config A is the developer's current working tree — the complete attack surface. **45 RED.**
- Config B is what this PR delivers: the tests land on the published baseline and are
  immediately **38 RED** against it (the `markus_run_ledger` tests skip because that module is
  local-master only — see CI section).
- Config C is the CI runner's view (no sibling VORPAL on GitHub): **31 RED**, the rest clean skips.

All three configurations yield far more than the 10-distinct-issue acceptance bar; the count of
RED tests is *understated* relative to findings because several tests are parametrized
(e.g. REG-05 = 6 malformed-FTS cases, REG-12 = 4 run_id cases, REG-16 = 11 endpoint cases).

**Scope of findings:** 25 distinct issues (REG-01 … REG-28b), covering 45 failing tests.
This exceeds the acceptance bar of 10 distinct issues with evidence.

---

## Severity legend

| Sev | Meaning |
|-----|---------|
| CRITICAL | Direct code execution / sandbox escape / data exfiltration / total auth bypass |
| HIGH     | Data exposure, DoS, or bypass of a security control |
| MED      | Integrity or hardening gap, exploitable under limited conditions |
| LOW      | Hardening / defense-in-depth gap |

---

## Findings at a glance

| ID | Title | Area | Sev | Tests |
|----|-------|------|-----|-------|
| REG-01 | Sandbox FS write escape | `markus_sandbox.py` | CRITICAL | 1 |
| REG-02 | Sandbox reads host secrets (auth.json) | `markus_sandbox.py` | CRITICAL | 1 |
| REG-04 | Sandbox timeout leaves orphan process tree | `markus_sandbox.py` | HIGH | 1 |
| REG-05 | Malformed FTS5 query raises OperationalError (HTTP 500 / crash) | `markus_db.py` | HIGH | 6 |
| REG-06 | Negative limit → full-table dump (`LIMIT -1` = unlimited) | `markus_db.py` | HIGH | 1 |
| REG-06b | Huge limit → unbounded allocation | `markus_db.py` | MED | 1 |
| REG-08 | SQLi via `search_thoughts` UNION into registers | `markus_db.py` | CRITICAL | 1 |
| REG-09 | THORS loopback trust bypass (attacker on host is never analyzed) | `markus_thors.py` | HIGH | 3 |
| REG-10 | THORS block state lost on engine restart | `markus_thors.py` | MED | 1 |
| REG-12 | `run_id` unvalidated charset (path traversal / SQLi / newline / spaces) | `markus_run_ledger.py` | HIGH | 4 |
| REG-14 | Checkpoint restore poisons protected registers (no allowlist) | `markus_checkpoint.py` | MED | 1 |
| REG-15 | Checkpoint index tamper/injection (index not integrity-protected) | `markus_checkpoint.py` | LOW | 1 |
| REG-16 | No auth on 10 security-critical POST endpoints | `markus_server.py` | CRITICAL | 11 |
| REG-17 | CORS allowlist accepts `null` origin | `markus_server.py` | MED | 1 |
| REG-17b | SSE stream emits wildcard `Access-Control-Allow-Origin: *` | `markus_server.py` | MED | 1 |
| REG-18 | Unbounded request body (Content-Length trusted verbatim) | `markus_server.py` | HIGH | 1 |
| REG-19 | Cortex search `limit` unvalidated / unclamped | `markus_server.py` | MED | 1 |
| REG-21 | ARK sandbox `__class__.__base__.__subclasses__()` escape | `VORPAL/CORE/ark_sandbox.py` | CRITICAL | 1 |
| REG-21b | ARK sandbox `importlib` escape | `VORPAL/CORE/ark_sandbox.py` | CRITICAL | 1 |
| REG-22 | ARK tier-2 wrapper never rebinds `open`/`socket` | `VORPAL/CORE/ark_sandbox.py` | CRITICAL | 1 |
| REG-23 | ARK sandbox `open()` reaches host FS | `VORPAL/CORE/ark_sandbox.py` | CRITICAL | 1 |
| REG-25 | Ledger spend TOCTOU race → concurrent overdraw | `VORPAL/CORE/syscalls` | HIGH | 1 |
| REG-26 | Quarantine `category` path traversal (repair-root escape) | `VORPAL/CORE/syscalls` | MED | 1 |
| REG-27 | Kernel spawn entrypoint not validated | `VORPAL` kernel / electron | MED | 1 |
| REG-28 | Electron-served pages carry no Content-Security-Policy | `markus_server.py` + electron | HIGH | 1 |

**Verified-secure guardrails (9 passing tests):** REG-03 sandbox network exfil blocked,
REG-11 code-exec payload in JSON detected, REG-13 invalid ledger state transition blocked,
REG-20 rate-limit tokens present on `/api/intent`, REG-24 syscalls `send()` profile path
validated, REG-28b electron child args validated, checkpoint checksum tamper detection,
unknown-checkpoint-id rejection, and one valid-FTS-query control case.

---

## Detailed findings

### REG-01 — Sandbox filesystem write escape  (CRITICAL)
**Area:** `markus_sandbox.py` — `Sandbox.execute_python_code`
**Repro:** `tests/battle/test_sandbox_isolation.py::test_cannot_write_outside_sandbox_root`
**Evidence:** The test writes `open(<host path>, 'w')` from inside the sandbox and the write
**succeeds** (test FAILS = write not blocked). The sandbox runs Python via
`asyncio.create_subprocess_exec` with no filesystem confinement — `open()` is the host `open()`.
**Fix:** Inject a `safe_open` into the sandbox's exec namespace that resolves the target against
`sandbox_root` and rejects any absolute/`..` path; deny `open` for the raw builtin; or run the
sandbox under OS-level confinement (container / restricted token) that the guest cannot escape.

### REG-02 — Sandbox reads host secrets  (CRITICAL)
**Area:** `markus_sandbox.py`
**Repro:** `tests/battle/test_sandbox_isolation.py::test_cannot_read_host_secrets`
**Evidence:** A fake `auth.json` containing a Nous agent key is readable from inside the sandbox
(test FAILS = read not blocked). The sandbox shares the host filesystem and process environment.
**Fix:** Same confinement as REG-01 (restricted `open`/`read`), plus strip `*_KEY`/`*_TOKEN`
environment variables from the sandbox subprocess environment.

### REG-04 — Sandbox timeout leaves orphan process tree  (HIGH)
**Area:** `markus_sandbox.py`
**Repro:** `tests/battle/test_sandbox_isolation.py::test_timeout_kills_process_tree`
**Evidence:** The sandbox's `wait_for(timeout=...)` raises `asyncio.TimeoutError` and returns, but
the child (and any children it spawned) are not terminated — the runaway process keeps running
(test FAILS = child still alive after timeout). This is an orphan-process DoS.
**Fix:** On timeout, `proc.kill()`/`terminate()` the process *group* (POSIX: `start_new_session=True`
+ `os.killpg`; Windows: `CREATE_NEW_PROCESS_GROUP` + `taskkill /T`), then `await proc.wait()` to reap.

### REG-05 — Malformed FTS5 query raises OperationalError  (HIGH)
**Area:** `markus_db.py::PersistentCortexDB.search_thoughts`
**Repro:** `tests/battle/test_db_fts_input.py::test_malformed_fts_query_does_not_crash[...]` (6 cases)
**Evidence:** Unterminated quotes, `*`, `(`, `)`, `NEAR(a b`, `"quote" NEAR(` all raise
`sqlite3.OperationalError` straight through the API surface (test FAILS). In the live server this
surfaces as an HTTP 500 / unhandled crash.
**Fix:** Validate FTS5 syntax before execution (wrap in `try/except sqlite3.OperationalError` and
return an empty result or a clean 4xx), or escape/quarantine the query, or use a parameterized
non-FTS fallback.

### REG-06 — Negative limit dumps the whole table  (HIGH)
**Area:** `markus_db.py::PersistentCortexDB.search_thoughts`
**Repro:** `tests/battle/test_db_fts_input.py::test_negative_limit_is_clamped`
**Evidence:** `search_thoughts("token", limit=-1)` returns **25 rows** from a 25-row table
(test FAILS: "negative limit returned 25 rows"). SQLite treats `LIMIT -1` as *no limit*.
**Fix:** Clamp `limit = max(1, min(int(limit), MAX_RESULTS))` before interpolation; reject negatives.

### REG-06b — Huge limit → unbounded allocation  (MED)
**Area:** `markus_db.py::PersistentCortexDB.get_recent_thoughts`
**Repro:** `tests/battle/test_db_fts_input.py::test_huge_limit_is_capped`
**Evidence:** `get_recent_thoughts(limit=10**9)` returns **130 rows** from a 130-row table
(test FAILS: "huge limit returned 130 rows"). A caller can force a full-table materialization.
**Fix:** Same clamp as REG-06; cap at a documented `MAX_RESULTS` (e.g. 100).

### REG-08 — SQL injection reads the registers table  (CRITICAL)
**Area:** `markus_db.py::PersistentCortexDB.search_thoughts`
**Repro:** `tests/battle/test_db_fts_input.py::test_sql_injection_cannot_read_registers`
**Evidence:** Payload `token') UNION SELECT val_json FROM registers --` returns register contents
(test FAILS). `search_thoughts` interpolates the raw user query into FTS5 SQL; the `registers`
table (which holds `OS_STATUS`, and in real deployments API keys / secrets) is reachable via
UNION from the injection point.
**Fix:** Do not interpolate the user query into SQL. Use FTS5 `MATCH` with a parameterized
`query` binding, or parse the query into a whitelisted token set; never allow the user string to
alter the statement structure.

### REG-09 — THORS loopback trust bypass  (HIGH)
**Area:** `markus_thors.py::ThorsEngine.analyze_request`
**Repro:** `tests/battle/test_thors_bypass.py::test_{attack,path_traversal,forbidden_call}_detected_from_loopback`
**Evidence:** `markus_thors.py` contains `TRUSTED_IPS = {"127.0.0.1", "::1"}` and a code path
"Trusted loopback IP — exempt from Thor analysis" that returns `threat_level=0` without
classifying the payload (test FAILS for SQLi, `../` path traversal, and
`exec(open('/etc/passwd').read())`). The server binds `127.0.0.1`, so ANY local process (malware,
a second user, an XSS'd browser tab via `file://`/CORS) is waved through the entire threat engine.
**Fix:** Do not bypass analysis on loopback — the IP only gates *blocking* decisions, never
*analysis*. Classify the payload first; use loopback trust only as a reputation hint, and keep
payload-level detection on.

### REG-10 — THORS block state lost on restart  (MED)
**Area:** `markus_thors.py`
**Repro:** `tests/battle/test_thors_bypass.py::test_block_persists_across_engine_restart`
**Evidence:** An attacker blocked in one engine instance is unblocked after the engine is
re-instantiated (test FAILS). Block decisions are held in-memory only and never persisted.
**Fix:** Persist block/reputation records to the cortex DB (the engine already takes a
`cortex_db`); load them on `__init__`.

### REG-12 — `run_id` unvalidated charset  (HIGH)
**Area:** `markus_run_ledger.py`
**Repro:** `tests/battle/test_run_ledger_input.py::test_unsafe_run_id_rejected[...]` (4 cases)
**Evidence:** `create_run(run_id=...)` accepts `../../../etc/evil`, `x' OR '1'='1`, `a\nb`, and
`run id with spaces` (test FAILS). The id flows into file paths / DB strings with no charset or
shape validation — path traversal, SQLi, and log-injection primitives.
**Fix:** Validate `run_id` against a strict charset (e.g. `^[A-Za-z0-9_\-]{1,64}$`) and reject
anything else with `RunLedgerError`/`ValueError` before any file/DB use.

### REG-14 — Checkpoint restore poisons protected registers  (MED)
**Area:** `markus_checkpoint.py::restore_checkpoint`
**Repro:** `tests/battle/test_checkpoint_integrity.py::test_restore_does_not_poison_protected_registers`
**Evidence:** A checksum-**valid** checkpoint carrying `OS_STATUS=DEGRADED` / `VERSION=0.0.0-EVIL`
is restored and **overwrites** the live protected registers (test FAILS). `restore_checkpoint`
re-commits every register verbatim with no namespace allowlist (lines ~150-153).
**Fix:** Maintain an allowlist of restorable register keys; refuse to restore protected system
registers (`OS_STATUS`, `VERSION`, auth/config keys) from any checkpoint, or require a separate
authorized "system restore" path.

### REG-15 — Checkpoint index tamper / injection  (LOW)
**Area:** `markus_checkpoint.py` (`_load_index` / `restore_checkpoint`)
**Repro:** `tests/battle/test_checkpoint_integrity.py::test_index_injection_does_not_restore_ghost`
**Evidence:** Rewriting `index.json` to advertise a ghost `chk_ghost` (with a self-consistent
payload + checksum) makes `restore_checkpoint("chk_ghost")` succeed and apply attacker data
(test FAILS). `_load_index` trusts `index.json` blindly — the index itself has no integrity
check, so the payload checksum is trivially self-consistent.
**Fix:** Integrity-protect the index (HMAC with a persisted secret, or a checksum entry over the
index), and/or store checkpoints in an append-only store the writer cannot silently rewrite.

### REG-16 — No authentication on security-critical POST endpoints  (CRITICAL)
**Area:** `markus_server.py` (`MarkusRequestHandler.do_POST`)
**Repro:** `tests/battle/test_server_api_surface.py::test_security_endpoints_require_auth` +
`test_each_security_endpoint_is_gated[...]` (10 endpoints)
**Evidence:** Zero occurrences of `Authorization` / `Bearer` / `X-API-Key` anywhere in
`markus_server.py`; every POST handler reads the body and dispatches without any token check.
The following execute with **no authentication at all**:
`/api/sandbox/eval`, `/api/dag/execute`, `/api/dag/step`, `/api/consensus/arbitrate`,
`/api/checkpoints/create`, `/api/checkpoints/restore`, `/api/intent`, `/api/vault/sync`,
`/api/context/prune`, `/api/speculation/precompute` (test FAILS for all 11).
Combined with REG-09 (loopback trust), this means any local process can run arbitrary code,
arbitrate consensus, restore checkpoints, and prune context on the live MARKUS instance.
**Fix:** Require a shared-secret auth token (env-provided) on every state-changing POST; verify it
before dispatch; reject with 401 otherwise. Bind-and-verify is not sufficient — the server binds
127.0.0.1 but any local actor can reach it.

### REG-17 — CORS allowlist accepts `null` origin  (MED)
**Area:** `markus_server.py` CORS handling
**Repro:** `tests/battle/test_server_api_surface.py::test_cors_does_not_allow_null_origin`
**Evidence:** `"null"` appears in the CORS allowlist (test FAILS). `Origin: null` is sent by
sandboxed iframes and `file://` pages — accepting it lets a locally-opened HTML file call the API
with no browser same-origin protection.
**Fix:** Remove `"null"` from the allowlist; only accept concrete `scheme://host[:port]` origins.

### REG-17b — SSE stream emits wildcard ACAO  (MED)
**Area:** `markus_server.py` `/api/stream`
**Repro:** `tests/battle/test_server_api_surface.py::test_sse_stream_does_not_send_wildcard_acao`
**Evidence:** The SSE handler emits `Access-Control-Allow-Origin: *` (test FAILS), bypassing the
origin allowlist entirely and letting any web origin subscribe to the telemetry stream.
**Fix:** Emit the specific allowed origin (or none) on the SSE response; never `*`.

### REG-18 — Unbounded request body  (HIGH)
**Area:** `markus_server.py::_read_body`
**Repro:** `tests/battle/test_server_api_surface.py::test_body_read_has_an_upper_bound`
**Evidence:** `_read_body` trusts `Content-Length` verbatim
(`content_length = int(self.headers.get("Content-Length", 0))`, no cap) — a client can post an
arbitrarily large body and exhaust memory (test FAILS: no `MAX_BODY` anywhere in the handler).
**Fix:** Cap `Content-Length` (e.g. 1 MB) and reject larger requests with 413; also bound the
actual read loop, not just the header.

### REG-19 — Cortex search limit unvalidated  (MED)
**Area:** `markus_server.py` cortex search handler
**Repro:** `tests/battle/test_server_api_surface.py::test_cortex_search_limit_is_validated`
**Evidence:** `limit=...` from the query string is parsed and passed through without
`min`/`max` clamping (test FAILS) — mirrors REG-06/06b at the HTTP boundary.
**Fix:** Parse as int, clamp to `[1, MAX_RESULTS]`, reject non-numeric.

### REG-21 / REG-21b — ARK sandbox object-graph escapes  (CRITICAL)
**Area:** `VORPAL/CORE/ark_sandbox.py`
**Repro:** `tests/battle/test_vorpal_ark_sandbox.py::test_classic_subclasses_escape_blocked`,
`test_importlib_escape_blocked`
**Evidence:** `().__class__.__base__.__subclasses__()` walks to `_frozen_importlib`/`subprocess`
classes and runs code (test FAILS); `importlib.import_module('os').system('echo PWNED')` returns
success (test FAILS). The sandbox's builtin blacklist is bypassable via the classic object-graph
walk.
**Fix:** Run guest code in a restricted execution model (subinterpreter, restricted
`builtins` dict that includes *no* classes beyond safe set, and `__class__`/`__subclasses__`
guarded), or move to real process/OS isolation so the Python-level restrictions are defense-in-depth
only.

### REG-22 — ARK tier-2 wrapper never rebinds `open`/`socket`  (CRITICAL)
**Area:** `VORPAL/CORE/ark_sandbox.py` (subprocess wrapper)
**Repro:** `tests/battle/test_vorpal_ark_sandbox.py::test_tier2_wrapper_actually_applies_isolation`
**Evidence:** The wrapper source contains no `open = _safe_open` rebinding (test FAILS), so the
"isolated" subprocess runs with the real `open`/`socket` builtins.
**Fix:** In the wrapper, explicitly rebind `open`, `io.open`, `os.open`, `socket.socket`, `os.system`,
`subprocess.*`, etc. to safe shims before executing the guest payload; verify via the regression test.

### REG-23 — ARK sandbox `open()` reaches host FS  (CRITICAL)
**Area:** `VORPAL/CORE/ark_sandbox.py`
**Repro:** `tests/battle/test_vorpal_ark_sandbox.py::test_tier1_open_escape_blocked`
**Evidence:** `open(<host path>, 'w')` from inside the sandbox succeeds (test FAILS).
**Fix:** As REG-22 — `open` must be confined to a sandbox root via a path-resolving shim.

### REG-25 — Ledger spend TOCTOU race → concurrent overdraw  (HIGH)
**Area:** `VORPAL/CORE/syscalls` ledger spend
**Repro:** `tests/battle/test_vorpal_syscalls.py::test_ledger_spend_is_atomic_under_race`
**Evidence:** 3 concurrent spends of 70 against a 100 balance **all succeed** (test FAILS:
"3 concurrent spends … 3 passed (TOCTOU overdraw)"). The balance read + write is not atomic.
**Fix:** Serialize the check-and-debit (threading lock / file lock / DB transaction / compare-and-swap).

### REG-26 — Quarantine `category` path traversal  (MED)
**Area:** `VORPAL/CORE/syscalls` quarantine
**Repro:** `tests/battle/test_vorpal_syscalls.py::test_quarantine_rejects_path_traversal_category`
**Evidence:** A `category` like `../..` escapes the repair root (test FAILS — no `ValueError`/`OSError`).
**Fix:** Validate `category` against a safe charset and resolve+confine it under the repair root.

### REG-27 — Kernel spawn entrypoint not validated  (MED)
**Area:** `VORPAL` kernel spawn
**Repro:** `tests/battle/test_vorpal_kernel_electron.py::test_kernel_spawn_validates_entrypoint`
**Evidence:** An arbitrary executable path as the "entrypoint" is accepted by the spawn path
(test FAILS — no `ValueError`/`TypeError` raised).
**Fix:** Whitelist allowed entrypoints; reject anything outside the known set before spawning.

### REG-28 — Electron-served pages carry no CSP  (HIGH)
**Area:** `markus_server.py` header emission (served to Electron at `http://127.0.0.1:8128`)
**Repro:** `tests/battle/test_vorpal_kernel_electron.py::test_electron_served_pages_have_csp`
**Evidence:** No `Content-Security-Policy` header is emitted for served pages (test FAILS).
The UI loads remote/`javascript:` content into `webContents`; without CSP, an XSS in any served
page becomes script execution inside the Electron context (with `nodeIntegration` risk).
**Fix:** Emit a strict CSP on every page response
(e.g. `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`), and keep
`nodeIntegration: false` / `contextIsolation: true` in the BrowserWindow.

---

## Verified-secure guardrails (controls that hold — 9 passing tests)

These tests encode secure behaviour and currently **pass**, proving the suite is not a blanket
"everything fails" dump and locking in behaviour that must not regress:

- **REG-03** — Sandbox cannot open sockets (network exfiltration blocked)
- **REG-11** — THORS detects code-exec payloads nested inside JSON bodies
- **REG-13** — Ledger blocks invalid `RECEIVED → COMMITTED` state transition
- **REG-20** — `/api/intent` has rate-limiting tokens in the handler
- **REG-24** — syscalls `send()` rejects path-traversal profile names
- **REG-28b** — Electron main validates the Python child server args
- Checkpoint tampered-payload checksum **is** detected and rejected
- Checkpoint restore of an unknown id raises cleanly
- Valid FTS query control case executes without error

---

## CI integration

`tests/battle` is wired into CI via `.github/workflows/battle-test.yml`:

- Runs on `windows-latest`, Python 3.11, on `push` to `master`/`feat/**`/`battle-test/**` and all PRs.
- Bootstraps the sibling `VORPAL` repo (best-effort clone; it is local-only and not
  published, so the clone is expected to fail and the VORPAL/run-ledger tests **skip
  cleanly** via `pytest.importorskip` with explicit reasons).
- Executes `python -m pytest tests/battle` with `continue-on-error: true` **because the suite is
  intentionally RED** — every failing test is a tracked, documented unpatched weakness in
  `battle-test-report.md`. As fixes land, tests flip green one by one and the suite becomes a
  regression gate; the workflow emits a CI notice pointing at the report so the posture is visible
  on every commit.

**CI posture against the published `origin/master` baseline (verified by simulating a clean
checkout):** `31 failed, 10 passed, 4 skipped`. The 31 RED tests reproduce the core weaknesses
that already exist on the published baseline (sandbox escapes, SQLi, unauthenticated endpoints,
unbounded body/limits, CORS, CSP, FTS crashes, ledger TOCTOU, checkpoint poisoning). The
remaining locally-RED findings (run-ledger input validation, ARK sandbox escapes, VORPAL syscalls)
exercise code that is present only in the local stack — they are exercised fully on the local
stack (45 RED) and skip in CI with a documented reason.

---

## Recommended remediation order

1. **REG-16** (auth on POST endpoints) — total control of the live instance today.
2. **REG-01/02/21/21b/22/23** (sandbox escapes, both sandboxes) — arbitrary host FS / code.
3. **REG-08** (SQLi into registers) — secret disclosure.
4. **REG-18/06/06b/19** (unbounded body / limits) — DoS.
5. **REG-12/26** (path-traversal inputs) — file/root escape primitives.
6. **REG-25** (ledger race) — monetary/integrity.
7. **REG-09/10** (THORS bypass) — detection evasion.
8. **REG-05/14/15/17/17b/27/28** — crash, integrity, CORS, and Electron hardening.
