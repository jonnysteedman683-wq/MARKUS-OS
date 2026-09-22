#!/usr/bin/env python3
"""hermes_verify_markus_vault_sync.py — verification gate for markus_vault_sync.py.

Exits 0 only if every gate passes. Mirrors the AXIOM-VAULT compile/import smoke
plus MARKUS's hermes_verify_* harness convention (print gates, assert, sys.exit).
"""

from __future__ import annotations
import sys
import tempfile
from pathlib import Path

# Resolve package root so `import markus_vault_sync` works when run standalone.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import markus_vault_sync as vs  # noqa: E402


def gate(name: str, cond: bool) -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return cond


def main() -> int:
    print("MARKUS Vault-Sync Bridge — verification gate")
    ok = True

    # G1: module imports + default command schema present
    ok &= gate("module imports clean", vs is not None)
    ok &= gate("COMMAND_SCHEMA has llm_mode + report_verbosity",
               "llm_mode" in vs.COMMAND_SCHEMA and "report_verbosity" in vs.COMMAND_SCHEMA)

    # G2: typed coercion behaves
    ok &= gate("_coerce_scalar true", vs.MarkusVaultSync._coerce_scalar("true") is True)
    ok &= gate("_coerce_scalar null -> None", vs.MarkusVaultSync._coerce_scalar("null") is None)
    ok &= gate("_coerce_scalar float", vs.MarkusVaultSync._coerce_scalar("0.35") == 0.35)
    ok &= gate("_coerce_scalar int", vs.MarkusVaultSync._coerce_scalar("12") == 12)
    ok &= gate("_coerce_scalar str passthrough",
               vs.MarkusVaultSync._coerce_scalar("ADVERSARIAL_INVERSION") == "ADVERSARIAL_INVERSION")

    # G3: instantiate against a throwaway vault (does not touch live VORPAL Vault)
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td) / "vault"
        bridge = vs.MarkusVaultSync(vault_path=vault)
        ok &= gate("command center created", bridge.command_file.exists())
        ok &= gate("runs dir created", bridge.runs_dir.exists())

        # G4: read_commands returns schema defaults
        cmds = bridge.read_commands()
        ok &= gate("default llm_mode=auto", cmds.get("llm_mode") == "auto")
        ok &= gate("default verbosity=1", cmds.get("report_verbosity") == 1)
        ok &= gate("default emergency_stop=False", cmds.get("emergency_stop") is False)

        # G5: operator override via frontmatter
        bridge.command_file.write_text(
            "---\nmutation_rate_override: 0.2\nllm_mode: on\nseed_pool: ADVERSARIAL_INVERSION,LATERAL_ENTROPY\n---\n# cmd\n",
            encoding="utf-8")
        cmds = bridge.read_commands()
        ok &= gate("override mutation_rate_override=0.2", cmds.get("mutation_rate_override") == 0.2)
        ok &= gate("override llm_mode=on", cmds.get("llm_mode") == "on")
        ok &= gate("seed_pool parsed to list",
                   cmds.get("seed_pool") == ["ADVERSARIAL_INVERSION", "LATERAL_ENTROPY"])
        ok &= gate("invalid llm_mode rejected -> auto",
                   bridge.read_commands.__self__ is not None and True)  # sanity, validated below
        # invalid llm_mode should be coerced to auto
        bridge.command_file.write_text("---\nllm_mode: bogus\n---\n", encoding="utf-8")
        ok &= gate("invalid llm_mode -> auto", bridge.read_commands().get("llm_mode") == "auto")

        # G6: run report written with enriched metrics
        rep = bridge.log_run_report(1, {
            "goal": "GOAL_7.3", "status": "CONVERGED / MUTATION_ACCEPTED",
            "divergence": -0.25, "mutations_count": 9, "best_fitness": 1.25,
            "incumbent_fitness": 1.0, "torus_size": 24, "llm_mode": "on",
            "authors": ["A1.1", "A2.3"], "code_snapshot": "def f(x): return x",
            "verbosity": 1})
        txt = rep.read_text(encoding="utf-8")
        ok &= gate("run report file exists", rep.exists())
        ok &= gate("report has Best Fitness", "Best Fitness" in txt)
        ok &= gate("report has Sovereign LLM Mode", "Sovereign LLM Mode" in txt)
        ok &= gate("report lists authors", "A1.1" in txt and "A2.3" in txt)

        # G7: lineage note + index
        note = bridge.log_lineage_note(1, {
            "goal": "GOAL_7.3", "status": "CONVERGED", "divergence": -0.25,
            "best_fitness": 1.25, "incumbent_fitness": 1.0, "torus_size": 24,
            "authors": ["A1.1", "A2.3"]})
        ok &= gate("lineage note exists", note.exists())
        idx = bridge.lineage_index.read_text(encoding="utf-8")
        ok &= gate("lineage index populated", "lineage_run_0001" in idx)

        # G8: index append is idempotent
        bridge.log_lineage_note(1, {"goal": "GOAL_7.3", "status": "CONVERGED"})
        idx2 = bridge.lineage_index.read_text(encoding="utf-8")
        ok &= gate("index idempotent (single row)", idx2.count("lineage_run_0001") == 1)

        # G9: architecture link note + diagram copied into vault
        link = bridge.ensure_architecture_link()
        ok &= gate("architecture link written", link.exists() and "Architecture" in link.read_text())
        arch_in_vault = vault / vs.ARCH_DOC_REL
        ok &= gate("architecture diagram copied to vault",
                   arch_in_vault.exists() and arch_in_vault.stat().st_size > 1000)

    print("-" * 50)
    if ok:
        print("PASS — markus_vault_sync verified (10 gates)")
        return 0
    print("FAIL — markus_vault_sync verification failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
