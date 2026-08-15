# Orb Voice & Presence — Design Spec (approved 2026-08-14)

**Status:** APPROVED — ready for implementation planning
**Scope:** always-listening voice (system tray) + hybrid user-presence vision for the Orb console
**Related artifacts:** `the-orb.html`, `memory-palace.html`, `orb_bridge.py` (in `…hermes-dev1/scripts/`)

---

## 1. Architecture & components

```
┌─────────────────────────────────────────────────────┐
│  orb-sentry.py  (system tray, auto-start w/ watchdog) │
│                                                     │
│  ┌──────────┐   ┌────────────┐   ┌──────────────┐  │
│  │ mic loop  │ → │ presence   │ → │ transcribe   │  │
│  │ (16kHz    │   │ gate       │   │ (whisper)    │  │
│  │ chunks)   │   │ (MediaPipe)│   │              │  │
│  └────┬─────┘   └─────┬──────┘   └──────┬───────┘  │
│       │               │                 │          │
│       └───────────────┼─────────────────┘          │
│                       ▼                            │
│               POST /voice  {text, when}             │
└───────────────────────┬─────────────────────────────┘
                        ▼
        ┌───────────────────────────────┐
        │  orb_bridge.py  (already live)│
        │  /voice → chat brain          │
        │  /presence → state            │
        │  /briefing → away-events      │
        └───────────────┬───────────────┘
                        ▼
        ┌───────────────────────────────┐
        │  the-orb.html  (the face)     │
        │  ● mic state · away briefing  │
        └───────────────────────────────┘
```

**Five components:**

1. **orb-sentry.py** — tray app: mic capture loop, presence detection, transcription, all feeding the bridge. Auto-started by a watchdog cron (same pattern as orb_bridge).
2. **Bridge additions** — `POST /voice` (transcript → existing chat brain, voice replies), `GET /presence` (current presence state), `GET /briefing` (what happened while away).
3. **the-orb.html** — mic/ear status indicator, "while you were away" briefing card, voice mode visible in chat.
4. **Presence logic** — MediaPipe face detection (local); ambiguous → one frame to vision LLM (gpt-5.6-terra via OpenRouter key).
5. **Away-briefing collector** — bridge snapshots hive state on presence-loss, diffs on return, renders narrative.

**Data flow:** mic chunks → presence gate (skip transcription when away) → whisper → `/voice` → same brain as typed chat → TTS reply via tray (ElevenLabs).

**Error handling:** mic unavailable → red tray icon + orb page "no mic"; whisper model missing → auto-download on first run; bridge down → sentry buffers up to ~10 transcripts, flushes on reconnect.

---

## 2. Presence detection (hybrid vision)

```
camera loop (tray app, 1-2 fps, low-res 320px)
    │
    ▼
MediaPipe Face Detection (local, ~2-5ms/frame)
    │
    ├─ face found, confidence > 0.6 ──→ PRESENT (no cloud)
    │
    ├─ face found, confidence 0.3-0.6 ─┐
    │                                 │  ambiguous →
    └─ no face, but motion detected ───┤  ONE frame to vision LLM
                                       ▼
                    gpt-5.6-terra (vision) → PRESENT / ABSENT
```

**State machine (debounced):**
- `absent → present`: 2 consecutive present-detections
- `present → absent`: **90 seconds** continuous absent

**Local detector:** MediaPipe Face Detection, free, CPU, no cloud. Face presence only — no identity/pose/gaze in v1.

**Cloud fallback:** only on ambiguous local signal. Frame downscaled, EXIF-stripped, sent once to vision LLM with strict prompt: *"Is a person present and facing a computer? Answer PRESENT or ABSENT."* No frame storage; response is a boolean.

**Privacy posture:**
- Camera only runs while sentry is alive; tray icon shows green eye when camera-on; tray menu has hard "disable camera" toggle that **releases the device**
- No recording, no frame storage — presence is a stream of booleans + timestamps only
- Away-log stores events (cycle numbers, intent changes), never frames or audio

**Power:** camera at 1-2fps / 320px ≈ 1-2% CPU. Whisper bursts gated by presence.

---

## 3. Voice interaction

**Transcription pipeline (sentry):**
- Mic 16kHz mono, 5-second rolling chunks
- Presence-gated: only chunks transcribed while PRESENT
- `faster-whisper` small model, local, English; ~2-4s latency per utterance
- Transcript + timestamp → `POST /voice` → same chat brain as typed (routing, memory, tools)

**Command parsing (always-transcribe, two-tier):**
1. **Prefix trigger** — sentences containing **"orb"** get full treatment → brain → spoken reply
   - "orb what's the swarm doing" → answered
   - "hey orb, dispatch a task to fix the docs" → dispatched
   - "can you pass the salt" (no orb) → ignored silently
2. **Ambient window** — non-orb speech logged to rolling 2-min memory-only window, so *"orb, do what I just said"* can replay recent context

Privacy posture: hears everything, answers only when addressed, persists only what it acts on.

**TTS:** ElevenLabs (configured provider, key in profile `.env`). Tray toggle + `/voice off` silences. Replies also stream to orb page (visual chat mirrors voice).

**"Orb" detection:** substring match on whisper transcript ("orb", "orb's", "a orb") — no separate wake-word engine needed.

**Pure-voice naturals** (routed through existing mechanisms):
- "orb, dispatch a task to…" → `/intent`
- "orb, what's the swarm doing?" → tool use (get_swarm_status)
- "orb, pause the swarm" → registry set-status
- "orb, show me the palace" → opens palace page
- "orb, remember that…" → supermemory save

---

## 4. Orb page UI (the face)

1. **Ear indicator** (top-right near toolbar): `●` green pulsing = listening/present; `◌` dim = away; `⛔` red = mic error/camera disabled. Click → popover: tray mirror (mute voice, disable camera) + last-heard transcript.
2. **"While you were away" briefing card** — on absent→present flip, top-center, auto-dismiss ~15s or click:
   ```
   ◈ YOU WERE AWAY · 42 MIN
   · swarm finished cycle 28 (3 commits, 2 intents resolved)
   · "write CHANGELOG" task → ✅ done
   · theme: untouched
   [dismiss]
   ```
   Data from `GET /briefing` (bridge diffs hive state between absent→present edges).
3. **Voice mode in chat** — `/voice` replies render identically to typed (copy button, routing chip, etc.) — one conversation channel.
4. **Presence state chip** — status line gains `● present` / `○ away`.

All additive — keyboard/mouse usage unchanged.

---

## 5. Testing, deployment, rollout

**Simulated (headless, no hardware):**
- Presence state machine: synthetic signals → assert transitions (2-tick present, 90s absent, ambiguous→LLM)
- Command parser: transcript strings → trigger/no-trigger/ambient classification
- Bridge endpoints: `/voice`, `/presence`, `/briefing` with mocked hive state
- Away-briefing diff: snapshot→change→diff→narrative

**Hardware (manual):**
- Launch sentry → tray icon → Windows camera/mic permissions
- "orb, what time is it" → hear reply
- Walk away 90s → ear dormant, orb shows away
- Return → briefing card with real away-events

**Deployment:**
- `orb_sentry_watchdog.py` (no_agent cron, 5m) keeps sentry alive
- Sentry + bridge auto-start together; tray shows both statuses
- Deps via `uv` venv (pystray, sounddevice, faster-whisper, mediapipe, elevenlabs)
- `?selftest=` hooks + existing error-trap pattern

**Rollout order:**
1. Bridge endpoints (+ selftests) — independently verifiable
2. orb-sentry.py core: mic → presence gate → whisper → /voice (fake mic test)
3. TTS replies (ElevenLabs)
4. Orb page UI (ear indicator, briefing card)
5. Watchdog + tray polish

---

*Generated via superpowers brainstorming → approved section-by-section by user (2026-08-14).*
