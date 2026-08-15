#!/usr/bin/env python3
"""
MARKUS OS Self-Calibrating AST Complexity & Refactoring Governor (Upgrade 27)
Computes cognitive and cyclomatic complexity, AST nesting depth, branch density,
and maintainability index across codebase modules.
Generates automated refactoring suggestions for complex functions or bloated modules.
"""

from __future__ import annotations
import ast
import json
import logging
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("Markus.ComplexityGovernor")

@dataclass
class FunctionComplexityMetrics:
    name: str
    lineno: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    max_nesting_depth: int
    parameter_count: int
    lines_of_code: int
    status: str  # "OPTIMAL", "MODERATE", "HIGH_COMPLEXITY", "CRITICAL_REFACTOR"
    refactoring_recommendations: List[str] = field(default_factory=list)

@dataclass
class ModuleComplexityAudit:
    module_name: str
    file_path: str
    total_loc: int
    total_ast_nodes: int
    average_cyclomatic: float
    max_cyclomatic: int
    maintainability_index: float
    functions: List[FunctionComplexityMetrics]
    status: str  # "CLEAN", "WARNING", "DEGRADED"
    elapsed_ms: float

class ComplexityVisitor(ast.NodeVisitor):
    """AST Visitor calculating cyclomatic complexity and nesting depth."""

    def __init__(self) -> None:
        self.functions: List[FunctionComplexityMetrics] = []

    def _calc_cyclomatic(self, node: ast.AST) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, (ast.comprehension,)):
                complexity += 1
        return complexity

    def _calc_nesting_and_cognitive(self, node: ast.AST, current_depth: int = 0) -> Tuple[int, int]:
        max_depth = current_depth
        cognitive = 0

        for child in ast.iter_child_nodes(node):
            is_branch = isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try, ast.ExceptHandler))
            next_depth = current_depth + (1 if is_branch else 0)

            if is_branch:
                cognitive += 1 + current_depth

            child_max, child_cog = self._calc_nesting_and_cognitive(child, next_depth)
            max_depth = max(max_depth, child_max)
            cognitive += child_cog

        return max_depth, cognitive

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._analyze_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._analyze_function(node)
        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        cyclo = self._calc_cyclomatic(node)
        max_depth, cognitive = self._calc_nesting_and_cognitive(node, current_depth=0)
        param_count = len(node.args.args) + (1 if node.args.vararg else 0) + (1 if node.args.kwarg else 0)
        loc = (node.end_lineno - node.lineno + 1) if hasattr(node, "end_lineno") and node.end_lineno else 1

        recommendations = []
        if cyclo > 10:
            recommendations.append(f"High cyclomatic complexity ({cyclo}). Extract sub-functions or split branching paths.")
        if max_depth > 4:
            recommendations.append(f"Deep nesting depth ({max_depth}). Guard clauses or early returns recommended.")
        if param_count > 6:
            recommendations.append(f"Excessive parameters ({param_count}). Group into dataclass or config object.")
        if loc > 60:
            recommendations.append(f"Function length ({loc} LOC) exceeds 60 lines. Decompose into atomic units.")

        if cyclo > 15 or max_depth > 5 or loc > 100:
            status = "CRITICAL_REFACTOR"
        elif cyclo > 8 or max_depth > 3 or loc > 50:
            status = "HIGH_COMPLEXITY"
        elif cyclo > 4:
            status = "MODERATE"
        else:
            status = "OPTIMAL"

        self.functions.append(FunctionComplexityMetrics(
            name=node.name,
            lineno=node.lineno,
            cyclomatic_complexity=cyclo,
            cognitive_complexity=cognitive,
            max_nesting_depth=max_depth,
            parameter_count=param_count,
            lines_of_code=loc,
            status=status,
            refactoring_recommendations=recommendations
        ))

class MarkusComplexityGovernor:
    """
    Codebase complexity auditor and refactoring governor.
    Evaluates Halstead maintainability and AST complexity indices.
    """

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or Path(os.getcwd()).resolve()

    def audit_code_string(self, code: str, module_name: str = "dynamic_snippet") -> ModuleComplexityAudit:
        t0 = time.perf_counter()
        try:
            tree = ast.parse(code, filename=module_name)
        except SyntaxError as e:
            t1 = time.perf_counter()
            return ModuleComplexityAudit(
                module_name=module_name,
                file_path="",
                total_loc=len(code.splitlines()),
                total_ast_nodes=0,
                average_cyclomatic=0.0,
                max_cyclomatic=0,
                maintainability_index=0.0,
                functions=[],
                status=f"SYNTAX_ERROR (Line {e.lineno})",
                elapsed_ms=round((t1 - t0) * 1000, 2)
            )

        visitor = ComplexityVisitor()
        visitor.visit(tree)

        total_nodes = sum(1 for _ in ast.walk(tree))
        loc = len(code.splitlines())
        avg_cyclo = (
            round(sum(f.cyclomatic_complexity for f in visitor.functions) / len(visitor.functions), 2)
            if visitor.functions else 1.0
        )
        max_cyclo = max((f.cyclomatic_complexity for f in visitor.functions), default=1)

        # Simplified Maintainability Index (0 to 100 scale)
        # MI = max(0, (171 - 5.2 * ln(Halstead Volume) - 0.23 * Cyclomatic - 16.2 * ln(LOC)) * 100 / 171)
        loc_term = 16.2 * math.log(max(1, loc))
        cyclo_term = 0.23 * avg_cyclo
        vol_approx = max(1.0, total_nodes * 2.5)
        vol_term = 5.2 * math.log(vol_approx)
        raw_mi = 171.0 - vol_term - cyclo_term - loc_term
        mi = round(max(0.0, min(100.0, (raw_mi / 171.0) * 100.0)), 2)

        has_critical = any(f.status == "CRITICAL_REFACTOR" for f in visitor.functions)
        has_high = any(f.status == "HIGH_COMPLEXITY" for f in visitor.functions)

        if has_critical or mi < 40.0:
            status = "DEGRADED"
        elif has_high or mi < 65.0:
            status = "WARNING"
        else:
            status = "CLEAN"

        t1 = time.perf_counter()
        return ModuleComplexityAudit(
            module_name=module_name,
            file_path="",
            total_loc=loc,
            total_ast_nodes=total_nodes,
            average_cyclomatic=avg_cyclo,
            max_cyclomatic=max_cyclo,
            maintainability_index=mi,
            functions=visitor.functions,
            status=status,
            elapsed_ms=round((t1 - t0) * 1000, 2)
        )

    def audit_file(self, file_path: Path) -> ModuleComplexityAudit:
        content = file_path.read_text(encoding="utf-8")
        audit = self.audit_code_string(content, module_name=file_path.name)
        audit.file_path = str(file_path)
        return audit

    def audit_workspace(self) -> Tuple[List[ModuleComplexityAudit], Dict[str, Any]]:
        audits = []
        py_files = sorted(list(self.root_dir.glob("*.py")) + list((self.root_dir / "hive-core").glob("*.py")))

        for p in py_files:
            try:
                audits.append(self.audit_file(p))
            except Exception as e:
                logger.error(f"Error auditing {p.name}: {e}")

        clean_count = sum(1 for a in audits if a.status == "CLEAN")
        warning_count = sum(1 for a in audits if a.status == "WARNING")
        degraded_count = sum(1 for a in audits if a.status == "DEGRADED")
        avg_mi = round(sum(a.maintainability_index for a in audits) / max(1, len(audits)), 2)

        summary = {
            "total_modules": len(audits),
            "clean_modules": clean_count,
            "warning_modules": warning_count,
            "degraded_modules": degraded_count,
            "average_maintainability_index": avg_mi,
            "system_health": "OPTIMAL" if degraded_count == 0 else "ATTENTION_REQUIRED"
        }
        return audits, summary

def _test_governor():
    print("=== MARKUS Complexity & Refactoring Governor Test ===")
    gov = MarkusComplexityGovernor()

    complex_sample = """
def heavily_nested_orchestrator(a, b, c, d, e, f, g):
    res = []
    if a:
        for i in range(10):
            if b:
                while c:
                    if d:
                        for j in range(5):
                            if e and f or g:
                                res.append(i * j)
    return res
"""

    audit = gov.audit_code_string(complex_sample, module_name="complex_sample")
    print(f"Module Status   : {audit.status}")
    print(f"Maintainability : {audit.maintainability_index}/100")
    print(f"Functions Found : {len(audit.functions)}")

    fn = audit.functions[0]
    print(f"  [{fn.name}] Cyclo={fn.cyclomatic_complexity} Nesting={fn.max_nesting_depth} Status={fn.status}")
    print(f"  Recommendations: {fn.refactoring_recommendations}")

    assert fn.cyclomatic_complexity > 5, "Cyclomatic complexity calculation failed"
    assert fn.max_nesting_depth >= 5, "Max nesting depth calculation failed"
    assert len(fn.refactoring_recommendations) >= 2, "Expected refactoring recommendations"

    # Workspace scan
    audits, summary = gov.audit_workspace()
    print(f"\nWorkspace Summary: {json.dumps(summary, indent=2)}")
    assert summary["total_modules"] >= 20, "Workspace audit did not find all modules"
    print("\n✅ Complexity & Refactoring Governor Test: PASSED")

if __name__ == "__main__":
    _test_governor()
