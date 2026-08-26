"""
MARKUS OS Multi-Model Semantic Intent Routing Engine (Upgrade 5)
Provides zero-latency semantic classification and cost/latency-optimized
model dispatch across free-tier and local inference providers.
"""

from __future__ import annotations
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Optional adaptive-matrix integration (present in the repo).
from markus_adaptive_matrix import MarkusAdaptiveWeightMatrix

# SINGLE source of truth for model routing: the brain backend's tier map.
from markus_brain_backend import TIER_MODELS

# Network telemetry written by markus_network_intel.py (auto-offline detection).
NETWORK_STATE_PATH = Path(__file__).resolve().parent / "markus_network_state.json"


@dataclass
class RouteDecision:
    target_model: str
    provider: str
    tier_category: str
    confidence: float
    reason: str
    estimated_tokens: int
    # Enriched feedback fields (populated when matrix telemetry is wired).
    matrix_model: Optional[str] = None
    matrix_weight: Optional[float] = None
    network_down: bool = False

class MarkusIntentRouter:
    """Triage engine mapping intents to the optimal model based on AST and semantic cues."""

    # Provider/Model Constants — from the brain backend's SINGLE source of
    # truth so target_model == the model the brain actually calls.
    # (pre-2026-08-26 these were phantom openrouter/*:free IDs that no client
    # could call; telemetry was learning from a model that never ran.)
    MODEL_CODE_FAST = TIER_MODELS["CODE_SPECIALIST"]
    MODEL_MEGACONTEXT_ARCH = TIER_MODELS["MEGACONTEXT_ARCH"]
    MODEL_REALTIME_LINT = TIER_MODELS["FAST_TELEMETRY"]
    MODEL_AIRGAPPED_LOCAL = "custom/qwen2.5-coder:7b"

    def __init__(self, use_matrix: bool = True) -> None:
        self.code_patterns = re.compile(r"\b(def|class|function|import|refactor|optimize|ast|compile|bug|test|async|return)\b", re.IGNORECASE)
        self.arch_patterns = re.compile(r"\b(architecture|multi-file|roadmap|system design|pipeline|migrate|database schema|specification)\b", re.IGNORECASE)
        self.lint_patterns = re.compile(r"\b(status|health|ping|check|lint|preflight|metrics|heartbeat)\b", re.IGNORECASE)
        self.use_matrix = use_matrix
        self.matrix: Optional[MarkusAdaptiveWeightMatrix] = \
            MarkusAdaptiveWeightMatrix() if use_matrix else None

    def _network_down(self) -> bool:
        """Auto-offline detection from the network-intel snapshot. Fail-open."""
        try:
            if not NETWORK_STATE_PATH.exists():
                return False
            data = json.loads(NETWORK_STATE_PATH.read_text(encoding="utf-8"))
            if time.time() - data.get("generated_at", 0) > 600:
                return False
            return not bool(data.get("has_internet", True))
        except Exception:  # noqa: BLE001
            return False

    def record_outcome(self, target_model: str, latency_ms: float, success: bool) -> None:
        """Feed post-dispatch telemetry back into the adaptive matrix so routing
        weights learn from real traffic. No-op when the matrix is disabled."""
        if self.matrix is not None:
            self.matrix.record_outcome(target_model, latency_ms, success)

    def _apply_matrix(self, decision: RouteDecision) -> RouteDecision:
        """Attach the matrix's highest-weighted model to a route decision
        (advisory signal; the router's rule still governs the primary target)."""
        if self.matrix is not None:
            best = self.matrix.select_best_model()
            decision.matrix_model = best.target_model
            decision.matrix_weight = best.effective_weight
            decision.network_down = best.metrics_snapshot.get("network_down", False)
        return decision

    def route_intent(self, prompt: str, context_tokens: int = 0, is_offline: bool = False) -> RouteDecision:
        estimated_tokens = len(prompt.split()) * 2 + context_tokens

        # Auto-offline detection: if the transport is down (fresh network-intel
        # snapshot says no internet), route to the local model regardless.
        network_down = self._network_down()
        if is_offline or network_down:
            return RouteDecision(
                target_model=self.MODEL_AIRGAPPED_LOCAL,
                provider="custom",
                tier_category="OFFLINE_LOCAL",
                confidence=1.0,
                reason=("System offline / local fallback mode requested."
                        if is_offline else "Network down -> forced local model (network-intel)."),
                estimated_tokens=estimated_tokens,
                network_down=network_down
            )

        # 2. Megacontext / Architecture Planning Rule (>15k tokens or multi-file architecture keywords)
        if estimated_tokens > 15000 or self.arch_patterns.search(prompt):
            return self._apply_matrix(RouteDecision(
                target_model=self.MODEL_MEGACONTEXT_ARCH,
                provider="nous",
                tier_category="MEGACONTEXT_ARCH",
                confidence=0.92,
                reason="Detected high token volume or broad system architecture planning scope.",
                estimated_tokens=estimated_tokens
            ))

        # 3. Code Optimization & AST Manipulation Rule
        if self.code_patterns.search(prompt):
            return self._apply_matrix(RouteDecision(
                target_model=self.MODEL_CODE_FAST,
                provider="nous",
                tier_category="CODE_SPECIALIST",
                confidence=0.95,
                reason="Detected code refactoring, AST optimization, or functional implementation.",
                estimated_tokens=estimated_tokens
            ))

        # 4. Fast Real-Time Linting / Status
        if self.lint_patterns.search(prompt):
            return self._apply_matrix(RouteDecision(
                target_model=self.MODEL_REALTIME_LINT,
                provider="nous",
                tier_category="FAST_TELEMETRY",
                confidence=0.90,
                reason="Detected fast status, health, or telemetry inspection intent.",
                estimated_tokens=estimated_tokens
            ))

        # Default to high-performance coding MoE
        return self._apply_matrix(RouteDecision(
            target_model=self.MODEL_CODE_FAST,
            provider="nous",
            tier_category="DEFAULT_BALANCED",
            confidence=0.85,
            reason="Balanced default routing via Laguna S 2.1 MoE.",
            estimated_tokens=estimated_tokens
        ))

if __name__ == "__main__":
    router = MarkusIntentRouter()

    test_prompts = [
        "Optimize the AST constant folding transformer in markus_evolver.py",
        "Design the complete multi-file distributed swarm architecture across 5 repositories",
        "Check system health and latency metrics for port 8128",
        "Explain the microkernel design while air-gapped"
    ]

    print("=== MARKUS Intent Routing Benchmark ===")
    for p in test_prompts:
        is_off = "air-gapped" in p
        res = router.route_intent(p, is_offline=is_off)
        print(f"\nPrompt: '{p}'")
        print(f" -> Target:     {res.target_model}")
        print(f" -> Category:   {res.tier_category} (Conf: {res.confidence*100:.0f}%)")
        print(f" -> Reason:     {res.reason}")
        if res.matrix_model:
            print(f" -> Matrix adv: {res.matrix_model} (w={res.matrix_weight}) | network_down={res.network_down}")

    # --- Feedback loop: route -> record outcome -> matrix learns ---
    print("\n=== Feedback Loop Test ===")
    lag = TIER_MODELS["CODE_SPECIALIST"]
    # Demote laguna (simulate a slow failure) so there is room to recover.
    router.record_outcome(lag, latency_ms=3000.0, success=False)
    dipped = router.matrix.models[lag].current_weight
    # Fast successes should now raise the weight back toward its ceiling.
    for _ in range(5):
        router.record_outcome(lag, latency_ms=80.0, success=True)
    recovered = router.matrix.models[lag].current_weight
    print(f"Laguna weight: dipped to {dipped}, recovered to {recovered} after 5 fast successes")
    assert recovered > dipped, "fast successes after a dip should raise the model's routing weight"
    print("[OK] Feedback loop: router record_outcome -> adaptive matrix: PASSED")
