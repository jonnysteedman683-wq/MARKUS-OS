#!/usr/bin/env python3
"""Test harness for SUPRIME PeerTable integration into markus_mesh.py"""
import time
from markus_mesh import MarkusMeshLayer, Peer, PeerState, PeerTable

# Test 1: PeerTable unit test
pt = PeerTable(self_id="test-node")
assert len(pt) == 0
assert pt.merge("peer-a", "192.168.1.1:8128", 1) == True
assert pt.merge("peer-a", "192.168.1.1:8128", 1) == False  # same heartbeat
assert pt.merge("peer-a", "192.168.1.1:8128", 2) == True   # newer
assert len(pt) == 1
print("[TEST] PeerTable merge/dedup: PASS")

# Test 2: SUSPECT state transition
pt2 = PeerTable(self_id="node-x", suspect_after=0.5, dead_after=1.0)
pt2.merge("peer-b", "1.2.3.4:8128", 1)
assert pt2.get("peer-b").state == PeerState.ALIVE
pt2._peers["peer-b"].last_update -= 0.6
pt2.tick()
assert pt2.get("peer-b").state == PeerState.SUSPECT
print("[TEST] PeerTable SUSPECT transition: PASS")

# Test 3: DEAD eviction
t0 = time.monotonic()
pt3 = PeerTable(self_id="node-y", suspect_after=1.0, dead_after=2.0, clock=lambda: t0)
pt3.merge("peer-c", "1.2.3.4:8128", 1)
pt3._peers["peer-c"].last_update = t0 - 3.0
pt3.tick()
assert "peer-c" not in pt3
print("[TEST] PeerTable DEAD eviction: PASS")

# Test 4: MeshLayer self-merge guard
layer = MarkusMeshLayer(node_name="test-runner", api_endpoint="http://localhost:8128")
layer.start()
time.sleep(0.5)
assert layer.peer_table.merge(layer.node_id, layer.api_endpoint, 0) == False
print("[TEST] MeshLayer self-merge guard: PASS")

# Test 5: Digest/apply_digest convergence
pt5 = PeerTable(self_id="origin")
pt5.merge("p1", "addr1", 1)
pt5.merge("p2", "addr2", 1)
digest = pt5.digest()
pt6 = PeerTable(self_id="replica")
assert pt6.apply_digest(digest) == True
assert pt6.get("p1") is not None
assert pt6.get("p2") is not None
assert pt6.apply_digest(digest) == False  # re-apply, no change
print("[TEST] PeerTable digest/apply_digest convergence: PASS")

# Test 6: Backward-compat MeshNode
peers = layer.discover_peers()
assert isinstance(peers, list)
layer.stop()
print("[TEST] MeshLayer discover_peers backward-compat: PASS")

print()
print("=== ALL 6 TESTS PASSED ===")
print(f"PeerTable: {len(pt5)} peers, {len(pt6)} replicas converged")
print(f"MeshLayer: node_id={layer.node_id}, peer_table has {len(layer.peer_table)} entries")
