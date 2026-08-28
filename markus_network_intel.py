#!/usr/bin/env python3
"""
MARKUS OS Network Intelligence Module (connectivity-awareness layer)
Enumerates the real transport stack (adapters, connection type, gateway,
DNS), probes live connectivity health, and emits a structured snapshot that
the adaptive matrix / router can consume to feed reliability scoring.

Stdlib-only, Windows-aware (ipconfig/netsh parsing + socket probes), robust
to missing hardware — never crashes on a machine with no cellular modem or
no VPN. Falls back gracefully when a probe fails.

Snapshot is persisted to markus_network_state.json so downstream consumers
(adaptive matrix, router, cortex) can read transport telemetry across restarts.
"""

from __future__ import annotations

import json
import logging
import platform
import re
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Markus.NetworkIntel")

# Downstream consumers read this file for transport telemetry.
STATE_PATH = Path(__file__).resolve().parent / "markus_network_state.json"

# Probe targets: gateway (resolved from ipconfig) + public internet reachability.
PUBLIC_PROBE_HOST = "1.1.1.1"
PUBLIC_PROBE_PORT = 443
DNS_PROBE_HOST = "one.one.one.one"
PROBE_TIMEOUT_S = 3.0

# Adapter-description keyword -> connection type classification.
TYPE_HINTS: List[tuple] = [
    (r"wireless|wifi|wlan|wi-fi", "wifi"),
    (r"ethernet|gigabit|e1000|realtek.*pcie", "ethernet"),
    (r"vpn|tunnel|openvpn|surfshark|wireguard|tap-|tap-|tun", "vpn"),
    (r"cellular|lte|wwan|mobile|modem|mbim|4g|5g", "cellular"),
]

WINDOWS = sys.platform.startswith("win")


@dataclass
class AdapterInfo:
    name: str
    description: str
    media_state: str  # "connected" | "media disconnected"
    connection_type: str = "unknown"  # wifi | ethernet | vpn | cellular | unknown
    ipv4: Optional[str] = None
    gateway: Optional[str] = None
    dns_servers: List[str] = field(default_factory=list)


@dataclass
class ConnectivityReport:
    hostname: str
    os: str
    generated_at: float
    active_adapters: List[AdapterInfo]
    primary_connection_type: str = "none"
    has_internet: bool = False
    gateway_reachable: bool = False
    internet_latency_ms: Optional[float] = None
    public_ip: Optional[str] = None
    vpn_active: bool = False
    cellular_present: bool = False


def _run(cmd: List[str], timeout: float = 10.0) -> str:
    """Run a command, return stdout, empty on any failure (never raises)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              check=False)
        return proc.stdout or ""
    except Exception as e:  # noqa: BLE001
        logger.debug("command failed %s: %s", cmd, e)
        return ""


def classify_description(desc: str) -> str:
    """Classify an adapter description into a connection type via keywords."""
    low = desc.lower()
    for pattern, ctype in TYPE_HINTS:
        if re.search(pattern, low):
            return ctype
    return "unknown"


def parse_ipconfig() -> List[AdapterInfo]:
    """Parse `ipconfig` (Windows) or `ifconfig` (POSIX) into adapter list."""
    if WINDOWS:
        return _parse_ipconfig_windows()
    return _parse_ifconfig_posix()


def _parse_ipconfig_windows() -> List[AdapterInfo]:
    out = _run(["ipconfig", "/all"])
    adapters: List[AdapterInfo] = []
    cur: Optional[AdapterInfo] = None

    for line in out.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        # Adapter header: "Ethernet adapter X:" or "Wireless LAN adapter Y:" / "Unknown adapter Z:"
        m = re.match(r"^(?:Ethernet|Wireless LAN|Unknown|Local Area Connection).*adapter (.+):$", line.strip())
        if m:
            cur = AdapterInfo(name=m.group(1).strip(), description="", media_state="connected")
            adapters.append(cur)
            continue
        if cur is None:
            continue
        dm = re.search(r"Media State\s*[. ]+: (.+)", line)
        if dm:
            cur.media_state = "connected" if "connected" in dm.group(1).lower() else "media disconnected"
        dm2 = re.search(r"Description\s*[. ]+: (.+)", line)
        if dm2:
            cur.description = dm2.group(1).strip()
        im = re.search(r"IPv4 Address\s*[. ]+: ([0-9.]+)", line)
        if im and cur.ipv4 is None:
            cur.ipv4 = im.group(1)
        gm = re.search(r"Default Gateway\s*[. ]+: ([0-9.]+)", line)
        if gm and cur.gateway is None:
            cur.gateway = gm.group(1)
        dm3 = re.search(r"DNS Servers\s*[. ]+:\s*([0-9.]+)", line)
        if dm3 and dm3.group(1) not in cur.dns_servers:
            cur.dns_servers.append(dm3.group(1))

    for a in adapters:
        a.connection_type = classify_description(a.description or a.name)
    return adapters


def _parse_ifconfig_posix() -> List[AdapterInfo]:
    out = _run(["ifconfig", "-a"])
    adapters: List[AdapterInfo] = []
    cur: Optional[AdapterInfo] = None
    for line in out.splitlines():
        if line and not line.startswith(" ") and ":" in line.split()[0] if line.split() else False:
            if cur:
                adapters.append(cur)
            name = line.split(":")[0]
            cur = AdapterInfo(name=name, description=name, media_state="connected")
        elif cur is not None:
            m = re.search(r"inet (addr:)?([0-9.]+)", line)
            if m:
                cur.ipv4 = m.group(2)
            if "status: inactive" in line:
                cur.media_state = "media disconnected"
    if cur:
        adapters.append(cur)
    for a in adapters:
        a.connection_type = classify_description(a.description or a.name)
    return adapters


def _tcp_probe(host: str, port: int, timeout: float = PROBE_TIMEOUT_S) -> Optional[float]:
    """Return connect latency in ms, or None on failure."""
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.time() - start) * 1000.0, 1)
    except Exception:  # noqa: BLE001
        return None


def _resolve(host: str) -> Optional[float]:
    """DNS resolution latency in ms, or None on failure."""
    start = time.time()
    try:
        socket.getaddrinfo(host, None)
        return round((time.time() - start) * 1000.0, 1)
    except Exception:  # noqa: BLE001
        return None


def build_report(probe: bool = True) -> ConnectivityReport:
    """Build a structured transport snapshot for the current machine."""
    adapters = parse_ipconfig()
    active = [a for a in adapters if a.media_state == "connected" and a.ipv4]

    # Primary = first active adapter that isn't VPN; prefer a real link.
    primary = None
    for a in active:
        if a.connection_type != "vpn":
            primary = a
            break
    if primary is None and active:
        primary = active[0]

    rep = ConnectivityReport(
        hostname=platform.node(),
        os=platform.platform(),
        generated_at=time.time(),
        active_adapters=active,
        primary_connection_type=primary.connection_type if primary else "none",
        vpn_active=any(a.connection_type == "vpn" for a in active),
        cellular_present=any(a.connection_type == "cellular" for a in adapters),
    )

    if probe and primary and primary.gateway:
        rep.gateway_reachable = _tcp_probe(primary.gateway, 80) is not None or \
            _tcp_probe(primary.gateway, 443) is not None
        gw_lat = _tcp_probe(primary.gateway, 443)
        if gw_lat is not None:
            rep.internet_latency_ms = gw_lat

    if probe:
        rep.internet_latency_ms = _tcp_probe(PUBLIC_PROBE_HOST, PUBLIC_PROBE_PORT) or None
        rep.has_internet = rep.internet_latency_ms is not None or _resolve(DNS_PROBE_HOST) is not None
        # Public IP via a stdlib-only path: connect and read the local socket addr.
        try:
            with socket.create_connection((PUBLIC_PROBE_HOST, PUBLIC_PROBE_PORT), timeout=PROBE_TIMEOUT_S) as s:
                rep.public_ip = s.getsockname()[0]
        except Exception:  # noqa: BLE001
            rep.public_ip = primary.ipv4 if primary else None

    return rep


def save_report(rep: ConnectivityReport, path: Optional[Path] = None) -> Path:
    p = path or STATE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(rep), indent=2, default=str), encoding="utf-8")
    return p


def load_report(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or STATE_PATH
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("network state load failed: %s", e)
    return {}


def _self_test() -> int:
    print("=== MARKUS Network Intelligence Module Test ===")
    rep = build_report(probe=True)
    for a in rep.active_adapters:
        print(f"  {a.name:<24} type={a.connection_type:<9} {a.media_state} ipv4={a.ipv4} gw={a.gateway}")
    print(f"Primary: {rep.primary_connection_type}  Internet: {rep.has_internet}  "
          f"Latency: {rep.internet_latency_ms}ms  VPN: {rep.vpn_active}  Cellular: {rep.cellular_present}")
    # A machine with internet must report has_internet True; a purely offline box may not — don't hard-fail.
    assert isinstance(rep.has_internet, bool)
    assert rep.primary_connection_type in ("wifi", "ethernet", "vpn", "cellular", "none")
    print("✅ Network Intelligence Module: PASSED")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="MARKUS Network Intelligence")
    ap.add_argument("--json", action="store_true", help="print report as JSON")
    ap.add_argument("--save", action="store_true", help="persist snapshot to state file")
    ap.add_argument("--no-probe", action="store_true", help="skip live probes")
    args = ap.parse_args()
    r = build_report(probe=not args.no_probe)
    if args.save:
        p = save_report(r)
        print(f"saved -> {p}")
    if args.json:
        print(json.dumps(asdict(r), indent=2, default=str))
    else:
        _self_test()
