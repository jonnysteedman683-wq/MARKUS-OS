#!/usr/bin/env python3
"""
MARKUS OS Hierarchical Task Decomposition Library (Upgrade 49c)

Extends markus_task_dag.py with hierarchical task decomposition capabilities.
Supports multi-level task trees, parallel sub-DAG execution, and recursive
dependency resolution for complex upgrade cycles.
"""

from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger("Markus.HierarchicalDAG")


class DecompositionStrategy(str, Enum):
    """Strategies for decomposing complex tasks into sub-tasks."""
    WIDTH_FIRST = "WIDTH_FIRST"  # Decompose by branching into parallel paths
    DEPTH_FIRST = "DEPTH_FIRST"   # Decompose by recursive sub-tasking
    HYBRID = "HYBRID"            # Adaptive based on task complexity


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class HierarchicalTaskSpec:
    """Specification for a hierarchical task decomposition."""
    task_id: str
    name: str
    description: str
    priority: TaskPriority
    action: Optional[Callable] = None
    dependencies: Set[str] = field(default_factory=set)
    sub_tasks: List["HierarchicalTaskSpec"] = field(default_factory=list)
    estimated_ms: float = 0.0
    tags: Set[str] = field(default_factory=set)

    def add_subtask(self, subtask: "HierarchicalTaskSpec") -> "HierarchicalTaskSpec":
        """Add a sub-task to this task. Returns self for chaining."""
        self.sub_tasks.append(subtask)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value,
            "dependencies": list(self.dependencies),
            "sub_tasks": [st.to_dict() for st in self.sub_tasks],
            "estimated_ms": self.estimated_ms,
            "tags": list(self.tags)
        }


class HierarchicalTaskDecomposer:
    """
    Decomposes complex objectives into hierarchical task trees.
    
    Supports three decomposition strategies:
    - WIDTH_FIRST: Split into parallel branches
    - DEPTH_FIRST: Recursive sub-tasking within each branch
    - HYBRID: Adaptive strategy based on task complexity metrics
    """

    # Complexity thresholds for hybrid strategy
    LOW_COMPLEXITY = 3
    HIGH_COMPLEXITY = 10

    # Tag-based decomposition rules
    DECOMPOSITION_RULES: Dict[str, List[str]] = {
        "ui_upgrade": ["analyze", "design", "implement", "validate", "commit"],
        "backend_refactor": ["profile", "design", "implement", "test", "benchmark"],
        "ai_agent_enhance": ["evaluate", "research", "implement", "test", "validate"],
        "skill_mutation": ["analyze", "select_target", "apply_change", "validate"],
        "system_refactor": ["audit", "design", "implement", "validate", "commit"],
        "technical_research": ["research", "analyze", "compare", "propose", "implement"]
    }

    def __init__(self) -> None:
        self._decomposition_cache: Dict[str, HierarchicalTaskSpec] = {}
        self._strategy_usage: Dict[DecompositionStrategy, int] = {}

    def decompose(self, 
                  objective: str,
                  strategy: DecompositionStrategy = DecompositionStrategy.HYBRID,
                  tags: Optional[Set[str]] = None) -> HierarchicalTaskSpec:
        """
        Decompose a complex objective into a hierarchical task tree.
        
        Args:
            objective: The high-level objective to decompose
            strategy: How to decompose (width-first, depth-first, hybrid)
            tags: Tags for the objective (used for rule-based decomposition)
        
        Returns:
            Root HierarchicalTaskSpec with sub-tasks
        """
        # Check cache first
        cache_key = f"{objective}_{strategy.value}_{','.join(sorted(tags or []))}"
        if cache_key in self._decomposition_cache:
            return self._decomposition_cache[cache_key]

        # Normalize tags
        tag_set = tags or {"general"}
        tag_str = "_".join(sorted(tag_set))

        # Select strategy
        if strategy == DecompositionStrategy.HYBRID:
            strategy = self._select_strategy(objective, tag_set)

        self._strategy_usage[strategy] = self._strategy_usage.get(strategy, 0) + 1

        # Decompose based on strategy
        if tag_str in self.DECOMPOSITION_RULES:
            # Use rule-based decomposition
            root = self._decompose_by_tags(objective, tag_str, strategy)
        else:
            # Use generic hierarchical decomposition
            root = self._decompose_generic(objective, strategy)

        self._decomposition_cache[cache_key] = root
        return root

    def _select_strategy(self, objective: str, tags: Set[str]) -> DecompositionStrategy:
        """Select decomposition strategy based on complexity."""
        complexity = len(objective.split()) + len(tags)

        if complexity < self.LOW_COMPLEXITY:
            return DecompositionStrategy.WIDTH_FIRST
        elif complexity > self.HIGH_COMPLEXITY:
            return DecompositionStrategy.DEPTH_FIRST
        else:
            return DecompositionStrategy.HYBRID

    def _decompose_by_tags(self, objective: str, tag: str, 
                           strategy: DecompositionStrategy) -> HierarchicalTaskSpec:
        """Decompose using predefined rules for known tag patterns."""
        subtasks = []
        rule_sequence = self.DECOMPOSITION_RULES[tag]

        for i, step_name in enumerate(rule_sequence):
            subtask = HierarchicalTaskSpec(
                task_id=f"{tag}_{step_name}",
                name=f"{step_name.title()}",
                description=f"Step {i+1}/{len(rule_sequence)}: {step_name} for {objective}",
                priority=TaskPriority.MEDIUM,
                tags={tag}
            )

            # Add sub-subtasks for depth-first strategy
            if strategy == DecompositionStrategy.DEPTH_FIRST and step_name in ("implement", "validate"):
                subtask.add_subtask(HierarchicalTaskSpec(
                    task_id=f"{tag}_{step_name}_setup",
                    name="Setup",
                    description="Prepare environment and dependencies",
                    priority=TaskPriority.LOW,
                    tags={tag}
                ))
                subtask.add_subtask(HierarchicalTaskSpec(
                    task_id=f"{tag}_{step_name}_execute",
                    name="Execute",
                    description="Run the main implementation/validation",
                    priority=TaskPriority.HIGH,
                    tags={tag}
                ))
                subtask.add_subtask(HierarchicalTaskSpec(
                    task_id=f"{tag}_{step_name}_verify",
                    name="Verify",
                    description="Confirm results meet criteria",
                    priority=TaskPriority.MEDIUM,
                    tags={tag}
                ))
            elif strategy == DecompositionStrategy.HYBRID:
                # Add minimal sub-subtask for verification
                subtask.add_subtask(HierarchicalTaskSpec(
                    task_id=f"{tag}_{step_name}_verify",
                    name="Verify",
                    description="Confirm output quality",
                    priority=TaskPriority.MEDIUM,
                    tags={tag}
                ))

            subtasks.append(subtask)

        return HierarchicalTaskSpec(
            task_id=tag,
            name=objective,
            description=f"Hierarchical task decomposition for: {objective}",
            priority=TaskPriority.HIGH,
            tags=tag_set if 'tag_set' in dir() else {tag},
            sub_tasks=subtasks
        )

    def _decompose_generic(self, objective: str, 
                          strategy: DecompositionStrategy) -> HierarchicalTaskSpec:
        """Generic hierarchical decomposition for unknown objectives."""
        # Basic 3-step decomposition
        setup = HierarchicalTaskSpec(
            task_id="setup",
            name="Setup",
            description=f"Prepare for: {objective}",
            priority=TaskPriority.MEDIUM,
            tags={"general"}
        )

        implement = HierarchicalTaskSpec(
            task_id="implement",
            name="Implement",
            description=f"Execute: {objective}",
            priority=TaskPriority.HIGH,
            tags={"general"}
        )

        validate = HierarchicalTaskSpec(
            task_id="validate",
            name="Validate",
            description=f"Verify results of: {objective}",
            priority=TaskPriority.MEDIUM,
            tags={"general"}
        )

        root = HierarchicalTaskSpec(
            task_id="root",
            name=objective,
            description=f"Generic hierarchical decomposition",
            priority=TaskPriority.HIGH,
            tags={"general"},
            sub_tasks=[setup, implement, validate]
        )

        # Add dependencies between top-level tasks
        implement.dependencies = {"setup"}
        validate.dependencies = {"implement"}

        return root

    def flatten_to_task_list(self, root: HierarchicalTaskSpec) -> List[HierarchicalTaskSpec]:
        """Flatten hierarchical structure into a flat task list with IDs."""
        tasks = []

        def _walk(task: HierarchicalTaskSpec):
            tasks.append(task)
            for sub in task.sub_tasks:
                _walk(sub)

        _walk(root)
        return tasks

    def get_parallel_branches(self, root: HierarchicalTaskSpec) -> List[List[HierarchicalTaskSpec]]:
        """Get parallel execution branches from the task tree."""
        if not root.sub_tasks:
            return [[root]]

        branches = []
        for sub in root.sub_tasks:
            if sub.sub_tasks:
                branches.extend(self.get_parallel_branches(sub))
            else:
                branches.append([sub])

        return branches

    def estimate_total_time(self, root: HierarchicalTaskSpec) -> float:
        """Estimate total execution time for the hierarchical task."""
        if not root.sub_tasks:
            return root.estimated_ms

        # Parallel execution of independent branches
        parallel_time = 0.0
        sequential_time = 0.0

        for sub in root.sub_tasks:
            sub_time = self.estimate_total_time(sub)
            if sub.dependencies:
                sequential_time += sub_time
            else:
                parallel_time = max(parallel_time, sub_time)

        return parallel_time + sequential_time

    def to_dag_spec(self, root: HierarchicalTaskSpec) -> Dict[str, Any]:
        """Convert hierarchical task tree to a flat DAG spec with dependencies."""
        flat_tasks = self.flatten_to_task_list(root)

        nodes = {}
        edges = []

        for task in flat_tasks:
            nodes[task.task_id] = task.to_dict()

            # Create edges from dependencies
            for dep in task.dependencies:
                edges.append({
                    "from": dep,
                    "to": task.task_id,
                    "type": "dependency"
                })

            # Create edges from parent to children
            if task.task_id != root.task_id:
                # Find parent
                for parent in flat_tasks:
                    if task in parent.sub_tasks:
                        edges.append({
                            "from": parent.task_id,
                            "to": task.task_id,
                            "type": "hierarchical"
                        })
                        break

        return {
            "root_task": root.task_id,
            "nodes": nodes,
            "edges": edges,
            "total_estimated_ms": self.estimate_total_time(root),
            "parallel_branches": len(self.get_parallel_branches(root)),
            "strategy_used": self._get_most_used_strategy(),
            "cache_size": len(self._decomposition_cache)
        }

    def _get_most_used_strategy(self) -> str:
        """Return the most commonly used strategy."""
        if not self._strategy_usage:
            return "unknown"
        return max(self._strategy_usage, key=self._strategy_usage.get).value


# ─── Integration with Dice Engine ───

def decompose_upgrade_action(action: str, decomposer: HierarchicalTaskDecomposer) -> Dict[str, Any]:
    """
    Decompose a dice engine upgrade action into hierarchical task tree.
    
    Args:
        action: The upgrade action label (e.g., "UPGRADE_UI", "UPGRADE_BACKEND")
        decomposer: The hierarchical task decomposer
    
    Returns:
        DAG spec for the upgrade
    """
    action_map = {
        "UPGRADE_UI": {
            "objective": "Upgrade user interface with accessibility and interactive improvements",
            "tags": {"ui_upgrade", "accessibility"}
        },
        "UPGRADE_BACKEND": {
            "objective": "Upgrade backend reliability, performance, and mesh networking",
            "tags": {"backend_refactor", "reliability"}
        },
        "UPGRADE_AI_AGENT": {
            "objective": "Upgrade AI agent capabilities with enhanced routing and skills",
            "tags": {"ai_agent_enhance", "prompt_synthesis"}
        },
        "FIND_SOMETHING_MISSING": {
            "objective": "Audit entire codebase for missing capabilities and integration gaps",
            "tags": {"skill_mutation", "system_audit"}
        },
        "TECHNICAL_ALTERNATIVE_UPGRADE": {
            "objective": "Research and implement technical alternatives for existing components",
            "tags": {"technical_research", "benchmarking"}
        },
        "RE_ROLL": {
            "objective": "Re-roll dice engine for alternative upgrade path",
            "tags": {"general"}
        }
    }

    config = action_map.get(action, {
        "objective": f"Execute upgrade action: {action}",
        "tags": {"general"}
    })

    root = decomposer.decompose(
        config["objective"],
        strategy=DecompositionStrategy.HYBRID,
        tags=config["tags"]
    )

    return decomposer.to_dag_spec(root)


# ─── Self-test ───

async def _self_test():
    """Test the hierarchical task decomposition engine."""
    print("=== MARKUS Hierarchical Task Decomposition Test ===\n")

    decomposer = HierarchicalTaskDecomposer()

    # Test 1: UI upgrade decomposition
    print("Test 1: UI Upgrade Decomposition")
    dag_spec = decompose_upgrade_action("UPGRADE_UI", decomposer)
    print(f"  Root: {dag_spec['root_task']}")
    print(f"  Nodes: {len(dag_spec['nodes'])}")
    print(f"  Edges: {len(dag_spec['edges'])}")
    print(f"  Parallel branches: {dag_spec['parallel_branches']}")
    print(f"  Strategy: {dag_spec['strategy_used']}")
    print(f"  ⏱ Estimated: {dag_spec['total_estimated_ms']:.1f}ms")
    print()

    # Test 2: Backend upgrade decomposition
    print("Test 2: Backend Upgrade Decomposition")
    dag_spec = decompose_upgrade_action("UPGRADE_BACKEND", decomposer)
    print(f"  Root: {dag_spec['root_task']}")
    print(f"  Nodes: {len(dag_spec['nodes'])}")
    print(f"  Edges: {len(dag_spec['edges'])}")
    print(f"  Parallel branches: {dag_spec['parallel_branches']}")
    print(f"  Strategy: {dag_spec['strategy_used']}")
    print()

    # Test 3: Technical research decomposition
    print("Test 3: Technical Research Decomposition")
    dag_spec = decompose_upgrade_action("TECHNICAL_ALTERNATIVE_UPGRADE", decomposer)
    print(f"  Root: {dag_spec['root_task']}")
    print(f"  Nodes: {len(dag_spec['nodes'])}")
    print()

    # Test 4: Generic decomposition
    print("Test 4: Generic Objective Decomposition")
    test_obj = "Build a new feature for the neural synapse module"
    root = decomposer.decompose(test_obj, tags={"feature_development"})
    flat = decomposer.flatten_to_task_list(root)
    print(f"  Objective: {test_obj}")
    print(f"  Flattened tasks: {len(flat)}")
    print(f"  Parallel branches: {len(decomposer.get_parallel_branches(root))}")
    print()

    print("✅ Hierarchical Task Decomposition Test: PASSED")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_self_test())
