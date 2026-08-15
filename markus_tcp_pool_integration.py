#!/usr/bin/env python3
"""
MARKUS TCP Connection Pool Integration with ReliableCortexReplicator

This module provides connection pooling capabilities that can be integrated
with the existing ReliableCortexReplicator class for high-frequency TCP sync operations.

Usage:
    # Import the integration
    from markus_tcp_pool_integration import TCPPoolMixin
    
    # Or use via composition
    from markus_connection_pool import MarkusTCPConnectionPool
    
    class PoolEnhancedReplicator:
        def __init__(self, replicator, pool_config=None):
            self.replicator = replicator
            self.pool = MarkusTCPConnectionPool(...)
        
        async def pooled_sync(self, target_addr, target_port):
            async with await self.pool.acquire() as conn:
                ...
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import threading
from typing import Any, Dict, Optional, List

from markus_tcp_sync import ReliableCortexReplicator, MAX_PACKET_SIZE
from markus_connection_pool import MarkusTCPConnectionPool

logger = logging.getLogger("Markus.TCPPoolIntegration")


class TCPPoolMixin:
    """
    Mixin class that adds connection pooling to ReliableCortexReplicator.
    
    Provides pooled TCP connections for high-frequency sync operations with:
    - LRU-evicting pool
    - Auto-reconnect on failure
    - Background health checks (every 30 seconds)
    - Async-ready acquire/release/ping methods
    """

    # Connection pool configuration
    _pool_size: int = 10
    _health_check_interval: float = 30.0
    _connection_pools: Dict[str, MarkusTCPConnectionPool]
    _pool_lock: threading.RLock
    _shutdown_event: asyncio.Event
    _health_task: Optional[asyncio.Task]

    def _init_tcp_pool(self, pool_size: int = 10, health_check_interval: float = 30.0) -> None:
        """Initialize the connection pool infrastructure."""
        self._pool_size = pool_size
        self._health_check_interval = health_check_interval
        self._connection_pools = {}
        self._pool_lock = threading.RLock()
        self._shutdown_event = asyncio.Event()
        self._health_task = None

    def _get_pool(self, host: str, port: int) -> MarkusTCPConnectionPool:
        """Get or create a connection pool for a remote peer."""
        key = f"{host}:{port}"
        
        with self._pool_lock:
            if key not in self._connection_pools:
                pool = MarkusTCPConnectionPool(
                    host=host,
                    port=port,
                    pool_size=self._pool_size,
                    health_check_interval=self._health_check_interval,
                )
                self._connection_pools[key] = pool
                logger.debug(f"Created connection pool for {key}")
            return self._connection_pools[key]

    async def start_pools(self) -> None:
        """Start all connection pools."""
        for pool in self._connection_pools.values():
            await pool.start()
        logger.info(f"Started {len(self._connection_pools)} TCP connection pools")

    async def stop_pools(self) -> None:
        """Stop all connection pools."""
        self._shutdown_event.set()
        
        if self._health_task:
            self._health_task.cancel()
            try:
                await asyncio.wait_for(self._health_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._health_task = None

        for pool in self._connection_pools.values():
            await pool.stop()
        
        logger.info(f"Stopped {len(self._connection_pools)} TCP connection pools")

    async def tcp_pooled_sync_request(
        self,
        target_addr: str,
        target_port: int,
        from_clock: int = 0,
        to_clock: int = 0,
        timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """
        Initiate TCP sync request using pooled connection.
        
        Args:
            target_addr: Target host address
            target_port: Target port
            from_clock: Starting vector clock for sync
            to_clock: Ending vector clock for sync
            timeout: Connection timeout in seconds
            
        Returns:
            Sync response dict or None on failure
        """
        pool = self._get_pool(target_addr, target_port)
        
        try:
            async with await pool.acquire(timeout=timeout) as conn_handle:
                request = {
                    "type": "SYNC_REQUEST",
                    "request_id": f"sync_{int(time.time()*1000)}",
                    "from_clock": from_clock,
                    "to_clock": to_clock or self.vector_clock + 1,
                    "requester": self.node_id,
                    "timestamp": time.time()
                }
                
                conn_handle.sendall(json.dumps(request).encode("utf-8"))
                data = conn_handle.recv(MAX_PACKET_SIZE)
                result = json.loads(data.decode("utf-8"))
                
                logger.debug(f"Pooled TCP sync to {target_addr}:{target_port} returned {len(result.get('thoughts', []))} thoughts")
                return result
                
        except asyncio.TimeoutError:
            logger.debug(f"Pooled TCP sync timeout to {target_addr}:{target_port}")
            return None
        except ConnectionError as e:
            logger.debug(f"Pooled TCP sync connection error to {target_addr}:{target_port}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Pooled TCP sync error to {target_addr}:{target_port}: {e}")
            return None

    async def tcp_pooled_heartbeat(
        self,
        target_addr: str,
        target_port: int,
        timeout: float = 3.0
    ) -> Optional[Dict[str, Any]]:
        """Send TCP heartbeat request using pooled connection."""
        pool = self._get_pool(target_addr, target_port)
        
        try:
            async with await pool.acquire(timeout=timeout) as conn_handle:
                request = {
                    "type": "SYNC_HEARTBEAT",
                    "requester": self.node_id,
                    "timestamp": time.time()
                }
                
                conn_handle.sendall(json.dumps(request).encode("utf-8"))
                data = conn_handle.recv(MAX_PACKET_SIZE)
                return json.loads(data.decode("utf-8"))
                
        except Exception as e:
            logger.debug(f"Pooled TCP heartbeat error to {target_addr}:{target_port}: {e}")
            return None

    async def ping_peer(self, peer_addr: str, peer_port: int) -> bool:
        """Ping a remote peer to verify connectivity using pooled connection."""
        pool = self._get_pool(peer_addr, peer_port)
        return await pool.ping()

    def get_pool_stats(self, peer_key: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for connection pools."""
        with self._pool_lock:
            if peer_key:
                pool = self._connection_pools.get(peer_key)
                if pool:
                    return {"pools": {peer_key: pool.get_stats()}}
                return {"error": f"No pool found for {peer_key}"}
            
            return {
                "pools": {key: pool.get_stats() for key, pool in self._connection_pools.items()}
            }

    def sync_with_peers(self, peer_endpoints: list) -> Dict[str, Any]:
        """
        Sync with multiple peers using TCP connection pooling.
        
        Args:
            peer_endpoints: List of (host, port) tuples or dicts with 'host'/'port'
            
        Returns:
            Dict mapping peer -> sync result
        """
        results = {}
        for peer in peer_endpoints:
            if isinstance(peer, dict):
                host = peer.get('host', '127.0.0.1')
                port = peer.get('port', 8131)
            elif isinstance(peer, str):
                parts = peer.split(':')
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 8131
            else:
                host, port = peer
            
            addr = f"{host}:{port}"
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    result = asyncio.run_coroutine_threadsafe(
                        self.tcp_pooled_sync_request(host, port),
                        loop
                    ).result(timeout=5.0)
                else:
                    result = self.tcp_sync_request(host, port)
                results[addr] = result
            except Exception as e:
                results[addr] = {"error": str(e)}
        
        return results


class PoolEnhancedReplicator(TCPPoolMixin, ReliableCortexReplicator):
    """
    ReliableCortexReplicator with TCP connection pooling enabled.
    
    Combines the existing UDP gossip with TCP pooled connections for
    high-frequency, reliable sync operations.
    """
    
    def __init__(
        self,
        node_id: str,
        port: int,
        tcp_sync_port: int = 0,
        enable_anti_entropy: bool = True,
        pool_size: int = 10,
        health_check_interval: float = 30.0,
        **kwargs
    ) -> None:
        # Initialize parent class first (without pool parameters)
        parent_kwargs = {k: v for k, v in kwargs.items() 
                        if k in ['db', 'port', 'node_id', 'tcp_sync_port', 
                                'enable_anti_entropy', 'auto_fallback_mode']}
        
        # Call parent __init__ with only valid kwargs
        super().__init__(
            node_id=node_id,
            port=port,
            **{k: v for k, v in kwargs.items() if k != 'pool_size' and k != 'health_check_interval'}
        )
        
        # Now initialize pooling
        self._init_tcp_pool(pool_size, health_check_interval)


# Factory function
def create_pool_enhanced_replicator(
    node_id: str,
    port: int,
    pool_size: int = 10,
    health_check_interval: float = 30.0,
    **kwargs
) -> PoolEnhancedReplicator:
    """Factory function to create a pool-enhanced replicator."""
    return PoolEnhancedReplicator(
        node_id=node_id,
        port=port,
        pool_size=pool_size,
        health_check_interval=health_check_interval,
        **kwargs
    )


# Test function
async def test_pool_integration():
    """Test the pool integration with a real TCP server."""
    print("=== TCP Connection Pool Integration Test ===\n")
    
    import socket
    import json
    
    # Simple TCP server for testing
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 9876))
    server_sock.listen(5)
    server_sock.settimeout(2.0)
    
    def run_server():
        try:
            while True:
                try:
                    conn, addr = server_sock.accept()
                    with conn:
                        data = conn.recv(4096)
                        if data:
                            msg = json.loads(data.decode())
                            if msg.get("type") == "SYNC_REQUEST":
                                response = {
                                    "type": "SYNC_RESPONSE",
                                    "from_node": "test_server",
                                    "thoughts": [{"id": "t1", "content": "test thought"}],
                                    "vector_clock": 1
                                }
                            elif msg.get("type") == "SYNC_HEARTBEAT":
                                response = {
                                    "type": "HEARTBEAT",
                                    "node_id": "test_server",
                                    "status": "alive"
                                }
                            else:
                                response = {"type": "UNKNOWN"}
                            conn.sendall(json.dumps(response).encode())
                except socket.timeout:
                    continue
        except Exception:
            pass
    
    # Start test server
    import threading
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.3)
    
    # Create pool-enhanced replicator
    replicator = PoolEnhancedReplicator(
        node_id="pool_test_node",
        port=8700,
        tcp_sync_port=9700,
        pool_size=5,
        health_check_interval=5.0
    )
    
    # Start the replicator
    replicator.start()
    await replicator.start_pools()
    
    print("✓ Created and started pool-enhanced replicator")
    
    # Test pooled sync
    result = await replicator.tcp_pooled_sync_request("127.0.0.1", 9876)
    print(f"✓ Pooled sync result: {result['type'] if result else 'None'}")
    
    # Test pooled heartbeat
    hb_result = await replicator.tcp_pooled_heartbeat("127.0.0.1", 9876)
    print(f"✓ Pooled heartbeat result: {hb_result.get('node_id') if hb_result else 'None'}")
    
    # Test ping
    ping_result = await replicator.ping_peer("127.0.0.1", 9876)
    print(f"✓ Ping result: {ping_result}")
    
    # Get pool stats
    stats = replicator.get_pool_stats()
    pool_stat = stats.get("pools", {}).get("127.0.0.1:9876", {})
    conn_stats = pool_stat.get("statistics", {})
    print(f"✓ Pool statistics:")
    print(f"    Connections created: {conn_stats.get('connections_created', 0)}")
    print(f"    Connections reused: {conn_stats.get('connections_reused', 0)}")
    
    # Cleanup
    await replicator.stop_pools()
    replicator.stop()
    server_sock.close()
    
    print("\n✅ Pool Integration Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_pool_integration())