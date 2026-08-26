"""
MARKUS OS Direct Brain Backend (Hermes-Independent)
Replaces the retired `hermes chat -p markus` shell-out with a direct call to
the Nous inference API (OpenAI-compatible /v1/chat/completions). MARKUS now
reads credentials from the shared Hermes auth.json but talks to the model
itself — no Hermes subprocess, no profile dependency.

Model routing follows the intent router's tier_category so cheap models serve
cheap intents and stronger models serve architecture/planning intents.
"""

from __future__ import annotations
import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("Markus.BrainBackend")

AUTH_JSON = Path(os.environ.get(
    "HERMES_AUTH_JSON",
    "C:/Users/jonny/AppData/Local/hermes/auth.json",
))

INFERENCE_BASE = "https://inference-api.nousresearch.com/v1"

# Router tier_category -> Nous model id (cost-aware)
TIER_MODELS: Dict[str, str] = {
    "CODE_SPECIALIST": "deepseek/deepseek-v4-flash",
    "MEGACONTEXT_ARCH": "deepseek/deepseek-v4-pro-0813",
    "FAST_TELEMETRY": "inclusionai/ling-3.0-flash",
    "DEFAULT_BALANCED": "deepseek/deepseek-v4-flash",
    "OFFLINE_LOCAL": "deepseek/deepseek-v4-flash",
}
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

# Cloudflare bans urllib's default UA (HTTP 403 error 1010) — send a browser UA.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def load_nous_key(auth_path: Path = AUTH_JSON) -> Optional[str]:
    """Read the Nous agent/access token from Hermes auth.json (keys never printed)."""
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
        nous = (data.get("providers") or {}).get("nous") or {}
        key = nous.get("agent_key") or nous.get("access_token")
        return key or None
    except Exception as exc:
        logger.error(f"Failed to read Nous key from {auth_path}: {exc}")
        return None


def ask_brain(
    prompt: str,
    model: Optional[str] = None,
    timeout_s: float = 60.0,
    system: str = "You are MARKUS, an autonomous AI operating system. Reply directly and concisely.",
) -> str:
    """Call the Nous inference API directly. Returns the model's reply text.

    On any failure returns a bracketed diagnostic string — never raises, so the
    REST layer can keep serving.
    """
    key = load_nous_key()
    if not key:
        return "(brain offline: no Nous key found in auth.json)"
    model = model or DEFAULT_MODEL

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1024,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{INFERENCE_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": _BROWSER_UA,
            "Accept": "application/json",
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        used_model = data.get("model", model)
        logger.info(f"Brain reply via {used_model} in {time.time()-t0:.1f}s")
        return reply or "(brain offline: empty reply)"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        logger.error(f"Brain HTTP {e.code}: {detail}")
        return f"(brain error: HTTP {e.code})"
    except Exception as exc:
        logger.error(f"Brain call failed: {exc}")
        return f"(brain error: {exc})"


def route_brain_model(tier_category: str) -> str:
    """Map an intent-router tier to the cheapest adequate Nous model."""
    return TIER_MODELS.get(tier_category, DEFAULT_MODEL)


if __name__ == "__main__":
    import sys
    probe = sys.argv[1] if len(sys.argv) > 1 else "Reply with exactly: BRAIN_LIVE"
    print("KEY:", "present" if load_nous_key() else "MISSING")
    print("REPLY:", ask_brain(probe))
