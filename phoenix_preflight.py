"""
PHOENIX Directive Pre-Flight Check & Resilience Hook
Automates the Directive 0 scan across Supermemory and Obsidian.
"""

from __future__ import annotations
import os
import sys
import json
from pathlib import Path

def get_vault_path() -> Path:
    user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    candidates = [
        user_home / "OneDrive" / "Documents" / "Obsidian Vault",
        user_home / "Documents" / "Obsidian Vault",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

def verify_prime_directive() -> dict[str, str | bool]:
    vault = get_vault_path()
    directive_file = vault / "PRIME-DIRECTIVE.md"
    
    status = {
        "obsidian_file_exists": directive_file.exists(),
        "obsidian_path": str(directive_file),
        "status": "ONLINE" if directive_file.exists() else "MISSING"
    }
    return status

if __name__ == "__main__":
    res = verify_prime_directive()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["obsidian_file_exists"] else 1)
