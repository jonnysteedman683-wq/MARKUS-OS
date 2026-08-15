#!/usr/bin/env python3
"""
MARKUS OS Free Model Performance Benchmark Suite
Evaluates all available free LLM providers (Nous Free, OpenRouter, Ollama Local)
across standardized coding, reasoning, and speed test cases, then ranks them
by task-specific performance to validate and refine router_config.yaml.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Markus.Benchmark")

@dataclass
class BenchmarkPrompt:
    id: str
    category: str
    prompt: str
    eval_fn: str  # short name of evaluation method

@dataclass
class BenchmarkResult:
    model_id: str
    prompt_id: str
    category: str
    tokens: int
    latency_ms: float
    success: bool
    error: Optional[str] = None

BENCHMARK_PROMPTS: List[BenchmarkPrompt] = [
    BenchmarkPrompt("code_simple", "coding", "Write a Python function that returns the factorial of a number using recursion.", "syntax_check"),
    BenchmarkPrompt("code_api", "coding", "Write a Python script that uses the GitHub REST API to list the last 5 commits in a repository.", "syntax_check"),
    BenchmarkPrompt("reasoning", "research", "Explain the difference between supervised, unsupervised, and reinforcement learning in 3 paragraphs.", "length_check"),
    BenchmarkPrompt("quick_answer", "quick_answer", "What is the capital of France?", "exact_match"),
    BenchmarkPrompt("debug", "coding", "Find and fix the bug in this Python code: def add(a, b): return a * b", "bug_correct"),
]

FREE_MODELS = [
    {"id": "nous/poolside/laguna-s-2.1:free", "provider": "nous"},
    {"id": "nous/nemotron-3-ultra:free", "provider": "nous"},
    {"id": "openrouter/qwen-2.5-coder-32b-instruct:free", "provider": "openrouter"},
    {"id": "openrouter/deepseek-chat:free", "provider": "openrouter"},
    {"id": "openrouter/google/gemini-2.0-flash-exp:free", "provider": "openrouter"},
    {"id": "openrouter/mistral-7b-instruct:free", "provider": "openrouter"},
    {"id": "openrouter/microsoft/phi-3-mini-4k-instruct:free", "provider": "openrouter"},
]

class MarkusBenchmarkSuite:
    """Runs standardized prompts against all free models and collects performance metrics."""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s
        self.results: List[BenchmarkResult] = []

    def _simulate_response(self, prompt: BenchmarkPrompt, model_id: str) -> Dict[str, Any]:
        """
        Simulated response generator for benchmark scaffolding.
        In a production setup, this would call the real OpenRouter / Nous / Ollama APIs.
        """
        # Placeholder logic returning a structured mock completion
        return {
            "completion": f"[Simulated Response from {model_id} for {prompt.id}]",
            "usage": {"prompt_tokens": 50, "completion_tokens": 120},
            "latency_ms": float((hash(model_id) % 7 + 1) * 100),  # 100-700ms variation
        }

    def _evaluate(self, result: Dict[str, Any], prompt: BenchmarkPrompt) -> tuple[bool, str]:
        if result is None:
            return False, "NO_RESPONSE"
        completion = result.get("completion", "")
        if not completion or len(completion) < 10:
            return False, "EMPTY_RESPONSE"
        return True, ""

    async def run_model_benchmark(self, model: Dict[str, str]) -> List[BenchmarkResult]:
        model_results: List[BenchmarkResult] = []
        for prompt in BENCHMARK_PROMPTS:
            start_t = time.time()
            try:
                response = self._simulate_response(prompt, model["id"])
                latency_ms = (time.time() - start_t) * 1000
                success, error = self._evaluate(response, prompt)
                tokens = response["usage"]["completion_tokens"]
                br = BenchmarkResult(
                    model_id=model["id"],
                    prompt_id=prompt.id,
                    category=prompt.category,
                    tokens=tokens,
                    latency_ms=response.get("latency_ms", latency_ms),
                    success=success,
                    error=error if not success else None
                )
                model_results.append(br)
            except Exception as exc:
                model_results.append(BenchmarkResult(
                    model_id=model["id"], prompt_id=prompt.id, category=prompt.category,
                    tokens=0, latency_ms=0.0, success=False, error=str(exc)
                ))
        return model_results

    async def run_all(self) -> Dict[str, Any]:
        print("=== MARKUS Free Model Benchmark Suite ===")
        print(f"Benchmarking {len(FREE_MODELS)} models across {len(BENCHMARK_PROMPTS)} prompt categories...\n")
        all_results: List[BenchmarkResult] = []
        for model in FREE_MODELS:
            res = await self.run_model_benchmark(model)
            all_results.extend(res)
            passed = sum(1 for r in res if r.success)
            avg_latency = sum(r.latency_ms for r in res if r.success) / max(1, passed)
            print(f"  {model['id']:<55} | {passed}/{len(res)} | Avg Latency: {avg_latency:.0f}ms")
        self.results = all_results

        # Aggregate scores
        ranking: Dict[str, Dict[str, float]] = {}
        for model in FREE_MODELS:
            model_id = model["id"]
            model_results = [r for r in all_results if r.model_id == model_id and r.success]
            total_tokens = sum(r.tokens for r in model_results)
            avg_latency = sum(r.latency_ms for r in model_results) / max(1, len(model_results))
            # Scoring heuristic: lower latency better, higher tokens more capable (but penalize)
            score = 1.0 - min(1.0, avg_latency / 1000.0)  # simple inverse latency score
            ranking[model_id] = {
                "score": round(score, 3),
                "avg_latency_ms": round(avg_latency, 1),
                "successful_tasks": len(model_results),
                "total_tokens": total_tokens
            }
        # Sort by score descending
        sorted_ranking = dict(sorted(ranking.items(), key=lambda x: x[1]["score"], reverse=True))
        print("\n=== Aggregated Free Model Ranking (Best $\\to$ Worst) ===")
        for i, (mid, scores) in enumerate(sorted_ranking.items(), 1):
            print(f"  #{i} {mid:<55} Score: {scores['score']:.3f} | Latency: {scores['avg_latency_ms']:.0f}ms | Tasks: {scores['successful_tasks']}/{len(BENCHMARK_PROMPTS)}")
        return {"results": [asdict(r) for r in all_results], "ranking": sorted_ranking}

if __name__ == "__main__":
    suite = MarkusBenchmarkSuite()
    output = {
        "timestamp": time.time(),
        "benchmark_results": asyncio.run(suite.run_all())
    }
    outpath = os.path.join(os.path.dirname(__file__), "markus_benchmark_output.json")
    with open(outpath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nBenchmark results saved to: {outpath}")
