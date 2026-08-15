"""
MARKUS AI — Autonomous Kernel & Unified Swarm Operating System
Core Kernel Architecture:
- Microkernel Process & Task Dispatcher
- Memory Cortex (L1 Volatile Register, L2 Vector Substrate, L3 Durable Vault)
- Tri-Engine Execution Bus (Deliberative, Reactive, Self-Healing Sentinel)
- Capability & Tool Bus (Sandboxed Execution, Hardware/Network Interfaces)
"""

from __future__ import annotations
import asyncio
import enum
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

# In-tree persistent DB cortex link and Ring Buffer
try:
    from markus_db import PersistentCortexDB
except ImportError:
    PersistentCortexDB = None

try:
    from markus_ring_buffer import MarkusSharedRingBuffer
except ImportError:
    MarkusSharedRingBuffer = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [MARKUS-OS] %(message)s")
logger = logging.getLogger("MarkusOS")

class TaskPriority(enum.IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    BACKGROUND = 3

class ProcessState(enum.Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"

@dataclass
class KernelMessage:
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender_pid: str = "KERNEL"
    target_pid: str = "ALL"
    topic: str = "SYSTEM"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass
class ProcessDescriptor:
    pid: str
    name: str
    priority: TaskPriority
    entrypoint: Callable[['MarkusKernel', ProcessDescriptor], Coroutine[Any, Any, None]]
    state: ProcessState = ProcessState.READY
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

class MemoryCortex:
    """
    Tiered Memory Substrate:
    - L1 Registers (Fast key-value cache)
    - L1.5 Hot-Thought Ring Buffer (Microsecond zero-copy circular IPC buffer)
    - L2 Context Buffer (Working memory sliding window)
    - L3 Persistent DB (SQLite FTS5 durable cortex)
    """
    def __init__(self, enable_ring: bool = True) -> None:
        self.l1_registers: Dict[str, Any] = {}
        self.l2_working_memory: List[Dict[str, Any]] = []
        self.l3_audit_log: List[Dict[str, Any]] = []
        self.db: Optional[Any] = PersistentCortexDB() if PersistentCortexDB else None
        self.hot_ring: Optional[Any] = None
        if enable_ring and MarkusSharedRingBuffer:
            try:
                self.hot_ring = MarkusSharedRingBuffer(name="markus_cortex_hot", capacity=256, slot_size=1024, create=True)
            except Exception as e:
                logger.warning(f"Could not initialize L1.5 shared ring buffer: {e}")

    def set_register(self, key: str, val: Any) -> None:
        self.l1_registers[key] = val
        if self.db:
            self.db.set_register(key, val)

    def get_register(self, key: str, default: Any = None) -> Any:
        if key in self.l1_registers:
            return self.l1_registers[key]
        if self.db:
            db_val = self.db.get_register(key, default)
            self.l1_registers[key] = db_val
            return db_val
        return default

    def commit_thought(self, agent: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry_id = str(uuid.uuid4())[:8]
        entry = {
            "entry_id": entry_id,
            "agent": agent,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time()
        }
        # Push to L1.5 Hot-Thought Ring Buffer
        if self.hot_ring:
            try:
                self.hot_ring.push(entry)
            except Exception as err:
                logger.debug(f"Failed to push thought to hot ring: {err}")

        # Push to L2 Working Memory (sliding window capped at 100)
        self.l2_working_memory.append(entry)
        self.l3_audit_log.append(entry)

        # Push to L3 Persistent DB
        if self.db:
            self.db.append_thought(entry_id, agent, content, metadata)

        # Cap working memory at 100 entries
        if len(self.l2_working_memory) > 100:
            self.l2_working_memory.pop(0)

        return entry

    def get_recent_hot_thoughts(self, count: int = 10) -> List[Dict[str, Any]]:
        """Retrieve the most recent unread thoughts from the L1.5 hot ring or fallback to L2."""
        if self.hot_ring:
            try:
                items = self.hot_ring.peek_recent(max_items=count)
                if items:
                    return [item for item in items if isinstance(item, dict)]
            except Exception:
                pass
        return self.l2_working_memory[-count:]

class MarkusKernel:
    """Core Agent Microkernel orchestrating processes, message bus, and capability routing."""
    def __init__(self) -> None:
        self.process_table: Dict[str, ProcessDescriptor] = {}
        self.message_queue: asyncio.Queue[KernelMessage] = asyncio.Queue()
        self.memory = MemoryCortex()
        self.running = False
        self._tasks: List[asyncio.Task[None]] = []

    def spawn(
        self,
        name: str,
        entrypoint: Callable[['MarkusKernel', ProcessDescriptor], Coroutine[Any, Any, None]],
        priority: TaskPriority = TaskPriority.NORMAL,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        pid = f"proc_{str(uuid.uuid4())[:6]}"
        proc = ProcessDescriptor(
            pid=pid,
            name=name,
            priority=priority,
            entrypoint=entrypoint,
            context=context or {}
        )
        self.process_table[pid] = proc
        logger.info(f"Spawned Process [{name}] PID={pid} Priority={priority.name}")
        return pid

    async def post_message(self, message: KernelMessage) -> None:
        await self.message_queue.put(message)

    async def broadcast_telemetry(self, topic: str, payload: Dict[str, Any]) -> None:
        msg = KernelMessage(sender_pid="KERNEL", target_pid="ALL", topic=topic, payload=payload)
        await self.post_message(msg)

    async def _process_runner(self, proc: ProcessDescriptor) -> None:
        proc.state = ProcessState.RUNNING
        try:
            await proc.entrypoint(self, proc)
            proc.state = ProcessState.TERMINATED
            logger.info(f"Process [{proc.name}] PID={proc.pid} exited cleanly.")
        except asyncio.CancelledError:
            proc.state = ProcessState.TERMINATED
            logger.warning(f"Process [{proc.name}] PID={proc.pid} cancelled.")
        except Exception as exc:
            proc.state = ProcessState.FAILED
            logger.error(f"Process [{proc.name}] PID={proc.pid} crashed: {exc}", exc_info=True)

    async def boot(self, duration_s: Optional[float] = None) -> None:
        self.running = True
        logger.info("=== MARKUS AI Operating System Booting ===")
        self.memory.set_register("OS_STATUS", "BOOTED")
        self.memory.set_register("VERSION", "1.0.0-ALPHA")

        # Launch all ready processes
        for pid, proc in list(self.process_table.items()):
            task = asyncio.create_task(self._process_runner(proc))
            self._tasks.append(task)

        if duration_s:
            await asyncio.sleep(duration_s)
            await self.shutdown()
        else:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        self.running = False
        logger.info("=== MARKUS AI Initiating Safe Kernel Shutdown ===")
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self.memory.set_register("OS_STATUS", "HALTED")
        logger.info("=== Kernel Halted. State Preserved. ===")

# Standard Daemon Services

async def sentinel_watchdog_daemon(kernel: MarkusKernel, proc: ProcessDescriptor) -> None:
    """Autonomous Sentinel monitoring kernel health & process status."""
    while kernel.running:
        active_procs = sum(1 for p in kernel.process_table.values() if p.state == ProcessState.RUNNING)
        kernel.memory.commit_thought(
            agent="SENTINEL",
            content="Heartbeat healthy",
            metadata={"active_procs": active_procs, "queue_depth": kernel.message_queue.qsize()}
        )
        await asyncio.sleep(1.0)

async def deliberative_planner_daemon(kernel: MarkusKernel, proc: ProcessDescriptor) -> None:
    """Deliberative MoA engine processing intent queue."""
    while kernel.running:
        if not kernel.message_queue.empty():
            msg = await kernel.message_queue.get()
            logger.info(f"Deliberative Engine consumed msg: topic={msg.topic} from {msg.sender_pid}")
            kernel.memory.commit_thought(
                agent="PLANNER",
                content=f"Processed message {msg.msg_id}",
                metadata={"topic": msg.topic}
            )
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    async def main_test() -> None:
        kernel = MarkusKernel()
        kernel.spawn("SentinelWatchdog", sentinel_watchdog_daemon, priority=TaskPriority.CRITICAL)
        kernel.spawn("DeliberativePlanner", deliberative_planner_daemon, priority=TaskPriority.HIGH)
        
        # Dispatch a test event
        await kernel.post_message(KernelMessage(sender_pid="USER", topic="TASK_INIT", payload={"task": "Initialize Swarm Mesh"}))
        await kernel.boot(duration_s=2.5)

        print("\n=== MARKUS OS Memory Cortex Telemetry ===")
        print(f"Registers: {kernel.memory.l1_registers}")
        print(f"Working Memory Log Entries: {len(kernel.memory.l2_working_memory)}")
        for entry in kernel.memory.l2_working_memory[-3:]:
            print(f"  [{entry['agent']}] {entry['content']} (meta={entry['metadata']})")

    asyncio.run(main_test())
