#!/usr/bin/env python3
"""
MARKUS OS Self-Optimizing LLM Context Pruner (Upgrade 22 & Enhancement R3)
Provides token importance scoring, AST-aware structural preservation,
semantic term salience, and recency-decay pruning to compress megacontext prompts
into optimal token budgets without losing critical symbols, errors, or code logic.
"""

from __future__ import annotations
import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Common stop words to deprioritize during importance scoring
STOP_WORDS = {
    "the", "is", "at", "which", "on", "a", "an", "and", "or", "in", "with",
    "to", "of", "for", "by", "this", "that", "it", "from", "as", "be", "are",
    "was", "were", "will", "would", "can", "could", "should", "all", "any"
}

# High-priority token patterns (errors, stack traces, keywords, code identifiers, directives)
PRIORITY_PATTERNS = [
    re.compile(r"\b(def|class|async|await|return|import|from|export|interface|function|type|struct|impl|fn)\b"),
    re.compile(r"\b(Error|Exception|Traceback|FAIL|PASS|CRITICAL|WARNING|SyntaxError|AssertionError)\b"),
    re.compile(r"\b(PRIME-DIRECTIVE|OMNIPRIME|INVARIANT|SECURITY)\b"),
    re.compile(r"\b(https?://\S+|[a-zA-Z0-9_-]+\.[a-zA-Z0-9_.-]+)\b"),
    re.compile(r"[`'\"][a-zA-Z0-9_./\-]+[`'\"]"),
    re.compile(r"\b[A-Za-z0-9_]+(?=\()"),  # Function call signatures
]

INVARIANT_PATTERN = re.compile(r"\b(Traceback|SyntaxError|AssertionError|PRIME-DIRECTIVE)\b")

@dataclass
class ScoredSegment:
    index: int
    text: str
    tokens_estimated: int
    score: float
    is_protected: bool = False
    source_type: str = "text"

@dataclass
class PruneResult:
    original_tokens: int
    pruned_tokens: int
    compression_ratio: float
    retained_segments: int
    total_segments: int
    text: str
    elapsed_ms: float

class MarkusContextPruner:
    """
    Intelligent context pruner applying multi-factor token importance scoring:
    - Salience: Matches with user query / focal terms.
    - Information Density: Ratio of non-stopwords, code symbols, and error markers.
    - Structural Protection: Preserves AST declarations, stack traces, and test results.
    - Recency Bias: Applies temporal decay favoring recent messages/thoughts.
    """

    def __init__(
        self,
        decay_factor: float = 0.05,
        protected_threshold: float = 0.85
    ) -> None:
        self.decay_factor = decay_factor
        self.protected_threshold = protected_threshold

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Heuristic token estimator (~4 chars per token average)."""
        return max(1, len(text) // 4)

    def _score_segment(
        self,
        text: str,
        index: int,
        total_segments: int,
        query_terms: Set[str]
    ) -> Tuple[float, bool]:
        if not text.strip():
            return 0.0, False

        # 1. Base Density Score
        words = re.findall(r"\w+", text.lower())
        if not words:
            return 0.0, False

        content_words = [w for w in words if w not in STOP_WORDS]
        density = len(content_words) / max(1, len(words))

        # 2. Query Term Salience
        query_hits = sum(1 for w in words if w in query_terms)
        salience = min(1.0, query_hits * 0.25)

        # 3. Code / Error Priority Match
        priority_hits = sum(len(p.findall(text)) for p in PRIORITY_PATTERNS)
        priority_boost = min(1.0, priority_hits * 0.2)

        # 4. Recency Bias (linear decay from latest segment)
        recency = 1.0 - (self.decay_factor * (total_segments - 1 - index))
        recency = max(0.2, min(1.0, recency))

        # 5. Composite Score
        composite = (density * 0.25) + (salience * 0.35) + (priority_boost * 0.30) + (recency * 0.10)

        # Check if segment contains critical invariant markers that must not be pruned
        is_protected = (
            bool(INVARIANT_PATTERN.search(text))
            or composite >= self.protected_threshold
        )

        return round(composite, 4), is_protected

    def prune(
        self,
        context: str | List[str],
        max_tokens: int = 2000,
        query: Optional[str] = None
    ) -> PruneResult:
        t0 = time.perf_counter()

        # Normalize into segments (by lines or entries)
        if isinstance(context, str):
            raw_segments = [s for s in context.splitlines(keepends=True) if s.strip()]
        else:
            raw_segments = [str(s) for s in context if str(s).strip()]

        if not raw_segments:
            return PruneResult(0, 0, 1.0, 0, 0, "", 0.0)

        query_terms = set(re.findall(r"\w+", query.lower())) if query else set()
        total_segs = len(raw_segments)

        scored_list: List[ScoredSegment] = []
        total_orig_tokens = 0

        for i, text in enumerate(raw_segments):
            t_count = self.estimate_tokens(text)
            total_orig_tokens += t_count
            score, is_prot = self._score_segment(text, i, total_segs, query_terms)
            scored_list.append(ScoredSegment(
                index=i,
                text=text,
                tokens_estimated=t_count,
                score=score,
                is_protected=is_prot
            ))

        # If already within budget, return as-is
        if total_orig_tokens <= max_tokens:
            t1 = time.perf_counter()
            return PruneResult(
                original_tokens=total_orig_tokens,
                pruned_tokens=total_orig_tokens,
                compression_ratio=1.0,
                retained_segments=total_segs,
                total_segments=total_segs,
                text="".join(raw_segments) if isinstance(context, str) else "\n".join(raw_segments),
                elapsed_ms=round((t1 - t0) * 1000, 2)
            )

        # Sort by priority (protected first, then score descending)
        ranked = sorted(
            scored_list,
            key=lambda s: (1 if s.is_protected else 0, s.score),
            reverse=True
        )

        # Greedily allocate budget
        allocated_tokens = 0
        selected_indices: Set[int] = set()

        for seg in ranked:
            if allocated_tokens + seg.tokens_estimated <= max_tokens:
                selected_indices.add(seg.index)
                allocated_tokens += seg.tokens_estimated
            elif seg.is_protected:
                # Force-fit protected items
                selected_indices.add(seg.index)
                allocated_tokens += seg.tokens_estimated

        # Re-assemble text in original chronological order
        retained = [s for s in scored_list if s.index in selected_indices]
        pruned_text = "".join(s.text for s in retained) if isinstance(context, str) else "\n".join(s.text for s in retained)

        t1 = time.perf_counter()
        ratio = round(allocated_tokens / max(1, total_orig_tokens), 3)

        return PruneResult(
            original_tokens=total_orig_tokens,
            pruned_tokens=allocated_tokens,
            compression_ratio=ratio,
            retained_segments=len(retained),
            total_segments=total_segs,
            text=pruned_text,
            elapsed_ms=round((t1 - t0) * 1000, 2)
        )

    def compact_thought_history(
        self,
        thoughts: List[Dict[str, Any]],
        max_tokens: int = 1500,
        query: Optional[str] = None
    ) -> PruneResult:
        """
        Formats a list of Cortex thought dictionaries into structured log lines and compresses
        them using multi-factor importance scoring within the specified token budget.
        """
        lines = []
        for t in thoughts:
            agent = t.get("agent", "UNKNOWN")
            content = t.get("content", "")
            meta = t.get("metadata", {})
            meta_str = f" [meta: {json.dumps(meta)}]" if meta else ""
            lines.append(f"[{agent}] {content}{meta_str}")
        return self.prune(lines, max_tokens=max_tokens, query=query)


def _test_context_pruner() -> None:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("=== MARKUS Context Pruner Subsystem Test ===")
    pruner = MarkusContextPruner()

    sample_context = [
        "System initialized. Everything is ready.",
        "Verbose log: checking dependency node 1... ok.",
        "Verbose log: checking dependency node 2... ok.",
        "PRIME-DIRECTIVE: System invariant must remain deterministic under air-gapped constraints.",
        "def execute_trade(symbol: str, amount: float) -> bool:",
        "    if amount <= 0: raise ValueError('Invalid amount')",
        "    return broker.submit_order(symbol, amount)",
        "Verbose log: connection heartbeat ping 127.0.0.1... alive.",
        "Traceback (most recent call last):",
        "  File 'server.py', line 42, in handle_request",
        "ZeroDivisionError: division by zero",
        "SyntaxError: invalid syntax in dynamic module",
        "AssertionError: invariant check failed",
        "Routine housekeeping done.",
        "Routine telemetry synchronized.",
        "Target conclusion: all subsystems active."
    ]

    res = pruner.prune(sample_context, max_tokens=100, query="execute_trade error")

    print(f"Original Tokens : {res.original_tokens}")
    print(f"Pruned Tokens   : {res.pruned_tokens}")
    print(f"Compression     : {res.compression_ratio * 100:.1f}% of original")
    print(f"Retained Lines  : {res.retained_segments}/{res.total_segments}")
    print(f"Elapsed Time    : {res.elapsed_ms}ms")
    print(f"\n--- Pruned Output ---\n{res.text}\n")

    # Invariant checks
    assert "def execute_trade" in res.text, "Failed to preserve critical function signature"
    assert "Traceback" in res.text, "Failed to preserve protected Traceback"
    assert "SyntaxError" in res.text, "Failed to preserve protected SyntaxError"
    assert "AssertionError" in res.text, "Failed to preserve protected AssertionError"
    assert "PRIME-DIRECTIVE" in res.text, "Failed to preserve protected PRIME-DIRECTIVE"

    # Test thought compaction helper
    thoughts_sample = [
        {"agent": "SENTINEL", "content": "Routine pulse check", "metadata": {"status": "ok"}},
        {"agent": "REDTEAM", "content": "Traceback: Crash in sandbox eval", "metadata": {"vuln_id": "v1"}},
        {"agent": "PLANNER", "content": "PRIME-DIRECTIVE: Ensure offline fallback", "metadata": {"gate": "active"}},
        {"agent": "WORKER", "content": "Telemetry ping heartbeat", "metadata": {}},
    ]
    thought_res = pruner.compact_thought_history(thoughts_sample, max_tokens=40, query="Traceback offline")
    assert "Traceback" in thought_res.text, "Thought compaction failed to preserve Traceback"
    assert "PRIME-DIRECTIVE" in thought_res.text, "Thought compaction failed to preserve PRIME-DIRECTIVE"

    # Test within budget passthrough
    short_context = ["Single line within budget"]
    pass_res = pruner.prune(short_context, max_tokens=100)
    assert pass_res.compression_ratio == 1.0, "Pass-through failed on small context"

    print("[PASS] Context Pruner Subsystem Test: PASSED")


if __name__ == "__main__":
    _test_context_pruner()

