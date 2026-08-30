"""
MARKUS OS Vault Run-Sync Bridge (ported from AXIOM-VAULT ObsidianVaultBridge)
============================================================================
Complements the existing markus_obsidian_sync.py (which journals cortex thoughts
into the VORPAL Vault). This module adds AXIOM's *operator-control + run-report*
pattern on top:

  * Typed command schema read from a YAML-frontmatter command center so the
    operator can inject runtime directives the way AXIOM does.
  * Per-run reports under Journal/Markus/Runs/run_NNNN.md (fitness, divergence,
    torus size, LLM mode, authors, code snapshot) — like AXIOM's reports/.
  * Vault-side lineage notes + auto LINEAGE_INDEX.md — like AXIOM's lineage/.
  * Architecture-doc link injection into the command-deck namespace.

Design choices to avoid clashing with markus_obsidian_sync.py:
  - Resuses the SAME vault resolver (_resolve_vault_path) and cortex DB so the
    two syncers never target different vaults.
  - Writes under a dedicated `Journal/Markus/Runs/` subtree; never touches the
    digest / live-stream / canvas / Index/Now.md files owned by the other module.
  - Git provenance is delegated to markus_obsidian_sync (single committer per
    vault) — this module only writes markdown, it does not commit.

Tested via hermes_verify_markus_vault_sync.py (auto-discovered by verify_all.py).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Markus.VaultSync")

# --------------------------------------------------------------------------
# Command-frontmatter schema (mirrors AXIOM-VAULT COMMAND_SCHEMA).
# Each entry: key -> {type, default}. Coerced by _coerce_scalar.
# --------------------------------------------------------------------------
COMMAND_SCHEMA: Dict[str, Dict[str, Any]] = {
    "state":                  {"type": "str",   "default": "ACTIVE"},
    "mutation_rate_override":  {"type": "float", "default": 0.35},
    "emergency_stop":          {"type": "bool",  "default": False},
    "force_dna_seed":          {"type": "str",   "default": None},
    "report_verbosity":        {"type": "int",   "default": 1},     # 0 quiet 1 normal 2 verbose
    "llm_mode":                {"type": "str",   "default": "auto"},  # auto|off|on
    "pause_after_generation":  {"type": "int",   "default": None},
    "seed_pool":               {"type": "list",  "default": None},
}
ALLOWED_LLM_MODES = {"auto", "off", "on"}
ALLOWED_VERBOSITY = {0, 1, 2}

# Where this syncer lives inside the vault (kept separate from the cortex journal).
RUNS_DIR_REL = Path("Journal") / "Markus" / "Runs"
ARCH_DOC_REL = Path("Journal") / "Markus" / "MARKUS-RUN-SYNC-architecture.html"


def _resolve_vault_path() -> Path:
    """Mirror markus_obsidian_sync._resolve_vault_path: prefer VORPAL Vault."""
    user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    vorpal = user_home / "OneDrive" / "Documents" / "VORPAL Vault"
    legacy = user_home / "OneDrive" / "Documents" / "Obsidian Vault"
    if vorpal.exists():
        return vorpal
    return legacy


class MarkusVaultSync:
    """Operator-command ingest + run/lineage reporting into the VORPAL Vault."""

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        self.vault_path = vault_path or _resolve_vault_path()
        self.runs_dir = self.vault_path / RUNS_DIR_REL
        self.lineage_dir = self.runs_dir / "lineage"
        self.command_file = self.runs_dir / "00_COMMAND_CENTER.md"
        self.lineage_index = self.lineage_dir / "LINEAGE_INDEX.md"
        self._initialize_vault()

    # ----------------------------------------------------------- bootstrap
    def _initialize_vault(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.lineage_dir.mkdir(parents=True, exist_ok=True)
        if not self.command_file.exists():
            self.command_file.write_text(self._default_command_markdown(), encoding="utf-8")
        if not self.lineage_index.exists():
            self.lineage_index.write_text(
                "# 🧬 MARKUS RUN LINEAGE INDEX\n\n"
                "_Auto-generated index of vault-side run notes. Do not hand-edit._\n\n"
                "| Run | Goal | Status | Link |\n"
                "| :--- | :--- | :--- | :--- |\n",
                encoding="utf-8")

    def _default_command_markdown(self) -> str:
        lines = ["---"]
        for key, spec in COMMAND_SCHEMA.items():
            d = spec["default"]
            rendered = ("null" if d is None
                        else ("true" if d is True else "false") if isinstance(d, bool)
                        else str(d))
            lines.append(f"{key}: {rendered}")
        lines += ["---", "",
                  "# 🕹️ MARKUS CENTRAL COMMAND INTERFACE",
                  "Modify frontmatter variables above to inject commands into the run engine."]
        return "\n".join(lines) + "\n"

    # ----------------------------------------------------------- parsing
    @staticmethod
    def _coerce_scalar(raw: str) -> Any:
        v = raw.strip()
        low = v.lower()
        if low in ("true", "yes", "on"):
            return True
        if low in ("false", "no", "off"):
            return False
        if low in ("null", "none", "nil", "~", ""):
            return None
        try:
            return float(v) if "." in v else int(v)
        except ValueError:
            return v

    def read_commands(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {}
        try:
            content = self.command_file.read_text(encoding="utf-8")
            if content.lstrip().startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].strip().split("\n"):
                        if not line.strip() or ":" not in line:
                            continue
                        k, raw = line.split(":", 1)
                        k = k.strip()
                        if k not in COMMAND_SCHEMA:
                            config[k] = self._coerce_scalar(raw)
                            continue
                        spec = COMMAND_SCHEMA[k]
                        if spec["type"] == "list":
                            val = [s.strip() for s in raw.split(",") if s.strip()] or None
                        elif spec["type"] == "bool":
                            val = self._coerce_scalar(raw)
                        elif spec["type"] == "float":
                            try:
                                val = float(raw.strip())
                            except ValueError:
                                val = None
                        elif spec["type"] == "int":
                            try:
                                val = int(raw.strip())
                            except ValueError:
                                val = None
                        else:  # str — keep verbatim, do NOT bool-coerce "on"/"off"
                            val = raw.strip()
                        config[k] = val
        except Exception:  # noqa: BLE001 — fall back to defaults
            pass
        for key, spec in COMMAND_SCHEMA.items():
            config.setdefault(key, spec["default"])
        if config.get("llm_mode") not in ALLOWED_LLM_MODES:
            config["llm_mode"] = "auto"
        if config.get("report_verbosity") not in ALLOWED_VERBOSITY:
            config["report_verbosity"] = 1
        return config

    # ------------------------------------------------------- run reports
    def log_run_report(self, run_id: int, data: Dict[str, Any]) -> Path:
        verbosity = int(data.get("verbosity", 1) or 1)
        status = data.get("status", "UNKNOWN")
        goal = data.get("goal", "—")
        divergence = float(data.get("divergence", 0.0) or 0.0)
        mutations = data.get("mutations_count", 0)
        best_fit = data.get("best_fitness", "—")
        inc_fit = data.get("incumbent_fitness", "—")
        torus_size = data.get("torus_size", "—")
        llm_mode = data.get("llm_mode", "auto")
        authors = data.get("authors") or []
        code = data.get("code_snapshot")

        md = f"""---
run: {run_id}
goal: {goal}
status: {status}
divergence: {divergence}
---

# 🧬 MARKUS Run Report: #{run_id}
- **Goal:** `{goal}`
- **Status:** `{status}`
- **Divergence:** `{divergence}`

| Metric | Value |
| :--- | :--- |
| **Mutations Applied** | `{mutations}` |
| **Best Fitness** | `{best_fit}` |
| **Incumbent Fitness** | `{inc_fit}` |
| **Torus Survivors** | `{torus_size}` |
| **Sovereign LLM Mode** | `{llm_mode}` |

"""
        if authors and verbosity >= 1:
            md += "### Contributing Agents\n" + "".join(f"- `{a}`\n" for a in authors) + "\n"
        if code and verbosity >= 1:
            md += f"## Executed Code Artifact\n```python\n{code}\n```\n"
        md += (f"\n## Links\n* Lineage Note: [[lineage_run_{run_id:04d}]]\n"
                f"* Command Deck: [[Index/Now]]\n")
        report_file = self.runs_dir / f"run_{run_id:04d}.md"
        report_file.write_text(md, encoding="utf-8")
        return report_file

    # ------------------------------------------------------- lineage
    def log_lineage_note(self, run_id: int, data: Dict[str, Any]) -> Path:
        note_file = self.lineage_dir / f"lineage_run_{run_id:04d}.md"
        goal = data.get("goal", "—")
        status = data.get("status", "—")
        divergence = data.get("divergence", "—")
        best_fit = data.get("best_fitness", "—")
        inc_fit = data.get("incumbent_fitness", "—")
        torus_size = data.get("torus_size", "—")
        authors = data.get("authors") or []
        authors_block = "".join(f"- `{a}`\n" for a in authors) or "—"

        md = f"""---
run: {run_id}
goal: {goal}
status: {status}
divergence: {divergence}
---

# 🧬 MARKUS Run Lineage: #{run_id}

| Field | Value |
| :--- | :--- |
| **Goal** | `{goal}` |
| **Status** | `{status}` |
| **Divergence** | `{divergence}` |
| **Best Fitness** | `{best_fit}` |
| **Incumbent Fitness** | `{inc_fit}` |
| **Torus Survivors** | `{torus_size}` |

### Agents
{authors_block}

### Links
- Report: [[run_{run_id:04d}]]
- Previous: [[lineage_run_{run_id-1:04d}]]
- Command Deck: [[Index/Now]]
"""
        note_file.write_text(md, encoding="utf-8")
        self._append_lineage_index(run_id, goal, status, note_file.name)
        return note_file

    def _append_lineage_index(self, run_id: int, goal: str, status: str, note_name: str) -> None:
        try:
            text = self.lineage_index.read_text(encoding="utf-8")
        except Exception:
            text = "# 🧬 MARKUS RUN LINEAGE INDEX\n\n| Run | Goal | Status | Link |\n| :--- | :--- | :--- | :--- |\n"
        row = f"| {run_id} | `{goal}` | `{status}` | [[{note_name.replace('.md', '')}]] |\n"
        if row.strip() in text:
            return
        text = text.rstrip("\n") + "\n" + row
        self.lineage_index.write_text(text, encoding="utf-8")

    # --------------------------------------------------- architecture link
    def ensure_architecture_link(self, arch_doc_rel: Optional[Path] = None) -> Path:
        """Write a small linker note pointing at the architecture HTML (if present)."""
        arch_rel = arch_doc_rel or ARCH_DOC_REL
        link_file = self.runs_dir / "ARCHITECTURE_LINK.md"
        md = (f"# 📐 MARKUS Run-Sync Architecture\n\n"
               f"- Diagram: [[{arch_rel.as_posix()}]]\n"
               f"- Generated by `markus_vault_sync.py` (ported from AXIOM-VAULT)\n")
        link_file.write_text(md, encoding="utf-8")
        return link_file
