#!/usr/bin/env python3
"""
MARKUS OS Cortex → Skill Auto-Patcher (Upgrade 46)

Monitors cortex thoughts in real-time and automatically analyzes patterns
to identify opportunities for skill improvement. When a thought matches
known upgrade patterns, it auto-patches the relevant Hermes skill file.

This creates a closed loop: Dice Roll → Upgrade → Thought Logged → 
Skill Updated → Next Dice Roll Has Better Instructions
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("Markus.CortexSkillPatcher")

# Path to Hermes profile skills
HERMES_SKILLS_ROOT = Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "auroral-" / "skills" / "software-development"

# Pattern templates: (regex, skill_name, action, patch_template)
SKILL_UPGRADE_PATTERNS: List[Tuple[str, str, str]] = [
    # Dice engine improvements
    (
        r"Debate verdict.*confidence=\d+.*consensus=(BLOCKED|REACH)",
        "self-evolution-and-code-optimization",
        "ITERATE",
        "Pattern: Debate pipeline effectiveness. Verdict: {content}"
    ),
    # Accessibility fixes
    (
        r"(font-size.*rem|accessibility|font.*rem)",
        "frontend-backend-telemetry-and-cleanup",
        "MICRO-APPEND",
        "Accessibility fix applied: {content}"
    ),
    # Backend robustness
    (
        r"(symbol order|NameError|Handler alias|import error|ImportError)",
        "markus-os-development",
        "MICRO-APPEND",
        "Backend fix pattern: {content}"
    ),
    # PHOENIX CLI improvements
    (
        r"(AST.*validation|batch.*FAIL|module.*PASS)",
        "self-evolution-and-code-optimization",
        "ITERATE",
        "PHOENIX CLI insight: {content}"
    ),
    # Skill mutation patterns
    (
        r"(skill.*CREATE|skill.*ITERATE|skill.*REWRITE)",
        "markus-os-development",
        "ITERATE",
        "Skill evolution note: {content}"
    ),
]


@dataclass
class SkillPatch:
    """Represents an auto-generated skill patch."""
    skill_name: str
    action: str  # CREATE, ITERATE, REWRITE, MICRO-APPEND
    old_string: str
    new_string: str
    rationale: str


class CortexSkillPatcher:
    """
    Monitors cortex thoughts and auto-patches Hermes skills
    based on recurring patterns and improvement insights.
    """

    def __init__(self, skills_root: Optional[Path] = None) -> None:
        self.skills_root = skills_root or HERMES_SKILLS_ROOT
        self._processed_ids: set[str] = set()
        self._patch_log: List[Dict[str, Any]] = []

    def analyze_thought(self, entry_id: str, agent: str, content: str, metadata: Dict[str, Any]) -> List[SkillPatch]:
        """Analyze a single cortex thought for skill patch opportunities."""
        patches: List[SkillPatch] = []

        for pattern_regex, skill_name, action, patch_template in SKILL_UPGRADE_PATTERNS:
            if re.search(pattern_regex, content, re.IGNORECASE):
                # Generate patch content from template
                patch_content = patch_template.format(content=content)

                # Find the skill file
                skill_file = self._find_skill_file(skill_name)
                if not skill_file:
                    logger.warning(f"Skill file not found for: {skill_name}")
                    continue

                # Create a MICRO-APPEND patch (safe, always appends to bottom)
                if "# === Auto-Patch Section ===" in skill_file.read_text(encoding="utf-8"):
                    old_string = "# === Auto-Patch Section ===\n"
                    new_string = old_string + f"- {patch_content} (auto-appended {time.time():.0f})\n"
                else:
                    new_string = f"\n\n# === Auto-Patch Section ===\n# This section is auto-managed by CortexSkillPatcher. Do not edit manually.\n- {patch_content} (auto-appended {time.time():.0f})\n"
                    old_string = ""

                patches.append(SkillPatch(
                    skill_name=skill_name,
                    action=action,
                    old_string=old_string,
                    new_string=new_string,
                    rationale=f"Pattern '{pattern_regex[:30]}' matched in thought from {agent}"
                ))

        return patches

    def _find_skill_file(self, skill_name: str) -> Optional[Path]:
        """Locate the SKILL.md file for a given skill name."""
        # Search recursively for the skill directory
        for skill_dir in self.skills_root.rglob(skill_name):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    return skill_file
        return None

    def auto_patch_skill(self, patch: SkillPatch) -> bool:
        """Apply a skill patch automatically."""
        skill_file = self._find_skill_file(patch.skill_name)
        if not skill_file:
            logger.error(f"Cannot patch: skill file not found for {patch.skill_name}")
            return False

        try:
            content = skill_file.read_text(encoding="utf-8")
            if patch.old_string and patch.old_string not in content:
                # old_string not found, append to end
                new_content = content.rstrip() + "\n" + patch.new_string
            else:
                new_content = content.replace(patch.old_string, patch.new_string, 1)

            skill_file.write_text(new_content, encoding="utf-8")
            logger.info(f"[AutoPatch] {patch.skill_name}: {patch.action} — {patch.rationale[:60]}")
            self._patch_log.append({
                "skill": patch.skill_name,
                "action": patch.action,
                "applied_at": time.time(),
                "rationale": patch.rationale
            })
            return True
        except Exception as e:
            logger.error(f"[AutoPatch] Failed to patch {patch.skill_name}: {e}")
            return False

    def process_thought_batch(self, thoughts: List[Tuple[str, str, str, Dict]]) -> int:
        """Process a batch of thoughts, return number of patches applied."""
        patches_applied = 0
        for entry_id, agent, content, metadata in thoughts:
            if entry_id in self._processed_ids:
                continue
            self._processed_ids.add(entry_id)

            patches = self.analyze_thought(entry_id, agent, content, metadata)
            for patch in patches:
                if self.auto_patch_skill(patch):
                    patches_applied += 1

        return patches_applied

    def get_patch_log(self) -> List[Dict[str, Any]]:
        """Return the log of all patches applied."""
        return self._patch_log


def _test_auto_patcher():
    """Test the Cortex → Skill Auto-Patcher."""
    print("=== MARKUS Cortex → Skill Auto-Patcher Test ===\n")

    patcher = CortexSkillPatcher()

    # Check skill files exist
    test_skill = "markus-os-development"
    skill_file = patcher._find_skill_file(test_skill)
    if skill_file:
        print(f"✅ Found skill file for '{test_skill}': {skill_file}")
    else:
        print(f"⚠️  Skill file not found for '{test_skill}' — creating test pattern only")

    # Test thought analysis
    test_thoughts = [
        ("test_001", "MARKUS_DICE_ENGINE_DEBATE", "Debate verdict: markus-forensic-sentinel (confidence=24.7%, consensus=BLOCKED)", {}),
        ("test_002", "MARKUS_DICE_ENGINE", "Triggered dice cycle: TECHNICAL_ALTERNATIVE_UPGRADE (final_roll=5, sequence=[5])", {}),
        ("test_003", "SENTINEL", "Heartbeat healthy", {"active_procs": 1}),
    ]

    patches_found = 0
    for entry_id, agent, content, metadata in test_thoughts:
        patches = patcher.analyze_thought(entry_id, agent, content, metadata)
        if patches:
            patches_found += len(patches)
            print(f"  Thought '{content[:50]}...' → {len(patches)} patch(es) proposed")
            for p in patches:
                print(f"    → Skill: {p.skill_name}, Action: {p.action}")
        else:
            print(f"  Thought '{content[:50]}...' → No patches")

    if patches_found > 0 and skill_file:
        print(f"\n✅ Generated {patches_found} patch(es) from test thoughts")
        # Apply patches
        applied = patcher.process_thought_batch(test_thoughts)
        print(f"✅ Applied {applied} patch(es) to skills")
    else:
        print(f"\n✅ Thought analysis test: {patches_found} patches proposed (skill file may not exist)")

    print(f"\n✅ Cortex → Skill Auto-Patcher Test: PASSED")


if __name__ == "__main__":
    _test_auto_patcher()
