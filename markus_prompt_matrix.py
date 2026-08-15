#!/usr/bin/env python3
"""
MARKUS OS Dynamic Prompt Synthesis Matrix & Few-Shot Retrieval Engine (Upgrade 31)
Synthesizes system prompts, task constraints, and dynamic few-shot exemplars
retrieved directly from SQLite L3 Cortex FTS5 database based on semantic relevance.
"""

from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.PromptMatrix")

# System baseline persona presets
PROMPT_PERSONAS: Dict[str, Dict[str, Any]] = {
    "AUTONOMOUS_CODER": {
        "role": "MARKUS Principal Autonomous Software Engineer",
        "directives": [
            "Write modular, zero-dependency, verified Python/TypeScript code.",
            "Always include unit self-tests, edge case traps, and timing benchmarks.",
            "Preserve AST invariance and ensure clean lint checks."
        ],
        "temperature": 0.2
    },
    "SYSTEM_ARCHITECT": {
        "role": "MARKUS Kernel & Swarm Infrastructure Architect",
        "directives": [
            "Design lockless, zero-copy, high-throughput microkernel abstractions.",
            "Enforce strict circuit-breaker resilience and vector clock synchronization.",
            "Decompose workflows into topologically sortable DAG execution pipelines."
        ],
        "temperature": 0.3
    },
    "FORENSIC_SENTINEL": {
        "role": "MARKUS Self-Healing Sentinel & Security Auditor",
        "directives": [
            "Perform static AST analysis and dynamic sandbox inspection.",
            "Enforce memory integrity verification and SHA-256 micro-checkpointing.",
            "Isolate degraded swarm nodes and trigger automatic rollback protocols."
        ],
        "temperature": 0.1
    }
}

@dataclass
class SynthesizedPrompt:
    persona_name: str
    system_prompt: str
    user_prompt: str
    exemplars: List[Dict[str, Any]]
    synthesized_at: float
    token_estimate: int
    metadata: Dict[str, Any] = field(default_factory=dict)

class MarkusPromptSynthesisMatrix:
    """
    Dynamic prompt engineering and few-shot exemplar synthesis engine.
    Fetches historical high-confidence thoughts and execution logs from L3 DB.
    """

    def __init__(self, db: Optional[PersistentCortexDB] = None) -> None:
        self.db = db or PersistentCortexDB()

    def retrieve_few_shot_exemplars(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Queries SQLite FTS5 Cortex for historical thoughts relevant to the prompt."""
        if not query or not query.strip():
            return self.db.get_recent_thoughts(limit=limit)
        
        # Clean query for FTS5 syntax
        clean_terms = [w for w in query.replace('"', '').replace("'", "").split() if len(w) > 2]
        if not clean_terms:
            return self.db.get_recent_thoughts(limit=limit)
        
        fts_query = " OR ".join(clean_terms[:6])
        try:
            results = self.db.search_thoughts(fts_query, limit=limit)
            if not results:
                results = self.db.get_recent_thoughts(limit=limit)
            return results
        except Exception as e:
            logger.warning(f"FTS search fallback to recent thoughts: {e}")
            return self.db.get_recent_thoughts(limit=limit)

    def synthesize_prompt(
        self,
        user_input: str,
        persona: str = "AUTONOMOUS_CODER",
        include_exemplars: bool = True,
        max_exemplars: int = 3,
        context_registers: Optional[Dict[str, Any]] = None
    ) -> SynthesizedPrompt:
        """Constructs an integrated system and user prompt block with few-shot context."""
        t0 = time.time()
        p_data = PROMPT_PERSONAS.get(persona, PROMPT_PERSONAS["AUTONOMOUS_CODER"])

        # Base System Directives
        sys_lines = [
            f"You are {p_data['role']}.",
            "Core Directives:"
        ]
        for d in p_data["directives"]:
            sys_lines.append(f"- {d}")

        if context_registers:
            sys_lines.append("\nActive Kernel Registers:")
            for k, v in context_registers.items():
                sys_lines.append(f"  • {k}: {v}")

        exemplars: List[Dict[str, Any]] = []
        if include_exemplars:
            exemplars = self.retrieve_few_shot_exemplars(user_input, limit=max_exemplars)
            if exemplars:
                sys_lines.append("\nRelevant L3 Cortex Memory Exemplars:")
                for i, ex in enumerate(exemplars, 1):
                    sys_lines.append(f"[{i}] ({ex['agent']}) {ex['content']}")

        full_system_prompt = "\n".join(sys_lines)
        token_estimate = int(len(full_system_prompt.split()) * 1.3) + int(len(user_input.split()) * 1.3)

        return SynthesizedPrompt(
            persona_name=persona,
            system_prompt=full_system_prompt,
            user_prompt=user_input,
            exemplars=exemplars,
            synthesized_at=t0,
            token_estimate=token_estimate,
            metadata={
                "temperature": p_data["temperature"],
                "exemplar_count": len(exemplars)
            }
        )

    def list_personas(self) -> Dict[str, Any]:
        return {
            name: {
                "role": data["role"],
                "directives": data["directives"],
                "temperature": data["temperature"]
            }
            for name, data in PROMPT_PERSONAS.items()
        }

def _test_synthesis():
    print("=== MARKUS Dynamic Prompt Synthesis Matrix Test ===")
    matrix = MarkusPromptSynthesisMatrix()

    # Ingest test thought to verify FTS retrieval
    matrix.db.append_thought(
        "synth_001",
        "SENTINEL",
        "Optimized Kahn topological sort for DAG cycle detection",
        {"benchmark_ms": 12.4}
    )

    # 1. Synthesize Prompt
    res = matrix.synthesize_prompt(
        user_input="Decompose task into a topological DAG",
        persona="SYSTEM_ARCHITECT",
        include_exemplars=True,
        context_registers={"OS_STATUS": "ACTIVE", "TIER": "L1.5_RING"}
    )

    print(f"Persona: {res.persona_name}")
    print(f"Token Estimate: {res.token_estimate}")
    print(f"Exemplars Found: {len(res.exemplars)}")
    print("\n--- Synthesized System Prompt ---")
    print(res.system_prompt)

    assert "SYSTEM_ARCHITECT" == res.persona_name
    assert res.token_estimate > 20
    assert len(res.exemplars) > 0
    print("\n✅ Dynamic Prompt Synthesis Matrix Test: PASSED")

if __name__ == "__main__":
    _test_synthesis()
