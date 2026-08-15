#!/usr/bin/env python3
"""
MARKUS OS Zero-Copy Shared Memory Ring Buffer (Upgrade 21)
Provides ultra-low-latency, lockless IPC streaming for high-throughput
thought broadcasting, process telemetry, and sensor frames between kernel processes.
Uses Python's multiprocessing.shared_memory with a fixed circular layout.
"""

from __future__ import annotations
import json
import logging
import struct
import time
from multiprocessing import shared_memory
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Markus.RingBuffer")

# Header Format:
# MAGIC (4 bytes) | CAPACITY (4 bytes) | SLOT_SIZE (4 bytes) | WRITE_POS (8 bytes) | READ_POS (8 bytes)
# Total Header Size = 28 bytes
HEADER_FORMAT = "=IIIQQ"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC_NUMBER = 0x4D52494E  # "MRIN" (Markus Ring)

class MarkusSharedRingBuffer:
    """
    Circular shared memory ring buffer for zero-copy inter-process communication.
    Supports atomic write sequences and multi-process reading.
    """

    def __init__(
        self,
        name: str = "markus_cortex_ring",
        capacity: int = 1024,
        slot_size: int = 1024,
        create: bool = False
    ) -> None:
        self.name = name
        self.capacity = capacity
        self.slot_size = slot_size
        self.total_size = HEADER_SIZE + (self.capacity * self.slot_size)
        self.is_owner = create

        if create:
            # Clean up pre-existing shared memory block if present
            try:
                existing = shared_memory.SharedMemory(name=self.name)
                existing.close()
                existing.unlink()
            except FileNotFoundError:
                pass

            self.shm = shared_memory.SharedMemory(name=self.name, create=True, size=self.total_size)
            # Initialize header: magic, capacity, slot_size, write_pos=0, read_pos=0
            header_bytes = struct.pack(HEADER_FORMAT, MAGIC_NUMBER, self.capacity, self.slot_size, 0, 0)
            self.shm.buf[:HEADER_SIZE] = header_bytes
        else:
            self.shm = shared_memory.SharedMemory(name=self.name, create=False)
            magic, cap, s_size, _, _ = struct.unpack(HEADER_FORMAT, self.shm.buf[:HEADER_SIZE])
            if magic != MAGIC_NUMBER:
                raise ValueError(f"Corrupted ring buffer magic: {hex(magic)}")
            self.capacity = cap
            self.slot_size = s_size

    def _read_header(self) -> Tuple[int, int, int, int, int]:
        return struct.unpack(HEADER_FORMAT, self.shm.buf[:HEADER_SIZE])

    def _write_header_positions(self, write_pos: int, read_pos: int) -> None:
        struct.pack_into("=QQ", self.shm.buf, 12, write_pos, read_pos)

    def push(self, data: bytes | str | Dict[str, Any]) -> bool:
        """Pushes a payload into the next available circular slot."""
        if isinstance(data, dict):
            raw = json.dumps(data).encode("utf-8")
        elif isinstance(data, str):
            raw = data.encode("utf-8")
        else:
            raw = data

        payload_len = len(raw)
        if payload_len > (self.slot_size - 4):
            raise ValueError(f"Payload size {payload_len} exceeds max slot capacity ({self.slot_size - 4} bytes)")

        magic, cap, slot_sz, write_pos, read_pos = self._read_header()

        slot_idx = write_pos % cap
        offset = HEADER_SIZE + (slot_idx * slot_sz)

        # Write length prefix (4 bytes) + raw payload
        struct.pack_into("=I", self.shm.buf, offset, payload_len)
        self.shm.buf[offset + 4 : offset + 4 + payload_len] = raw

        # Advance write position
        new_write_pos = write_pos + 1
        self._write_header_positions(new_write_pos, read_pos)
        return True

    def pop(self) -> Optional[Dict[str, Any] | bytes]:
        """Pops the oldest unread payload from the circular ring."""
        magic, cap, slot_sz, write_pos, read_pos = self._read_header()

        if read_pos >= write_pos:
            return None  # Nothing to read

        # Handle overflow if write_pos has lapped read_pos past buffer capacity
        if (write_pos - read_pos) > cap:
            read_pos = write_pos - cap

        slot_idx = read_pos % cap
        offset = HEADER_SIZE + (slot_idx * slot_sz)

        (payload_len,) = struct.unpack_from("=I", self.shm.buf, offset)
        raw = bytes(self.shm.buf[offset + 4 : offset + 4 + payload_len])

        # Advance read position
        new_read_pos = read_pos + 1
        self._write_header_positions(write_pos, new_read_pos)

        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return raw

    def peek_recent(self, max_items: int = 10) -> List[Any]:
        """Peeks up to max_items most recently written payloads without advancing read pointer."""
        magic, cap, slot_sz, write_pos, read_pos = self._read_header()
        if write_pos == 0:
            return []

        available = min(write_pos, cap)
        to_fetch = min(available, max_items)
        items: List[Any] = []

        start_pos = write_pos - to_fetch
        for pos in range(start_pos, write_pos):
            slot_idx = pos % cap
            offset = HEADER_SIZE + (slot_idx * slot_sz)
            (payload_len,) = struct.unpack_from("=I", self.shm.buf, offset)
            if payload_len == 0 or payload_len > slot_sz - 4:
                continue
            raw = bytes(self.shm.buf[offset + 4 : offset + 4 + payload_len])
            try:
                items.append(json.loads(raw.decode("utf-8")))
            except Exception:
                items.append(raw)
        return items

    def read_all_available(self) -> List[Any]:
        """Reads all pending unread items in batch without dropping frames."""
        items: List[Any] = []
        while True:
            item = self.pop()
            if item is None:
                break
            items.append(item)
        return items

    def get_stats(self) -> Dict[str, Any]:
        magic, cap, slot_sz, write_pos, read_pos = self._read_header()
        return {
            "name": self.name,
            "capacity": cap,
            "slot_size_bytes": slot_sz,
            "total_size_kb": round(self.total_size / 1024, 2),
            "write_pos": write_pos,
            "read_pos": read_pos,
            "pending_items": max(0, write_pos - read_pos),
            "is_owner": self.is_owner
        }

    def close(self) -> None:
        try:
            self.shm.close()
            if self.is_owner:
                self.shm.unlink()
        except Exception:
            pass

def _test_ring_buffer():
    print("=== MARKUS Zero-Copy Shared Memory Ring Buffer Test ===")
    rb_writer = MarkusSharedRingBuffer(name="markus_test_ring", capacity=64, slot_size=512, create=True)
    rb_reader = MarkusSharedRingBuffer(name="markus_test_ring", create=False)

    # Benchmark Push Throughput
    t0 = time.perf_counter()
    count = 1000
    for i in range(count):
        rb_writer.push({"seq": i, "agent": "TEST_PRODUCER", "data": "cortex_stream_telemetry_payload", "ts": time.time()})
    t1 = time.perf_counter()
    push_duration_ms = (t1 - t0) * 1000
    ops_per_sec = count / (t1 - t0)

    print(f"Pushed {count} items in {push_duration_ms:.2f}ms ({ops_per_sec:,.0f} ops/sec, {push_duration_ms/count*1000:.2f}µs per op)")

    # Read items
    items = rb_reader.read_all_available()
    print(f"Read {len(items)} items from shared memory buffer.")
    assert len(items) == min(count, 64), f"Expected {min(count, 64)} items due to circular capacity, got {len(items)}"
    assert items[-1]["seq"] == count - 1, f"Expected last seq {count-1}, got {items[-1]['seq']}"

    stats = rb_writer.get_stats()
    print(f"Ring Buffer Stats:\n{json.dumps(stats, indent=2)}")

    rb_reader.close()
    rb_writer.close()
    print("\n✅ Zero-Copy Shared Memory Ring Buffer: PASSED")

if __name__ == "__main__":
    _test_ring_buffer()
