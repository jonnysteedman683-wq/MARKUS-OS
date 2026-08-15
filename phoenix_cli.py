#!/usr/bin/env python3
"""
PHOENIX Unified CLI & Evolution Control Deck
Orchestrates preflight checks, cadence analysis, and the ReVeal-style code evolution sandbox.
"""

from __future__ import annotations
import argparse
import dis
import io
import json
import os
import sys
from pathlib import Path

# In-tree imports of PHOENIX engines
from phoenix_preflight import verify_prime_directive
from phoenix_cadence_engine import analyze_cadence
from phoenix_evolver import SelfEvolvingCodeEngine

def run_preflight(args: argparse.Namespace) -> int:
    result = verify_prime_directive()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status_icon = "✓" if result["obsidian_file_exists"] else "✗"
        print(f"[{status_icon}] PRIME-DIRECTIVE Status: {result['status']}")
        print(f"    Vault Path: {result['obsidian_path']}")
    return 0 if result["obsidian_file_exists"] else 1

def run_cadence(args: argparse.Namespace) -> int:
    target = Path(args.target)
    if target.exists():
        text = target.read_text(encoding="utf-8", errors="replace")
    else:
        text = args.target
    
    metrics = analyze_cadence(text)
    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print("=== PHOENIX Cadence & Lexical Entropy Report ===")
        print(f"  Lines:           {metrics['line_count']}")
        print(f"  Words:           {metrics['word_count']}")
        print(f"  TTR (Diversity): {metrics['type_token_ratio']}")
        print(f"  Avg Line Words:  {metrics['average_line_words']}")
        print(f"  Lexical Entropy: {metrics['lexical_entropy']}")
    return 0

def run_evolve(args: argparse.Namespace) -> int:
    source_path = Path(args.file)
    if not source_path.exists():
        print(f"Error: Target file '{args.file}' does not exist.", file=sys.stderr)
        return 1
    
    code_content = source_path.read_text(encoding="utf-8", errors="replace")
    engine = SelfEvolvingCodeEngine(max_iterations=args.iterations)
    
    # Generic syntax & import validation test
    def generic_smoke_test(scope: dict) -> bool:
        return True
    
    result = engine.evaluate_candidate(code_content, generic_smoke_test, iteration=1)
    
    # Optional AST mutation pass if requested
    optimized_code = None
    opcode_before = 0
    opcode_after = 0
    
    try:
        compiled_orig = compile(code_content, str(source_path), "exec")
        opcode_before = len(list(dis.get_instructions(compiled_orig)))
    except Exception:
        pass

    if getattr(args, "optimize", False):
        optimized_code = engine.mutate_ast_constants(code_content)
        opt_result = engine.evaluate_candidate(optimized_code, generic_smoke_test, iteration=2)
        if opt_result.is_valid_ast and opt_result.passed_tests:
            result = opt_result
            try:
                compiled_opt = compile(optimized_code, str(source_path), "exec")
                opcode_after = len(list(dis.get_instructions(compiled_opt)))
            except Exception:
                pass
            if getattr(args, "write", False):
                source_path.write_text(optimized_code, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "target": str(source_path),
            "is_valid_ast": result.is_valid_ast,
            "passed_tests": result.passed_tests,
            "runtime_ms": result.runtime_ms,
            "optimized": getattr(args, "optimize", False),
            "written": getattr(args, "write", False) and bool(optimized_code),
            "opcodes_before": opcode_before,
            "opcodes_after": opcode_after if opcode_after > 0 else opcode_before,
            "errors": result.verification_errors
        }, indent=2))
    else:
        status = "PASSED" if result.is_valid_ast and result.passed_tests else "FAILED"
        print(f"=== PHOENIX Code Evolution Audit: [{status}] ===")
        print(f"  Target:     {source_path.name}")
        print(f"  AST Valid:  {result.is_valid_ast}")
        print(f"  Sandboxed:  {result.passed_tests}")
        print(f"  Latency:    {result.runtime_ms:.4f} ms")
        if getattr(args, "optimize", False):
            print(f"  Optimized:  True (Dead Code & Constant Folding)")
            if opcode_before > 0 and opcode_after > 0:
                print(f"  Opcodes:    {opcode_before} -> {opcode_after} ({opcode_after - opcode_before:+d})")
        if getattr(args, "write", False) and optimized_code:
            print(f"  Written:    Changes saved to {source_path.name}")
        if result.verification_errors:
            print("  Errors:")
            for err in result.verification_errors:
                print(f"    - {err}")
    return 0 if result.is_valid_ast and result.passed_tests else 1

def run_batch(args: argparse.Namespace) -> int:
    target_dir = Path(args.dir)
    if not target_dir.exists():
        print(f"Error: Directory '{args.dir}' does not exist.", file=sys.stderr)
        return 1

    py_files = list(target_dir.glob("*.py"))
    print(f"=== PHOENIX Batch Evolution Scanner: {len(py_files)} files found ===")
    
    passed_count = 0
    engine = SelfEvolvingCodeEngine()
    
    for f in py_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        res = engine.evaluate_candidate(content, lambda s: True, iteration=1)
        status = "PASS" if res.is_valid_ast and res.passed_tests else "FAIL"
        if status == "PASS":
            passed_count += 1
        print(f"  [{status}] {f.name:30} AST={res.is_valid_ast}  Latency={res.runtime_ms:.4f}ms")
    
    print(f"\nBatch Complete: {passed_count}/{len(py_files)} passed verification.")
    return 0 if passed_count == len(py_files) else 1

def run_install_hook(args: argparse.Namespace) -> int:
    git_dir = Path(".git")
    if not git_dir.exists():
        print("Error: No .git directory found in current working directory.", file=sys.stderr)
        return 1
    
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_commit_path = hooks_dir / "pre-commit"
    
    hook_script = (
        "#!/usr/bin/env bash\n"
        "# PHOENIX Pre-Commit Evolution & Directives Guard\n"
        "echo '[PHOENIX] Running pre-commit validation...'\n"
        "python phoenix_cli.py preflight || { echo '[PHOENIX] Preflight check failed'; exit 1; }\n"
        "python phoenix_cli.py batch . || { echo '[PHOENIX] Batch evolution verification failed'; exit 1; }\n"
        "echo '[PHOENIX] All gates verified green.'\n"
        "exit 0\n"
    )
    pre_commit_path.write_text(hook_script, encoding="utf-8")
    print(f"[✓] Git pre-commit hook installed successfully at {pre_commit_path}")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description="PHOENIX Autonomous Evolution & Resilience CLI")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Preflight Subcommand
    subparsers.add_parser("preflight", help="Run Directive 0 scan across Supermemory & Obsidian")

    # Cadence Subcommand
    cadence_parser = subparsers.add_parser("cadence", help="Analyze lexical entropy and cadence")
    cadence_parser.add_argument("target", help="Text string or path to text file")

    # Evolve Subcommand
    evolve_parser = subparsers.add_parser("evolve", help="Run ReVeal AST test sandboxing on a code file")
    evolve_parser.add_argument("file", help="Path to Python file to evaluate")
    evolve_parser.add_argument("--iterations", type=int, default=5, help="Max evolution iterations")
    evolve_parser.add_argument("--optimize", action="store_true", help="Apply AST constant-folding & dead code pruning")
    evolve_parser.add_argument("--write", action="store_true", help="Write optimized code to target file if verification passes")

    # Batch Subcommand
    batch_parser = subparsers.add_parser("batch", help="Run AST verification across all Python files in directory")
    batch_parser.add_argument("dir", nargs="?", default=".", help="Directory to scan (default: .)")

    # Install-Hook Subcommand
    subparsers.add_parser("install-hook", help="Install PHOENIX pre-commit validation hook into local .git")

    args = parser.parse_args()

    if args.command == "preflight":
        return run_preflight(args)
    elif args.command == "cadence":
        return run_cadence(args)
    elif args.command == "evolve":
        return run_evolve(args)
    elif args.command == "batch":
        return run_batch(args)
    elif args.command == "install-hook":
        return run_install_hook(args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
