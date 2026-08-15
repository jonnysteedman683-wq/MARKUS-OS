#!/usr/bin/env python3
"""MARKUS OS Adaptive UDP→TCP Fallback Detector

Monitors UDP mesh reliability and auto-switches to TCP when packet loss
exceeds threshold. Provides metrics for intelligent transport selection.
"""
from __future__ import annotations
import time
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger("Markus.Fallback")

FALLBACK_THRESHOLD = 0.10  # 10% packet loss triggers TCP
MONITOR_WINDOW = 5.0       # seconds to evaluate
REVERT_WINDOW = 10.0       # seconds of stability to revert to UDP
HEALTH_CHECK_INTERVAL = 1.0


@dataclass
class FallbackMetrics:
    """Metrics for transport fallback decisions."""
    inbound_count: int = 0
    outbound_count: int = 0
    expected_inbound: int = 0
    packet_loss_ratio: float = 0.0
    current_mode: str = "UDP"  # or "TCP_FALLBACK"
    active_since: float = 0.0
    fallback_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "inbound_count": self.inbound_count,
            "outbound_count": self.outbound_count,
            "expected_inbound": self.expected_inbound,
            "packet_loss_ratio": round(self.packet_loss_ratio, 4),
            "current_mode": self.current_mode,
            "active_since": self.active_since,
            "fallback_count": self.fallback_count
        }


class AdaptiveFallbackDetector:
    """
    Detects when UDP mesh reliability degrades and auto-switches to TCP.
    """
    
    def __init__(
        self,
        threshold: float = FALLBACK_THRESHOLD,
        monitor_window: float = MONITOR_WINDOW,
        revert_window: float = REVERT_WINDOW,
        health_check_interval: float = HEALTH_CHECK_INTERVAL
    ):
        self.threshold = threshold
        self.monitor_window = monitor_window
        self.revert_window = revert_window
        self.health_check_interval = health_check_interval
        
        self._inbound_history: deque = deque(maxlen=100)
        self._outbound_history: deque = deque(maxlen=100)
        self._expected_history: deque = deque(maxlen=100)
        
        self._metrics = FallbackMetrics()
        self._lock = threading.Lock()
        self._last_check = 0.0
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
    @property
    def metrics(self) -> FallbackMetrics:
        with self._lock:
            return self._metrics
    
    @property
    def should_fallback(self) -> bool:
        with self._lock:
            if self._metrics.current_mode == "TCP_FALLBACK":
                return False
            loss = self._metrics.packet_loss_ratio
            duration = time.time() - self._metrics.active_since
            return loss > self.threshold and duration < self.monitor_window
    
    @property
    def should_revert(self) -> bool:
        with self._lock:
            if self._metrics.current_mode == "UDP":
                return False
            now = time.time()
            tcp_duration = now - self._metrics.active_since
            return tcp_duration > self.revert_window
    
    def record_outbound(self, count: int = 1) -> None:
        """Record outbound broadcast attempts."""
        with self._lock:
            self._metrics.outbound_count += count
        now = time.time()
        self._outbound_history.append((now, count))
    
    def record_inbound(self, count: int = 1) -> None:
        """Record inbound replications."""
        with self._lock:
            self._metrics.inbound_count += count
        now = time.time()
        self._inbound_history.append((now, count))
    
    def update_expected_inbound(self, expected: int) -> None:
        """Update expected inbound count for loss calculation."""
        with self._lock:
            self._expected_history.append((time.time(), expected))
    
    def check_udp_health(self) -> bool:
        """Check UDP health and update metrics. Returns True if healthy."""
        now = time.time()
        
        while self._inbound_history and now - self._inbound_history[0][0] > self.monitor_window:
            self._inbound_history.popleft()
        while self._outbound_history and now - self._outbound_history[0][0] > self.monitor_window:
            self._outbound_history.popleft()
        
        with self._lock:
            total_inbound = sum(c for _, c in self._inbound_history)
            total_outbound = sum(c for _, c in self._outbound_history)
            
            self._metrics.inbound_count = total_inbound
            self._metrics.outbound_count = total_outbound
            
            if total_outbound > 0:
                ratio = total_inbound / total_outbound
                if ratio < 1.0:
                    self._metrics.packet_loss_ratio = 1.0 - ratio
                elif ratio > 1.5:
                    self._metrics.packet_loss_ratio = 0.5
                else:
                    self._metrics.packet_loss_ratio = 0.0
            else:
                self._metrics.packet_loss_ratio = 0.0
            
            return self._metrics.packet_loss_ratio <= self.threshold
    
    def evaluate_fallback(self, peers_count: int = 3) -> str:
        """Evaluate and return recommended transport mode."""
        healthy = self.check_udp_health()
        
        with self._lock:
            if self._metrics.current_mode == "UDP" and not healthy:
                self._metrics.current_mode = "TCP_FALLBACK"
                self._metrics.active_since = time.time()
                self._metrics.fallback_count += 1
                logger.warning(f"UDP fallback: loss_ratio={self._metrics.packet_loss_ratio:.2%} > "
                             f"threshold={self.threshold:.0%}")
                return "TCP_FALLBACK"
            
            elif self._metrics.current_mode == "TCP_FALLBACK" and self.should_revert:
                self._metrics.current_mode = "UDP"
                logger.info(f"UDP revert: stable after TCP fallback")
                return "UDP"
            
            return self._metrics.current_mode
    
    def reset_counters(self) -> None:
        """Reset observation counters."""
        with self._lock:
            self._inbound_history.clear()
            self._outbound_history.clear()
            self._expected_history.clear()
            self._metrics.inbound_count = 0
            self._metrics.outbound_count = 0
    
    def start_monitoring(self, interval: float = HEALTH_CHECK_INTERVAL) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
    
    def _monitor_loop(self, interval: float) -> None:
        while self._running:
            try:
                self.check_udp_health()
                time.sleep(interval)
            except Exception as e:
                logger.debug(f"Monitor loop error: {e}")
                time.sleep(interval)


def integrate_with_replicator(replicator_instance):
    """Monkey-patch a MarkusCortexReplicator to add adaptive fallback."""
    original_broadcast = replicator_instance.broadcast_thought
    detector = AdaptiveFallbackDetector()
    
    def adaptive_broadcast(entry_id, agent, content, metadata=None, target_addr="255.255.255.255"):
        detector.record_outbound()
        mode = detector.evaluate_fallback()
        
        if mode == "TCP_FALLBACK":
            logger.debug(f"TCP fallback for {entry_id}")
        
        return original_broadcast(entry_id, agent, content, metadata, target_addr)
    
    replicator_instance.broadcast_thought = adaptive_broadcast
    replicator_instance.fallback_detector = detector
    
    return detector


# Test
def test_fallback_detector():
    import json as json_module
    print("=== Adaptive Fallback Detector Test ===\n")
    
    # Test 1: Healthy UDP (low loss)
    detector = AdaptiveFallbackDetector(threshold=0.10, monitor_window=5.0)
    
    # Simulate 3 peers receiving most broadcasts
    for i in range(100):
        detector.record_outbound()
    for i in range(310):  # 3.1 inbound per outbound = healthy
        detector.record_inbound()
    
    mode = detector.evaluate_fallback(peers_count=3)
    print(f"Test 1 - Healthy UDP:")
    print(f"  Mode: {mode}")
    print(f"  Loss ratio: {detector.metrics.packet_loss_ratio:.2%}")
    print(f"  Result: {'✅ UDP healthy' if mode == 'UDP' else '⚠️ Unexpected fallback'}")
    
    # Test 2: High packet loss
    detector2 = AdaptiveFallbackDetector(threshold=0.10, monitor_window=5.0)
    for i in range(100):
        detector2.record_outbound()
    for i in range(40):  # Only 0.4 inbound per outbound = 60% loss
        detector2.record_inbound()
    
    mode2 = detector2.evaluate_fallback(peers_count=3)
    print(f"\nTest 2 - High UDP loss:")
    print(f"  Mode: {mode2}")
    print(f"  Loss ratio: {detector2.metrics.packet_loss_ratio:.2%}")
    print(f"  Result: {'✅ Fallback triggered' if mode2 == 'TCP_FALLBACK' else '⚠️ Should have fallen back'}")
    
    passed = (mode == 'UDP' and mode2 == 'TCP_FALLBACK')
    print(f"\n{'✅ Fallback Detector Test: PASSED' if passed else '⚠️ Test results mixed'}")


if __name__ == "__main__":
    test_fallback_detector()