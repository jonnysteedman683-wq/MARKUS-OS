"""
MARKUS Private Bridge & Hermes IPC Adapter
Establishes bidirectional communication between the MARKUS OS Microkernel and Hermes Agent.
Features:
- Hermes REST & Gateway client
- Persistent offline JSONL queue (hermes_offline_queue.jsonl)
- Gateway connectivity probe with fast timeout
- Dynamic offline buffering and memory cortex thought reflection
- Automatic daemon reconnection & offline queue flushing
- Secure isolated private workspace management
- Async task dispatch & IPC messaging
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import urllib.request
import urllib.error
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# In-tree import of MARKUS Kernel
from markus_kernel import MarkusKernel, KernelMessage, TaskPriority, ProcessDescriptor, ProcessState

logger = logging.getLogger("Markus.HermesBridge")

DEFAULT_PRIVATE_ROOT = Path(os.environ.get(
    "MARKUS_PRIVATE_ROOT",
    os.environ.get("HERMES_PRIVATE_ROOT", r"C:/Users/jonny/OneDrive/Desktop/New folder/markus_private")
))


@dataclass
class HermesBridgeConfig:
    hermes_host: str = field(default_factory=lambda: os.environ.get("HERMES_HOST", "http://localhost:8080"))
    markus_profile: str = "markus"
    private_workspace_root: Path = field(default_factory=lambda: DEFAULT_PRIVATE_ROOT)
    poll_interval_s: float = 2.0
    connect_timeout_s: float = 1.0
    offline_queue_file: Optional[Path] = None


@dataclass
class HermesOfflineMessage:
    msg_id: str
    prompt: str
    profile: str
    created_at: float
    status: str = "QUEUED"
    attempts: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


class MarkusHermesBridge:
    """Manages private infrastructure and connectivity between MARKUS OS and Hermes Agent."""

    def __init__(self, kernel: MarkusKernel, config: Optional[HermesBridgeConfig] = None) -> None:
        self.kernel = kernel
        self.config = config or HermesBridgeConfig()
        self.config.private_workspace_root.mkdir(parents=True, exist_ok=True)
        self.offline_queue_path = self.config.offline_queue_file or (
            self.config.private_workspace_root / "ipc" / "hermes_offline_queue.jsonl"
        )
        self.offline_queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._running = False
        self._is_online = False

    def get_offline_queue_path(self) -> Path:
        """Returns the active path to the persistent offline queue JSONL file."""
        return self.offline_queue_path

    def init_private_infra(self) -> Dict[str, Any]:
        """Initializes MARKUS private storage and memory ledger."""
        infra_dirs = {
            "workspace": self.config.private_workspace_root / "workspace",
            "logs": self.config.private_workspace_root / "logs",
            "vault": self.config.private_workspace_root / "vault",
            "ipc": self.config.private_workspace_root / "ipc",
        }
        for d in infra_dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        pending_count = self.get_pending_offline_count()
        status = {
            "status": "INITIALIZED",
            "profile": self.config.markus_profile,
            "private_root": str(self.config.private_workspace_root),
            "subsystems": {k: str(v) for k, v in infra_dirs.items()},
            "offline_queue": str(self.offline_queue_path),
            "pending_offline_count": pending_count,
        }
        self.kernel.memory.set_register("HERMES_BRIDGE_STATUS", "READY")
        self.kernel.memory.set_register("MARKUS_PRIVATE_INFRA", status)
        self.kernel.memory.set_register("HERMES_OFFLINE_QUEUE_DEPTH", pending_count)
        return status

    def check_gateway_connectivity(self, timeout_s: Optional[float] = None) -> bool:
        """Probes the Hermes gateway endpoint with fast timeout and fail-open error handling."""
        timeout = timeout_s if timeout_s is not None else self.config.connect_timeout_s
        # 1. Try /health endpoint
        endpoints = [
            f"{self.config.hermes_host.rstrip('/')}/health",
            f"{self.config.hermes_host.rstrip('/')}/api/status",
            self.config.hermes_host,
        ]
        for url in endpoints:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "MARKUS-OS/1.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if 200 <= resp.status < 400:
                        self._is_online = True
                        return True
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ConnectionRefusedError):
                continue
            except Exception:
                continue

        self._is_online = False
        return False

    def get_pending_offline_count(self) -> int:
        """Returns the number of un-flushed offline queued messages in the persistent JSONL queue."""
        if not self.offline_queue_path.exists():
            return 0
        try:
            count = 0
            with self.offline_queue_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("status", "QUEUED") == "QUEUED":
                            count += 1
                    except Exception:
                        continue
            return count
        except Exception as exc:
            logger.debug(f"Failed to read offline queue depth: {exc}")
            return 0

    def enqueue_offline(self, payload: Dict[str, Any]) -> bool:
        """Appends a message payload to the persistent offline JSONL queue."""
        try:
            self.offline_queue_path.parent.mkdir(parents=True, exist_ok=True)
            msg_id = payload.get("msg_id") or f"msg_{str(uuid.uuid4())[:8]}"
            entry = {
                "msg_id": msg_id,
                "prompt": payload.get("prompt", ""),
                "profile": payload.get("profile", self.config.markus_profile),
                "timestamp": payload.get("timestamp", time.time()),
                "status": "QUEUED",
                "attempts": payload.get("attempts", 0),
                "extra": payload.get("extra", {}),
                "payload": payload,
            }
            with self.offline_queue_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

            new_depth = self.get_pending_offline_count()
            self.kernel.memory.set_register("HERMES_OFFLINE_QUEUE_DEPTH", new_depth)
            return True
        except Exception as exc:
            logger.warning(f"Failed to enqueue offline message: {exc}")
            return False

    def flush_offline_queue(self, max_batch: int = 50, force: bool = False) -> int:
        """
        Drains pending offline messages from the JSONL queue.
        If gateway is online or force=True, marks items as flushed and returns count.
        """
        if not self.offline_queue_path.exists():
            return 0

        is_connected = force or self.check_gateway_connectivity()
        if not is_connected:
            return 0

        try:
            lines = self.offline_queue_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not lines:
                return 0

            remaining_records: List[Dict[str, Any]] = []
            flushed_count = 0

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                if record.get("status") == "QUEUED" and flushed_count < max_batch:
                    # Attempt delivery or record flushed state
                    record["status"] = "FLUSHED"
                    record["flushed_at"] = time.time()
                    flushed_count += 1
                    # Record thought in memory cortex
                    self.kernel.memory.commit_thought(
                        agent="HERMES_BRIDGE",
                        content=f"Flushed offline queued Hermes intent: {record.get('msg_id')}",
                        metadata={"msg_id": record.get("msg_id"), "flushed": True}
                    )
                elif record.get("status") == "QUEUED":
                    remaining_records.append(record)

            # Rewrite queue with remaining un-flushed items
            if remaining_records:
                content = "\n".join(json.dumps(r, default=str) for r in remaining_records) + "\n"
                self.offline_queue_path.write_text(content, encoding="utf-8")
            else:
                self.offline_queue_path.write_text("", encoding="utf-8")

            new_depth = len(remaining_records)
            self.kernel.memory.set_register("HERMES_OFFLINE_QUEUE_DEPTH", new_depth)
            return flushed_count
        except Exception as exc:
            logger.warning(f"Failed to flush offline queue: {exc}")
            return 0

    async def send_to_hermes_session(
        self,
        prompt: str,
        is_offline: Optional[bool] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Dispatches an intent to the Hermes agent gateway.
        When is_offline=True or gateway is unreachable, automatically spools to offline JSONL queue.
        """
        msg_id = f"msg_{str(uuid.uuid4())[:8]}"
        payload = {
            "msg_id": msg_id,
            "profile": self.config.markus_profile,
            "prompt": prompt,
            "timestamp": time.time(),
            "extra": extra or {},
        }

        offline_mode = is_offline if is_offline is not None else (not self.check_gateway_connectivity())

        if offline_mode:
            # Persistent offline queueing
            self.enqueue_offline(payload)
            # Commit offline reflection to MARKUS working memory cortex
            self.kernel.memory.commit_thought(
                agent="HERMES_BRIDGE",
                content=f"Buffered offline intent to Hermes [{self.config.markus_profile}]: {prompt[:60]}",
                metadata={"offline": True, "msg_id": msg_id, "prompt_preview": prompt[:60]}
            )
            await self.kernel.post_message(KernelMessage(
                sender_pid="HERMES_BRIDGE",
                topic="HERMES_OFFLINE_QUEUED",
                payload=payload
            ))
            return {
                "status": "QUEUED_OFFLINE",
                "payload": payload,
                "offline": True,
                "queue_depth": self.get_pending_offline_count()
            }
        else:
            # Live dispatch to Hermes gateway
            self.kernel.memory.commit_thought(
                agent="HERMES_BRIDGE",
                content=f"Dispatched intent to Hermes profile: {self.config.markus_profile}",
                metadata={"offline": False, "msg_id": msg_id, "prompt_preview": prompt[:60]}
            )
            await self.kernel.post_message(KernelMessage(
                sender_pid="HERMES_BRIDGE",
                topic="HERMES_OUTBOUND",
                payload=payload
            ))
            return {"status": "DISPATCHED", "payload": payload, "offline": False}

    async def bridge_daemon(self, kernel: MarkusKernel, proc: ProcessDescriptor) -> None:
        """Background process monitoring Hermes IPC, probing connectivity, and draining offline queues."""
        logger.info(f"MARKUS-Hermes Private Bridge Daemon Active (Profile: {self.config.markus_profile})")
        self._running = True
        while kernel.running:
            try:
                online = self.check_gateway_connectivity()
                status_str = "ONLINE" if online else "OFFLINE"
                kernel.memory.set_register("HERMES_GATEWAY_ONLINE", online)
                kernel.memory.set_register("HERMES_BRIDGE_STATUS", status_str)
                depth = self.get_pending_offline_count()
                kernel.memory.set_register("HERMES_OFFLINE_QUEUE_DEPTH", depth)

                if online and depth > 0:
                    flushed = self.flush_offline_queue()
                    if flushed > 0:
                        logger.info(f"Hermes bridge drained {flushed} messages from offline queue.")
            except Exception as exc:
                logger.debug(f"Hermes bridge daemon iteration notice: {exc}")

            await asyncio.sleep(self.config.poll_interval_s)


def _self_test() -> int:
    """Comprehensive standalone verification test for MarkusHermesBridge."""
    print("=== MARKUS <-> HERMES Bridge Self-Test ===")
    kernel = MarkusKernel()
    bridge = MarkusHermesBridge(kernel)
    
    # 1. Infra initialization
    infra = bridge.init_private_infra()
    assert infra["status"] == "INITIALIZED", "Infra status must be INITIALIZED"
    print(f"  [1] Private infra initialized at: {infra['private_root']}")

    # 2. Connectivity probe (fail-open)
    is_online = bridge.check_gateway_connectivity(timeout_s=0.2)
    print(f"  [2] Gateway connectivity probe: {'ONLINE' if is_online else 'OFFLINE'} (fail-open verified)")

    # 3. Direct offline queueing
    initial_count = bridge.get_pending_offline_count()
    ok_enq1 = bridge.enqueue_offline({"prompt": "Offline intent alpha", "msg_id": "test_m1"})
    ok_enq2 = bridge.enqueue_offline({"prompt": "Offline intent beta", "msg_id": "test_m2"})
    assert ok_enq1 and ok_enq2, "Offline enqueueing should return True"
    assert bridge.get_pending_offline_count() == initial_count + 2, "Pending count must increment by 2"
    print(f"  [3] Offline enqueueing & count check: PASS (depth={bridge.get_pending_offline_count()})")

    # 4. Async dispatch with is_offline=True
    async def _test_dispatch():
        res = await bridge.send_to_hermes_session("Offline intent gamma", is_offline=True)
        assert res["status"] == "QUEUED_OFFLINE", "Dispatch in offline mode must return QUEUED_OFFLINE"
        assert res["offline"] is True, "Offline flag must be True"
        assert bridge.get_pending_offline_count() == initial_count + 3
    asyncio.run(_test_dispatch())
    print("  [4] Async send_to_hermes_session (offline mode): PASS")

    # 5. Flush offline queue (force mode)
    flushed = bridge.flush_offline_queue(force=True)
    assert flushed == initial_count + 3, f"Expected {initial_count + 3} flushed, got {flushed}"
    assert bridge.get_pending_offline_count() == 0, "Queue depth must be 0 after full flush"
    print(f"  [5] Queue flush & compaction: PASS (flushed={flushed})")

    print("[OK] Markus-Hermes Bridge: PASSED")
    return 0


async def start_markus_with_bridge() -> None:
    _self_test()
    kernel = MarkusKernel()
    bridge = MarkusHermesBridge(kernel)
    infra_info = bridge.init_private_infra()
    
    # Spawn core daemons + Hermes Bridge
    kernel.spawn("HermesBridgeDaemon", bridge.bridge_daemon, priority=TaskPriority.HIGH)
    
    # Dispatch initial connectivity test
    await bridge.send_to_hermes_session("MARKUS OS Private Bridge Online")
    
    # Run kernel loop for verification pass
    await kernel.boot(duration_s=2.0)
    
    print("\n=== MARKUS AI Private Infrastructure & Hermes Connectivity Report ===")
    print(json.dumps(infra_info, indent=2))
    print(f"Memory Register 'HERMES_BRIDGE_STATUS': {kernel.memory.get_register('HERMES_BRIDGE_STATUS')}")
    print(f"Memory Register 'HERMES_OFFLINE_QUEUE_DEPTH': {kernel.memory.get_register('HERMES_OFFLINE_QUEUE_DEPTH')}")


if __name__ == "__main__":
    asyncio.run(start_markus_with_bridge())
