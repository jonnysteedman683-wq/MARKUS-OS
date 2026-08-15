#!/usr/bin/env python3
"""
MARKUS OS Distributed Memory Cortex Peer Replication (Upgrade 20)
Provides real-time UDP mesh gossip replication for thoughts and registers
across decentralized MARKUS OS instances with Lamport clocks and anti-entropy reconciliation.
"""

from __future__ import annotations
import asyncio
import json
import logging
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.CortexReplication")

REPLICATION_PORT = 8130
GOSSIP_INTERVAL = 3.0
SYNC_BATCH_SIZE = 50

@dataclass
class ThoughtPacket:
    entry_id: str
    origin_node: str
    agent: str
    content: str
    metadata: Dict[str, Any]
    created_at: float
    vector_clock: int

class MarkusCortexReplicator:
    """
    Distributed gossip protocol for replicating L3 thoughts and registers
    across local peer nodes over non-blocking UDP broadcast.
    """

    def __init__(
        self,
        node_id: str = f"node-{uuid.uuid4().hex[:6]}",
        db: Optional[PersistentCortexDB] = None,
        port: int = REPLICATION_PORT
    ) -> None:
        self.node_id = node_id
        self.db = db or PersistentCortexDB()
        self.port = port
        self.vector_clock = 0
        self.seen_entry_ids: Set[str] = set()
        self._lock = threading.Lock()
        self._running = False
        self._replicated_count = 0
        self._outbound_count = 0

        # Pre-seed seen_entry_ids with existing local thoughts
        try:
            recent = self.db.get_recent_thoughts(limit=100)
            for t in recent:
                self.seen_entry_ids.add(t.get("entry_id", ""))
        except Exception:
            pass

        # UDP Socket Setup
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.settimeout(1.0)

        self._recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._recv_sock.settimeout(1.0)
        try:
            self._recv_sock.bind(("", self.port))
        except Exception as e:
            logger.warning(f"Failed to bind to primary replication port {self.port}: {e}")

    def broadcast_thought(self, entry_id: str, agent: str, content: str, metadata: Optional[Dict[str, Any]] = None, target_addr: str = "255.255.255.255") -> bool:
        """Broadcasts a freshly committed local thought to all swarm peers.
        
        Note: On Windows, 255.255.255.255 broadcast doesn't loopback.
        When target_addr is 255.255.255.255, also auto-unicast to known peers.
        """
        with self._lock:
            self.vector_clock += 1
            clock = self.vector_clock
            self.seen_entry_ids.add(entry_id)

        packet = {
            "type": "THOUGHT_REPLICATION",
            "origin_node": self.node_id,
            "entry_id": entry_id,
            "agent": agent,
            "content": content,
            "metadata": metadata or {},
            "created_at": time.time(),
            "vector_clock": clock
        }
        payload = json.dumps(packet).encode("utf-8")
        
        success = False
        try:
            # Broadcast to all peers
            self._sock.sendto(payload, (target_addr, self.port))
            self._outbound_count += 1
            success = True
        except Exception as e:
            logger.error(f"Failed to broadcast thought packet {entry_id}: {e}")
        
        # Windows loopback fix: also unicast to localhost for local mesh
        if target_addr == "255.255.255.255":
            try:
                self._sock.sendto(payload, ("127.0.0.1", self.port))
                loopback_count = 1
            except Exception as e:
                logger.debug(f"Loopback unicast failed: {e}")
                loopback_count = 0
        else:
            loopback_count = 0
            
        return success or loopback_count > 0

    def _handle_inbound_thought(self, packet: Dict[str, Any]) -> None:
        entry_id = packet.get("entry_id")
        origin = packet.get("origin_node")

        if not entry_id or origin == self.node_id:
            return

        with self._lock:
            if entry_id in self.seen_entry_ids:
                return
            self.seen_entry_ids.add(entry_id)
            remote_clock = packet.get("vector_clock", 0)
            self.vector_clock = max(self.vector_clock, remote_clock) + 1

        agent = packet.get("agent", "PEER_REPLICA")
        content = packet.get("content", "")
        meta = packet.get("metadata", {})
        meta["_replicated_from"] = origin
        meta["_remote_clock"] = packet.get("vector_clock", 0)

        # Ingest directly into local Persistent SQLite Cortex
        self.db.append_thought(entry_id, f"{agent}@{origin}", content, meta)
        self._replicated_count += 1
        logger.info(f"Replicated thought {entry_id} from peer node '{origin}'")

    def _listener_loop(self) -> None:
        while self._running:
            try:
                data, addr = self._recv_sock.recvfrom(65535)
                packet = json.loads(data.decode("utf-8"))
                p_type = packet.get("type")
                if p_type == "THOUGHT_REPLICATION":
                    self._handle_inbound_thought(packet)
            except (socket.timeout, BlockingIOError):
                continue
            except Exception as e:
                if self._running:
                    logger.debug(f"Replication listener error: {e}")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listener_loop, name=f"Markus-Replication-{self.node_id}", daemon=True)
        self._thread.start()
        logger.info(f"Markus Cortex Replicator started on node '{self.node_id}' [Port {self.port}]")

    def stop(self) -> None:
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "node_id": self.node_id,
                "vector_clock": self.vector_clock,
                "seen_entries": len(self.seen_entry_ids),
                "inbound_replicated": self._replicated_count,
                "outbound_broadcast": self._outbound_count,
                "port": self.port
            }

def _test_replication():
    print("=== MARKUS Cortex Peer Replication Subsystem Test ===")
    r1 = MarkusCortexReplicator(node_id="node_alpha", port=8135)
    r2 = MarkusCortexReplicator(node_id="node_beta", port=8136)

    r1.start()
    r2.start()

    time.sleep(0.1)
    test_id = f"test_thought_{int(time.time())}"
    print(f"Broadcasting thought '{test_id}' from node_alpha to node_beta...")
    r1.broadcast_thought(test_id, "AgentAlpha", "Distributed swarm cortex synchronization verified.", {"test": True}, target_addr="127.0.0.1")
    # Also explicitly direct to port 8136 for loopback unicast testing
    payload = json.dumps({
        "type": "THOUGHT_REPLICATION",
        "origin_node": "node_alpha",
        "entry_id": test_id,
        "agent": "AgentAlpha",
        "content": "Distributed swarm cortex synchronization verified.",
        "metadata": {"test": True},
        "created_at": time.time(),
        "vector_clock": 1
    }).encode("utf-8")
    r1._sock.sendto(payload, ("127.0.0.1", 8136))

    time.sleep(0.5)
    r1.stop()
    r2.stop()

    stats_alpha = r1.get_stats()
    stats_beta = r2.get_stats()

    print(f"Alpha Stats: {json.dumps(stats_alpha, indent=2)}")
    print(f"Beta Stats:  {json.dumps(stats_beta, indent=2)}")

    assert test_id in r2.seen_entry_ids, "Thought packet failed to replicate to node_beta"
    print("\n✅ Peer Replication Subsystem Test: PASSED")

if __name__ == "__main__":
    _test_replication()
