#!/usr/bin/env python3
"""
MARKUS OS Web Research Integration (Upgrade 49b)
Enables the dice engine to research external architectures when rolling
Action 5: TECHNICAL_ALTERNATIVE_UPGRADE.
"""

from __future__ import annotations
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Markus.WebResearch")

# Where research reports are appended so the dice engine's research slot
# leaves a durable artifact (not just stdout).
DEFAULT_ROADMAP = Path(__file__).resolve().parent / "research" / "evolutionary_loop_roadmap.md"


class WebResearchEngine:
    """
    Provides research capabilities for technical alternatives when
    the dice engine rolls Action 5 (TECHNICAL_ALTERNATIVE_UPGRADE).
    
    Integrates with available web search tools or falls back to
    pre-indexed research patterns.
    """

    # Pre-indexed research patterns for common AI agent OS architectures
    RESEARCH_KNOWLEDGE_BASE: Dict[str, List[str]] = {
        "autonomous_agent_loop": [
            "AutoGPT recursive goal decomposition → task queue → self-reflection",
            "BabyAGI priority-based task queue with LLM-generated subtasks",
            "SWE-agent: Computer-use agent solving GitHub issues with terminal+browser",
            "Reflexion: Self-reflection → critique → refinement loop",
            "DevSwarm: Strange-loop self-healing with AST validation",
            "EvoAgentX: Dynamic topology adaptation for multi-agent evolution"
        ],
        "microkernel_architecture": [
            "MINIX microkernel with message passing between services",
            "seL4 formally verified microkernel with capability-based security",
            "Mach microkernel with RPC-based service architecture",
            "L4 microkernel with fast IPC and small trusted computing base",
            "QEMU user-mode emulation for cross-platform kernel development"
        ],
        "multi_model_routing": [
            "vLLM: High-throughput LLM inference with PagedAttention",
            "TGI: HuggingFace Text Generation Inference with continuous batching",
            "Ollama: Local model serving with ModELFUSE pipeline",
            "OpenRouter: Unified API with performance-based routing",
            "Adaptive Model Switcher: Real-time reliability scoring",
            "Confidence triage: >=0.8 hermes, >=0.5 ollama, <0.5 nous"
        ],
        "self_improving_code": [
            "Genetic programming with AST mutation operators",
            "Neural architecture search for code generation",
            "Meta-learning: Learning to learn optimization algorithms",
            "Automated program repair with semantic patching",
            "SWE-bench: Benchmark for evaluating autonomous coding agents",
            "EvoSuite: Automated test generation through evolutionary search"
        ],
        "swarm_intelligence": [
            "UDP gossip protocols with Lamport vector clocks for consistency",
            "TCP reliability layer for message delivery guarantees",
            "Ant colony optimization for distributed task assignment",
            "Particle swarm optimization for parameter tuning",
            "RAFT consensus for distributed state machine replication",
            "Gossip-based failure detection with φ accrual monitors"
        ]
    }

    def __init__(self, cortex=None) -> None:
        self.cortex = cortex
        self._research_cache: Dict[str, str] = {}

    def research_technical_alternative(self, topic: str,
                                       max_results: int = 5,
                                       live_findings: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Research a technical alternative topic.
        Uses the pre-indexed knowledge base plus optional live findings injected
        by the orchestrating agent (e.g. from a real web_search / web_extract).
        """
        # Check cache first
        cache_key = f"research_{topic}_{int(time.time() / 300)}"  # 5-minute cache
        if cache_key in self._research_cache:
            return json.loads(self._research_cache[cache_key])

        findings: List[str] = []

        # Get from knowledge base
        if topic in self.RESEARCH_KNOWLEDGE_BASE:
            findings.extend(self.RESEARCH_KNOWLEDGE_BASE[topic][:max_results])

        # Merge live findings (real web search results fed in by the caller).
        if live_findings:
            for f in live_findings:
                if f not in findings:
                    findings.append(f)
            findings = findings[:max_results + 3]

        # Generate analysis and recommendation
        analysis = self._analyze_findings(findings, topic)

        result = {
            "topic": topic,
            "findings": findings,
            "live_findings": bool(live_findings),
            "analysis": analysis,
            "timestamp": time.time()
        }

        # Cache and log to cortex
        self._research_cache[cache_key] = json.dumps(result)
        if self.cortex:
            self.cortex.append_thought(
                f"research_{int(time.time())}", "WEB_RESEARCH_ENGINE",
                f"Researched: {topic} — {len(findings)} findings",
                {"topic": topic, "findings_count": len(findings)}
            )

        return result

    def write_to_roadmap(self, result: Dict[str, Any],
                         report_path: Optional[Path] = None) -> Path:
        """
        Append the improvement proposal for a research result to the roadmap,
        leaving a durable artifact. Returns the file that was written.
        """
        path = Path(report_path or DEFAULT_ROADMAP)
        proposal = self.generate_improvement_proposal(result)
        all_findings = "\n".join(f"- {f}" for f in result.get("findings", []))
        ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        block = (
            f"\n## {ts} — Dice Research Slot: {result['topic']}\n"
            f"Live web findings: {'yes' if result.get('live_findings') else 'no'}\n\n"
            f"### All findings ({len(result.get('findings', []))})\n"
            f"{all_findings}\n\n"
            f"{proposal}\n"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
        return path

    def research_and_report(self, topic: str,
                            live_findings: Optional[List[str]] = None,
                            report_path: Optional[Path] = None,
                            max_results: int = 5) -> Dict[str, Any]:
        """Research a topic and persist the proposal to the roadmap in one step."""
        result = self.research_technical_alternative(topic, max_results=max_results,
                                                     live_findings=live_findings)
        written = self.write_to_roadmap(result, report_path=report_path)
        result["report_path"] = str(written)
        return result

    def _analyze_findings(self, findings: List[str], topic: str) -> Dict[str, Any]:
        """Analyze research findings and extract actionable insights."""
        # Extract key patterns, tradeoffs, and recommendations
        patterns = []
        tradeoffs = []
        recommendations = []
        
        # Simple pattern matching for known architectures
        for finding in findings:
            if "tradeoff" in finding.lower() or "vs" in finding.lower():
                tradeoffs.append(finding)
            elif "consensus" in finding.lower() or "routing" in finding.lower():
                patterns.append(finding)
            else:
                recommendations.append(finding)
        
        return {
            "patterns": patterns[:3],
            "tradeoffs": tradeoffs[:3],
            "recommendations": recommendations[:3],
            "implementation_feasibility": self._assess_feasibility(topic)
        }

    def _assess_feasibility(self, topic: str) -> Dict[str, Any]:
        """Assess how feasible it is to implement findings in MARKUS."""
        assessments = {
            "autonomous_agent_loop": {
                "current_coverage": "High - Dice engine + debate pipeline",
                "improvement_opportunity": "Add hierarchical task decomposition",
                "effort_estimate": "Medium"
            },
            "microkernel_architecture": {
                "current_coverage": "Medium - Tiered memory cortex",
                "improvement_opportunity": "Message-passing between services",
                "effort_estimate": "High"
            },
            "multi_model_routing": {
                "current_coverage": "Medium - Adaptive matrix",
                "improvement_opportunity": "Real-time reliability scoring",
                "effort_estimate": "Low"
            },
            "self_improving_code": {
                "current_coverage": "High - PHOENIX AST + debate pipeline",
                "improvement_opportunity": "Genetic programming operators",
                "effort_estimate": "Very High"
            },
            "swarm_intelligence": {
                "current_coverage": "Medium - UDP gossip replication",
                "improvement_opportunity": "RAFT consensus, failure detection",
                "effort_estimate": "High"
            }
        }
        
        return assessments.get(topic, {
            "current_coverage": "Unknown",
            "improvement_opportunity": "Research needed",
            "effort_estimate": "Unknown"
        })

    def generate_improvement_proposal(self, research_result: Dict[str, Any]) -> str:
        """Generate a concrete improvement proposal from research findings."""
        topic = research_result["topic"]
        analysis = research_result["analysis"]
        
        proposal = f"""
## Improvement Proposal: {topic.replace('_', ' ').title()}

### Current MARKUS Coverage
{analysis['implementation_feasibility']['current_coverage']}

### Key Findings from Research
{chr(10).join(f"- {r}" for r in analysis['recommendations'])}

### Identified Tradeoffs
{chr(10).join(f"- {t}" for t in analysis['tradeoffs'])}

### Proposed Enhancement
{analysis['implementation_feasibility']['improvement_opportunity']}

### Effort Estimate
{analysis['implementation_feasibility']['effort_estimate']}

### Next Steps
1. Create implementation plan for {analysis['implementation_feasibility']['improvement_opportunity']}
2. Generate PHOENIX CLI module for AST validation
3. Test with existing test suite
4. Commit with conventional commit format
"""
        return proposal.strip()


def _test_research():
    """Test the web research engine, including roadmap persistence."""
    import tempfile
    print("=== MARKUS Web Research Engine Test ===\n")

    engine = WebResearchEngine()

    topics = [
        "autonomous_agent_loop",
        "swarm_intelligence",
        "multi_model_routing"
    ]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "research.md"
        for topic in topics:
            print(f"\n🔍 Researching: {topic}")
            # Inject fake live findings to exercise the live seam.
            live = [f"[LIVE] Candidate approach {i} for {topic}" for i in range(1, 3)]
            result = engine.research_and_report(topic, live_findings=live, report_path=tmp_path)
            print(f"  Findings: {len(result['findings'])} (live={result['live_findings']})")
            print(f"  Feasibility: {result['analysis']['implementation_feasibility']['effort_estimate']}")
            print(f"  Persisted: {result['report_path']}")

            proposal = engine.generate_improvement_proposal(result)
            print(f"\n{proposal[:300]}...")

        # Verify the roadmap file was actually written with all 3 topics.
        written = tmp_path.read_text(encoding="utf-8")
        for t in topics:
            assert f"Dice Research Slot: {t}" in written, f"roadmap missing report for {t}"
        assert written.count("Dice Research Slot:") == len(topics), "one report block per topic"
        print(f"\n✅ Persistence verified: {len(topics)} report blocks written to roadmap")

    print(f"\n✅ Web Research Engine Test: PASSED")


if __name__ == "__main__":
    import sys as _sys
    argv = _sys.argv[1:]
    if "--report" in argv:
        # CLI mode: research one topic and persist to the real roadmap.
        idx = argv.index("--report")
        topic = argv[idx + 1] if idx + 1 < len(argv) else "autonomous_agent_loop"
        engine = WebResearchEngine()
        result = engine.research_and_report(topic)
        print(f"Researched '{topic}' — {len(result['findings'])} findings "
              f"(live={result['live_findings']})")
        print(f"Report appended to: {result['report_path']}")
    else:
        _test_research()
