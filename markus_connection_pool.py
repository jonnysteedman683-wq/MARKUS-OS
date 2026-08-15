#!/usr/bin/env python3
"""
MARKUS OS TCP Connection Pool for Mesh Reliability Layer
Provides pooled TCP connections with LRU eviction, auto-reconnect, and health checks.
Async-ready for high-frequency sync operations.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("Markus.ConnectionPool")

# Default pool settings
DEFAULT_POOL_SIZE = 10
DEFAULT_MAX_CONNECTIONS = 50
DEFAULT_HEALTH_CHECK_INTERVAL = 30.0  # seconds
DEFAULT_CONNECT_TIMEOUT = 5.0  # seconds
DEFAULT_SOCKET_TIMEOUT = 10.0  # seconds


class ConnectionState(Enum):
    """Connection lifecycle state."""
    IDLE = "idle"
    ACTIVE = "active"
    CONNECTING = "connecting"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass
class PooledConnection:
    """A pooled TCP connection with metadata."""
    host: str
    port: int
    sock: Optional[socket.socket] = None
    state: ConnectionState = ConnectionState.CLOSED
    last_used: float = 0.0
    last_health_check: float = 0.0
    created_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    failure_count: int = 0
    max_retries: int = 3
    reconnect_delay: float = 1.0

    @property
    def is_healthy(self) -> bool:
        return self.state == ConnectionState.ACTIVE and self.sock is not None

    @property
    def is_expired(self) -> bool:
        """Check if connection has been idle too long."""
        idle_time = time.time() - self.last_used
        return idle_time > 60.0  # Expire after 60s idle

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "state": self.state.value,
            "age_seconds": time.time() - self.created_at,
            "idle_seconds": time.time() - self.last_used,
            "failure_count": self.failure_count,
        }


class ConnectionPoolConfig:
    """Configuration for the connection pool."""

    def __init__(
        self,
        pool_size: int = DEFAULT_POOL_SIZE,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        health_check_interval: float = DEFAULT_HEALTH_CHECK_INTERVAL,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        socket_timeout: float = DEFAULT_SOCKET_TIMEOUT,
        max_retries: int = 3,
        reconnect_delay: float = 1.0,
        idle_timeout: float = 60.0,
    ):
        self.pool_size = pool_size
        self.max_connections = max_connections
        self.health_check_interval = health_check_interval
        self.connect_timeout = connect_timeout
        self.socket_timeout = socket_timeout
        self.max_retries = max_retries
        self.reconnect_delay = reconnect_delay
        self.idle_timeout = idle_timeout


class MarkusTCPConnectionPool:
    """
    LRU-evicting TCP connection pool for MARKUS TCP mesh reliability.
    Async-ready with auto-reconnect and periodic health checks.
    
    Features:
    - LRU eviction when pool exceeds max_connections
    - Automatic reconnection on failure
    - Background health checks every 30 seconds (configurable)
    - Connection reuse for improved performance
    - Async context manager support
    
    Usage:
        pool = MarkusTCPConnectionPool(host="192.168.1.100", port=8131)
        
        async with pool.acquire() as conn:
            conn.sendall(data)
            response = conn.recv(4096)
        
        # Health check
        if await pool.ping():
            print("Connection pool healthy")
    """

    def __init__(
        self,
        host: str,
        port: int,
        pool_size: int = DEFAULT_POOL_SIZE,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        health_check_interval: float = DEFAULT_HEALTH_CHECK_INTERVAL,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        socket_timeout: float = DEFAULT_SOCKET_TIMEOUT,
        max_retries: int = 3,
        reconnect_delay: float = 1.0,
        idle_timeout: float = 60.0,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.host = host
        self.port = port
        self.loop = loop or asyncio.get_event_loop()
        self.config = ConnectionPoolConfig(
            pool_size=pool_size,
            max_connections=max_connections,
            health_check_interval=health_check_interval,
            connect_timeout=connect_timeout,
            socket_timeout=socket_timeout,
            max_retries=max_retries,
            reconnect_delay=reconnect_delay,
            idle_timeout=idle_timeout,
        )

        # LRU-ordered pool: host:port -> PooledConnection
        self._pool: OrderedDict[str, PooledConnection] = OrderedDict()
        
        # Threading lock for sync access, asyncio lock for async methods
        self._sync_lock = threading.RLock()
        self._async_lock: Optional[asyncio.Lock] = None
        
        # Background health check task
        self._health_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Statistics
        self._stats = {
            "connections_created": 0,
            "connections_reused": 0,
            "connect_failures": 0,
            "health_checks_passed": 0,
            "health_checks_failed": 0,
            "connections_reaped": 0,
        }

    def _get_async_lock(self) -> asyncio.Lock:
        """Get or create the async lock (must be called in async context)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def _pool_key(self, host: str, port: int) -> str:
        return f"{host}:{port}"

    @staticmethod
    def _socket_is_alive(sock: socket.socket) -> bool:
        """Probe a socket without injecting bytes into the peer protocol."""
        sock.setblocking(False)
        try:
            data = sock.recv(1, socket.MSG_PEEK)
        except BlockingIOError:
            return True
        except (ConnectionResetError, BrokenPipeError, OSError):
            return False
        finally:
            try:
                sock.setblocking(True)
            except OSError:
                pass
        return data != b""

    async def _create_connection(self) -> PooledConnection:
        """Create a new TCP connection."""
        key = self._pool_key(self.host, self.port)
        
        async with self._get_async_lock():
            # Check if we already have a connection
            if key in self._pool:
                conn = self._pool[key]
                if conn.is_healthy:
                    # Move to end (most recently used)
                    self._pool.move_to_end(key)
                    conn.state = ConnectionState.ACTIVE
                    conn.last_used = time.time()
                    self._stats["connections_reused"] += 1
                    return conn

            # Enforce max connections limit
            if len(self._pool) >= self.config.max_connections:
                # Evict LRU connection
                oldest_key, oldest_conn = self._pool.popitem(last=False)
                try:
                    if oldest_conn.sock:
                        oldest_conn.sock.close()
                except Exception:
                    pass
                self._stats["connections_reaped"] += 1
                logger.debug(f"Evicted LRU connection {oldest_key}")

            # Create new connection
            conn = PooledConnection(
                host=self.host,
                port=self.port,
                max_retries=self.config.max_retries,
                reconnect_delay=self.config.reconnect_delay,
            )
            
            success = await self._connect_socket(conn)
            if success:
                self._pool[key] = conn
                self._stats["connections_created"] += 1
                logger.debug(f"Created new connection to {self.host}:{self.port}")
                return conn
            else:
                conn.state = ConnectionState.FAILED
                self._stats["connect_failures"] += 1
                raise ConnectionError(f"Failed to connect to {self.host}:{self.port}")

    async def _connect_socket(self, conn: PooledConnection) -> bool:
        """Establish the underlying socket connection."""
        retry_count = 0
        while retry_count < conn.max_retries:
            sock: Optional[socket.socket] = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(self.config.connect_timeout)

                # Use asyncio's event loop for non-blocking connect
                await self.loop.sock_connect(sock, (conn.host, conn.port))
                sock.settimeout(self.config.socket_timeout)

                conn.sock = sock
                conn.state = ConnectionState.ACTIVE
                conn.last_used = time.time()
                conn.last_health_check = time.time()
                return True

            except Exception as e:
                retry_count += 1
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                logger.debug(f"Connect attempt {retry_count} failed to {conn.host}:{conn.port}: {e}")
                if retry_count < conn.max_retries:
                    await asyncio.sleep(conn.reconnect_delay * retry_count)
                else:
                    return False
        return False

    def _reconnect_socket(self, conn: PooledConnection) -> bool:
        """Synchronous reconnection attempt for health checks."""
        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(self.config.connect_timeout)
            sock.connect((conn.host, conn.port))
            sock.settimeout(self.config.socket_timeout)

            # Close the old sock if it exists
            if conn.sock:
                try:
                    conn.sock.close()
                except OSError:
                    pass

            conn.sock = sock
            conn.state = ConnectionState.ACTIVE
            conn.last_used = time.time()
            conn.last_health_check = time.time()
            conn.failure_count = 0
            return True

        except Exception as e:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
            conn.failure_count += 1
            logger.debug(f"Reconnect failed for {conn.host}:{conn.port}: {e}")
            return False

    async def start(self) -> None:
        """Start the connection pool and background health check task."""
        if self._shutdown_event.is_set():
            self._shutdown_event.clear()
        
        # Create async lock if needed
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"Started TCP connection pool for {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the connection pool and cleanup all connections."""
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel health check task
        if self._health_task:
            self._health_task.cancel()
            try:
                # Use wait_for with timeout to prevent hanging
                await asyncio.wait_for(self._health_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._health_task = None

        # Close all pooled connections
        with self._sync_lock:
            for key, conn in list(self._pool.items()):
                try:
                    if conn.sock:
                        conn.sock.close()
                except Exception:
                    pass
            self._pool.clear()
        
        logger.info(f"Stopped TCP connection pool for {self.host}:{self.port}")

    async def _health_check_loop(self) -> None:
        """Background task to periodically check connection health."""
        check_interval = self.config.health_check_interval
        while not self._shutdown_event.is_set():
            try:
                # Wait directly on the event so fractional intervals work and
                # shutdown does not need to wait for a one-second polling tick.
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=max(0.1, float(check_interval)),
                    )
                except asyncio.TimeoutError:
                    pass

                if self._shutdown_event.is_set():
                    return

                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def _perform_health_checks(self) -> None:
        """Check and reconnect stale or failed connections."""
        now = time.time()
        keys_to_remove = []
        
        async with self._get_async_lock():
            for key, conn in list(self._pool.items()):
                # Check if connection is expired
                if conn.is_expired:
                    try:
                        if conn.sock:
                            conn.sock.close()
                    except Exception:
                        pass
                    keys_to_remove.append(key)
                    conn.state = ConnectionState.CLOSED
                    self._stats["connections_reaped"] += 1
                    logger.debug(f"Expired idle connection {key}")
                    continue

                # Check health if enough time has passed
                if now - conn.last_health_check >= self.config.health_check_interval:
                    if conn.is_healthy:
                        # Try to check if socket is still connected
                        try:
                            if conn.sock and not self._socket_is_alive(conn.sock):
                                # Socket disconnected, try to reconnect.
                                if self._reconnect_socket(conn):
                                    self._stats["health_checks_passed"] += 1
                                else:
                                    self._stats["health_checks_failed"] += 1
                                conn.last_health_check = now
                                continue

                            self._stats["health_checks_passed"] += 1
                            conn.last_health_check = now
                        except Exception as e:
                            logger.debug(f"Health check detected stale connection {key}: {e}")
                            conn.state = ConnectionState.FAILED
                            conn.failure_count += 1
                            self._stats["health_checks_failed"] += 1
                    else:
                        self._stats["health_checks_failed"] += 1

        # Remove expired connections
        with self._sync_lock:
            for key in keys_to_remove:
                if key in self._pool:
                    del self._pool[key]

    async def acquire(self, timeout: Optional[float] = None) -> 'PooledConnectionHandle':
        """
        Acquire a connection from the pool.
        Returns a context manager that handles release automatically.
        """
        try:
            conn = await asyncio.wait_for(self._create_connection(), timeout=timeout)
            return PooledConnectionHandle(conn, self)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Failed to acquire connection within {timeout}s")

    def _release_connection(self, conn: PooledConnection) -> None:
        """Return a connection to the pool."""
        with self._sync_lock:
            key = self._pool_key(conn.host, conn.port)
            if key in self._pool:
                self._pool.move_to_end(key)  # Mark as recently used
                conn.last_used = time.time()
                logger.debug(f"Released connection {key} back to pool")
            else:
                logger.debug(f"Connection {key} not in pool, discarding")

    async def ping(self) -> bool:
        """
        Ping the remote endpoint to verify connectivity.
        Returns True if healthy, False otherwise.
        """
        try:
            key = self._pool_key(self.host, self.port)
            
            async with self._get_async_lock():
                if key in self._pool:
                    conn = self._pool[key]
                    if conn.sock:
                        try:
                            if self._socket_is_alive(conn.sock):
                                self._stats["health_checks_passed"] += 1
                                return True

                            # Socket disconnected, try to reconnect without
                            # sending a protocol-invalid heartbeat byte.
                            if self._reconnect_socket(conn):
                                self._stats["health_checks_passed"] += 1
                                return True
                            self._stats["health_checks_failed"] += 1
                            return False
                        except Exception as e:
                            logger.debug(f"Ping failed on existing connection: {e}")
                            conn.state = ConnectionState.FAILED
            
            # No connection exists, try to create one
            conn = await self._create_connection()
            self._stats["health_checks_passed"] += 1
            return True
            
        except Exception as e:
            logger.debug(f"Ping error: {e}")
            self._stats["health_checks_failed"] += 1
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics (thread-safe sync version)."""
        with self._sync_lock:
            return {
                "host": self.host,
                "port": self.port,
                "pool_size": len(self._pool),
                "config": {
                    "pool_size": self.config.pool_size,
                    "max_connections": self.config.max_connections,
                    "health_check_interval": self.config.health_check_interval,
                },
                "statistics": dict(self._stats),
                "connections": [
                    (key, conn.to_dict()) for key, conn in list(self._pool.items())
                ],
            }

    async def get_stats_async(self) -> Dict[str, Any]:
        """Get pool statistics (async version with proper locking)."""
        async with self._get_async_lock():
            return {
                "host": self.host,
                "port": self.port,
                "pool_size": len(self._pool),
                "config": {
                    "pool_size": self.config.pool_size,
                    "max_connections": self.config.max_connections,
                    "health_check_interval": self.config.health_check_interval,
                },
                "statistics": dict(self._stats),
                "connections": [
                    (key, conn.to_dict()) for key, conn in list(self._pool.items())
                ],
            }

    def clear_stats(self) -> None:
        """Reset statistics counters."""
        with self._sync_lock:
            for key in self._stats:
                self._stats[key] = 0


class PooledConnectionHandle:
    """Context manager for acquiring/releasing pooled connections."""

    def __init__(self, conn: PooledConnection, pool: MarkusTCPConnectionPool):
        self._conn = conn
        self._pool = pool
        self._released = False

    @property
    def sock(self) -> socket.socket:
        """Get the underlying socket."""
        return self._conn.sock

    async def __aenter__(self) -> 'PooledConnectionHandle':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()

    def __enter__(self) -> 'PooledConnectionHandle':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Sync context manager - can't await, so we schedule release
        try:
            asyncio.create_task(self.release())
        except RuntimeError:
            pass  # Event loop closed

    @property
    def connection(self) -> PooledConnection:
        return self._conn

    def sendall(self, data: bytes) -> None:
        """Send data over the connection."""
        self._conn.sock.sendall(data)

    def send(self, data: bytes) -> int:
        """Send data and return bytes sent."""
        return self._conn.sock.send(data)

    def recv(self, bufsize: int) -> bytes:
        """Receive data from the connection."""
        return self._conn.sock.recv(bufsize)

    async def release(self) -> None:
        """Release the connection back to the pool."""
        if not self._released:
            self._pool._release_connection(self._conn)
            self._released = True


class _HealthCheckProtocol(asyncio.Protocol):
    """Simple protocol for health checking connections."""
    
    def __init__(self, conn: PooledConnection):
        self.conn = conn
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        transport.close()

    def connection_lost(self, exc):
        pass

    def error_received(self, exc):
        pass


# Async context manager for pool operations
async def get_connection(
    pool: MarkusTCPConnectionPool,
    timeout: Optional[float] = None
) -> PooledConnectionHandle:
    """Convenience function to acquire a pooled connection."""
    return await pool.acquire(timeout=timeout)


# Factory function for creating pools
def create_connection_pool(
    host: str,
    port: int,
    config: Optional[ConnectionPoolConfig] = None,
) -> MarkusTCPConnectionPool:
    """Factory function to create a TCP connection pool."""
    if config is None:
        config = ConnectionPoolConfig()
    
    return MarkusTCPConnectionPool(
        host=host,
        port=port,
        pool_size=config.pool_size,
        max_connections=config.max_connections,
        health_check_interval=config.health_check_interval,
        connect_timeout=config.connect_timeout,
        socket_timeout=config.socket_timeout,
        max_retries=config.max_retries,
        reconnect_delay=config.reconnect_delay,
        idle_timeout=config.idle_timeout,
    )


if __name__ == "__main__":
    async def _demo_pool():
        print("=== MARKUS TCP Connection Pool Demo ===\n")
        
        # Create a pool (using localhost for demo)
        pool = MarkusTCPConnectionPool(
            host="127.0.0.1",
            port=8130,  # Default port
            pool_size=3,
            health_check_interval=10.0,
        )
        
        await pool.start()
        
        # Test ping (will fail since no server, but demonstrates API)
        ping_result = await pool.ping()
        print(f"Ping result (no server): {ping_result}")
        print(f"Stats: {pool.get_stats()}")
        
        await pool.stop()
        print("\n=== Pool Demo Complete ===")

    asyncio.run(_demo_pool())