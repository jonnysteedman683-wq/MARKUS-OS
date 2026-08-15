#!/usr/bin/env python3
"""
MARKUS OS Live Adaptive Weight Matrix for Semantic Intent Routing (Upgrade 24)
Provides dynamic latency/cost/error-rate feedback adjustment for multi-model dispatch.
Adapts routing weights dynamically based on live runtime feedback and circuit-breaker telemetry.
"""

from __future__ import annotations
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Markus.AdaptiveMatrix")

@dataclass
class ModelMetrics:
    model_name: str
    provider: str
    tier_category: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_error_time: float = 0.0
    base_weight: float = 1.0
    current_weight: float = 1.0

@dataclass
class AdaptiveRouteDecision:
    target_model: str
    provider: str
    tier_category: str
    confidence: float
    reason: str
    effective_weight: float
    metrics_snapshot: Dict[str, Any]

class MarkusAdaptiveWeightMatrix:
    """
    Dynamically tracks model performance and updates intent routing weights
    based on exponential moving average latency and success rate penalties.
    """

    DEFAULT_MODELS = [
        {"model": "openrouter/poolside/laguna-s-2.1:free", "provider": "openrouter", "tier": "FAST_CODE", "weight": 1.2},
        {"model": "openrouter/nvidia/nemotron-3-ultra:free", "provider": "openrouter", "tier": "MEGACONTEXT_ARCH", "weight": 1.5},
        {"model": "openrouter/inclusionai/ling-3.0-flash:free", "provider": "openrouter", "tier": "REALTIME_LINT", "weight": 1.0},
        {"model": "custom/qwen2.5-coder:7b", "provider": "ollama", "tier": "AIRGAPPED_LOCAL", "weight": 0.8},
        {"model": "google/gemini-3.7-flash", "provider": "nous", "tier": "PAID_HIGH_REASONING", "weight": 1.4}
    ]

    def __init__(self, learning_rate: float = 0.1, error_penalty: float = 0.4) -> None:
        self.learning_rate = learning_rate
        self.error_penalty = error_penalty
        self.models: Dict[str, ModelMetrics] = {}
        self._init_models()

    def _init_models(self) -> None:
        for m in self.DEFAULT_MODELS:
            name = m["model"]
            self.models[name] = ModelMetrics(
                model_name=name,
                provider=m["provider"],
                tier_category=m["tier"],
                base_weight=m["weight"],
                current_weight=m["weight"]
            )

    def record_outcome(self, model_name: str, latency_ms: float, success: bool) -> None:
        """Updates runtime performance metrics and recalculates current weight."""
        if model_name not in self.models:
            return

        m = self.models[model_name]
        m.total_calls += 1
        m.total_latency_ms += latency_ms

        if success:
            m.successful_calls += 1
        else:
            m.failed_calls += 1
            m.last_error_time = time.time()

        # Update EMA latency
        if m.avg_latency_ms == 0.0:
            m.avg_latency_ms = latency_ms
        else:
            m.avg_latency_ms = (1.0 - self.learning_rate) * m.avg_latency_ms + (self.learning_rate * latency_ms)

        # Recalculate adaptive weight: base_weight * (success_rate) / log(latency)
        success_rate = m.successful_calls / max(1, m.total_calls)
        latency_factor = 100.0 / max(50.0, m.avg_latency_ms)  # Lower latency yields higher factor
        penalty = self.error_penalty if (time.time() - m.last_error_time < 30.0 and not success) else 0.0

        new_weight = (m.base_weight * 0.5) + (success_rate * 0.3) + (min(1.0, latency_factor) * 0.2) - penalty
        m.current_weight = round(max(0.1, new_weight), 3)

    def select_best_model(self, tier_category: Optional[str] = None) -> AdaptiveRouteDecision:
        """Picks the highest weighted model for a requested category or across all tiers."""
        candidates = list(self.models.values())
        if tier_category:
            filtered = [m for m in candidates if m.tier_category == tier_category]
            if filtered:
                candidates = filtered

        best = max(candidates, key=lambda m: m.current_weight)
        confidence = round(min(0.99, best.current_weight / 2.0), 3)

        return AdaptiveRouteDecision(
            target_model=best.model_name,
            provider=best.provider,
            tier_category=best.tier_category,
            confidence=confidence,
            reason=f"Selected {best.model_name} via Adaptive Matrix (Weight={best.current_weight}, AvgLat={best.avg_latency_ms:.1f}ms)",
            effective_weight=best.current_weight,
            metrics_snapshot={
                "total_calls": best.total_calls,
                "success_rate": round(best.successful_calls / max(1, best.total_calls), 2),
                "avg_latency_ms": round(best.avg_latency_ms, 2)
            }
        )

    def get_matrix_state(self) -> List[Dict[str, Any]]:
        return [
            {
                "model": m.model_name,
                "provider": m.provider,
                "tier": m.tier_category,
                "base_weight": m.base_weight,
                "current_weight": m.current_weight,
                "total_calls": m.total_calls,
                "success_rate": round(m.successful_calls / max(1, m.total_calls), 2),
                "avg_latency_ms": round(m.avg_latency_ms, 2)
            }
            for m in self.models.values()
        ]

def _test_adaptive_matrix():
    print("=== MARKUS Live Adaptive Weight Matrix Test ===")
    matrix = MarkusAdaptiveWeightMatrix()

    # Initial selection
    init_choice = matrix.select_best_model("FAST_CODE")
    print(f"Initial FAST_CODE Choice: {init_choice.target_model} (Weight: {init_choice.effective_weight})")

    # Simulate fast success on Laguna
    matrix.record_outcome("openrouter/poolside/laguna-s-2.1:free", latency_ms=85.0, success=True)
    matrix.record_outcome("openrouter/poolside/laguna-s-2.1:free", latency_ms=90.0, success=True)

    # Simulate slow/failing calls on Nemotron
    matrix.record_outcome("openrouter/nvidia/nemotron-3-ultra:free", latency_ms=1200.0, success=False)
    matrix.record_outcome("openrouter/nvidia/nemotron-3-ultra:free", latency_ms=1500.0, success=False)

    post_choice = matrix.select_best_model()
    print(f"Post-telemetry Best Model : {post_choice.target_model} (Weight: {post_choice.effective_weight})")

    state = matrix.get_matrix_state()
    print("\nMatrix Snapshot:")
    for s in state:
        print(f"  {s['model'].ljust(44)} Weight={s['current_weight']} AvgLat={s['avg_latency_ms']}ms SuccessRate={s['success_rate']}")

    assert matrix.models["openrouter/poolside/laguna-s-2.1:free"].current_weight > matrix.models["openrouter/nvidia/nemotron-3-ultra:free"].current_weight
    print("\n✅ Live Adaptive Weight Matrix: PASSED")

if __name__ == "__main__":
    _test_adaptive_matrix()
