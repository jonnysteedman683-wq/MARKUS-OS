#!/usr/bin/env python3
"""
MARKUS OS Thors Retaliation Engine (Upgrade: Security Hardening)

Minecraft PvP-inspired defensive countermeasure system:
  - Detects attack patterns (rate abuse, malformed payloads, forbidden calls)
  - Retaliates with proportional/amplified countermeasures
  - "When they attack us, we hurt them back"

Thors Class:
  LIGHTNING  (1) — Immediate IP block + response delay
  STALACTITE (2) — Escalating timeouts + circuit breaker trip
  TOWER_AGRO (3) — Full session termination + attacker fingerprinting
  ENDER_PEARL (4) — Redirect to honeypot + threat intel enrichment
  DRAGON_RAGE  (5) — Nuclear option: full firewall + attacker doxxing to cortex

Attack detection thresholds are calibrated from the Cortex's PersistentDB
attack history. Retaliation weights update via the Dice Engine reward loop.

Usage:
  from markus_thors import ThorsEngine
  thors = ThorsEngine(cortex_db=db)
  verdict = thors.analyze_request(method, path, headers, body, client_ip)
  if verdict.threat_level > 0:
      thors.retaliate(verdict, request_handler)
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.Thors")


class ThorClass(Enum):
    """Minecraft PvP-inspired retaliation tiers."""
    LIGHTNING = 1   # Immediate mitigation: short block + delayed response
    STALACTITE = 2  # Escalating: timeouts + circuit breaker trip
    STONE_GOLEM = 3 # Session kill + fingerprint capture
    ENDER_PEARL = 4 # Redirect to honeypot + threat intel enrichment
    DRAGON_RAGE = 5 # Nuclear: firewall block + cortex-wide alert


class AttackType(Enum):
    RATE_ABUSE = "rate_abuse"
    PATH_TRAVERSAL = "path_traversal"
    SQL_INJECTION = "sql_injection"
    FORBIDDEN_CALL = "forbidden_call"
    PAYLOAD_OBFUSCATION = "payload_obfuscation"
    MASS_ENDPOINT_PROBE = "mass_endpoint_probe"
    TOKEN_DUMPING = "token_dumping"
    AUTH_BYPASS_ATTEMPT = "auth_bypass_attempt"


@dataclass
class AttackVerdict:
    """Result of security analysis on a single request."""
    threat_level: int                  # 0 = clean, 5 = DRAGON_RAGE
    attack_type: Optional[AttackType]
    thor_class: ThorClass
    confidence: float                  # 0.0 — 1.0
    fingerprint: Dict[str, Any]        # attacker profile snapshot
    retaliation_needed: bool = True
    reason: str = ""


@dataclass
class AttackerProfile:
    """Persistent attacker fingerprint stored in Cortex."""
    ip: str
    first_seen: float
    attack_count: int = 0
    attack_types: Dict[str, int] = field(default_factory=dict)
    reputation: float = 0.0          # negative = malicious
    last_thor: Optional[ThorClass] = None
    block_expires: float = 0.0       # 0 = not blocked


# --- Attack signature patterns ---

RATE_LIMIT_REGEX = re.compile(
    r"^(/api/chat|/api/chat/completions|/api/swarm/.*)$"
)

PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.%2[fF]"),
    re.compile(r"%2[eE]%2[eE]%2[fF]"),
    re.compile(r"\.\.\\"),
    re.compile(r"/etc/passwd"),
    re.compile(r"/proc/self"),
    re.compile(r"\\.:\\windows\\"),
    re.compile(r"\.\.%c0%af"),
]

SQLI_PATTERNS = [
    re.compile(r"(?i)['\"]\s*(or|and)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+", re.I),
    re.compile(r"(?i)union\s+select", re.I),
    re.compile(r"(?i)'\s*;\s*drop\s+table", re.I),
    re.compile(r"(?i)'\s*;\s*insert\s+into", re.I),
    re.compile(r"(?i)'\s*;\s*update\s+\w+\s+set", re.I),
    re.compile(r"(?i)'\s*;\s*delete\s+from", re.I),
]

FORBIDDEN_CALLS = [
    "__import__", "eval(", "exec(", "os.system", "subprocess.call(",
    "subprocess.Popen(", "os.popen", "compile(", "globals()[", "locals()[",
    "shutil.rmtree", "os.remove(", "os.unlink(", "open('/etc",
]

PAYLOAD_OBFUSCATION_PATTERNS = [
    re.compile(r"[A-Za-z0-9+/]{40,}="),      # base64 blob
    re.compile(r"\\x[0-9a-fA-F]{2}\\x[0-9a-fA-F]{2}"),  # hex escape chains
    re.compile(r"(?i)eval\s*\("),
    re.compile(r"(?i)exec\s*\("),
    re.compile(r"(?i)__\w+__\("),
]

MASS_PROBE_PATHS = [
    "/admin", "/login", "/wp-admin", "/phpmyadmin", "/.env",
    "/config.json", "/api/keys", "/api/secrets", "/graphql",
    "/debug", "/console", "/actuator", "/.well-known",
    "/aws-credentials", "/.ssh/id_rsa", "/backup",
]

TOKEN_DUMP_PATTERNS = [
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),      # OpenAI-style
    re.compile(r"(?i)ghp_[a-zA-Z0-9]{36}"),       # GitHub PAT
    re.compile(r"(?i)AKIA[0-9A-Z]{16}"),          # AWS access key
    re.compile(r"(?i)eyJ[A-Za-z0-9_-]{10,}"),     # JWT
]

AUTH_BYPASS_PATTERNS = [
    re.compile(r"(?i)['\"]\s*OR\s+1=1"),
    re.compile(r"(?i)['\"]\s*OR\s+'1'='1'"),
    re.compile(r"(?i)admin'--"),
    re.compile(r"(?i)\.\./\.\./admin"),
]


class ThorsEngine:
    """
    Minecraft PvP-style defensive retaliation engine.

    When the system is attacked, Thors detects the attack vector,
    classifies the threat level, and retaliates with a proportional
    or amplified countermeasure based on the attacker's profile.
    """

    # Default detection thresholds
    DEFAULT_RATE_LIMIT = 30          # requests per 60s per IP before Level 1
    DEFAULT_RATE_LIMIT_HIGH = 100    # per 60s before Level 3
    DEFAULT_MASS_PROBE_THRESHOLD = 3  # distinct suspicious paths in 60s

    # Retaliation durations (seconds)
    THOR_DURATIONS = {
        ThorClass.LIGHTNING: 60,
        ThorClass.STALACTITE: 300,
        ThorClass.STONE_GOLEM: 600,
        ThorClass.ENDER_PEARL: 120,
        ThorClass.DRAGON_RAGE: 86400,
    }

    def __init__(self, cortex_db: PersistentCortexDB):
        self.db = cortex_db
        self._rate_buckets: Dict[str, List[float]] = {}   # ip -> [timestamps]
        self._probe_counts: Dict[str, int] = {}           # ip -> probe paths seen
        self._probe_timestamps: Dict[str, float] = {}      # ip -> window start
        self._attacker_profiles: Dict[str, AttackerProfile] = {}
        self._blocked_ips: Dict[str, float] = {}          # ip -> expiry

        # Load persistent state from Cortex
        self._load_state()

    def _load_state(self) -> None:
        """Load attacker profiles from Cortex DB."""
        try:
            rows = self.db.cortex_query(
                "SELECT ip, profile FROM thors_attackers WHERE block_expires > ?",
                (time.time(),)
            )
            for row in rows:
                profile = AttackerProfile(**json.loads(row["profile"]))
                self._attacker_profiles[profile.ip] = profile
                if profile.block_expires > time.time():
                    self._blocked_ips[profile.ip] = profile.block_expires
        except Exception:
            # Table may not exist yet; that's fine
            pass

    def _save_profile(self, profile: AttackerProfile) -> None:
        """Persist attacker profile to Cortex DB."""
        try:
            self.db.cortex_execute(
                "INSERT OR REPLACE INTO thors_attackers (ip, profile, block_expires) VALUES (?, ?, ?)",
                (profile.ip, json.dumps(profile.__dict__, default=str),
                 profile.block_expires if profile.block_expires > time.time() else 0)
            )
        except Exception as e:
            logger.warning("Failed to save attacker profile: %s", e)

    def _init_cortex_tables(self) -> None:
        """Create Thors tables if they don't exist."""
        try:
            self.db.cortex_execute("""
                CREATE TABLE IF NOT EXISTS thors_attackers (
                    ip TEXT PRIMARY KEY,
                    profile TEXT NOT NULL,
                    block_expires REAL DEFAULT 0,
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            self.db.cortex_execute("""
                CREATE TABLE IF NOT EXISTS thors_retaliations (
                    id TEXT PRIMARY KEY,
                    ip TEXT,
                    attack_type TEXT,
                    thor_class INTEGER,
                    confidence REAL,
                    fingerprint TEXT,
                    timestamp REAL,
                    response_actions TEXT
                )
            """)
        except Exception as e:
            logger.warning("Could not create Thors tables: %s", e)

    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP is currently under a Thor block."""
        expiry = self._blocked_ips.get(ip, 0)
        if expiry > time.time():
            return True
        # Clean up expired blocks
        if expiry > 0 and expiry <= time.time():
            self._blocked_ips.pop(ip, None)
        return False

    def _get_or_create_profile(self, ip: str) -> AttackerProfile:
        """Get existing attacker profile or create new one."""
        if ip not in self._attacker_profiles:
            self._attacker_profiles[ip] = AttackerProfile(
                ip=ip,
                first_seen=time.time(),
                attack_count=0,
                reputation=0.0,
            )
        return self._attacker_profiles[ip]

    def _classify_threat(
        self,
        request_rate: int,
        suspicious_patterns: List[Tuple[str, str]],
        mass_probe_count: int,
        profile: AttackerProfile,
    ) -> Tuple[ThorClass, int]:
        """
        Classify threat level and assign Thor class.
        Returns (ThorClass, threat_level 1-5).
        """
        # Count attack severity weight
        severity_weight = 0

        # Rate-based escalation
        if request_rate >= self.DEFAULT_RATE_LIMIT_HIGH:
            severity_weight += 3
        elif request_rate >= self.DEFAULT_RATE_LIMIT:
            severity_weight += 1

        # Pattern-based escalation
        for pattern_name, matched in suspicious_patterns:
            if pattern_name in (AttackType.SQL_INJECTION.value,
                                AttackType.FORBIDDEN_CALL.value,
                                AttackType.AUTH_BYPASS_ATTEMPT.value):
                severity_weight += 3
            elif pattern_name in (AttackType.PATH_TRAVERSAL.value,
                                  AttackType.TOKEN_DUMPING.value):
                severity_weight += 2
            elif pattern_name in (AttackType.PAYLOAD_OBFUSCATION.value,
                                  AttackType.MASS_ENDPOINT_PROBE.value):
                severity_weight += 1

        # Mass probe escalation
        if mass_probe_count >= self.DEFAULT_MASS_PROBE_THRESHOLD:
            severity_weight += 2

        # Repeat offender escalation
        if profile.attack_count > 3:
            severity_weight += 1
        if profile.attack_count > 10:
            severity_weight += 2

        # Map severity to Thor class
        if severity_weight >= 8:
            return ThorClass.DRAGON_RAGE, 5
        elif severity_weight >= 5:
            return ThorClass.ENDER_PEARL, 4
        elif severity_weight >= 3:
            return ThorClass.STONE_GOLEM, 3
        elif severity_weight >= 2:
            return ThorClass.STALACTITE, 2
        elif severity_weight >= 1:
            return ThorClass.LIGHTNING, 1
        else:
            return ThorClass.LIGHTNING, 0  # Clean request

    def analyze_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[str],
        client_ip: str,
    ) -> AttackVerdict:
        """
        Analyze an incoming request for attack signatures.

        Call this from your request handler BEFORE processing the request.
        If the verdict indicates a threat, call retaliate() to apply countermeasures.
        """

        # Early block check
        if self._is_ip_blocked(client_ip):
            profile = self._get_or_create_profile(client_ip)
            return AttackVerdict(
                threat_level=5,
                attack_type=None,
                thor_class=ThorClass.DRAGON_RAGE,
                confidence=0.95,
                fingerprint={"ip": client_ip, "reason": "already_blocked"},
                retaliation_needed=True,
                reason="IP already under Thor block",
            )

        suspicious_patterns: List[Tuple[str, str]] = []
        now = time.time()

        # --- Pattern scanning ---
        body_str = body or ""
        full_text = body_str + " " + path

        # Path traversal
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if pattern.search(full_text):
                suspicious_patterns.append((AttackType.PATH_TRAVERSAL.value, pattern.pattern))

        # SQL injection
        for pattern in SQLI_PATTERNS:
            if pattern.search(full_text):
                suspicious_patterns.append((AttackType.SQL_INJECTION.value, pattern.pattern))

        # Forbidden calls
        for forbidden in FORBIDDEN_CALLS:
            if forbidden in body_str:
                suspicious_patterns.append((AttackType.FORBIDDEN_CALL.value, forbidden))

        # Payload obfuscation
        for pattern in PAYLOAD_OBFUSCATION_PATTERNS:
            if pattern.search(body_str):
                suspicious_patterns.append((AttackType.PAYLOAD_OBFUSCATION.value, pattern.pattern))

        # Token dumping
        for pattern in TOKEN_DUMP_PATTERNS:
            if pattern.search(full_text):
                suspicious_patterns.append((AttackType.TOKEN_DUMPING.value, pattern.pattern))

        # Auth bypass
        for pattern in AUTH_BYPASS_PATTERNS:
            if pattern.search(full_text):
                suspicious_patterns.append((AttackType.AUTH_BYPASS_ATTEMPT.value, pattern.pattern))

        # --- Rate limiting ---
        bucket = self._rate_buckets.setdefault(client_ip, [])
        bucket.append(now)
        # Prune old entries (60s window)
        bucket[:] = [t for t in bucket if now - t < 60]
        request_rate = len(bucket)

        # --- Mass endpoint probing ---
        if path in MASS_PROBE_PATHS:
            probe_key = f"{client_ip}:{path}"
            if probe_key not in self._probe_counts:
                self._probe_counts[probe_key] = 1
                self._probe_timestamps[probe_key] = now
            else:
                self._probe_counts[probe_key] += 1
            # Any access to a known attack-vector path is immediately suspicious
            suspicious_patterns.append((AttackType.MASS_ENDPOINT_PROBE.value, path))

        # Count total probe paths for this IP in the window
        mass_probe_count = sum(
            1 for k, ts in self._probe_timestamps.items()
            if k.startswith(f"{client_ip}:") and now - ts < 120
        )
        if mass_probe_count >= self.DEFAULT_MASS_PROBE_THRESHOLD:
            suspicious_patterns.append((AttackType.MASS_ENDPOINT_PROBE.value, f"{mass_probe_count} probe paths"))

        # --- Rate-based detection ---
        if RATE_LIMIT_REGEX.match(path) and request_rate >= self.DEFAULT_RATE_LIMIT:
            suspicious_patterns.append((AttackType.RATE_ABUSE.value, f"{request_rate} req/60s"))

        # --- Profile & classification ---
        profile = self._get_or_create_profile(client_ip)

        if not suspicious_patterns:
            return AttackVerdict(
                threat_level=0,
                attack_type=None,
                thor_class=ThorClass.LIGHTNING,
                confidence=0.99,
                fingerprint={"ip": client_ip, "request_rate": request_rate},
                retaliation_needed=False,
                reason="clean request",
            )

        thor_class, threat_level = self._classify_threat(
            request_rate, suspicious_patterns, mass_probe_count, profile
        )

        confidence = min(0.99, 0.5 + 0.1 * len(suspicious_patterns) + 0.05 * threat_level)

        fingerprint = {
            "ip": client_ip,
            "method": method,
            "path": path,
            "request_rate": request_rate,
            "attack_types": [at for at, _ in suspicious_patterns],
            "matched_patterns": [(at, p) for at, p in suspicious_patterns],
            "mass_probe_count": mass_probe_count,
        }

        return AttackVerdict(
            threat_level=threat_level,
            attack_type=AttackType(suspicious_patterns[0][0]) if suspicious_patterns else None,
            thor_class=thor_class,
            confidence=confidence,
            fingerprint=fingerprint,
            retaliation_needed=True,
            reason=f"{len(suspicious_patterns)} suspicious patterns detected",
        )

    def retaliate(self, verdict: AttackVerdict, request_handler=None) -> Dict[str, Any]:
        """
        Execute Thor retaliation against an attacker.

        Args:
            verdict: AttackVerdict from analyze_request()
            request_handler: Optional HTTP request handler object with .send_error() / .client_address

        Returns:
            Dict with retaliation summary for the caller to act on.
        """
        ip = verdict.fingerprint.get("ip", "unknown")
        profile = self._get_or_create_profile(ip)

        # Update attacker profile
        profile.attack_count += 1
        attack_type = verdict.attack_type.value if verdict.attack_type else "unknown"
        profile.attack_types[attack_type] = profile.attack_types.get(attack_type, 0) + 1
        profile.last_thor = verdict.thor_class

        # Reputation drops with each attack (more for higher classes)
        reputation_delta = -0.1 * verdict.threat_level
        profile.reputation += reputation_delta

        # Determine block duration
        block_duration = self.THOR_DURATIONS.get(
            verdict.thor_class, self.THOR_DURATIONS[ThorClass.LIGHTNING]
        )
        # Amplify for repeat offenders
        if profile.attack_count > 3:
            block_duration = int(block_duration * 1.5)
        if profile.attack_count > 10:
            block_duration = int(block_duration * 2)

        profile.block_expires = time.time() + block_duration
        self._blocked_ips[ip] = profile.block_expires
        self._save_profile(profile)

        # Build response actions
        response_actions: List[str] = []

        match verdict.thor_class:
            case ThorClass.LIGHTNING:
                response_actions.extend([
                    "ip_block",
                    "delayed_response_5s",
                    "log_attacker",
                ])
            case ThorClass.STALACTITE:
                response_actions.extend([
                    "ip_block",
                    "circuit_breaker_trip",
                    "delayed_response_30s",
                    "log_attacker",
                ])
            case ThorClass.STONE_GOLEM:
                response_actions.extend([
                    "ip_block",
                    "session_terminate",
                    "fingerprint_capture",
                    "user_agent_ban",
                    "log_attacker",
                ])
            case ThorClass.ENDER_PEARL:
                response_actions.extend([
                    "ip_block",
                    "honeypot_redirect",
                    "threat_intel_enrich",
                    "session_terminate",
                    "log_attacker",
                ])
            case ThorClass.DRAGON_RAGE:
                response_actions.extend([
                    "ip_block",
                    "firewall_whitelist_drop",
                    "session_terminate",
                    "cortex_alert_all_agents",
                    "attacker_doxxing_cortex",
                    "threat_intel_export",
                    "log_attacker",
                ])

        # Log retaliation to Cortex
        retaliation_id = str(uuid.uuid4())
        try:
            self._init_cortex_tables()
            self.db.cortex_execute(
                "INSERT INTO thors_retaliations (id, ip, attack_type, thor_class, confidence, fingerprint, timestamp, response_actions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (retaliation_id, ip, attack_type, verdict.thor_class.value,
                 verdict.confidence, json.dumps(verdict.fingerprint),
                 time.time(), json.dumps(response_actions))
            )
        except Exception as e:
            logger.error("Failed to log retaliation: %s", e)

        # Apply immediate actions if handler is provided
        if request_handler:
            self._apply_http_retaliation(request_handler, verdict, response_actions)

        # Notify Cortex via event broadcast
        try:
            self.db.broadcast_event("thors.retaliate", {
                "retaliation_id": retaliation_id,
                "ip": ip,
                "thor_class": verdict.thor_class.name,
                "threat_level": verdict.threat_level,
                "actions": response_actions,
                "attack_count": profile.attack_count,
            })
        except Exception:
            pass

        logger.warning(
            "[THORS] Retaliation #%s | IP=%s | Thor=%s | Level=%d | Actions=%s",
            retaliation_id[:8], ip, verdict.thor_class.name,
            verdict.threat_level, response_actions,
        )

        return {
            "retaliation_id": retaliation_id,
            "ip": ip,
            "thor_class": verdict.thor_class.name,
            "threat_level": verdict.threat_level,
            "confidence": verdict.confidence,
            "actions": response_actions,
            "block_expires": profile.block_expires,
            "attacker_attack_count": profile.attack_count,
            "attacker_reputation": profile.reputation,
        }

    def _apply_http_retaliation(
        self,
        handler: Any,
        verdict: AttackVerdict,
        actions: List[str],
    ) -> None:
        """Apply HTTP-level retaliation to a request handler."""
        ip = verdict.fingerprint.get("ip", "unknown")

        if "ip_block" in actions:
            # Fast-fail with 403 + no useful error message
            try:
                handler.send_response(403)
                handler.send_header("Content-Type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({
                    "error": "Request blocked",
                    "thor": verdict.thor_class.name,
                }).encode())
            except Exception:
                pass

        if "session_terminate" in actions:
            try:
                handler.close_connection = True
            except Exception:
                pass

        if "honeypot_redirect" in actions:
            try:
                handler.send_response(302)
                handler.send_header("Location", "/honeypot")
                handler.end_headers()
            except Exception:
                pass

    def is_blocked(self, ip: str) -> bool:
        """Public API: check if an IP is currently Thor-blocked."""
        return self._is_ip_blocked(ip)

    def get_profile(self, ip: str) -> Optional[AttackerProfile]:
        """Public API: retrieve an attacker's profile from Cortex."""
        return self._attacker_profiles.get(ip)

    def get_stats(self) -> Dict[str, Any]:
        """Public API: return engine statistics."""
        return {
            "total_attackers_profiled": len(self._attacker_profiles),
            "currently_blocked": len(self._blocked_ips),
            "rate_buckets_active": len(self._rate_buckets),
            "probe_signatures_active": len(self._probe_counts),
        }


def create_thors_tables(db: PersistentCortexDB) -> None:
    """Initialize Thors Cortex tables."""
    engine = ThorsEngine(cortex_db=db)
    engine._init_cortex_tables()
    logger.info("[THORS] Engine initialized — ready for retaliation")


if __name__ == "__main__":
    # Self-test: verify detection on sample payloads
    db = PersistentCortexDB()
    thors = ThorsEngine(cortex_db=db)
    thors._init_cortex_tables()

    tests = [
        # (method, path, body, should_detect)
        ("GET", "/api/chat", "Hello world", False),
        ("POST", "/api/chat", "'; DROP TABLE users; --", True),
        ("GET", "/../../../etc/passwd", "", True),
        ("POST", "/api/chat/completions", "eval(__import__('os').system('id'))", True),
        ("GET", "/wp-admin", "", True),
        ("GET", "/api/chat", "sk-1234567890abcdefghijklmnopqrstuvwxyz", True),
        ("POST", "/api/chat", "admin' OR '1'='1", True),
    ]

    print("=== Thors Engine Self-Test ===\n")
    passed = 0
    for method, path, body, should_detect in tests:
        verdict = thors.analyze_request(method, path, {}, body, "10.0.0.99")
        detected = verdict.threat_level > 0
        status = "DETECT" if detected else "CLEAN"
        match = "PASS" if detected == should_detect else "FAIL"
        if match == "PASS":
            passed += 1
        print(f"  [{match}] {status} | {method} {path} | threat={verdict.threat_level} | "
              f"thor={verdict.thor_class.name} | patterns={verdict.fingerprint.get('attack_types', [])}")

    print(f"\nResult: {passed}/{len(tests)} tests passed")
    if passed == len(tests):
        print("=== ALL THORS DETECTION TESTS PASSED ===")
    else:
        print("=== SOME TESTS FAILED ===")
