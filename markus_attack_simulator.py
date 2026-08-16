#!/usr/bin/env python3
"""
MARKUS OS Attack Simulator — Red Team harness for Thors validation.

Throws controlled attack payloads at the Thors retaliation engine to validate
detection accuracy, classification escalation, and retaliation effectiveness.
Mirrors the RED→BLUE→VALIDATE loop from markus_redteam.py but targets the
security layer directly.

Stolen patterns from:
- markus_redteam.py: RedTeamAgent, MutationResult, FIX_PATTERNS
- markus_consensus.py: UNSAFE_CALLS, safety validation
- markus_resilience.py: CircuitBreakerManager for error tracking
- markus_sandbox.py: MarkusProcessSandbox for isolated payload execution
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from markus_db import PersistentCortexDB
from markus_thors import ThorsEngine, AttackVerdict, ThorClass

REPO_ROOT = Path(__file__.parent.resolve()) if "__file__" in dir() else Path.cwd()
logger = logging.getLogger("Markus.AttackSim")


@dataclass
class AttackResult:
    """Result of a single simulated attack against Thors."""
    attack_id: str
    attack_type: str
    payload_description: str
    detected: bool
    threat_level: int
    thor_class: str
    confidence: float
    retaliation_actions: List[str]
    attacker_profile_updated: bool
    latency_ms: float
    passed: bool  # True if detected at expected level


@dataclass
class AttackSuite:
    """A suite of attack payloads targeting specific Thor classes."""
    suite_name: str
    target_thor: ThorClass
    attacks: List[Tuple[str, str, str, Optional[str]]]
    # Each attack: (attack_type, method, path, body_template)
    # body_template can contain {token} for token-dumping payloads


class AttackSuiteRunner:
    """
    Runs controlled attack payloads against the Thors engine.
    Validates detection, classification, and retaliation effectiveness.

    Mirrors RedTeamAgent's RED→BLUE→VALIDATE loop but focused on security.
    """

    # Stolen attack vectors from markus_redteam.py + OWASP top 10
    ATTACK_SUITES: List[AttackSuite] = [
        AttackSuite(
            suite_name="Lightning-Tier Probes",
            target_thor=ThorClass.LIGHTNING,
            attacks=[
                ("mass_endpoint_probe", "GET", "/wp-admin", None),
                ("mass_endpoint_probe", "GET", "/.env", None),
                ("mass_endpoint_probe", "GET", "/admin", None),
                ("rate_abuse", "POST", "/api/chat", "ping"),
                ("rate_abuse", "POST", "/api/chat", "ping"),
            ],
        ),
        AttackSuite(
            suite_name="Stone Golem Escalation",
            target_thor=ThorClass.STONE_GOLEM,
            attacks=[
                ("sql_injection", "POST", "/api/intent", "' OR '1'='1"),
                ("path_traversal", "GET", "/../../../etc/passwd", None),
                ("forbidden_call", "POST", "/api/sandbox/eval", "eval(1)"),
                ("auth_bypass_attempt", "POST", "/api/intent", "admin'--"),
            ],
        ),
        AttackSuite(
            suite_name="Dragon Rage Nuclear",
            target_thor=ThorClass.DRAGON_RAGE,
            attacks=[
                ("forbidden_call", "POST", "/api/sandbox/eval",
                 "eval(__import__('os').system('rm -rf /'))"),
                ("token_dumping", "POST", "/api/intent", "sk-1234567890abcdefghijklmnopqrstuvwxyz"),
                ("payload_obfuscation", "POST", "/api/intent",
                 "eval(compile('x' + 'y', '<s>', 'exec'))"),
            ],
        ),
        AttackSuite(
            suite_name="Ender Pearl Redirects",
            target_thor=ThorClass.ENDER_PEARL,
            attacks=[
                ("sql_injection", "POST", "/api/intent",
                 "1' UNION SELECT username, password FROM users--"),
                ("path_traversal", "GET", "/proc/self/environ", None),
                ("token_dumping", "POST", "/api/chat",
                 "ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
            ],
        ),
        AttackSuite(
            suite_name="Stalactite Circuit Breakers",
            target_thor=ThorClass.STALACTITE,
            attacks=[
                ("sql_injection", "POST", "/api/intent",
                 "'; DROP TABLE users; --"),
                ("auth_bypass_attempt", "POST", "/api/intent",
                 "' OR 1=1 --"),
            ],
        ),
    ]

    # Expected minimum threat level per attack type
    THREAT_LEVEL_EXPECTATIONS = {
        "mass_endpoint_probe": 1,
        "rate_abuse": 1,
        "sql_injection": 3,
        "path_traversal": 3,
        # forbidden_call: eval(1) matches forbidden_call + payload_obfuscation = L3
        # But eval(__import__('os').system(...)) matches multiple patterns = L5
        "forbidden_call": 3,
        "auth_bypass_attempt": 3,
        "payload_obfuscation": 3,
        "token_dumping": 2,
    }

    def __init__(self, thors: ThorsEngine):
        self.thors = thors
        self.results: List[AttackResult] = []
        self._attack_counter = 0

    def _next_attack_id(self) -> str:
        self._attack_counter += 1
        return f"ATK-{int(time.time())}-{self._attack_counter:04d}"

    def _build_payload(self, body_template: Optional[str]) -> str:
        """Inject simulated secrets/tokens into body templates."""
        if body_template is None:
            return ""
        if "{token}" in body_template:
            body_template = body_template.replace(
                "{token}", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
            )
        return body_template

    def run_attack(
        self,
        attack_type: str,
        method: str,
        path: str,
        body_template: Optional[str],
        client_ip: str = "10.0.0.666",
    ) -> AttackResult:
        """Execute a single attack payload against Thors and record the result."""
        body = self._build_payload(body_template)
        start = time.perf_counter()

        verdict = self.thors.analyze_request(method, path, {}, body, client_ip)

        retaliation_result: Dict[str, Any] = {}
        if verdict.threat_level > 0:
            retaliation_result = self.thors.retaliate(verdict, None)

        latency_ms = (time.perf_counter() - start) * 1000

        expected_min = self.THREAT_LEVEL_EXPECTATIONS.get(attack_type, 1)
        passed = verdict.threat_level >= expected_min

        result = AttackResult(
            attack_id=self._next_attack_id(),
            attack_type=attack_type,
            payload_description=f"{method} {path} {body[:80] if body else ''}",
            detected=verdict.threat_level > 0,
            threat_level=verdict.threat_level,
            thor_class=verdict.thor_class.name,
            confidence=verdict.confidence,
            retaliation_actions=retaliation_result.get("actions", []),
            attacker_profile_updated=retaliation_result.get("attacker_attack_count", 0) > 0,
            latency_ms=round(latency_ms, 2),
            passed=passed,
        )
        self.results.append(result)
        return result

    def run_suite(self, suite: AttackSuite, client_ip: str = "10.0.0.666") -> List[AttackResult]:
        """Run all attacks in a suite against the Thors engine."""
        # Use unique IP per suite to avoid cross-suite attack count accumulation
        suite_ip = f"10.0.0.{hash(suite.suite_name) % 200 + 1}"
        print(f"\n  [{suite.suite_name}] — target: {suite.target_thor.name} @ {suite_ip}")
        for attack_type, method, path, body_template in suite.attacks:
            result = self.run_attack(attack_type, method, path, body_template, suite_ip)
            status = "PASS" if result.passed else "FAIL"
            symbol = "✓" if result.passed else "✗"
            print(f"    {symbol} [{status}] {result.thor_class} (L{result.threat_level}) | "
                  f"{result.attack_type} | {result.latency_ms:.1f}ms")
        return self.results[-len(suite.attacks):]

    def run_all(self) -> Dict[str, Any]:
        """Run all attack suites and return aggregated results."""
        print("=" * 72)
        print("  THORS ATTACK SIMULATOR — Red Team Validation")
        print("=" * 72)

        total_attacks = 0
        total_passed = 0
        total_detected = 0

        for suite in self.ATTACK_SUITES:
            results = self.run_suite(suite)
            total_attacks += len(results)
            total_passed += sum(1 for r in results if r.passed)
            total_detected += sum(1 for r in results if r.detected)

        # Run a dedicated attacker profile test
        profile_test = self._test_attacker_profile()
        print(f"\n  [Attacker Profile] — {profile_test}")

        print(f"\n{'=' * 72}")
        print(f"  SIMULATION COMPLETE")
        print(f"  Total attacks:    {total_attacks}")
        print(f"  Detected:         {total_detected}/{total_attacks}")
        print(f"  Passed (level>=expected): {total_passed}/{total_attacks}")
        print(f"  Profile test:    {'PASS' if profile_test else 'FAIL'}")
        print(f"  Success rate:    {(total_passed / total_attacks * 100):.1f}%")
        print(f"{'=' * 72}")

        return {
            "total_attacks": total_attacks,
            "total_detected": total_detected,
            "total_passed": total_passed,
            "success_rate": round(total_passed / total_attacks * 100, 1),
            "profile_test_passed": profile_test,
            "results": [r.__dict__ for r in self.results],
        }

    def _test_attacker_profile(self) -> bool:
        """
        Test that repeated attacks escalate the attacker profile correctly.
        Uses a fresh IP and fires progressively more severe attacks.
        """
        test_ip = "10.0.0.777"
        # Fire 5 attacks from same IP
        attacks = [
            ("mass_endpoint_probe", "GET", "/admin", None),
            ("sql_injection", "POST", "/api/intent", "' OR 1=1--"),
            ("forbidden_call", "POST", "/api/sandbox/eval", "eval(1)"),
            ("token_dumping", "POST", "/api/chat", "sk-test1234567890abcdef"),
            ("path_traversal", "GET", "/../../../etc/passwd", None),
        ]

        for atk_type, method, path, body in attacks:
            self.run_attack(atk_type, method, path, body, test_ip)

        profile = self.thors.get_profile(test_ip)
        if profile is None:
            print(f"    ✗ [FAIL] No profile created for {test_ip}")
            return False

        # Expect: attack_count >= 5, reputation < 0, escalated to ENDER_PEARL
        if profile.attack_count < 5:
            print(f"    ✗ [FAIL] attack_count={profile.attack_count} (expected >= 5)")
            return False
        if profile.reputation >= 0:
            print(f"    ✗ [FAIL] reputation={profile.reputation:.2f} (expected < 0)")
            return False
        # After 5 attacks: attack 1 = LIGHTNING, attacks 2-5 = escalation from block
        # attack_count=5 triggers ENDER_PEARL threshold
        if profile.last_thor != ThorClass.ENDER_PEARL:
            print(f"    ✗ [FAIL] last_thor={profile.last_thor} (expected ENDER_PEARL)")
            return False
        if not profile.block_expires or profile.block_expires < time.time():
            print(f"    ✗ [FAIL] no active block (expected ENDER_PEARL 120s+ block)")
            return False

        print(f"    ✓ [PASS] Profile: count={profile.attack_count}, "
              f"reputation={profile.reputation:.2f}, "
              f"last_thor={profile.last_thor.name}, block=active")
        return True

    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """Generate a JSON report of all attack results."""
        report = {
            "timestamp": time.time(),
            "engine": "markus_thors",
            "total_attacks": len(self.results),
            "results": [r.__dict__ for r in self.results],
        }
        report_json = json.dumps(report, indent=2, default=str)
        if output_path:
            output_path.write_text(report_json)
            print(f"  Report saved to: {output_path}")
        return report_json


def main():
    """Entry point: run the full attack simulation against Thors."""
    logging.basicConfig(level=logging.WARNING)

    db = PersistentCortexDB()
    thors = ThorsEngine(cortex_db=db)

    runner = AttackSuiteRunner(thors)
    summary = thors.get_stats()

    print(f"  Thors engine pre-state: {summary}")

    report = runner.run_all()

    post_stats = thors.get_stats()
    print(f"\n  Thors engine post-state: {post_stats}")

    # Save report
    report_path = REPO_ROOT / ".hermes" / "thors_attack_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    runner.generate_report(report_path)

    # Exit code: 0 if all passed, 1 if any failed
    all_passed = report["total_passed"] == report["total_attacks"] and report["profile_test_passed"]
    print(f"\n  Exit: {'PASS' if all_passed else 'FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
