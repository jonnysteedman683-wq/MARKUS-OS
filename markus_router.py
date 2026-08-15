"""
MARKUS OS Multi-Model Semantic Intent Routing Engine (Upgrade 5)
Provides zero-latency semantic classification and cost/latency-optimized
model dispatch across free-tier and local inference providers.
"""

from __future__ import annotations
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class RouteDecision:
    target_model: str
    provider: str
    tier_category: str
    confidence: float
    reason: str
    estimated_tokens: int

class MarkusIntentRouter:
    """Triage engine mapping intents to the optimal model based on AST and semantic cues."""

    # Provider/Model Constants
    MODEL_CODE_FAST = "openrouter/poolside/laguna-s-2.1:free"
    MODEL_MEGACONTEXT_ARCH = "openrouter/nvidia/nemotron-3-ultra:free"
    MODEL_REALTIME_LINT = "openrouter/inclusionai/ling-3.0-flash:free"
    MODEL_AIRGAPPED_LOCAL = "custom/qwen2.5-coder:7b"

    def __init__(self) -> None:
        self.code_patterns = re.compile(r"\b(def|class|function|import|refactor|optimize|ast|compile|bug|test|async|return)\b", re.IGNORECASE)
        self.arch_patterns = re.compile(r"\b(architecture|multi-file|roadmap|system design|pipeline|migrate|database schema|specification)\b", re.IGNORECASE)
        self.lint_patterns = re.compile(r"\b(status|health|ping|check|lint|preflight|metrics|heartbeat)\b", re.IGNORECASE)

    def route_intent(self, prompt: str, context_tokens: int = 0, is_offline: bool = False) -> RouteDecision:
        estimated_tokens = len(prompt.split()) * 2 + context_tokens
        
        # 1. Air-Gapped Local Rule
        if is_offline:
            return RouteDecision(
                target_model=self.MODEL_AIRGAPPED_LOCAL,
                provider="custom",
                tier_category="OFFLINE_LOCAL",
                confidence=1.0,
                reason="System offline / local fallback mode requested.",
                estimated_tokens=estimated_tokens
            )

        # 2. Megacontext / Architecture Planning Rule (>15k tokens or multi-file architecture keywords)
        if estimated_tokens > 15000 or self.arch_patterns.search(prompt):
            return RouteDecision(
                target_model=self.MODEL_MEGACONTEXT_ARCH,
                provider="openrouter",
                tier_category="MEGACONTEXT_ARCH",
                confidence=0.92,
                reason="Detected high token volume or broad system architecture planning scope.",
                estimated_tokens=estimated_tokens
            )

        # 3. Code Optimization & AST Manipulation Rule
        if self.code_patterns.search(prompt):
            return RouteDecision(
                target_model=self.MODEL_CODE_FAST,
                provider="openrouter",
                tier_category="CODE_SPECIALIST",
                confidence=0.95,
                reason="Detected code refactoring, AST optimization, or functional implementation.",
                estimated_tokens=estimated_tokens
            )

        # 4. Fast Real-Time Linting / Status
        if self.lint_patterns.search(prompt):
            return RouteDecision(
                target_model=self.MODEL_REALTIME_LINT,
                provider="openrouter",
                tier_category="FAST_TELEMETRY",
                confidence=0.90,
                reason="Detected fast status, health, or telemetry inspection intent.",
                estimated_tokens=estimated_tokens
            )

        # Default to high-performance coding MoE
        return RouteDecision(
            target_model=self.MODEL_CODE_FAST,
            provider="openrouter",
            tier_category="DEFAULT_BALANCED",
            confidence=0.85,
            reason="Balanced default routing via Laguna S 2.1 MoE.",
            estimated_tokens=estimated_tokens
        )

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
