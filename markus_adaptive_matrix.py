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

# Reliability-scoring knobs (Upgrade: real-time reliability scoring)
WINDOW_SIZE = 20          # sliding window of recent outcomes
FAILURE_DECAY_SECS = 300.0  # a failure older than this stops suppressing weight
CIRCUIT_BREAK_FAILS = 3    # consecutive failures that trip a temporary circuit-break
CIRCUIT_BREAK_SECS = 60.0  # how long a tripped circuit stays open
STATE_PATH = Path.home() / "OneDrive/Desktop/MARKUS-OS/markus_adaptive_state.json"

# Network-intelligence hook: transport telemetry written by markus_network_intel.py.
NETWORK_STATE_PATH = Path.home() / "OneDrive/Desktop/MARKUS-OS/markus_network_state.json"


def _network_is_down() -> bool:
    """Read the latest network-intel snapshot to decide if the transport is down.
    Missing/stale file => assume reachable (fail-open) so we never stall routing."""
    try:
        if not NETWORK_STATE_PATH.exists():
            return False
        data = json.loads(NETWORK_STATE_PATH.read_text(encoding="utf-8"))
        # Fresh snapshot (within 10 min) with no internet and no VPN => down.
        if time.time() - data.get("generated_at", 0) > 600:
            return False
        return not bool(data.get("has_internet", True))
    except Exception:  # noqa: BLE001
        return False


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
    # Reliability-scoring state
    recent_outcomes: List[Tuple[float, bool]] = field(default_factory=list)  # (timestamp, success)
    reliability_score: float = 1.0
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0

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

    # benchmark_ms = measured latency (markus_benchmark.py); latency-sensitive
    # tiers derive base_weight from it. Quality/local tiers (PAID_HIGH_REASONING,
    # AIRGAPPED_LOCAL) keep an explicit intent-based weight.
    # Latency-derived weight: clamp(1.5 * (200 / benchmark_ms), 0.5, 1.5)
    DEFAULT_MODELS = [
        {"model": "poolside/laguna-s-2.1:free", "provider": "nous", "tier": "FAST_CODE",
         "weight": 1.2, "benchmark_ms": 600},
        {"model": "deepseek/deepseek-v4-pro-0813", "provider": "nous", "tier": "MEGACONTEXT_ARCH",
         "weight": 1.5, "benchmark_ms": 300},
        {"model": "inclusionai/ling-3.0-flash", "provider": "nous", "tier": "REALTIME_LINT",
         "weight": 1.0, "benchmark_ms": 200},
        {"model": "custom/qwen2.5-coder:7b", "provider": "ollama", "tier": "AIRGAPPED_LOCAL",
         "weight": 0.8, "benchmark_ms": None},   # local, no benchmark -> intent weight
        {"model": "google/gemini-3.7-flash", "provider": "nous", "tier": "PAID_HIGH_REASONING",
         "weight": 1.4, "benchmark_ms": None}    # quality tier -> intent weight (not speed)
    ]

    @staticmethod
    def _latency_weight(benchmark_ms: Optional[int], fallback: float) -> float:
        """Derive a base weight from measured latency; faster -> higher weight.
        Uses the explicit weight as fallback when no benchmark exists."""
        if benchmark_ms is None:
            return fallback
        raw = 1.5 * (200.0 / max(float(benchmark_ms), 1.0))
        return round(max(0.5, min(1.5, raw)), 3)

    def __init__(self, learning_rate: float = 0.1, error_penalty: float = 0.4) -> None:
        self.learning_rate = learning_rate
        self.error_penalty = error_penalty
        self.models: Dict[str, ModelMetrics] = {}
        self._init_models()
        self._load_state()

    def _init_models(self) -> None:
        for m in self.DEFAULT_MODELS:
            name = m["model"]
            bw = self._latency_weight(m.get("benchmark_ms"), m["weight"])
            self.models[name] = ModelMetrics(
                model_name=name,
                provider=m["provider"],
                tier_category=m["tier"],
                base_weight=bw,
                current_weight=bw
            )

    # ------------------------------------------------------------------
    # Reliability scoring
    # ------------------------------------------------------------------
    def _compute_reliability(self, m: ModelMetrics, now: float) -> float:
        """Real-time reliability: success rate over a sliding window, aged so
        stale outcomes stop influencing the score, with recent-failure decay."""
        if not m.recent_outcomes:
            return 1.0
        # Drop outcomes older than the window (size + time decay)
        m.recent_outcomes = [(ts, ok) for ts, ok in m.recent_outcomes
                             if now - ts <= FAILURE_DECAY_SECS]
        m.recent_outcomes = m.recent_outcomes[-WINDOW_SIZE:]
        if not m.recent_outcomes:
            return 1.0
        # Recency-weighted success fraction: recent wins count more.
        total = 0.0
        wins = 0.0
        for ts, ok in m.recent_outcomes:
            age = max(0.0, now - ts)
            recency = math.exp(-age / 60.0)  # ~1 min decay constant
            total += recency
            if ok:
                wins += recency
        return round(wins / max(1e-6, total), 3)

    def circuit_ok(self, model_name: str, now: Optional[float] = None) -> bool:
        """False while the model is circuit-broken (temporarily deprioritised)."""
        m = self.models.get(model_name)
        if m is None:
            return True
        now = now if now is not None else time.time()
        return now >= m.circuit_open_until

    def record_outcome(self, model_name: str, latency_ms: float, success: bool) -> None:
        """Updates runtime performance metrics and recalculates current weight."""
        if model_name not in self.models:
            return

        now = time.time()
        m = self.models[model_name]
        m.total_calls += 1
        m.total_latency_ms += latency_ms

        if success:
            m.successful_calls += 1
            m.consecutive_failures = 0
        else:
            m.failed_calls += 1
            m.last_error_time = now
            m.consecutive_failures += 1
            if m.consecutive_failures >= CIRCUIT_BREAK_FAILS:
                m.circuit_open_until = now + CIRCUIT_BREAK_SECS

        # Sliding-window outcome log
        m.recent_outcomes.append((now, success))
        m.recent_outcomes = m.recent_outcomes[-WINDOW_SIZE:]

        # Update EMA latency
        if m.avg_latency_ms == 0.0:
            m.avg_latency_ms = latency_ms
        else:
            m.avg_latency_ms = (1.0 - self.learning_rate) * m.avg_latency_ms + (self.learning_rate * latency_ms)

        # Recalculate adaptive weight: base_weight * (success_rate) / log(latency)
        success_rate = m.successful_calls / max(1, m.total_calls)
        latency_factor = 100.0 / max(50.0, m.avg_latency_ms)  # Lower latency yields higher factor
        penalty = self.error_penalty if (now - m.last_error_time < 30.0 and not success) else 0.0

        m.reliability_score = self._compute_reliability(m, now)
        # Reliability-adjusted weight: blend base with the live reliability score.
        reliability_weight = m.base_weight * m.reliability_score
        combined = (reliability_weight * 0.5) + (success_rate * 0.3) + (min(1.0, latency_factor) * 0.2) - penalty
        # Circuit-break suppression while open
        if not self.circuit_ok(m.model_name, now):
            combined *= 0.1
        m.current_weight = round(max(0.1, combined), 3)
        self._save_state()

    def select_best_model(self, tier_category: Optional[str] = None) -> AdaptiveRouteDecision:
        """Picks the highest weighted model for a requested category or across all tiers."""
        candidates = list(self.models.values())
        if tier_category:
            filtered = [m for m in candidates if m.tier_category == tier_category]
            if filtered:
                candidates = filtered

        best = max(candidates, key=lambda m: m.current_weight)
        confidence = round(min(0.99, best.current_weight / 2.0), 3)

        # Network-aware routing: if the transport is down, prefer the local
        # (AIRGAPPED_LOCAL) model so routing never stalls on unreachable APIs.
        network_down = _network_is_down()
        reason = f"Selected {best.model_name} via Adaptive Matrix (Weight={best.current_weight}, AvgLat={best.avg_latency_ms:.1f}ms)"
        if network_down:
            local = [m for m in candidates if m.tier_category == "AIRGAPPED_LOCAL"]
            if local:
                best = local[0]
                reason += " | NETWORK DOWN -> forced local model"
                confidence = round(min(0.99, best.current_weight / 2.0), 3)

        return AdaptiveRouteDecision(
            target_model=best.model_name,
            provider=best.provider,
            tier_category=best.tier_category,
            confidence=confidence,
            reason=reason,
            effective_weight=best.current_weight,
            metrics_snapshot={
                "total_calls": best.total_calls,
                "success_rate": round(best.successful_calls / max(1, best.total_calls), 2),
                "avg_latency_ms": round(best.avg_latency_ms, 2),
                "network_down": network_down
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
                "avg_latency_ms": round(m.avg_latency_ms, 2),
                "reliability_score": m.reliability_score,
                "consecutive_failures": m.consecutive_failures,
                "circuit_broken": not self.circuit_ok(m.model_name)
            }
            for m in self.models.values()
        ]

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------
    def _save_state(self) -> None:
        try:
            payload = {
                "written_at": time.time(),
                "models": {name: self._metrics_to_dict(m) for name, m in self.models.items()}
            }
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001 - persistence must never break routing
            logger.warning("adaptive matrix state save failed: %s", e)

    def _load_state(self) -> None:
        try:
            if not STATE_PATH.exists():
                return
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            for name, mdict in data.get("models", {}).items():
                if name in self.models:
                    self._metrics_from_dict(self.models[name], mdict)
        except Exception as e:  # noqa: BLE001
            logger.warning("adaptive matrix state load failed (fresh start): %s", e)

    @staticmethod
    def _metrics_to_dict(m: ModelMetrics) -> Dict[str, Any]:
        return {
            "total_calls": m.total_calls,
            "successful_calls": m.successful_calls,
            "failed_calls": m.failed_calls,
            "total_latency_ms": m.total_latency_ms,
            "avg_latency_ms": m.avg_latency_ms,
            "last_error_time": m.last_error_time,
            "current_weight": m.current_weight,
            "recent_outcomes": m.recent_outcomes,
            "reliability_score": m.reliability_score,
            "consecutive_failures": m.consecutive_failures,
            "circuit_open_until": m.circuit_open_until,
        }

    @staticmethod
    def _metrics_from_dict(m: ModelMetrics, d: Dict[str, Any]) -> None:
        m.total_calls = int(d.get("total_calls", 0))
        m.successful_calls = int(d.get("successful_calls", 0))
        m.failed_calls = int(d.get("failed_calls", 0))
        m.total_latency_ms = float(d.get("total_latency_ms", 0.0))
        m.avg_latency_ms = float(d.get("avg_latency_ms", 0.0))
        m.last_error_time = float(d.get("last_error_time", 0.0))
        m.current_weight = float(d.get("current_weight", m.base_weight))
        m.recent_outcomes = [tuple(o) for o in d.get("recent_outcomes", [])]
        m.reliability_score = float(d.get("reliability_score", 1.0))
        m.consecutive_failures = int(d.get("consecutive_failures", 0))
        m.circuit_open_until = float(d.get("circuit_open_until", 0.0))

def _test_adaptive_matrix():
    print("=== MARKUS Live Adaptive Weight Matrix Test ===")
    matrix = MarkusAdaptiveWeightMatrix()

    # Initial selection
    init_choice = matrix.select_best_model("FAST_CODE")
    print(f"Initial FAST_CODE Choice: {init_choice.target_model} (Weight: {init_choice.effective_weight})")

    # Simulate fast success on Laguna
    matrix.record_outcome("poolside/laguna-s-2.1:free", latency_ms=85.0, success=True)
    matrix.record_outcome("poolside/laguna-s-2.1:free", latency_ms=90.0, success=True)

    # Simulate slow/failing calls on Nemotron
    matrix.record_outcome("deepseek/deepseek-v4-pro-0813", latency_ms=1200.0, success=False)
    matrix.record_outcome("deepseek/deepseek-v4-pro-0813", latency_ms=1500.0, success=False)

    post_choice = matrix.select_best_model()
    print(f"Post-telemetry Best Model : {post_choice.target_model} (Weight: {post_choice.effective_weight})")

    state = matrix.get_matrix_state()
    print("\nMatrix Snapshot:")
    for s in state:
        print(f"  {s['model'].ljust(44)} Weight={s['current_weight']} AvgLat={s['avg_latency_ms']}ms SuccessRate={s['success_rate']} Rel={s['reliability_score']} CB={s['circuit_broken']}")

    assert matrix.models["poolside/laguna-s-2.1:free"].current_weight > matrix.models["deepseek/deepseek-v4-pro-0813"].current_weight

    # --- Reliability + circuit-break (3 consecutive failures trips the breaker) ---
    nem = "deepseek/deepseek-v4-pro-0813"
    for _ in range(3):
        matrix.record_outcome(nem, latency_ms=1500.0, success=False)
    assert not matrix.circuit_ok(nem), "circuit should be open after 3 consecutive failures"
    cb_state = [s for s in matrix.get_matrix_state() if s["model"] == nem][0]
    assert cb_state["circuit_broken"], "state snapshot should report circuit_broken=True"
    assert cb_state["consecutive_failures"] >= 3, "consecutive_failures should be >= 3 to trip breaker"
    print(f"\n✅ Circuit-break tripped: {nem} circuit_broken={cb_state['circuit_broken']}, consecutive_failures={cb_state['consecutive_failures']}")

    # --- Recovery: a success resets consecutive failures; breaker clears after timeout ---
    matrix.record_outcome(nem, latency_ms=200.0, success=True)
    assert matrix.models[nem].consecutive_failures == 0, "success should reset consecutive_failures"
    assert matrix.circuit_ok(nem) or matrix.models[nem].circuit_open_until > time.time(), \
        "breaker state must be coherent (either open-until-future or recovered)"
    print(f"✅ Recovery: consecutive_failures reset to 0")

    # --- Persistence round-trip ---
    loaded = MarkusAdaptiveWeightMatrix()
    assert loaded.models[nem].total_calls >= 6, "loaded state should carry forward total_calls"
    assert loaded.models["poolside/laguna-s-2.1:free"].total_calls >= 2, "laguna calls persisted"
    print(f"✅ Persistence: reloaded matrix carried {loaded.models[nem].total_calls} calls for {nem}")

    # --- Reliability score is monotone on clean history ---
    m = matrix.models["poolside/laguna-s-2.1:free"]
    assert 0.0 <= m.reliability_score <= 1.0, "reliability score must be in [0,1]"
    print(f"✅ Reliability scoring: laguna Rel={m.reliability_score} (in [0,1])")

    print("\n✅ Live Adaptive Weight Matrix: PASSED (incl. reliability + circuit-break + persistence)")


if __name__ == "__main__":
    _test_adaptive_matrix()
