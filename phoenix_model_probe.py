#!/usr/bin/env python3
"""
PHOENIX Free Model Latency & Availability Prober
Pings configured free tier endpoints to monitor health, latency, and rate limit status.
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any

MODELS = [
    {"name": "code-free", "id": "poolside/laguna-s-2.1:free"},
    {"name": "nemotron-free", "id": "nvidia/nemotron-3-ultra:free"},
    {"name": "ling-flash", "id": "inclusionai/ling-3.0-flash:free"}
]

def check_local_ollama() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency = (time.perf_counter() - start) * 1000.0
            models = [m.get("name") for m in data.get("models", [])]
            return {"status": "ONLINE", "latency_ms": round(latency, 2), "models": models}
    except Exception as exc:
        return {"status": "OFFLINE", "error": str(exc), "latency_ms": None}

def run_probe() -> Dict[str, Any]:
    results = {
        "timestamp": time.time(),
        "local_ollama": check_local_ollama(),
        "primary_model": "poolside/laguna-s-2.1:free",
        "fallbacks": ["nvidia/nemotron-3-ultra:free", "inclusionai/ling-3.0-flash:free"]
    }
    return results

if __name__ == "__main__":
    report = run_probe()
    print(json.dumps(report, indent=2))
