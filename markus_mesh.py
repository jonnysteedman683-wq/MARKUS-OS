"""
MARKUS OS Lightweight Mesh Networking Layer (Upgrade 10)
Provides zero-configuration UDP broadcast discovery for connecting
multiple MARKUS OS instances across a local network into a resilient swarm.

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

logger = logging.getLogger("Markus.Mesh")

MESH_BROADCAST_PORT = 8129
MESH_HEARTBEAT_INTERVAL = 5.0  # seconds
MESH_NODE_TIMEOUT = 15.0  # seconds

@dataclass
class MeshNode:
    """Represents a discovered peer in the MARKUS swarm mesh."""
    node_id: str
    hostname: str
    api_endpoint: str
    capabilities: List[str]
    cpu_load: float
    last_seen: float
    os_version: str = "1.0.0"

class MarkusMeshLayer:
    """
    UDP broadcast listener broadcaster for automatic peer discovery.
    Integrates directly into the MarkusKernel as the 'mesh' subsystem.
    """
    def __init__(self, node_name: str, api_endpoint: str, capabilities: Optional[List[str]] = None, db_path: Optional[Path] = None, port: int = MESH_BROADCAST_PORT) -> None:
        self.node_id = f"{node_name}-{socket.gethostname()}".lower()
        self.api_endpoint = api_endpoint
        self.capabilities = capabilities or []
        self.port = port
        self.nodes: Dict[str, MeshNode] = {}
        # RLock: _evict_dead_nodes() guards internally and is called both from
        # the broadcaster thread (no lock held) and the listener thread (lock
        # already held) — re-entrant lock prevents a deadlock while eliminating
        # the concurrent peer-dict mutation race.
        self._lock = threading.RLock()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._broadcaster_thread: Optional[threading.Thread] = None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.settimeout(1.0)
        self._sock.bind(("", self.port))

    def _build_heartbeat(self) -> bytes:
        payload = {
            "node_id": self.node_id,
            "hostname": socket.gethostname(),
            "api_endpoint": self.api_endpoint,
            "capabilities": self.capabilities,
            "cpu_load": self._get_cpu_load(),
            "timestamp": time.time(),
            "os_version": "1.0.0"
        }
        return json.dumps(payload).encode("utf-8")

    def _get_cpu_load(self) -> float:
        """Lightweight CPU load estimator (fallback to static value if psutil unavailable)."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1) / 100.0
        except ImportError:
            return 0.05

    def _parse_peer(self, data: bytes, addr: tuple) -> Optional[MeshNode]:
        try:
            payload = json.loads(data.decode("utf-8"))
            node_id = payload.get("node_id", "")
            if node_id == self.node_id:  # Ignore own broadcasts
                return None
            return MeshNode(
                node_id=node_id,
                hostname=payload.get("hostname", addr[0]),
                api_endpoint=payload.get("api_endpoint", ""),
                capabilities=payload.get("capabilities", []),
                cpu_load=payload.get("cpu_load", 0.0),
                last_seen=time.time(),
                os_version=payload.get("os_version", "unknown")
            )
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
                        if peer.node_id in self.nodes:
                            self.nodes[peer.node_id].last_seen = time.time()
                            self.nodes[peer.node_id].cpu_load = peer.cpu_load
                        else:
                            self.nodes[peer.node_id] = peer
                            logger.info(f"Discovered peer: {peer.node_id}")
                            self._evict_dead_nodes()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Mesh listener error: {e}")

    def _broadcast_loop(self) -> None:
        while self._running:
            if self._running:
                try:
                    self._sock.sendto(self._build_heartbeat(), ("255.255.255.255", self.port))
                    self._evict_dead_nodes()
                    time.sleep(MESH_HEARTBEAT_INTERVAL)
                except Exception as e:
                    logger.error(f"Mesh broadcast error: {e}")
                    time.sleep(1.0)

    def _evict_dead_nodes(self) -> None:
        # Guard internally: callers span multiple threads and may already hold
        # _lock (listener) or not (broadcaster, discover_peers). RLock is
        # re-entrant, so all three call sites serialize safely.
        with self._lock:
            now = time.time()
            expired = [nid for nid, n in self.nodes.items() if (now - n.last_seen) > MESH_NODE_TIMEOUT]
            for nid in expired:
                logger.info(f"Evicted stale peer: {nid}")
                del self.nodes[nid]

    def start(self) -> None:
        if self._running:
            return
        self._running = True
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
        self._evict_dead_nodes()
        with self._lock:
            return list(self.nodes.values())

    def get_best_peer(self) -> Optional[MeshNode]:
        peers = self.discover_peers()
        if not peers:
            return None
        return min(peers, key=lambda p: p.cpu_load)

if __name__ == "__main__":
    layer = MarkusMeshLayer(node_name="markus-node", api_endpoint="http://localhost:8128")
    layer.start()
    print("=== MARKUS Mesh Networking Layer Active ===")
    print(f"Node ID: {layer.node_id}")
    print(f"Broadcast Port: {layer.port}")
    print(f"Heartbeat Interval: {MESH_HEARTBEAT_INTERVAL}s")
    print("Listening for peer broadcasts... (Ctrl+C to stop)")

    try:
        while True:
            time.sleep(2)
            peers = layer.discover_peers()
            print(f"\r[Peers Live: {len(peers)}]", end="", flush=True)
    except KeyboardInterrupt:
        print("\nShutting down mesh layer...")
        layer.stop()
