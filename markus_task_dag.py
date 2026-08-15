#!/usr/bin/env python3
"""
MARKUS OS Multi-Agent Task Graph DAG Subsystem (Upgrade 15)
Decomposes complex objectives into atomic, directed acyclic graphs (DAGs)
with topological dependency resolution, parallel execution, and cycle detection.
"""

from __future__ import annotations
import asyncio
import enum
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logger = logging.getLogger("Markus.TaskDAG")

class NodeState(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

@dataclass
class TaskNode:
    id: str
    name: str
    action: Callable[..., Coroutine[Any, Any, Any]]
    dependencies: Set[str] = field(default_factory=set)
    state: NodeState = NodeState.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def runtime_ms(self) -> float:
        if self.end_time > self.start_time:
            return round((self.end_time - self.start_time) * 1000, 2)
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize current node state and metadata for UI/API consumption."""
        return {
            "id": self.id,
            "name": self.name,
            "dependencies": list(self.dependencies),
            "state": self.state.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "runtime_ms": self.runtime_ms
        }

class TaskDAG:
    """Directed Acyclic Graph orchestrator for multi-agent task execution."""

    def __init__(self, dag_id: str = "default_dag") -> None:
        self.dag_id = dag_id
        self.nodes: Dict[str, TaskNode] = {}

    def to_spec(self) -> Dict[str, Any]:
        """Returns the full DAG specification and node status map."""
        return {
            "dag_id": self.dag_id,
            "has_cycles": self.detect_cycles() if self.nodes else False,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "node_count": len(self.nodes)
        }

    async def step_node(self, node_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a single specific ready node in isolation (Step-Stepping mode)."""
        node = self.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node '{node_id}' not found in DAG '{self.dag_id}'")

        # Verify dependencies
        for dep_id in node.dependencies:
            dep_node = self.nodes.get(dep_id)
            if not dep_node or dep_node.state != NodeState.COMPLETED:
                raise RuntimeError(f"Cannot step node '{node_id}': dependency '{dep_id}' is not COMPLETED.")

        node.state = NodeState.RUNNING
        node.start_time = time.time()
        try:
            dep_results = {dep_id: self.nodes[dep_id].result for dep_id in node.dependencies}
            if context:
                dep_results.update(context)

            if asyncio.iscoroutinefunction(node.action):
                node.result = await node.action(dep_results)
            else:
                node.result = node.action(dep_results)
            node.state = NodeState.COMPLETED
        except Exception as exc:
            node.error = str(exc)
            node.state = NodeState.FAILED
            logger.error(f"Single step failed on node {node.id}: {exc}")
        finally:
            node.end_time = time.time()

        return node.to_dict()

    def add_node(
        self,
        node_id: str,
        name: str,
        action: Callable[..., Coroutine[Any, Any, Any]],
        dependencies: Optional[Set[str]] = None
    ) -> TaskNode:
        if node_id in self.nodes:
            raise ValueError(f"Node '{node_id}' already exists in DAG '{self.dag_id}'")
        
        deps = dependencies or set()
        node = TaskNode(id=node_id, name=name, action=action, dependencies=deps)
        self.nodes[node_id] = node
        return node

    def detect_cycles(self) -> bool:
        """Kahn's algorithm for cycle detection."""
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.id] += 1
                else:
                    raise ValueError(f"Dependency '{dep}' referenced by node '{node.id}' does not exist.")

        queue: List[str] = [nid for nid, deg in in_degree.items() if deg == 0]
        visited_count = 0

        # Build adjacency list: dep -> dependents
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                adj[dep].append(node.id)

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited_count != len(self.nodes)

    def get_ready_nodes(self) -> List[TaskNode]:
        """Return nodes whose dependencies are all COMPLETED and are currently PENDING."""
        ready: List[TaskNode] = []
        for node in self.nodes.values():
            if node.state == NodeState.PENDING:
                all_deps_done = True
                for dep_id in node.dependencies:
                    dep_node = self.nodes.get(dep_id)
                    if not dep_node or dep_node.state != NodeState.COMPLETED:
                        all_deps_done = False
                        break
                if all_deps_done:
                    ready.append(node)
        return ready

    async def execute(self, max_concurrency: int = 4) -> Dict[str, Any]:
        """Execute the DAG concurrently resolving topological dependencies."""
        if self.detect_cycles():
            raise RuntimeError(f"Cycle detected in DAG '{self.dag_id}'! Execution aborted.")

        start_time = time.time()
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _run_node(node: TaskNode):
            async with semaphore:
                node.state = NodeState.RUNNING
                node.start_time = time.time()
                try:
                    # Collect dependency results as kwargs/context
                    dep_results = {dep_id: self.nodes[dep_id].result for dep_id in node.dependencies}
                    if asyncio.iscoroutinefunction(node.action):
                        node.result = await node.action(dep_results)
                    else:
                        node.result = node.action(dep_results)
                    node.state = NodeState.COMPLETED
                except Exception as exc:
                    node.error = str(exc)
                    node.state = NodeState.FAILED
                    logger.error(f"DAG Node {node.id} failed: {exc}")
                finally:
                    node.end_time = time.time()

        running_tasks: Dict[str, asyncio.Task] = {}

        while True:
            # Check for completed or failed tasks
            ready_nodes = self.get_ready_nodes()
            for node in ready_nodes:
                node.state = NodeState.READY
                task = asyncio.create_task(_run_node(node))
                running_tasks[node.id] = task

            if not running_tasks:
                break

            # Wait for at least one running task to complete
            done, _ = await asyncio.wait(
                running_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cleanup finished tasks
            finished_ids = [nid for nid, t in running_tasks.items() if t in done]
            for nid in finished_ids:
                del running_tasks[nid]

            # If any node failed, check if remaining nodes cannot proceed
            failed_nodes = [n for n in self.nodes.values() if n.state == NodeState.FAILED]
            if failed_nodes and not running_tasks and not self.get_ready_nodes():
                # Mark unreached pending nodes as SKIPPED
                for n in self.nodes.values():
                    if n.state in (NodeState.PENDING, NodeState.READY):
                        n.state = NodeState.SKIPPED
                break

        elapsed = round((time.time() - start_time) * 1000, 2)
        all_completed = all(n.state == NodeState.COMPLETED for n in self.nodes.values())

        return {
            "dag_id": self.dag_id,
            "success": all_completed,
            "elapsed_ms": elapsed,
            "nodes": {
                nid: {
                    "state": n.state.value,
                    "runtime_ms": n.runtime_ms,
                    "error": n.error,
                    "result": n.result
                }
                for nid, n in self.nodes.items()
            }
        }

async def _self_test():
    dag = TaskDAG("markus_pipeline_test")

    async def step_fetch(ctx):
        await asyncio.sleep(0.01)
        return {"data": [1, 2, 3]}

    async def step_process_a(ctx):
        await asyncio.sleep(0.01)
        data = ctx["fetch"]["data"]
        return [x * 2 for x in data]

    async def step_process_b(ctx):
        await asyncio.sleep(0.01)
        data = ctx["fetch"]["data"]
        return [x + 10 for x in data]

    async def step_aggregate(ctx):
        a = ctx["proc_a"]
        b = ctx["proc_b"]
        return {"combined": a + b}

    dag.add_node("fetch", "Fetch Initial State", step_fetch)
    dag.add_node("proc_a", "Process Transform A", step_process_a, dependencies={"fetch"})
    dag.add_node("proc_b", "Process Transform B", step_process_b, dependencies={"fetch"})
    dag.add_node("aggregate", "Aggregate Outputs", step_aggregate, dependencies={"proc_a", "proc_b"})

    res = await dag.execute()
    print("=== MARKUS Task DAG Test Result ===")
    print(json.dumps(res, indent=2))
    assert res["success"] is True
    assert res["nodes"]["aggregate"]["result"] == {"combined": [2, 4, 6, 11, 12, 13]}
    print("Task DAG self-test: PASSED")

if __name__ == "__main__":
    asyncio.run(_self_test())
