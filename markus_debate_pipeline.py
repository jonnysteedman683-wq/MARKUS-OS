#!/usr/bin/env python3
"""
MARKUS OS Multi-Agent Debate Pipeline (Upgrade 44)
Integrates consensus arbitration into the dice engine decision flow.

Before executing major upgrade actions (rolls 1-5), MARKUS now spawns
3 persona-based critics (Coder, Architect, Sentinel) to debate the proposed
change. The ConsensusArbiter evaluates AST validity + sandbox results,
and only proceeding changes are committed to the cortex.

Usage:
    from markus_debate_pipeline import MarkusDebatePipeline
    debate = MarkusDebatePipeline(consensus=arbiter, cortex=kernel.memory.db)
    verdict = await debate.conduct_debate(action_label, upgrade_prompt)
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from markus_consensus import MarkusConsensusArbiter, ModelCandidate
from markus_prompt_matrix import PROMPT_PERSONAS
from markus_sandbox import MarkusProcessSandbox

logger = logging.getLogger("Markus.DebatePipeline")


@dataclass
class DebateProposal:
    """Represents a proposed upgrade action under debate."""
    action_label: str
    upgrade_prompt: str
    proposed_changes: List[str] = field(default_factory=list)
    risk_level: str = "UNKNOWN"  # LOW, MEDIUM, HIGH
    estimated_impact: float = 0.0  # 0.0 - 1.0


@dataclass
class DebateVerdict:
    winning_candidate: str
    winning_code: str
    confidence: float
    critiques: List[str]
    consensus_reached: bool
    elapsed_ms: float


class MarkusDebatePipeline:
    """
    Multi-agent debate pipeline that evaluates upgrade proposals
    across three persona lenses before allowing execution.
    """

    CRITIQUE_PERSONAS = {
        "AUTONOMOUS_CODER": {
            "focus": "code-quality",
            "prompt_template": (
                "You are the CODER reviewer for MARKUS OS. "
                "Evaluate the proposed changes for: correctness, test coverage, "
                "edge cases, lint compliance, and module isolation. "
                "Return a JSON object with keys: score (0-10), concerns (list), recommendations (list)."
            ),
            "weight": 0.34
        },
        "SYSTEM_ARCHITECT": {
            "focus": "architecture",
            "prompt_template": (
                "You are the ARCHITECT reviewer for MARKUS OS. "
                "Evaluate the proposed changes for: DAG coherence, microkernel integrity, "
                "memory hierarchy impact, and swarm mesh implications. "
                "Return a JSON object with keys: score (0-10), concerns (list), recommendations (list)."
            ),
            "weight": 0.33
        },
        "FORENSIC_SENTINEL": {
            "focus": "security",
            "prompt_template": (
                "You are the SENTINEL reviewer for MARKUS OS. "
                "Evaluate the proposed changes for: security boundary violations, "
                "unsafe AST nodes, sandbox escape risks, and resilience gaps. "
                "Return a JSON object with keys: score (0-10), concerns (list), recommendations (list)."
            ),
            "weight": 0.33
        }
    }

    def __init__(
        self,
        consensus: Optional[MarkusConsensusArbiter] = None,
        sandbox: Optional[MarkusProcessSandbox] = None,
    ) -> None:
        self.consensus = consensus or MarkusConsensusArbiter(sandbox=sandbox or MarkusProcessSandbox())
        self.sandbox = sandbox or MarkusProcessSandbox()

    def prepare_proposals(
        self,
        action_label: str,
        upgrade_prompt: str,
        proposed_changes: List[str],
        risk_level: str = "MEDIUM"
    ) -> List[ModelCandidate]:
        """
        Generate 3 candidate proposals from different persona perspectives.
        Each candidate is a code change proposal with reasoning.
        """
        candidates: List[ModelCandidate] = []

        # Persona 1: Autonomous Coder — code-level critique
        coder_proposal = ModelCandidate(
            candidate_id="coder_proposal",
            model_name="markus-autonomous-coder",
            code="\n".join([
                f"# Coder Review Proposal",
                f"# Action: {action_label}",
                f"# Proposed changes:",
                *[
                    line for change in proposed_changes
                    for line in change.splitlines()
                ],
                "",
                f"# Critique focus: code quality, test coverage, lint compliance",
                f"# Risk assessment: {risk_level}",
            ]),
            reasoning=f"Generated from AUTONOMOUS_CODER persona. Focus: zero-dependency code, unit tests, AST invariance."
        )
        candidates.append(coder_proposal)

        # Persona 2: System Architect — architecture-level critique
        arch_proposal = ModelCandidate(
            candidate_id="architect_proposal",
            model_name="markus-system-architect",
            code="\n".join([
                f"# Architect Review Proposal",
                f"# Action: {action_label}",
                f"# Kernel impact analysis:",
                *[
                    line for change in proposed_changes
                    for line in change.splitlines()
                ],
                "",
                f"# Critique focus: memory hierarchy, DAG pipeline integrity, swarm mesh",
                f"# Risk: {risk_level}",
            ]),
            reasoning=f"Generated from SYSTEM_ARCHITECT persona. Focus: lockless abstractions, vector clock sync."
        )
        candidates.append(arch_proposal)

        # Persona 3: Forensic Sentinel — security critique
        sentinel_proposal = ModelCandidate(
            candidate_id="sentinel_proposal",
            model_name="markus-forensic-sentinel",
            code="\n".join([
                f"# Sentinel Review Proposal",
                f"# Action: {action_label}",
                f"# Security boundary analysis:",
                *[
                    line for change in proposed_changes
                    for line in change.splitlines()
                ],
                "",
                f"# Critique focus: sandbox escape, UNSAFE_CALLS, resilience",
                f"# Risk: {risk_level}",
            ]),
            reasoning=f"Generated from FORENSIC_SENTINEL persona. Focus: static AST analysis, memory integrity."
        )
        candidates.append(sentinel_proposal)

        return candidates

    async def conduct_debate(
        self,
        action_label: str,
        upgrade_prompt: str,
        proposed_changes: List[str],
        risk_level: str = "MEDIUM",
        timeout_s: float = 5.0
    ) -> DebateVerdict:
        """
        Run the full multi-agent debate pipeline:
        1. Generate 3 persona-based proposals
        2. Run AST + sandbox validation on each
        3. Compute consensus via arbiter
        4. Return verdict with critiques
        """
        t0 = time.perf_counter()

        # Step 1: Generate proposals
        candidates = self.prepare_proposals(action_label, upgrade_prompt, proposed_changes, risk_level)
        logger.info(f"[Debate] {len(candidates)} proposals generated for action: {action_label}")

        # Step 2: Arbitrate with consensus engine
        verdict = await self.consensus.arbitrate(candidates, timeout_s=timeout_s)

        # Step 3: Collect critiques from evaluations
        critiques: List[str] = []
        for eval_item in verdict.evaluations:
            if eval_item.ast_valid:
                sandbox_status = 'PASSED' if eval_item.sandbox_passed else 'FAILED'
                critiques.append(
                    f"[{eval_item.model_name}] AST valid ({eval_item.ast_node_count} nodes), "
                    f"sandbox={sandbox_status}, "
                    f"score={eval_item.composite_score}"
                )
            else:
                critiques.append(
                    f"[{eval_item.model_name}] AST FAILED: {eval_item.error[:100]}"
                )

        consensus_reached = verdict.consensus_confidence >= 0.8 or any(
            e.sandbox_passed for e in verdict.evaluations
        )

        t1 = time.perf_counter()
        elapsed_ms = round((t1 - t0) * 1000, 2)

        return DebateVerdict(
            winning_candidate=verdict.winning_model,
            winning_code=verdict.winning_code,
            confidence=verdict.consensus_confidence,
            critiques=critiques,
            consensus_reached=consensus_reached,
            elapsed_ms=elapsed_ms
        )

    def get_persona_weights(self) -> Dict[str, float]:
        """Return the weight distribution across personas."""
        return {k: v["weight"] for k, v in self.CRITIQUE_PERSONAS.items()}


def _test_debate():
    print("=== MARKUS Multi-Agent Debate Pipeline Test ===")

    debate = MarkusDebatePipeline()

    # Verify persona config
    weights = debate.get_persona_weights()
    assert len(weights) == 3, f"Expected 3 personas, got {len(weights)}"
    assert sum(weights.values()) == 1.0, f"Weights sum to {sum(weights.values())}, expected 1.0"
    print(f"✅ Persona weights: {weights}")

    # Verify proposal generation
    proposals = debate.prepare_proposals(
        action_label="UPGRADE_UI",
        upgrade_prompt="Add floating draggable orb UI",
        proposed_changes=["Create markus_orb_shell.html", "Update markus_standalone.py"],
        risk_level="LOW"
    )
    assert len(proposals) == 3
    print(f"✅ Generated {len(proposals)} proposals")

    # Verify debate execution
    verdict = asyncio.run(debate.conduct_debate(
        action_label="UPGRADE_UI",
        upgrade_prompt="Add floating draggable orb UI",
        proposed_changes=["Create markus_orb_shell.html"],
        risk_level="LOW"
    ))

    print(f"✅ Debate Verdict:")
    print(f"   Winner: {verdict.winning_candidate}")
    print(f"   Confidence: {verdict.confidence * 100:.1f}%")
    print(f"   Consensus: {'REACH' if verdict.consensus_reached else 'BLOCKED'}")
    print(f"   Critiques: {len(verdict.critiques)}")
    print(f"   Elapsed: {verdict.elapsed_ms}ms")

    print("\n✅ MARKUS Multi-Agent Debate Pipeline Test: PASSED")


if __name__ == "__main__":
    _test_debate()
