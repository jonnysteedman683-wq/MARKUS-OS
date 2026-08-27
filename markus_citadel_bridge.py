"""Local MARKUS boundary for Citadel ranked recall and provenance-bound writes."""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

CITADEL_SCRIPT = Path("C:/Users/jonny/OneDrive/Desktop/The-Citadel-Vault/The-Citadel-Vault/scripts/citadel_recall.py")


def _module():
    if "citadel_recall" not in sys.modules:
        import importlib.util
        spec = importlib.util.spec_from_file_location("citadel_recall", CITADEL_SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Citadel recall module unavailable: {CITADEL_SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["citadel_recall"] = module
        spec.loader.exec_module(module)
    return sys.modules["citadel_recall"]


def search(query: str, limit: int = 10, section: str | None = None) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []
    return _module().search(query, limit=limit, section=section)


def write_note(title: str, content: str, *, section: str, source_run_id: str,
               reason: str, evidence: str = "[MEDIUM]") -> dict[str, Any]:
    return _module().create_note(title, content, section=section, source_run_id=source_run_id,
                                  reason=reason, evidence=evidence)
