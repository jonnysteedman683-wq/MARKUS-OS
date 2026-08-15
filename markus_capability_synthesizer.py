#!/usr/bin/env python3
"""
MARKUS OS Self-Evolving Capability Driver Synthesizer (Upgrade 32)
Dynamically synthesizes, compiles, sandboxes, and hot-loads new capability drivers
into the active CapabilityRegistry with AST safety invariants and ReVeal validation.
"""

from __future__ import annotations
import ast
import asyncio
import importlib.util
import json
import logging
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from markus_capabilities import (
    BaseCapability,
    CapabilityMetadata,
    CapabilityRegistry,
    CapabilityType
)
from markus_sandbox import MarkusProcessSandbox, SandboxResult

logger = logging.getLogger("Markus.CapabilitySynthesizer")

CAPABILITY_OUTPUT_DIR = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/drivers")

# Forbidden AST calls for driver safety
FORBIDDEN_CALLS = {"os.system", "subprocess.Popen", "subprocess.call", "eval", "exec", "__import__"}

@dataclass
class DriverSynthesisResult:
    driver_name: str
    driver_type: str
    version: str
    is_valid_ast: bool
    is_safe: bool
    is_sandboxed_pass: bool
    loaded_into_registry: bool
    file_path: Optional[str] = None
    ast_errors: List[str] = field(default_factory=list)
    sandbox_stdout: str = ""
    elapsed_ms: float = 0.0

class DriverASTValidator(ast.NodeVisitor):
    """Inspects generated driver Python code for safety, typing, and subclassing invariants."""

    def __init__(self) -> None:
        self.errors: List[str] = []
        self.has_subclass = False
        self.has_async_execute = False
        self.class_name: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "BaseCapability":
                self.has_subclass = True
                self.class_name = node.name
            elif isinstance(base, ast.Attribute) and base.attr == "BaseCapability":
                self.has_subclass = True
                self.class_name = node.name
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name == "execute":
            self.has_async_execute = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = ""
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                call_name = f"{node.func.value.id}.{node.func.attr}"

        if call_name in FORBIDDEN_CALLS:
            self.errors.append(f"Forbidden call detected: '{call_name}' on line {node.lineno}")
        self.generic_visit(node)

class MarkusCapabilitySynthesizer:
    """
    Synthesizes and hot-reloads runtime capability drivers into Markus OS.
    Executes AST validation + sandboxed dry-runs prior to live registration.
    """

    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        sandbox: Optional[MarkusProcessSandbox] = None,
        output_dir: Path = CAPABILITY_OUTPUT_DIR
    ) -> None:
        self.registry = registry or CapabilityRegistry()
        self.sandbox = sandbox or MarkusProcessSandbox()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def validate_ast(self, code: str) -> Tuple[bool, bool, Optional[str], List[str]]:
        """Static AST verification of driver code structure and safety."""
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return False, False, None, [f"SyntaxError: {exc}"]

        validator = DriverASTValidator()
        validator.visit(tree)

        errors = validator.errors
        if not validator.has_subclass:
            errors.append("Class must inherit from BaseCapability")
        if not validator.has_async_execute:
            errors.append("Class must implement 'async def execute(self, params)'")

        is_valid = len(errors) == 0
        is_safe = len(validator.errors) == 0
        return is_valid, is_safe, validator.class_name, errors

    async def synthesize_driver(
        self,
        name: str,
        code: str,
        cap_type: str = CapabilityType.TOOL,
        description: str = "",
        test_params: Optional[Dict[str, Any]] = None
    ) -> DriverSynthesisResult:
        """Full synthesis lifecycle: Validate AST -> Sandbox Dry-Run -> Hot Load."""
        t0 = time.perf_counter()
        is_valid, is_safe, class_name, ast_errs = self.validate_ast(code)

        if not is_valid:
            t1 = time.perf_counter()
            return DriverSynthesisResult(
                driver_name=name,
                driver_type=cap_type,
                version="1.0.0",
                is_valid_ast=False,
                is_safe=is_safe,
                is_sandboxed_pass=False,
                loaded_into_registry=False,
                ast_errors=ast_errs,
                elapsed_ms=round((t1 - t0) * 1000, 2)
            )

        # 2. Sandboxed Dry Run Test Harness
        test_script = f"""
import sys
sys.path.insert(0, r"C:/Users/jonny/OneDrive/Desktop/New folder")
import asyncio
import json
{code}

async def _test():
    inst = {class_name}()
    res = await inst.execute({json.dumps(test_params or {{}})})
    print("SANDBOX_OUT:" + json.dumps(res))

asyncio.run(_test())
"""
        sandbox_res: SandboxResult = await self.sandbox.execute_python_code(test_script, timeout_s=4.0)
        sandbox_pass = (sandbox_res.exit_code == 0) and ("SANDBOX_OUT:" in sandbox_res.stdout)

        if not sandbox_pass:
            t1 = time.perf_counter()
            return DriverSynthesisResult(
                driver_name=name,
                driver_type=cap_type,
                version="1.0.0",
                is_valid_ast=True,
                is_safe=True,
                is_sandboxed_pass=False,
                loaded_into_registry=False,
                ast_errors=[f"Sandbox execution failed: {sandbox_res.stderr or sandbox_res.stdout}"],
                sandbox_stdout=sandbox_res.stdout,
                elapsed_ms=round((t1 - t0) * 1000, 2)
            )

        # 3. Write validated driver to storage
        driver_file = self.output_dir / f"driver_{name}.py"
        driver_file.write_text(code, encoding="utf-8")

        # 4. Dynamic Import & Hot Load into Registry
        loaded = False
        try:
            spec = importlib.util.spec_from_file_location(f"dynamic_driver_{name}", str(driver_file))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                driver_cls = getattr(mod, class_name)
                instance = driver_cls()
                self.registry.register(instance)
                loaded = True
        except Exception as exc:
            ast_errs.append(f"Hot-loading dynamic module failed: {exc}")

        t1 = time.perf_counter()
        return DriverSynthesisResult(
            driver_name=name,
            driver_type=cap_type,
            version="1.0.0",
            is_valid_ast=True,
            is_safe=True,
            is_sandboxed_pass=True,
            loaded_into_registry=loaded,
            file_path=str(driver_file),
            ast_errors=ast_errs,
            sandbox_stdout=sandbox_res.stdout,
            elapsed_ms=round((t1 - t0) * 1000, 2)
        )

def _test_synthesizer():
    print("=== MARKUS Capability Driver Synthesizer Test ===")
    reg = CapabilityRegistry()
    synth = MarkusCapabilitySynthesizer(registry=reg)

    sample_driver_code = """
import time
from markus_capabilities import BaseCapability, CapabilityMetadata, CapabilityType

class JsonTransformerCapability(BaseCapability):
    def __init__(self) -> None:
        super().__init__(CapabilityMetadata(
            name="json_transformer",
            cap_type=CapabilityType.TOOL,
            description="Transforms and normalizes dictionary payloads."
        ))

    async def execute(self, params: dict) -> dict:
        data = params.get("data", {})
        return {
            "status": "TRANSFORMED",
            "keys_count": len(data),
            "keys": list(data.keys()),
            "timestamp": time.time()
        }
"""

    loop = asyncio.new_event_loop()
    res = loop.run_until_complete(
        synth.synthesize_driver(
            name="json_transformer",
            code=sample_driver_code,
            test_params={"data": {"alpha": 1, "beta": 2}}
        )
    )

    print(f"Driver Name: {res.driver_name}")
    print(f"AST Valid: {res.is_valid_ast}")
    print(f"Sandbox Pass: {res.is_sandboxed_pass}")
    print(f"Loaded: {res.loaded_into_registry}")
    print(f"Latency: {res.elapsed_ms}ms")

    assert res.is_valid_ast is True
    assert res.is_sandboxed_pass is True
    assert res.loaded_into_registry is True
    assert reg.get("json_transformer") is not None

    # Verify runtime invocation
    invoked = loop.run_until_complete(reg.invoke("json_transformer", {"data": {"foo": "bar"}}))
    print(f"Invoked Result: {invoked}")
    assert invoked["status"] == "TRANSFORMED"
    loop.close()

    print("\n✅ Capability Driver Synthesizer: PASSED")

if __name__ == "__main__":
    _test_synthesizer()
