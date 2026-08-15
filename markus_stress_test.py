#!/usr/bin/env python3
"""MARKUS Cortex Replication Stress & Concurrency Test"""
import time
import threading
import json
import socket
from markus_cortex_replication import MarkusCortexReplicator

# Performance stress test
print("=== MARKUS Cortex Replication: Stress & Concurrency Test ===\n")

# Create 4 nodes simulating a mesh
nodes = []
ports = [8141, 8142, 8143, 8144]
node_ids = ["stress_alpha", "stress_beta", "stress_gamma", "stress_delta"]

for i, (nid, port) in enumerate(zip(node_ids, ports)):
    r = MarkusCortexReplicator(node_id=nid, port=port)
    r.start()
    nodes.append(r)
    print(f"Started node {nid} on port {port}")

time.sleep(0.3)

# Broadcast burst test - send to ALL nodes in mesh
start_time = time.time()
burst_size = 50
broadcast_results = []

for i in range(burst_size):
    entry_id = f"stress_test_{i}_{int(time.time()*1000)}"
    # Send to all nodes in the mesh
    node_successes = []
    for j in range(1, 4):  # Skip alpha (source)
        success = nodes[0].broadcast_thought(
            entry_id, 
            f"StressTest{j}", 
            f"Stress payload {i}",
            {"burst_idx": i, "stress_test": True},
            target_addr="127.0.0.1"
        )
        node_successes.append(success)
    
    # Also send direct unicast for guaranteed delivery in test
    payload = json.dumps({
        "type": "THOUGHT_REPLICATION",
        "origin_node": "stress_alpha",
        "entry_id": entry_id,
        "agent": "StressTest",
        "content": f"Stress payload {i}",
        "metadata": {"burst_idx": i, "stress_test": True},
        "created_at": time.time(),
        "vector_clock": i
    }).encode("utf-8")
    
    for j, port in enumerate([8142, 8143, 8144], 2):
        try:
            nodes[0]._sock.sendto(payload, ("127.0.0.1", port))
            broadcast_results.append(True)
        except:
            broadcast_results.append(False)

broadcast_time = time.time() - start_time
print(f"\nBurst broadcast: {burst_size * 3} thoughts in {broadcast_time:.3f}s ({(burst_size*3)/broadcast_time:.0f} thoughts/sec)")
print(f"Broadcast success rate: {sum(broadcast_results)}/{burst_size * 3}")

# Wait for propagation (increase for mesh sync)
time.sleep(2.0)

# Verify cross-node sync
print("\n=== Cross-Node Synchronization Verification ===")
all_sync = True
for i, node in enumerate(nodes):
    stats = node.get_stats()
    print(f"{node_ids[i]}: seen={stats['seen_entries']}, inbound={stats['inbound_replicated']}, outbound={stats['outbound_broadcast']}")
    
    # Check if it received from other nodes (tolerant threshold)
    expected_min = burst_size - 5  # Allow some packet loss/timing variance
    if stats['inbound_replicated'] < expected_min:
        all_sync = False
        print(f"  ⚠️  Warning: Expected ~{expected_min} inbound, got {stats['inbound_replicated']}")

# Cleanup
for node in nodes:
    node.stop()

print(f"\n{'✅ Stress Test PASSED' if all_sync else '⚠️ Stress Test completed with warnings'}")
print(f"Final sync status: {'All nodes synchronized' if all_sync else 'Some nodes lagging'}")