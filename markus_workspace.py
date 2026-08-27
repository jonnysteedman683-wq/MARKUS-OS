#!/usr/bin/env python3
"""Portable execution boundary: local and sandbox workspaces share one API."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from markus_sandbox import MarkusProcessSandbox, SandboxResult

@dataclass(frozen=True)
class WorkspaceResult:
    mode: str
    result: SandboxResult

class LocalWorkspace:
    def __init__(self, root: Optional[Path] = None, timeout_s: float = 10.0):
        self.root = Path(root or Path.cwd()).resolve()
        self.timeout_s = timeout_s

    async def execute_python(self, code: str) -> WorkspaceResult:
        sandbox = MarkusProcessSandbox(self.root, self.timeout_s)
        result = await sandbox.execute_python_code(code, timeout_s=self.timeout_s)
        return WorkspaceResult("local", result)

class SandboxWorkspace:
    def __init__(self, root: Optional[Path] = None, timeout_s: float = 10.0):
        self.root = Path(root or "C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/workspace").resolve()
        self.timeout_s = timeout_s

    async def execute_python(self, code: str) -> WorkspaceResult:
        sandbox = MarkusProcessSandbox(self.root, self.timeout_s)
        result = await sandbox.execute_python_code(code, timeout_s=self.timeout_s)
        return WorkspaceResult("sandbox", result)

async def _self_test() -> int:
    local = await LocalWorkspace().execute_python("print('WORKSPACE_OK')")
    sandbox = await SandboxWorkspace().execute_python("print('WORKSPACE_OK')")
    ok = all(r.result.exit_code == 0 and r.result.stdout.strip() == "WORKSPACE_OK" for r in (local, sandbox))
    print("PASS - local/sandbox contract parity" if ok else "FAIL - local/sandbox contract parity")
    print("OVERALL: PASS" if ok else "OVERALL: FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(asyncio.run(_self_test()))
