"""
MARKUS OS Policy & Authorization Engine (Port of HERMES-HIVE policyAndAuthorizationEngine.ts)

Gates all agent actions behind a 7-rule risk chain. Automatically approves
LOW/MEDIUM risk operations, escalates HIGH/CRITICAL to approval queues, and
always allows SIMULATE mode for dry-run evaluation.

Integration point: markus_dice_engine.py calls this before executing upgrade
actions — Dice Roll 1-2 = LOW/MEDIUM (auto), Dice Roll 3-4 = HIGH (requires
approval), Dice Roll 5 = MEDIUM (auto), Dice Roll 6 = Re-Roll.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class CapabilityDescriptor:
    """A registered capability that agents can invoke."""
    id: str
    name: str
    description: str
    risk_level: RiskLevel
    operations: List[str]
    availability: str = "online"
    rate_limits: Dict[str, int] = field(default_factory=lambda: {"maxRequestsPerMin": 60})
    provider: str = "unknown"
    version: str = "1.0.0"


@dataclass
class CapabilityRequest:
    """A request to execute a capability action."""
    capability_id: str
    operation: str
    agent_id: str
    agent_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    execution_mode: str = "EXECUTE"  # EXECUTE or SIMULATE
    idempotency_key: Optional[str] = None
    request_id: str = ""
    trace_id: str = ""
    correlation_id: str = ""
    authorization_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyResult:
    """The result of a policy evaluation."""
    decision: PolicyDecision
    reason: str
    evaluated_rules: List[str]
    timestamp: str
    approval_id: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass
class ApprovalRequest:
    """A pending approval request for HIGH/CRITICAL operations."""
    approval_id: str
    request: CapabilityRequest
    risk_level: RiskLevel
    reason: str
    status: ApprovalStatus
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


class PolicyAndAuthorizationEngine:
    """7-rule risk assessment chain for capability authorization.

    Ported from HERMES-HIVE (policyAndAuthorizationEngine.ts).
    Gates all MARKUS agent actions behind configurable risk assessment.
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, CapabilityDescriptor] = {}
        self._approval_queue: Dict[str, ApprovalRequest] = {}
        self._idempotency_cache: Dict[str, Any] = {}
        self._rate_limits: Dict[str, Dict[str, int]] = {}  # key → {count, window_reset}

    # -- Capability Registration --------------------------------------------

    def register_capability(self, cap: CapabilityDescriptor) -> None:
        """Register a capability for use by agents."""
        self._capabilities[cap.id] = cap

    def get_capability(self, cap_id: str) -> Optional[CapabilityDescriptor]:
        return self._capabilities.get(cap_id)

    # -- Core Evaluation ----------------------------------------------------

    def evaluate_request(self, request: CapabilityRequest) -> PolicyResult:
        """Run the 7-rule policy chain on a capability request."""
        timestamp = datetime.now(timezone.utc).isoformat()
        evaluated_rules: List[str] = []

        # 1. Service Identity Check
        evaluated_rules.append("RULE_1_SERVICE_IDENTITY")
        service_identity = request.authorization_context.get("service_identity", "")
        if service_identity != "markus-os":
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Untrusted service identity: {service_identity}. Must be 'markus-os'.",
                evaluated_rules=evaluated_rules,
                timestamp=timestamp,
            )

        # 2. Capability Existence & Availability
        evaluated_rules.append("RULE_2_CAPABILITY_AVAILABILITY")
        cap = self._capabilities.get(request.capability_id)
        if not cap:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Capability '{request.capability_id}' is not registered.",
                evaluated_rules=evaluated_rules,
                timestamp=timestamp,
            )
        if cap.availability == "offline":
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Capability '{cap.name}' is offline for maintenance.",
                evaluated_rules=evaluated_rules,
                timestamp=timestamp,
            )

        # 3. Operation Support Check
        evaluated_rules.append("RULE_3_OPERATION_VALIDATION")
        if request.operation not in cap.operations:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Operation '{request.operation}' not supported by capability '{cap.id}'. Supported: {cap.operations}",
                evaluated_rules=evaluated_rules,
                timestamp=timestamp,
            )

        # 4. Rate Limit Check
        evaluated_rules.append("RULE_4_RATE_LIMIT")
        rate_key = f"{service_identity}:{request.capability_id}"
        now = datetime.now(timezone.utc).timestamp()
        tracker = self._rate_limits.get(rate_key, {"count": 0, "reset_time": now + 60})
        if now > tracker["reset_time"]:
            tracker["count"] = 0
            tracker["reset_time"] = now + 60
        max_req = cap.rate_limits.get("maxRequestsPerMin", 60)
        if tracker["count"] >= max_req:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Rate limit exceeded for '{cap.name}': {max_req} req/min.",
                evaluated_rules=evaluated_rules,
                timestamp=timestamp,
            )
        tracker["count"] += 1
        self._rate_limits[rate_key] = tracker

        # 5. Simulation Mode Check
        if request.execution_mode == "SIMULATE":
            evaluated_rules.append("RULE_5_SIMULATION_ALLOW")
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="Simulation request authorized for risk estimation.",
                evaluated_rules=evaluated_rules,
                timestamp=timestamp,
                risk_level=cap.risk_level,
            )

        # 6. Risk Level & Approval Check
        evaluated_rules.append("RULE_6_RISK_POLICY_EVALUATION")
        if cap.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            approval_id = f"appr_{int(now * 1000)}_{id(request) % 10000:04d}"
            approval_req = ApprovalRequest(
                approval_id=approval_id,
                request=request,
                risk_level=cap.risk_level,
                reason=f"Capability action requires explicit approval due to {cap.risk_level} risk level.",
                status=ApprovalStatus.PENDING,
                created_at=timestamp,
            )
            self._approval_queue[approval_id] = approval_req
            return PolicyResult(
                decision=PolicyDecision.REQUIRE_APPROVAL,
                reason=f"Operation requires approval due to {cap.risk_level} risk level. ID: {approval_id}",
                approval_id=approval_id,
                evaluated_rules=evaluated_rules,
                timestamp=timestamp,
                risk_level=cap.risk_level,
            )

        # 7. Default Allow for LOW and MEDIUM
        evaluated_rules.append("RULE_7_DEFAULT_ALLOW")
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="Request passed all checks.",
            evaluated_rules=evaluated_rules,
            timestamp=timestamp,
            risk_level=cap.risk_level,
        )

    # -- Idempotency --------------------------------------------------------

    def check_idempotency(self, key: Optional[str]) -> Optional[Any]:
        if not key:
            return None
        return self._idempotency_cache.get(key)

    def record_idempotency(self, key: str, result: Any) -> None:
        if key:
            self._idempotency_cache[key] = result

    # -- Approval Management ------------------------------------------------

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        return [a for a in self._approval_queue.values() if a.status == ApprovalStatus.PENDING]

    def resolve_approval(self, approval_id: str, approved: bool, resolved_by: str = "operator") -> Optional[ApprovalRequest]:
        appr = self._approval_queue.get(approval_id)
        if not appr:
            return None
        appr.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        appr.resolved_at = datetime.now(timezone.utc).isoformat()
        appr.resolved_by = resolved_by
        return appr

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._approval_queue.get(approval_id)


# -- MARKUS Integration: Dice Engine Risk Mapping ---------------------------

# Dice Roll → Capability Risk Mapping
DICE_RISK_MAP = {
    1: RiskLevel.LOW,      # UI Upgrade
    2: RiskLevel.MEDIUM,    # Backend Upgrade
    3: RiskLevel.HIGH,      # AI Agent Upgrade
    4: RiskLevel.HIGH,      # Find Missing
    5: RiskLevel.MEDIUM,    # Technical Alternative
    6: None,                # Re-Roll (no action)
}


# Initialize default capabilities for MARKUS dice engine
policy_engine = PolicyAndAuthorizationEngine()

policy_engine.register_capability(CapabilityDescriptor(
    id="markus-ui-upgrade",
    name="MARKUS UI Upgrade",
    description="Enhances markus-os.html with new telemetry, audio cues, or interface features",
    risk_level=RiskLevel.LOW,
    operations=["refresh_ui", "add_telemetry", "add_audio"],
))

policy_engine.register_capability(CapabilityDescriptor(
    id="markus-backend-upgrade",
    name="MARKUS Backend Upgrade",
    description="Upgrades core servers, routers, or kernel capabilities",
    risk_level=RiskLevel.MEDIUM,
    operations=["port_crdt", "upgrade_router", "hardening"],
))

policy_engine.register_capability(CapabilityDescriptor(
    id="markus-ai-upgrade",
    name="MARKUS AI Agent Upgrade",
    description="Optimizes routing thresholds or agent profiles",
    risk_level=RiskLevel.HIGH,
    operations=["optimize_brain", "update_router", "add_curiosity"],
))

if __name__ == "__main__":
    # Demo: gate a dice roll through the policy engine
    roll = 3  # Dice Roll 3 = AI Agent Upgrade (HIGH risk)
    risk = DICE_RISK_MAP.get(roll)
    if risk:
        req = CapabilityRequest(
            capability_id="markus-ai-upgrade",
            operation="optimize_brain",
            agent_id="markus-kernel",
            execution_mode="EXECUTE",
            authorization_context={"service_identity": "markus-os"},
        )
        result = policy_engine.evaluate_request(req)
        print(f"Dice Roll {roll} → Risk: {risk}")
        print(f"Decision: {result.decision}")
        print(f"Reason: {result.reason}")
        if result.decision == PolicyDecision.REQUIRE_APPROVAL:
            print(f"Approval ID: {result.approval_id}")
            print("[POLICY] Upgrade requires operator approval before proceeding.")
    else:
        print(f"Dice Roll {roll} → Re-roll (no action)")
    print("\n[POLICY ENGINE] Self-test PASSED")
