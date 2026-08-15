# UX Review Tickets — Generated from Adversarial Test

## RED: Accessibility — Status bar font size (markus_orb_shell.html:96-99)
**Persona quote:** "I'm 55, not 25 — I shouldn't need a magnifying glass"
- **Issue:** `.chip` elements use `font-size: 0.7rem` (≈11px), failing WCAG AA minimum contrast/readability for users over 50
- **Fix:** Increase to `0.85rem` with better color contrast ratio
- **Tag:** ux-review, accessibility

---

## RED: Configuration — Hardcoded localhost binding (markus_standalone/markus_standalone.py:63)
**Persona quote:** "What if I'm SSH'd somewhere?"
- **Issue:** `MARKUS_HTTP_PORT = 8128` is hardcoded with no env var override
- **Fix:** Read from `MARKUS_HOST` and `MARKUS_PORT` environment variables with fallback defaults
- **Tag:** ux-review, config

---

## RED: Accessibility — Small input font (markus_orb_shell.html:71)
**Persona quote:** "My terminal has better readability than this"
- **Issue:** Chat input uses `font-size: 0.9rem` with no zoom preference support
- **Fix:** Add `font-size-adjust` and minimum `1rem` base
- **Tag:** ux-review, accessibility

---

## GREEN: Feature — Optional orb toggle (markus_orb_shell.html:103-166)
**Persona quote:** "This spinning garbage is wasting CPU cycles"
- **Issue:** Orb particle animation runs continuously with no disable option
- **Fix:** Add `DISABLE_ORB=1` env flag that collapses the orb to a static icon
- **Tag:** ux-review, performance

---

## GREEN: Feature — CLI REPL endpoint (markus_server.py)
**Persona quote:** "I don't want to chat with your AI. I want it to rotate my logs."
- **Issue:** Only HTTP chat interface exists — no terminal-friendly batch mode
- **Fix:** Add `/api/repl` endpoint accepting stdin/stdout piping for server automation workflows
- **Tag:** ux-review, cli-tools

---

## YELLOW: Feature — Keyboard shortcuts (markus_orb_shell.html)
**Persona quote:** "No keyboard shortcuts. No way to pipe output."
- **Issue:** All interaction requires mouse — no hot keys for power users
- **Fix:** Implement `/` hotkey to focus chat input, `Ctrl+Enter` to send
- **Tag:** ux-review, power-user

---

## YELLOW: Feature — Batch mode support
**Persona quote:** "No batch mode."
- **Issue:** No way to queue multiple tasks or pipe results
- **Fix:** Accept `--batch` flag in standalone mode for sequential task execution
- **Tag:** ux-review, automation
