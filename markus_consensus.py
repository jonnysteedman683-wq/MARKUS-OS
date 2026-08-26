#!/usr/bin/env python3
"""
MARKUS OS Automated Multi-Model Consensus & AST Cross-Validation Arbiter (Upgrade 23)
Evaluates code patches and logic proposals across multiple model outputs or agent branches.
Applies AST syntax validation, structural similarity analysis, safety linting, and sandboxed
test execution to select the consensus-optimal candidate.
"""

from __future__ import annotations
import ast
import asyncio
import difflib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from markus_sandbox import MarkusProcessSandbox

logger = logging.getLogger("Markus.ConsensusArbiter")

@dataclass
class ModelCandidate:
    candidate_id: str
    model_name: str
    code: str
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CandidateEvaluation:
    candidate_id: str
    model_name: str
    ast_valid: bool
    ast_node_count: int
    defined_functions: List[str]
    defined_classes: List[str]
    has_unsafe_nodes: bool
    sandbox_exit_code: Optional[int] = None
    sandbox_passed: bool = False
    sandbox_runtime_ms: float = 0.0
    similarity_to_peers: float = 0.0
    composite_score: float = 0.0
    error: str = ""

@dataclass
class ConsensusVerdict:
    winning_candidate_id: str
    winning_model: str
    winning_code: str
    consensus_confidence: float
    total_candidates: int
    evaluations: List[CandidateEvaluation]
    elapsed_ms: float

class MarkusConsensusArbiter:
    """
    Cross-validates multiple candidate implementations across models using AST analysis,
    sandbox test runs, and structural consensus voting.
    """

    UNSAFE_CALLS = {"os.system", "shutil.rmtree", "eval", "exec", "__import__"}

    def __init__(self, sandbox: Optional[MarkusProcessSandbox] = None) -> None:
        self.sandbox = sandbox or MarkusProcessSandbox()

    def _analyze_ast(self, code: str) -> Tuple[bool, int, List[str], List[str], bool, str]:
        """Parses AST and extracts structural metrics and safety flags."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, 0, [], [], False, f"SyntaxError line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, 0, [], [], False, str(e)

        node_count = sum(1 for _ in ast.walk(tree))
        functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

        has_unsafe = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self.UNSAFE_CALLS:
                    has_unsafe = True
                    break
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    full_call = f"{node.func.value.id}.{node.func.attr}"
                    if full_call in self.UNSAFE_CALLS:
                        has_unsafe = True
                        break

        return True, node_count, functions, classes, has_unsafe, ""

    def _calculate_similarity_matrix(self, codes: List[str]) -> List[float]:
        """Computes pairwise sequence similarity between candidate codebases."""
        n = len(codes)
        if n <= 1:
            return [1.0] * n

        avg_similarities = []
        for i in range(n):
            sim_sum = 0.0
            for j in range(n):
                if i == j:
                    continue
                ratio = difflib.SequenceMatcher(None, codes[i], codes[j]).ratio()
                sim_sum += ratio
            avg_similarities.append(round(sim_sum / (n - 1), 4))
        return avg_similarities

    async def arbitrate(
        self,
        candidates: List[ModelCandidate],
        test_harness_code: Optional[str] = None,
        timeout_s: float = 5.0
    ) -> ConsensusVerdict:
        t0 = time.perf_counter()
        if not candidates:
            raise ValueError("No candidates provided for consensus arbitration.")

        codes = [c.code for c in candidates]
        peer_similarities = self._calculate_similarity_matrix(codes)

        evaluations: List[CandidateEvaluation] = []

        for idx, cand in enumerate(candidates):
            ast_ok, node_cnt, funcs, classes, unsafe, err = self._analyze_ast(cand.code)
            eval_item = CandidateEvaluation(
                candidate_id=cand.candidate_id,
                model_name=cand.model_name,
                ast_valid=ast_ok,
                ast_node_count=node_cnt,
                defined_functions=funcs,
                defined_classes=classes,
                has_unsafe_nodes=unsafe,
                similarity_to_peers=peer_similarities[idx],
                error=err
            )

            # If AST is valid and not explicitly unsafe, run sandbox test validation if provided
            if ast_ok and not unsafe and test_harness_code:
                full_test_code = f"{cand.code}\n\n# --- Test Harness ---\n{test_harness_code}\n"
                res = await self.sandbox.execute_python_code(full_test_code, timeout_s=timeout_s)
                eval_item.sandbox_exit_code = res.exit_code
                eval_item.sandbox_passed = (res.exit_code == 0)
                eval_item.sandbox_runtime_ms = res.runtime_ms
                if res.exit_code != 0 and res.stderr:
                    eval_item.error = res.stderr.strip()[:200]
            elif ast_ok and not unsafe:
                # Without test harness, dry-run AST module execution
                res = await self.sandbox.execute_python_code(cand.code, timeout_s=timeout_s)
                eval_item.sandbox_exit_code = res.exit_code
                eval_item.sandbox_passed = (res.exit_code == 0)
                eval_item.sandbox_runtime_ms = res.runtime_ms

            # Compute composite arbitration score
            score = 0.0
            if eval_item.ast_valid:
                score += 30.0
            if not eval_item.has_unsafe_nodes:
                score += 10.0
            if eval_item.sandbox_passed:
                score += 40.0
            # Peer consensus bonus (up to 20 points)
            score += eval_item.similarity_to_peers * 20.0

            eval_item.composite_score = round(score, 2)
            evaluations.append(eval_item)

        # Select highest composite score
        best_eval = max(evaluations, key=lambda e: e.composite_score)
        winning_cand = next(c for c in candidates if c.candidate_id == best_eval.candidate_id)

        # Consensus confidence is normalized winning score (0.0 - 1.0)
        confidence = round(min(1.0, best_eval.composite_score / 100.0), 3)
        t1 = time.perf_counter()

        return ConsensusVerdict(
            winning_candidate_id=winning_cand.candidate_id,
            winning_model=winning_cand.model_name,
            winning_code=winning_cand.code,
            consensus_confidence=confidence,
            total_candidates=len(candidates),
            evaluations=evaluations,
            elapsed_ms=round((t1 - t0) * 1000, 2)
        )

def _test_arbiter():
    print("=== MARKUS Multi-Model Consensus Arbiter Subsystem Test ===")
    arbiter = MarkusConsensusArbiter()

    cand1 = ModelCandidate(
        candidate_id="cand_nemotron",
        model_name="deepseek/deepseek-v4-pro-0813",
        code="def compute_fibonacci(n: int) -> int:\n    if n <= 1: return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b\n"
    )

    cand2 = ModelCandidate(
        candidate_id="cand_laguna",
        model_name="poolside/laguna-s-2.1:free",
        code="def compute_fibonacci(n: int) -> int:\n    if n < 0:\n        raise ValueError('Negative input')\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b\n"
    )

    cand3 = ModelCandidate(
        candidate_id="cand_broken",
        model_name="inclusionai/ling-3.0-flash",
        code="def compute_fibonacci(n: int) -> int\n    return n + 1\n"  # Syntax error
    )

    test_harness = "assert compute_fibonacci(10) == 55\nassert compute_fibonacci(0) == 0\nprint('TESTS_PASS')\n"

    verdict = asyncio.run(arbiter.arbitrate([cand1, cand2, cand3], test_harness_code=test_harness))

    print(f"Winning Candidate : {verdict.winning_candidate_id} ({verdict.winning_model})")
    print(f"Confidence Score  : {verdict.consensus_confidence * 100:.1f}%")
    print(f"Arbitration Time  : {verdict.elapsed_ms}ms")
    print("\nEvaluations:")
    for e in verdict.evaluations:
        print(f"  [{e.candidate_id}] AST={e.ast_valid} SandboxPassed={e.sandbox_passed} Similarity={e.similarity_to_peers} Score={e.composite_score}")

    assert verdict.winning_candidate_id in ("cand_laguna", "cand_nemotron")
    assert verdict.evaluations[2].ast_valid is False
    print("\n✅ Multi-Model Consensus Arbiter Test: PASSED")

if __name__ == "__main__":
    _test_arbiter()
