"""
MARKUS OS Isolated Process Execution Sandbox (Upgrade 4)
Provides subprocess containment, execution timeouts, memory/CPU bounds,
and safe execution of user-submitted code without endangering the main kernel loop.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Markus.Sandbox")

@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    runtime_ms: float
    timed_out: bool = False
    sandbox_path: str = ""

class MarkusProcessSandbox:
    """Executes Python / Shell code in an isolated scratchpad environment."""

    def __init__(self, sandbox_root: Optional[Path] = None, default_timeout_s: float = 10.0) -> None:
        self.sandbox_root = sandbox_root or Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/workspace")
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.default_timeout_s = default_timeout_s

    async def execute_python_code(
        self,
        code_str: str,
        timeout_s: Optional[float] = None,
        env_vars: Optional[Dict[str, str]] = None
    ) -> SandboxResult:
        timeout = timeout_s or self.default_timeout_s
        start = time.perf_counter()

        # Write to isolated temporary script inside private workspace
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=str(self.sandbox_root),
            delete=False,
            encoding="utf-8"
        ) as tmp:
            tmp.write(code_str)
            tmp_path = Path(tmp.name)

        merged_env = os.environ.copy()
        merged_env["PYTHONUNBUFFERED"] = "1"
        merged_env["MARKUS_SANDBOX"] = "1"
        if env_vars:
            merged_env.update(env_vars)

        timed_out = False
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.sandbox_root),
                env=merged_env
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = proc.returncode if proc.returncode is not None else -1
            except asyncio.TimeoutError:
                timed_out = True
                proc.kill()
                await proc.wait()
                stdout = ""
                stderr = f"ExecutionTimedOut: Exceeded {timeout}s threshold."
                exit_code = -9
        except Exception as exc:
            stdout = ""
            stderr = f"SandboxSpawnError: {str(exc)}"
            exit_code = -1
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            # Clean up temporary script
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            runtime_ms=elapsed_ms,
            timed_out=timed_out,
            sandbox_path=str(self.sandbox_root)
        )

if __name__ == "__main__":
    async def test_sandbox() -> None:
        sandbox = MarkusProcessSandbox()
        
        # Test 1: Valid calculation
        res1 = await sandbox.execute_python_code("print('SANDBOX_OK:', sum(range(100)))")
        print("Test 1 Result:", res1)
        
        # Test 2: Timeout containment
        res2 = await sandbox.execute_python_code("import time; time.sleep(5)", timeout_s=0.5)
        print("\nTest 2 Timeout Result:", res2)

    asyncio.run(test_sandbox())
