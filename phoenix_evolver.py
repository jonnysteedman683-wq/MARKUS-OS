"""
PHOENIX Self-Evolving Code Engine & Verification Loop (ReVeal Architecture)
Implements an iterative self-testing code synthesizer with AST verification and dynamic benchmark evaluation.
"""

from __future__ import annotations
import ast
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

@dataclass
class CodeCandidate:
    source_code: str
    iteration: int
    is_valid_ast: bool = False
    runtime_ms: float = 0.0
    verification_errors: List[str] = field(default_factory=list)
    passed_tests: bool = False

class SelfEvolvingCodeEngine:
    """
    Automated generation -> AST verification -> Execution Sandbox -> Mutation loop.
    Modeled after ReVeal and EvoAgentX iterative self-improvement pipelines.
    """

    def __init__(self, max_iterations: int = 5) -> None:
        self.max_iterations = max_iterations
        self.evolution_history: List[CodeCandidate] = []

    def verify_ast(self, code_str: str) -> tuple[bool, Optional[str]]:
        try:
            ast.parse(code_str)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} at line {e.lineno}"

    def evaluate_candidate(
        self,
        candidate_code: str,
        test_fn: Callable[[Dict[str, Any]], bool],
        iteration: int = 1
    ) -> CodeCandidate:
        valid_ast, ast_err = self.verify_ast(candidate_code)
        candidate = CodeCandidate(source_code=candidate_code, iteration=iteration, is_valid_ast=valid_ast)

        if not valid_ast:
            candidate.verification_errors.append(ast_err or "Unknown AST error")
            self.evolution_history.append(candidate)
            return candidate

        # Sandbox execution and benchmark timing
        # Execute in a unified namespace so module-level imports and decorators are resolved in class scopes
        sandbox_env: Dict[str, Any] = {"__builtins__": __builtins__}
        start = time.perf_counter()
        try:
            compiled = compile(candidate_code, "<phoenix_sandbox>", "exec")
            exec(compiled, sandbox_env, sandbox_env)
            passed = test_fn(sandbox_env)
            candidate.passed_tests = passed
            if not passed:
                candidate.verification_errors.append("Assertion / benchmark validation failed.")
        except Exception as exc:
            candidate.verification_errors.append(f"RuntimeError: {str(exc)}")
            candidate.passed_tests = False
        finally:
            candidate.runtime_ms = (time.perf_counter() - start) * 1000.0

        self.evolution_history.append(candidate)
        return candidate

    def mutate_ast_constants(self, code_str: str) -> str:
        """Applies deterministic AST constant-folding, dead-branch pruning, and micro-optimizations."""
        class AdvancedOptimizer(ast.NodeTransformer):
            def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
                self.generic_visit(node)
                if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                    try:
                        if isinstance(node.op, ast.Add):
                            return ast.Constant(value=node.left.value + node.right.value)
                        elif isinstance(node.op, ast.Sub):
                            return ast.Constant(value=node.left.value - node.right.value)
                        elif isinstance(node.op, ast.Mult):
                            return ast.Constant(value=node.left.value * node.right.value)
                        elif isinstance(node.op, ast.FloorDiv) and node.right.value != 0:
                            return ast.Constant(value=node.left.value // node.right.value)
                    except Exception:
                        pass
                return node

            def visit_If(self, node: ast.If) -> Any:
                self.generic_visit(node)
                # Dead code elimination on constant condition
                if isinstance(node.test, ast.Constant):
                    if bool(node.test.value):
                        return node.body
                    else:
                        return node.orelse if node.orelse else None
                return node

        try:
            tree = ast.parse(code_str)
            optimized_tree = AdvancedOptimizer().visit(tree)
            ast.fix_missing_locations(optimized_tree)
            return ast.unparse(optimized_tree)
        except Exception:
            return code_str

if __name__ == "__main__":
    engine = SelfEvolvingCodeEngine()
    
    sample_code = "def compute_sum(n: int) -> int:\n    return (n * (n + 1)) // 2\n"
    
    def test_sum(scope: Dict[str, Any]) -> bool:
        fn = scope.get("compute_sum")
        if not fn:
            return False
        return fn(100) == 5050 and fn(10) == 55

    result = engine.evaluate_candidate(sample_code, test_sum, iteration=1)
    print(f"Verified: AST={result.is_valid_ast}, Passed={result.passed_tests}, Latency={result.runtime_ms:.4f}ms")
