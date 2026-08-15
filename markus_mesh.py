"""
MARKUS OS Lightweight Mesh Networking Layer (Upgrade 10 — Enhanced with SUPRIME PeerTable)
Provides zero-configuration UDP broadcast discovery for connecting
multiple MARKUS OS instances across a local network into a resilient swarm.

Stealable integration: SUPRIME PeerTable (suprime/peers.py) ported for
heartbeat-based failure detection with SUSPECT/DEAD state transitions.

Broadcast Port: 8129 (Non-conflicting with HTTP port 8128)
"""

from __future__ import annotations
import json
import logging
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum

logger = logging.getLogger("Markus.Mesh")

MESH_BROADCAST_PORT = 8129
MESH_HEARTBEAT_INTERVAL = 5.0  # seconds
MESH_NODE_TIMEOUT = 15.0  # seconds

# --- SUPRIME PeerTable integration (port from suprime/peers.py) ---

class PeerState(str, Enum):
    """Peer failure-detection states. Ported from SUPRIME."""
    ALIVE = "alive"
    SUSPECT = "suspect"
    DEAD = "dead"


@dataclass
class Peer:
    """A remote node as seen from the local membership table.

    Ported from SUPRIME's Peer class — uses heartbeat counter + state machine
    instead of naive last_seen timeout.
    """
    node_id: str
    address: str
    heartbeat: int = 0
    state: PeerState = PeerState.ALIVE
    last_update: float = 0.0
    # MARKUS-specific extensions
    hostname: str = ""
    api_endpoint: str = ""
    capabilities: List[str] = field(default_factory=list)
    cpu_load: float = 0.0
    os_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, object]:
        return {
            "node_id": self.node_id,
            "address": self.address,
            "heartbeat": self.heartbeat,
        }


@dataclass
class MeshNode:
    """Backward-compatible wrapper — MARKUS MeshNode now extends Peer semantics.

    Kept for API compatibility with existing code that calls MeshNode.
    Internally delegates to Peer for failure detection.
    """
    node_id: str
    hostname: str
    api_endpoint: str
    capabilities: List[str]
    cpu_load: float
    last_seen: float
    os_version: str = "1.0.0"
    # NEW: heartbeat-based state (SUPRIME extension)
    heartbeat: int = 0
    state: PeerState = PeerState.ALIVE


class PeerTable:
    """Local view of swarm membership with heartbeat failure detection.

    Ported from SUPRIME (suprime/peers.py) — pure state, no I/O, deterministic.
    Replaces MARKUS's naive last_seen timeout with a proper SUSPECT/DEAD state
    machine that avoids false-positive evictions.

    Args:
        self_id: The owning node's identity.
        suspect_after: Seconds without a heartbeat advance before SUSPECT.
        dead_after: Seconds without a heartbeat advance before DEAD (evicted).
        clock: Injectable time source; defaults to time.monotonic.
    """

    def __init__(
        self,
        self_id: str,
        suspect_after: float = 3.0,
        dead_after: float = 6.0,
        clock=time.monotonic,
    ) -> None:
        self._self_id = self_id
        self._suspect_after = suspect_after
        self._dead_after = dead_after
        self._clock = clock
        self._peers: Dict[str, Peer] = {}

    def merge(self, node_id: str, address: str, heartbeat: int) -> bool:
        """Integrate a heartbeat observation. Returns True if state changed."""
        if node_id == self._self_id:
            return False
        now = self._clock()
        existing = self._peers.get(node_id)
        if existing is None:
            self._peers[node_id] = Peer(
                node_id=node_id,
                address=address,
                heartbeat=heartbeat,
                state=PeerState.ALIVE,
                last_update=now,
            )
            return True
        if heartbeat > existing.heartbeat:
            existing.heartbeat = heartbeat
            existing.address = address
            existing.last_update = now
            existing.state = PeerState.ALIVE
            return True
        return False

    def refresh(self, node_id: str) -> bool:
        """Mark a peer alive on a direct liveness signal (e.g. SWIM ACK)."""
        peer = self._peers.get(node_id)
        if peer is None:
            return False
        peer.last_update = self._clock()
        peer.state = PeerState.ALIVE
        return True

    def evict(self, node_id: str) -> None:
        self._peers.pop(node_id, None)

    def tick(self) -> None:
        """Advance failure-detection state based on elapsed time.

        Peers → SUSPECT then DEAD as heartbeats go stale. Dead peers removed.
        """
        now = self._clock()
        for peer in list(self._peers.values()):
            silence = now - peer.last_update
            if silence >= self._dead_after:
                peer.state = PeerState.DEAD
                self._peers.pop(peer.node_id, None)
            elif silence >= self._suspect_after:
                peer.state = PeerState.SUSPECT

    def get(self, node_id: str) -> Optional[Peer]:
        return self._peers.get(node_id)

    def all(self) -> List[Peer]:
        return list(self._peers.values())

    def alive(self) -> List[Peer]:
        return [p for p in self._peers.values() if p.state == PeerState.ALIVE]

    def addresses(self) -> List[str]:
        return [p.address for p in self._peers.values()]

    def known_ids(self, include_self: bool = False) -> List[str]:
        ids = list(self._peers.keys())
        if include_self:
            ids.append(self._self_id)
        return ids

    def digest(self) -> List[Dict[str, object]]:
        """Compact serialisable snapshot for gossip piggybacking."""
        return [p.to_dict() for p in self._peers.values()]

    def apply_digest(self, entries: list) -> bool:
        """Merge a batch of peer descriptors from a gossip message."""
        changed = False
        for entry in entries:
            node_id = str(entry["node_id"])
            address = str(entry["address"])
            heartbeat = int(entry["heartbeat"])
            if self.merge(node_id, address, heartbeat):
                changed = True
        return changed

    def __len__(self) -> int:
        return len(self._peers)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._peers


class MarkusMeshLayer:
    """
    UDP broadcast listener broadcaster for automatic peer discovery.
    Integrates directly into the MarkusKernel as the 'mesh' subsystem.

    Enhanced with SUPRIME's PeerTable for heartbeat-based failure detection
    (replaces naive last_seen timeout with SUSPECT/DEAD state machine).
    """

    def __init__(
        self,
        node_name: str,
        api_endpoint: str,
        capabilities: Optional[List[str]] = None,
        db_path: Optional[Path] = None,
        port: int = MESH_BROADCAST_PORT,
    ) -> None:
        self.node_id = f"{node_name}-{socket.gethostname()}".lower()
        self.api_endpoint = api_endpoint
        self.capabilities = capabilities or []
        self.port = port

        # SUPRIME PeerTable — replaces the old self.nodes: Dict
        self.peer_table = PeerTable(self_id=self.node_id)
        # Backward-compatible alias
        self.nodes: Dict[str, MeshNode] = {}

        self._lock = threading.Lock()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._broadcaster_thread: Optional[threading.Thread] = None
        self._heartbeat_counter = 0  # Monotonic counter for SUPRIME-style gossip
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.settimeout(1.0)
        self._sock.bind(("", self.port))

    def _build_heartbeat(self) -> bytes:
        self._heartbeat_counter += 1
        payload = {
            "node_id": self.node_id,
            "hostname": socket.gethostname(),
            "api_endpoint": self.api_endpoint,
            "capabilities": self.capabilities,
            "cpu_load": self._get_cpu_load(),
            "timestamp": time.time(),
            "os_version": "1.0.0",
            "heartbeat": self._heartbeat_counter,  # NEW: monotonic counter for SUPRIME merge
        }
        return json.dumps(payload).encode("utf-8")

    def _get_cpu_load(self) -> float:
        """Lightweight CPU load estimator."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1) / 100.0
        except ImportError:
            return 0.05

    def _parse_peer(self, data: bytes, addr: tuple) -> Optional[Peer]:
        try:
            payload = json.loads(data.decode("utf-8"))
            node_id = payload.get("node_id", "")
            if node_id == self.node_id:
                return None

            heartbeat = payload.get("heartbeat", 0)

            peer = Peer(
                node_id=node_id,
                address=f"{addr[0]}:{payload.get('api_endpoint', '').split(':')[-1] or self.port}",
                heartbeat=heartbeat,
                state=PeerState.ALIVE,
                last_update=time.time(),
                hostname=payload.get("hostname", addr[0]),
                api_endpoint=payload.get("api_endpoint", ""),
                capabilities=payload.get("capabilities", []),
                cpu_load=payload.get("cpu_load", 0.0),
                os_version=payload.get("os_version", "unknown"),
            )

            # Backward-compat: also populate self.nodes for legacy callers
            mesh_node = MeshNode(
                node_id=node_id,
                hostname=peer.hostname,
                api_endpoint=peer.api_endpoint,
                capabilities=peer.capabilities,
                cpu_load=peer.cpu_load,
                last_seen=time.time(),
                os_version=peer.os_version,
                heartbeat=heartbeat,
                state=peer.state,
            )

            return peer
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Dropped malformed mesh packet from {addr}: {e}")
            return None

    def _listen_loop(self) -> None:
        logger.info(f"Mesh listener bound to port {self.port}")
        while self._running:
            try:
                data, addr = self._sock.recvfrom(1500)
                peer = self._parse_peer(data, addr)
                if peer:
                    with self._lock:
                        # SUPRIME-style merge: heartbeat-based, no false positives
                        self.peer_table.merge(peer.node_id, peer.address, peer.heartbeat)
                        # Sync peer metadata
                        stored = self.peer_table.get(peer.node_id)
                        if stored:
                            stored.hostname = peer.hostname
                            stored.api_endpoint = peer.api_endpoint
                            stored.capabilities = peer.capabilities
                            stored.cpu_load = peer.cpu_load
                            stored.os_version = peer.os_version

                        # Backward-compat: populate self.nodes
                        self.nodes[peer.node_id] = MeshNode(
                            node_id=peer.node_id,
                            hostname=peer.hostname,
                            api_endpoint=peer.api_endpoint,
                            capabilities=peer.capabilities,
                            cpu_load=peer.cpu_load,
                            last_seen=time.time(),
                            os_version=peer.os_version,
                            heartbeat=peer.heartbeat,
                            state=peer.state,
                        )

                        logger.info(f"Discovered peer: {peer.node_id}")
                        self._evict_dead_nodes()
            except socket.timeout:
                # Tick the PeerTable state machine on every timeout
                with self._lock:
                    self.peer_table.tick()
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Mesh listener error: {e}")

    def _broadcast_loop(self) -> None:
        while self._running:
            if self._running:
                try:
                    self._sock.sendto(self._build_heartbeat(), ("255.255.255.255", self.port))
                    with self._lock:
                        self.peer_table.tick()
                        self._evict_dead_nodes()
                    time.sleep(MESH_HEARTBEAT_INTERVAL)
                except Exception as e:
                    logger.error(f"Mesh broadcast error: {e}")
                    time.sleep(1.0)

    def _evict_dead_nodes(self) -> None:
        """Evict DEAD peers from both PeerTable and backward-compat nodes dict."""
        # SUPRIME: tick advances SUSPECT → DEAD, then removes DEAD from table
        self.peer_table.tick()

        # Sync backward-compat dict
        alive_ids = {p.node_id for p in self.peer_table.all()}
        dead_in_legacy = [nid for nid in self.nodes if nid not in alive_ids]
        for nid in dead_in_legacy:
            logger.info(f"Evicted stale peer: {nid}")
            del self.nodes[nid]

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        # Register self in PeerTable as a known peer (for gossip)
        self.peer_table.merge(self.node_id, self.api_endpoint, 0)
        self._listener_thread = threading.Thread(target=self._listen_loop, name="Markus-Mesh-Listen", daemon=True)
        self._broadcaster_thread = threading.Thread(target=self._broadcast_loop, name="Markus-Mesh-Bcast", daemon=True)
        self._listener_thread.start()
        self._broadcaster_thread.start()
        logger.info(f"MarkusMeshLayer started. NodeID: {self.node_id}")

    def stop(self) -> None:
        self._running = False
        self._sock.close()
        logger.info("MarkusMeshLayer stopped.")

    def discover_peers(self) -> List[MeshNode]:
        """Return live peers using SUPRIME's heartbeat-based detection."""
        with self._lock:
            self.peer_table.tick()
            peers = self.peer_table.all()

            # Rebuild backward-compat nodes dict from PeerTable
            self.nodes = {
                p.node_id: MeshNode(
                    node_id=p.node_id,
                    hostname=p.hostname,
                    api_endpoint=p.api_endpoint,
                    capabilities=p.capabilities,
                    cpu_load=p.cpu_load,
                    last_seen=p.last_update,
                    os_version=p.os_version,
                    heartbeat=p.heartbeat,
                    state=p.state,
                )
                for p in peers
            }

            return list(self.nodes.values())

    def get_best_peer(self) -> Optional[MeshNode]:
        peers = self.discover_peers()
        if not peers:
            return None
        return min(peers, key=lambda p: p.cpu_load)


if __name__ == "__main__":
    layer = MarkusMeshLayer(node_name="markus-node", api_endpoint="http://localhost:8128")
    layer.start()
    print("=== MARKUS Mesh Networking Layer Active (SUPRIME-Enhanced) ===")
    print(f"Node ID: {layer.node_id}")
    print(f"Broadcast Port: {layer.port}")
    print(f"Heartbeat Interval: {MESH_HEARTBEAT_INTERVAL}s")
    print(f"Suspect Threshold: 3.0s | Dead Threshold: 6.0s")
    print("Listening for peer broadcasts... (Ctrl+C to stop)")

    try:
        while True:
            time.sleep(2)
            peers = layer.discover_peers()
            suspect = sum(1 for p in peers if p.state == PeerState.SUSPECT)
            alive_count = sum(1 for p in peers if p.state == PeerState.ALIVE)
            print(f"\r[Peers: {len(peers)} (ALIVE: {alive_count}, SUSPECT: {suspect})]", end="", flush=True)
    except KeyboardInterrupt:
        print("\nShutting down mesh layer...")
        layer.stop()
