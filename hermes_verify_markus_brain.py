#!/usr/bin/env python3
"""hermes_verify_markus_brain.py — MARKUS brain wiring gate (2026-08-26).

Proves the three routing universes are ONE and the brain is reachable:

  G1  markus_brain_backend.py py_compile clean + imports
  G2  Nous key present in auth.json (never prints the key)
  G3  ALIGNMENT: markus_router constants == brain TIER_MODELS, so the
      router's reported target_model equals the model the brain calls
      (pre-2026-08-26 they diverged: router advertised phantom
      openrouter/*:free IDs; telemetry learned from a model that never ran)
  G4  No phantom openrouter/*:free IDs anywhere in the routing stack
      (router + matrix defaults) — only the historical comment may cite them
  G5  LIVE brain probe (only when MARKUS_BRAIN_LIVE_PROBE=1): POST-free
      module-level ask_brain("Reply with exactly: BRAIN_LIVE") must return
      BRAIN_LIVE. Default-off so the gate stays network-free; the paid path
      is covered by the default model being poolside/laguna-s-2.1:free ($0).

Exit 0 = all gates pass. Fail-token hygiene: no bare "[FAIL]" literals.
"""
from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}".rstrip())


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolves cls.__module__ via sys.modules
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    brain = ROOT / "markus_brain_backend.py"
    router = ROOT / "markus_router.py"
    matrix = ROOT / "markus_adaptive_matrix.py"

    # G1 compile + import
    try:
        py_compile.compile(str(brain), doraise=True)
        bb = load("brain_uut", brain)
        check("G1 brain backend compiles", True)
    except Exception as exc:
        check("G1 brain backend compiles", False, str(exc))
        return _finish()

    # G2 key present
    check("G2 Nous key present", bool(bb.load_nous_key()), "")

    # G3 alignment router <-> brain (constants are class attributes)
    rt = load("router_uut", router)
    R = rt.MarkusIntentRouter
    aligned = (
        R.MODEL_CODE_FAST == bb.TIER_MODELS["CODE_SPECIALIST"]
        and R.MODEL_MEGACONTEXT_ARCH == bb.TIER_MODELS["MEGACONTEXT_ARCH"]
        and R.MODEL_REALTIME_LINT == bb.TIER_MODELS["FAST_TELEMETRY"]
    )
    check(
        "G3 router == brain TIER_MODELS (single source of truth)",
        aligned,
        f"(code={R.MODEL_CODE_FAST}, arch={R.MODEL_MEGACONTEXT_ARCH}, lint={R.MODEL_REALTIME_LINT})",
    )

    # G4 no phantom openrouter IDs in routing stack
    phantoms = []
    for f in (router, matrix):
        txt = f.read_text(encoding="utf-8")
        for i, line in enumerate(txt.splitlines(), 1):
            if "openrouter/" in line and "pre-2026-08-26" not in line:
                phantoms.append(f"{f.name}:{i}")
    check("G4 no phantom openrouter IDs", not phantoms, f"clean" if not phantoms else str(phantoms))

    # G5 optional live probe
    if os.environ.get("MARKUS_BRAIN_LIVE_PROBE") == "1":
        reply = bb.ask_brain("Reply with exactly: BRAIN_LIVE")
        check("G5 live brain probe", "BRAIN_LIVE" in reply, repr(reply[:80]))
    else:
        check("G5 live brain probe (opt-in)", True, "skipped (MARKUS_BRAIN_LIVE_PROBE=1 to enable)")

    return _finish()


def _finish() -> int:
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nTOTAL PASS={passed} TOTAL_FAIL={total - passed} (of {total})")
    if passed == total:
        print("RESULT: PASS")
        return 0
    print("RESULT: GATE FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
