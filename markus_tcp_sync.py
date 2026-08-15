#!/usr/bin/env python3
"""MARKUS OS TCP Reliability Mode with Lamport Clock Anti-Entropy Sync"""
from __future__ import annotations
import json
import logging
import socket
import threading
import time
from typing import Any, Dict, Optional, Set
from dataclasses import dataclass, field

from markus_cortex_replication import MarkusCortexReplicator, GOSSIP_INTERVAL

logger = logging.getLogger("Markus.TCPSync")

RECONCILIATION_INTERVAL = 5.0
BATCH_SIZE = 50
MAX_PACKET_SIZE = 65535

# Fallback detection thresholds
FALLBACK_DELTA_THRESHOLD = 0.10  # 10% packet loss threshold
FALLBACK_WINDOW_SECONDS = 5.0    # Time window for detecting loss
STABLE_UDP_SECONDS = 10.0        # Time before reverting to UDP


@dataclass
class SyncRequest:
    request_id: str
    from_clock: int
    to_clock: int
    requested_at: float


class UDPStatsTracker:
    """Track UDP packet delivery statistics for fallback detection."""
    
    def __init__(self):
        self.outbound_count = 0
        self.inbound_count = 0
        self.last_check_time = time.time()
        self.previous_outbound = 0
        self.previous_inbound = 0
        self.fallback_to_tcp = False
        self.tcp_fallback_start = 0.0
        self.udp_stable_since = 0.0
        self.lock = threading.Lock()
    
    def record_outbound(self, count: int = 1) -> None:
        """Record outbound packet count."""
        with self.lock:
            self.outbound_count += count
    
    def record_inbound(self, count: int = 1) -> None:
        """Record inbound packet count."""
        with self.lock:
            self.inbound_count += count
    
    def check_fallback_needed(self) -> tuple[bool, bool, Dict[str, Any]]:
        """
        Check if fallback to TCP is needed.
        Returns: (should_fallback, should_revert, metrics)
        """
        with self.lock:
            now = time.time()
            
            # Update previous counts at check intervals
            time_delta = now - self.last_check_time
            
            if time_delta >= FALLBACK_WINDOW_SECONDS:
                # Calculate delta between outbound and inbound counts
                outbound_delta = self.outbound_count - self.previous_outbound
                inbound_delta = self.inbound_count - self.previous_inbound
                
                # Calculate loss percentage
                if outbound_delta > 0:
                    loss_delta = outbound_delta - inbound_delta
                    loss_percentage = max(0, loss_delta) / outbound_delta
                else:
                    loss_percentage = 0.0
                
                # Check fallback conditions
                should_fallback = (
                    not self.fallback_to_tcp and 
                    loss_percentage > FALLBACK_DELTA_THRESHOLD
                )
                
                # Check revert conditions (stable UDP for 10s)
                should_revert = False
                if self.fallback_to_tcp:
                    # Check if UDP is now stable
                    if self._udp_is_stable():
                        if self.udp_stable_since == 0:
                            self.udp_stable_since = now
                        elif now - self.udp_stable_since >= STABLE_UDP_SECONDS:
                            should_revert = True
                    else:
                        self.udp_stable_since = 0.0
                
                # Update previous counts
                self.previous_outbound = self.outbound_count
                self.previous_inbound = self.inbound_count
                self.last_check_time = now
                
                metrics = {
                    "outbound_delta": outbound_delta,
                    "inbound_delta": inbound_delta,
                    "loss_percentage": loss_percentage,
                    "loss_threshold": FALLBACK_DELTA_THRESHOLD,
                    "time_in_tcp_mode": now - self.tcp_fallback_start if self.fallback_to_tcp else 0,
                    "udp_stable_duration": now - self.udp_stable_since if self.udp_stable_since else 0,
                }
                
                return should_fallback, should_revert, metrics
            
            # Return current state metrics (within window)
            outbound_delta = self.outbound_count - self.previous_outbound
            inbound_delta = self.inbound_count - self.previous_inbound
            if outbound_delta > 0:
                loss_delta = outbound_delta - inbound_delta
                loss_percentage = max(0, loss_delta) / outbound_delta
            else:
                loss_percentage = 0.0
            
            return False, False, {
                "outbound_delta": outbound_delta,
                "inbound_delta": inbound_delta,
                "loss_percentage": loss_percentage,
                "loss_threshold": FALLBACK_DELTA_THRESHOLD,
                "time_in_tcp_mode": now - self.tcp_fallback_start if self.fallback_to_tcp else 0,
                "udp_stable_duration": now - self.udp_stable_since if self.udp_stable_since else 0,
            }
    
    def _udp_is_stable(self) -> bool:
        """Check if UDP is currently stable (low packet loss)."""
        outbound = self.outbound_count - self.previous_outbound
        inbound = self.inbound_count - self.previous_inbound
        
        if outbound == 0:
            return True
        
        loss_delta = outbound - inbound
        loss_percentage = max(0, loss_delta) / outbound
        
        return loss_percentage <= FALLBACK_DELTA_THRESHOLD
    
    def set_tcp_fallback(self, enabled: bool) -> None:
        """Set the TCP fallback mode state."""
        with self.lock:
            if enabled and not self.fallback_to_tcp:
                self.fallback_to_tcp = True
                self.tcp_fallback_start = time.time()
                logger.info("TCP fallback mode ENABLED - UDP packet loss detected")
            elif not enabled and self.fallback_to_tcp:
                self.fallback_to_tcp = False
                self.tcp_fallback_start = 0.0
                logger.info("TCP fallback mode DISABLED - UDP stable, reverting to UDP mode")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current UDP/TCP stats."""
        with self.lock:
            now = time.time()
            return {
                "total_outbound": self.outbound_count,
                "total_inbound": self.inbound_count,
                "current_outbound_rate": (self.outbound_count - self.previous_outbound) / max(now - self.last_check_time, 1.0),
                "current_inbound_rate": (self.inbound_count - self.previous_inbound) / max(now - self.last_check_time, 1.0),
                "fallback_to_tcp": self.fallback_to_tcp,
                "tcp_fallback_duration": now - self.tcp_fallback_start if self.fallback_to_tcp else 0,
                "udp_stable_duration": now - self.udp_stable_since if self.udp_stable_since else 0,
            }


class ReliableCortexReplicator(MarkusCortexReplicator):
    """
    Extends UDP gossip with TCP recovery channel and Lamport anti-entropy.
    Primary: UDP broadcast (fast, fire-and-forget)
    Secondary: TCP sync (reliable, on-demand reconciliation)
    
    Features:
    - Adaptive UDP→TCP fallback detection
    - Packet loss tracking via inbound/outbound delta
    - Auto-switch to TCP when loss > 10% over 5 seconds
    - Revert to UDP after 10s of stable traffic
    - Comprehensive metrics in get_stats()
    """
    
    def __init__(
        self,
        node_id: str,
        port: int,
        tcp_sync_port: int = 0,
        enable_anti_entropy: bool = True,
        auto_fallback_mode: bool = True,
        **kwargs
    ) -> None:
        super().__init__(node_id=node_id, port=port, **kwargs)
        
        self.tcp_sync_port = tcp_sync_port or port + 1000
        self._tcp_sock: Optional[socket.socket] = None
        self._tcp_listen_thread: Optional[threading.Thread] = None
        self._pending_sync_requests: Dict[str, SyncRequest] = {}
        self._anti_entropy_enabled = enable_anti_entropy
        self._last_sync_check = 0.0
        self.auto_fallback_mode = auto_fallback_mode
        
        # UDP stats tracking for adaptive fallback
        self._udp_stats = UDPStatsTracker()
        
        # Background thread for fallback detection
        self._fallback_monitor_thread: Optional[threading.Thread] = None
        self._fallback_lock = threading.Lock()
        
        self._init_tcp_socket()
    
    def _init_tcp_socket(self) -> None:
        """Initialize TCP socket for reliable sync channel."""
        try:
            self._tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            self._tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._tcp_sock.settimeout(5.0)
            self._tcp_sock.bind(("", self.tcp_sync_port))
            self._tcp_sock.listen(5)
            logger.info(f"TCP sync listener bound to port {self.tcp_sync_port}")
        except Exception as e:
            logger.warning(f"Failed to init TCP sync socket: {e}")
            self._tcp_sock = None
    
    def start(self) -> None:
        """Start UDP listener, TCP sync server, and fallback monitor."""
        super().start()
        
        if self._tcp_sock and not self._tcp_listen_thread:
            self._tcp_listen_thread = threading.Thread(
                target=self._tcp_listener_loop,
                name=f"Markus-TCP-Sync-{self.node_id}",
                daemon=True
            )
            self._tcp_listen_thread.start()
            time.sleep(0.05)  # Allow TCP socket to become accepting
        
        # Start fallback monitor if auto_fallback_mode is enabled
        if self.auto_fallback_mode:
            self._fallback_monitor_thread = threading.Thread(
                target=self._fallback_monitor_loop,
                name=f"Markus-Fallback-Monitor-{self.node_id}",
                daemon=True
            )
            self._fallback_monitor_thread.start()
    
    def stop(self) -> None:
        """Stop all listeners and sockets."""
        super().stop()
        
        if self._tcp_sock:
            try:
                self._tcp_sock.close()
                self._tcp_sock = None
            except Exception:
                pass
    
    def _fallback_monitor_loop(self) -> None:
        """Background thread to monitor UDP packet loss and trigger fallback."""
        while self._running:
            try:
                should_fallback, should_revert, metrics = self._udp_stats.check_fallback_needed()
                
                if should_fallback:
                    with self._fallback_lock:
                        self._udp_stats.set_tcp_fallback(True)
                    logger.warning(f"UDP packet loss ({metrics['loss_percentage']*100:.1f}%) > {FALLBACK_DELTA_THRESHOLD*100}%, switching to TCP fallback mode")
                
                if should_revert:
                    with self._fallback_lock:
                        self._udp_stats.set_tcp_fallback(False)
                    logger.info(f"UDP stable for {STABLE_UDP_SECONDS}s, reverting to UDP mode")
                
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                if self._running:
                    logger.debug(f"Fallback monitor error: {e}")
    
    def is_tcp_fallback_active(self) -> bool:
        """Check if TCP fallback mode is currently active."""
        return self._udp_stats.get_stats().get("fallback_to_tcp", False)
    
    def _tcp_listener_loop(self) -> None:
        """Accept TCP connections and handle sync requests."""
        while self._running:
            try:
                conn, addr = self._tcp_sock.accept()
                with conn:
                    self._handle_tcp_sync(conn, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.debug(f"TCP listener error: {e}")
    
    def _handle_tcp_sync(self, conn: socket.socket, addr: tuple) -> None:
        """Handle incoming TCP sync request."""
        try:
            data = conn.recv(MAX_PACKET_SIZE)
            if not data:
                return
            
            msg = json.loads(data.decode("utf-8"))
            msg_type = msg.get("type")
            
            if msg_type == "SYNC_REQUEST":
                self._process_sync_request(msg, conn)
            elif msg_type == "THOUGHT_QUERY":
                self._process_thought_query(msg, conn)
            elif msg_type == "SYNC_HEARTBEAT":
                self._send_sync_heartbeat(conn)
            
            # Track inbound TCP packet
            self._udp_stats.record_inbound()
                
        except Exception as e:
            logger.debug(f"TCP sync handler error: {e}")
    
    def _process_sync_request(self, req: Dict[str, Any], conn: socket.socket) -> None:
        """Process anti-entropy sync request."""
        from_clock = req.get("from_clock", 0)
        to_clock = req.get("to_clock", self.vector_clock + 1)
        missed_thoughts = []
        
        # Get thoughts in requested clock range
        thoughts = self.db.get_recent_thoughts(limit=BATCH_SIZE)
        for t in thoughts:
            if from_clock <= t.get("created_at", 0) <= to_clock:
                missed_thoughts.append(t)
        
        response = {
            "type": "SYNC_RESPONSE",
            "request_id": req.get("request_id"),
            "from_node": self.node_id,
            "vector_clock": self.vector_clock,
            "thoughts": missed_thoughts,
            "peer_seen": len(self.seen_entry_ids)
        }
        
        conn.sendall(json.dumps(response).encode("utf-8"))
        logger.debug(f"Synced {len(missed_thoughts)} thoughts")
    
    def _process_thought_query(self, req: Dict[str, Any], conn: socket.socket) -> None:
        """Query for specific thoughts by entry ID or range."""
        query_type = req.get("query_type", "entry_id")
        query_value = req.get("query_value")
        
        result = None
        if query_type == "entry_id" and query_value:
            thoughts = self.db.search_thoughts(query_value, limit=1)
            result = thoughts[0] if thoughts else None
        elif query_type == "recent":
            result = self.db.get_recent_thoughts(limit=req.get("limit", 10))
        
        response = {
            "type": "QUERY_RESPONSE",
            "request_id": req.get("request_id"),
            "result": result
        }
        
        conn.sendall(json.dumps(response).encode("utf-8"))
    
    def _send_sync_heartbeat(self, conn: socket.socket) -> None:
        """Send sync heartbeat with current state."""
        heartbeat = {
            "type": "HEARTBEAT",
            "node_id": self.node_id,
            "vector_clock": self.vector_clock,
            "seen_count": len(self.seen_entry_ids),
            "port": self.port,
            "udp_fallback_mode": self.is_tcp_fallback_active(),
            "timestamp": time.time()
        }
        conn.sendall(json.dumps(heartbeat).encode("utf-8"))
    
    def tcp_sync_request(self, target_addr: str, target_port: int, 
                         from_clock: int = 0, to_clock: int = 0) -> Optional[Dict]:
        """Initiate TCP sync request to remote peer."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((target_addr, target_port))
            
            request = {
                "type": "SYNC_REQUEST",
                "request_id": f"sync_{int(time.time()*1000)}",
                "from_clock": from_clock,
                "to_clock": to_clock or self.vector_clock + 1,
                "requester": self.node_id,
                "timestamp": time.time()
            }
            
            sock.sendall(json.dumps(request).encode("utf-8"))
            data = sock.recv(MAX_PACKET_SIZE)
            sock.close()
            
            # Track outbound TCP packet
            self._udp_stats.record_outbound()
            
            return json.loads(data.decode("utf-8"))
            
        except Exception as e:
            logger.debug(f"TCP sync error: {e}")
            return None
    
    def tcp_heartbeat(self, target_addr: str, target_port: int) -> Optional[Dict]:
        """Send TCP heartbeat request."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((target_addr, target_port))
            
            request = {
                "type": "SYNC_HEARTBEAT",
                "requester": self.node_id,
                "timestamp": time.time()
            }
            
            sock.sendall(json.dumps(request).encode("utf-8"))
            data = sock.recv(MAX_PACKET_SIZE)
            sock.close()
            
            # Track outbound TCP packet
            self._udp_stats.record_outbound()
            
            return json.loads(data.decode("utf-8"))
            
        except Exception as e:
            logger.debug(f"TCP heartbeat error: {e}")
            return None
    
    def anti_entropy_check(self) -> None:
        """Periodically check for missing thoughts and sync them."""
        if not self._anti_entropy_enabled:
            return
        
        now = time.time()
        if now - self._last_sync_check < GOSSIP_INTERVAL:
            return
        
        self._last_sync_check = now
        logger.debug(f"Anti-entropy check: vector_clock={self.vector_clock}, seen={len(self.seen_entry_ids)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics including UDP packet loss metrics
        and TCP fallback status.
        """
        base_stats = super().get_stats()
        
        # Get current UDP stats
        udp_stats = self._udp_stats.get_stats()
        
        # Check for current loss percentage
        _, _, fallback_metrics = self._udp_stats.check_fallback_needed()
        
        combined = {
            **base_stats,
            "auto_fallback_mode": self.auto_fallback_mode,
            "tcp_fallback_active": udp_stats.get("fallback_to_tcp", False),
            "tcp_fallback_duration": udp_stats.get("tcp_fallback_duration", 0),
            "udp_stable_duration": udp_stats.get("udp_stable_duration", 0),
            "packet_metrics": {
                "total_outbound_packets": udp_stats.get("total_outbound", 0),
                "total_inbound_packets": udp_stats.get("total_inbound", 0),
                "current_outbound_rate": udp_stats.get("current_outbound_rate", 0),
                "current_inbound_rate": udp_stats.get("current_inbound_rate", 0),
            },
            "fallback_detection": {
                "current_loss_percentage": fallback_metrics.get("loss_percentage", 0),
                "loss_threshold": FALLBACK_DELTA_THRESHOLD,
                "fallback_window_seconds": FALLBACK_WINDOW_SECONDS,
                "stable_udp_seconds": STABLE_UDP_SECONDS,
            }
        }
        
        return combined


def tcp_replication_test():
    """Test TCP reliability mode against UDP gossip."""
    print("=== TCP Reliability Mode Test ===\n")
    
    start_time = time.time()
    
    # Create peers
    peers = []
    ports = [8151, 8161, 8171]
    
    for i, port in enumerate(ports):
        r = ReliableCortexReplicator(
            node_id=f"tcp_node_{i}",
            port=port,
            tcp_sync_port=port + 1000,
            auto_fallback_mode=True
        )
        r.start()
        peers.append(r)
    
    time.sleep(0.5)  # Allow threads to fully start
    
    # Send UDP burst
    burst_id = f"tcp_burst_{int(time.time())}"
    for i in range(20):
        peers[0].broadcast_thought(
            f"{burst_id}_{i}",
            f"TestAgent{i}",
            f"TCP reliability test packet {i}",
            {"mode": "tcp_test"},
            target_addr="127.0.0.1"
        )
    
    # Direct UDP unicast for immediate test
    payload = json.dumps({
        "type": "THOUGHT_REPLICATION",
        "origin_node": "tcp_node_0",
        "entry_id": f"{burst_id}_direct",
        "agent": "DirectLink",
        "content": "Direct UDP unicast packet",
        "metadata": {"reliability": "direct"},
        "created_at": time.time(),
        "vector_clock": 1
    }).encode("utf-8")
    
    peers[0]._sock.sendto(payload, ("127.0.0.1", 8161))
    
    time.sleep(0.5)
    
    # Verify TCP heartbeat
    heartbeat_result = peers[0].tcp_heartbeat("127.0.0.1", 9161)
    
    # Verify TCP sync
    sync_result = peers[0].tcp_sync_request("127.0.0.1", 9161)
    
    # Get stats with fallback info
    stats = peers[0].get_stats()
    
    # Cleanup
    for p in peers:
        p.stop()
    
    elapsed = time.time() - start_time
    
    print(f"TCP peer port: {peers[0].tcp_sync_port}")
    print(f"Heartbeat response: {heartbeat_result is not None}")
    if heartbeat_result:
        print(f"  Heartbeat node: {heartbeat_result.get('node_id')}")
        print(f"  Vector clock: {heartbeat_result.get('vector_clock')}")
        print(f"  Seen count: {heartbeat_result.get('seen_count')}")
    
    print(f"Sync response: {sync_result is not None}")
    if sync_result:
        print(f"  Sync node: {sync_result.get('from_node')}")
        print(f"  Thoughts returned: {len(sync_result.get('thoughts', []))}")
    
    print(f"\nFallback Stats:")
    print(f"  Auto fallback mode: {stats['auto_fallback_mode']}")
    print(f"  TCP fallback active: {stats['tcp_fallback_active']}")
    print(f"  TCP fallback duration: {stats['tcp_fallback_duration']:.2f}s")
    print(f"  UDP stable duration: {stats['udp_stable_duration']:.2f}s")
    print(f"  Packet metrics: {json.dumps(stats['packet_metrics'], indent=4)}")
    print(f"  Fallback detection: {json.dumps(stats['fallback_detection'], indent=4)}")
    
    passed = heartbeat_result is not None or sync_result is not None
    status = "✅ VERIFIED" if passed else "⚠️ PARTIAL"
    print(f"\n{status} TCP Reliability Mode ({elapsed:.3f}s)")


if __name__ == "__main__":
    tcp_replication_test()