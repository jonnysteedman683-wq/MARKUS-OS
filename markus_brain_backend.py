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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("Markus.BrainBackend")

AUTH_JSON = Path(os.environ.get(
    "HERMES_AUTH_JSON",
    "C:/Users/jonny/AppData/Local/hermes/auth.json",
))

INFERENCE_BASE = "https://inference-api.nousresearch.com/v1"

# Router tier_category -> Nous model id (cost-aware). This is the SINGLE
# source of truth: markus_router.py imports it, so the router's reported
# target_model always equals the model the brain actually calls.
# Prices verified live 2026-08-26 against the Nous /models catalog:
#   laguna-s-2.1:free      $0 / $0            (free code/default tier)
#   deepseek-v4-pro-0813   $0.8976/M / $2.69/M (arch/planning, selectively used)
#   ling-3.0-flash         $0.0168/M / $0.05/M (cheapest paid, telemetry)
#   custom/qwen2.5-coder:7b  offline-only signal (never called over network)
TIER_MODELS: Dict[str, str] = {
    "CODE_SPECIALIST": "poolside/laguna-s-2.1:free",
    "MEGACONTEXT_ARCH": "deepseek/deepseek-v4-pro-0813",
    "FAST_TELEMETRY": "inclusionai/ling-3.0-flash",
    "DEFAULT_BALANCED": "poolside/laguna-s-2.1:free",
    "OFFLINE_LOCAL": "custom/qwen2.5-coder:7b",
}
DEFAULT_MODEL = "poolside/laguna-s-2.1:free"

# Per-token prices in USD, verified live 2026-08-26 against the Nous /models
# catalog (prompt, completion). Free/offline models cost zero.
#   deepseek-v4-flash   0.0000000709 / 0.0000001418
#   deepseek-v4-pro-0813 0.0000008976 / 0.0000026928
#   ling-3.0-flash      0.0000000168 / 0.0000000504
#   gemini-3.7-flash    0.0000003000 / 0.0000015000
MODEL_PRICES: Dict[str, tuple[float, float]] = {
    "poolside/laguna-s-2.1:free": (0.0, 0.0),
    "deepseek/deepseek-v4-flash": (0.0000000709, 0.0000001418),
    "deepseek/deepseek-v4-pro-0813": (0.0000008976, 0.0000026928),
    "inclusionai/ling-3.0-flash": (0.0000000168, 0.0000000504),
    "google/gemini-3.7-flash": (0.0000003000, 0.0000015000),
}
COST_LEDGER = Path(os.environ.get(
    "MARKUS_COST_LEDGER",
    "C:/Users/jonny/OneDrive/Desktop/MARKUS-OS/markus_brain_cost_ledger.jsonl",
))
_ledger_lock = __import__("threading").Lock()


def estimate_cost(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Compute USD cost for a call using the per-model price table."""
    p_prompt, p_completion = MODEL_PRICES.get(model, (0.0, 0.0))
    return prompt_tokens * p_prompt + completion_tokens * p_completion


def record_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    tier: str = "",
) -> float:
    """Append one call to the JSONL cost ledger; returns USD cost."""
    cost = estimate_cost(model, prompt_tokens, completion_tokens)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "tier": tier,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost, 12),
        "latency_ms": round(latency_ms, 1),
    }
    try:
        COST_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _ledger_lock, open(COST_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        logger.error(f"Cost ledger write failed: {exc}")
    return cost


def cost_summary() -> dict:
    """Read the ledger and return per-model + total cost summary."""
    totals: Dict[str, float] = {}
    calls = 0
    total_cost = 0.0
    if COST_LEDGER.exists():
        for line in COST_LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            calls += 1
            cost = float(e.get("cost_usd", 0.0))
            total_cost += cost
            totals[e.get("model", "?")] = totals.get(e.get("model", "?"), 0.0) + cost
    return {
        "calls": calls,
        "total_cost_usd": round(total_cost, 8),
        "per_model": {m: round(c, 8) for m, c in totals.items()},
    }

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
    tier: str = "",
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
        elapsed = time.time() - t0
        # c52: per-call cost accounting. Every brain call now lands in the
        # ledger with tokens + USD, priced per-model (free tiers cost zero).
        usage = data.get("usage") or {}
        p_tok = int(usage.get("prompt_tokens", 0) or 0)
        c_tok = int(usage.get("completion_tokens", 0) or 0)
        cost = record_cost(used_model, p_tok, c_tok, elapsed * 1000.0, tier=tier)
        logger.info(
            f"Brain reply via {used_model} in {elapsed:.1f}s "
            f"({p_tok}p+{c_tok}c tokens, ${cost:.8f})"
        )
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
    args = sys.argv[1:]
    if args and args[0] == "--ledger":
        print(json.dumps(cost_summary(), indent=2))
    else:
        probe = args[0] if args else "Reply with exactly: BRAIN_LIVE"
        print("KEY:", "present" if load_nous_key() else "MISSING")
        print("REPLY:", ask_brain(probe))
        print("LEDGER:", json.dumps(cost_summary()))
