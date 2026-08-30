#!/usr/bin/env python3
"""Pyramid Agent Lifecycle System
Binary tree structure: 1-2-4-8 agents (T0-T3)
Each agent spawns 2 children and consolidates 2 inputs from below
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import hashlib

class Tier(Enum):
    TIER_0 = 0  # Final consolidator (1 agent)
    TIER_1 = 1  # Intermediate (2 agents)
    TIER_2 = 2  # Aggregate (4 agents)
    TIER_3 = 3  # Leaf workers (8 agents)

@dataclass
class AgentState:
    """State for pyramid agents"""
    agent_id: str
    tier: int  # Store as int for JSON serialization
    pyramid_dir: str = ""
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    work_completed: bool = False

class PyramidAgent:
    """Base agent class for pyramid structure"""
    
    def __init__(self, agent_id: str, tier: Tier, pyramid_dir: Path):
        self.state = AgentState(agent_id=agent_id, tier=tier.value, pyramid_dir=str(pyramid_dir))
        self._tier_enum = tier  # Keep enum for runtime use
        self.pyramid_dir = Path(pyramid_dir)
        self.agent_file = self.pyramid_dir / f"tier{tier.value}" / f"{agent_id}.json"
        
    def spawn_children(self) -> List['PyramidAgent']:
        """Spawn 2 children agents (for tiers 0-2)"""
        if self._tier_enum == Tier.TIER_3:
            return []  # Leaf agents don't spawn children
        
        children = []
        child_tier = Tier(self._tier_enum.value + 1)
        for i in range(2):
            child_id = f"{self.state.agent_id}_child_{i}"
            child = PyramidAgent(child_id, child_tier, self.pyramid_dir)
            self._register_child(child_id)
            children.append(child)
        
        # Set parent reference for children
        for child in children:
            child._set_parent(self.state.agent_id)
            
        return children
    
    def _register_child(self, child_id: str):
        """Register child in file system"""
        self.state.child_ids.append(child_id)
        self._save_state()
    
    def _set_parent(self, parent_id: str):
        """Set parent reference"""
        self.state.parent_ids.append(parent_id)
    
    def receive_input(self, data: Dict[str, Any]):
        """Receive consolidated work from children (tiers 1-3)"""
        self.state.input_data = data
        self.state.status = "processing"
    
    def process_work(self):
        """Do tier-appropriate work"""
        tier = Tier(self.state.tier)
        if tier == Tier.TIER_3:
            self._do_leaf_work()
        else:
            self._consolidate_children()
        
        self.state.status = "completed"
        self.state.work_completed = True
    
    def _do_leaf_work(self):
        """T3: Perform foundational work"""
        work_items = [f"work_item_{self.state.agent_id}_{i}" for i in range(4)]
        self.state.output_data = {
            "agent_id": self.state.agent_id,
            "tier": self.state.tier,
            "chunks": work_items,
            "hash": self._compute_hash(work_items)
        }
    
    def _consolidate_children(self):
        """Higher tiers: consolidate 2 child results"""
        if self.state.parent_ids:
            pass
        
        merged = []
        for key, val in self.state.input_data.items():
            if key in ("sources", "source_agents"):
                continue
            if isinstance(val, dict):
                if "chunks" in val:
                    merged.extend(val["chunks"])
        
        consolidated = {
            "agent_id": self.state.agent_id,
            "tier": self.state.tier,
            "consolidated_from": len(self.state.input_data.get("sources", [])),
            "chunks": merged,
            "source_agents": self.state.input_data.get("sources", [])
        }
        self.state.output_data = consolidated
    
    def _compute_hash(self, data: Any) -> str:
        """Compute SHA256 hash for data integrity"""
        return hashlib.sha256(str(data).encode()).hexdigest()[:16]
    
    def _save_state(self):
        """Persist agent state to file"""
        self.agent_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.agent_file, 'w') as f:
            json.dump(self.state.__dict__, f, indent=2)
    
    def load_state(self) -> AgentState:
        """Load agent state from file"""
        if self.agent_file.exists():
            with open(self.agent_file, 'r') as f:
                data = json.load(f)
                self.state = AgentState(**data)
        return self.state
    
    def get_result(self) -> Dict[str, Any]:
        """Get agent's output data"""
        return self.state.output_data

class PyramidOrchestrator:
    """Manages the entire pyramid lifecycle"""
    
    def __init__(self, base_dir: Path = None):
        env_base = os.environ.get("PYRAMID_BASE_DIR")
        self.base_dir = Path(base_dir or env_base or "C:/Users/jonny/AppData/Local/.pyramid_agents")
        self.tier_dirs = {
            Tier.TIER_0: self.base_dir / "tier0",
            Tier.TIER_1: self.base_dir / "tier1", 
            Tier.TIER_2: self.base_dir / "tier2",
            Tier.TIER_3: self.base_dir / "tier3"
        }
    
    def initialize_structure(self):
        """Create directory structure"""
        for tier_dir in self.tier_dirs.values():
            tier_dir.mkdir(parents=True, exist_ok=True)
    
    def create_pyramid(self):
        """Initialize the full pyramid: 1-2-4-8"""
        self.initialize_structure()
        
        t0_agent = PyramidAgent("consolidator_final", Tier.TIER_0, self.base_dir)
        t0_agents = [t0_agent]
        
        t1_agents = [
            PyramidAgent(f"t1_agent_{i}", Tier.TIER_1, self.base_dir) 
            for i in range(2)
        ]
        
        t2_agents = [
            PyramidAgent(f"t2_agent_{i}", Tier.TIER_2, self.base_dir)
            for i in range(4)
        ]
        
        t3_agents = [
            PyramidAgent(f"t3_agent_{i}", Tier.TIER_3, self.base_dir)
            for i in range(8)
        ]
        
        self._wire_pyramid(t0_agents, t1_agents, t2_agents, t3_agents)
        
        return {
            "tier0": t0_agents,
            "tier1": t1_agents,
            "tier2": t2_agents,
            "tier3": t3_agents
        }
    
    def _wire_pyramid(self, t0, t1, t2, t3):
        """Wire parent-child relationships"""
        for i, t1_agent in enumerate(t1):
            t2_parents = t2[i*2:(i+1)*2]
            t2_agent_ids = [t2_parents[0].state.agent_id, t2_parents[1].state.agent_id]
            t1_agent.state.parent_ids = t2_agent_ids
            t1_agent._save_state()
            
            for t2_agent in t2_parents:
                t2_agent._register_child(t1_agent.state.agent_id)
        
        for i, t2_agent in enumerate(t2):
            t3_parents = t3[i*2:(i+1)*2]
            t3_agent_ids = [t3_parents[0].state.agent_id, t3_parents[1].state.agent_id]
            t2_agent.state.parent_ids = t3_agent_ids
            t2_agent._save_state()
            
            for t3_agent in t3_parents:
                t3_agent._register_child(t2_agent.state.agent_id)
        
        t0 = t0[0]
        t1_agent_ids = [t1_agent.state.agent_id for t1_agent in t1]
        t0.state.parent_ids = t1_agent_ids
        t0._save_state()
        
        for t1_agent in t1:
            t1_agent._register_child(t0.state.agent_id)
    
    def run_lifecycle(self, agents: Dict[str, List]) -> Dict[str, Any]:
        """Execute pyramid lifecycle: T3 → T2 → T1 → T0"""
        results = {"tier_results": {}, "final_output": None}
        
        # Phase 1: T3 leaves do work
        for agent in agents["tier3"]:
            agent.process_work()
        
        # Phase 2: T2 aggregates T3 outputs
        for i, agent in enumerate(agents["tier2"]):
            t3_parents = agents["tier3"][i*2:(i+1)*2]
            child_results = {t3.state.agent_id: t3.get_result() for t3 in t3_parents}
            
            agent.receive_input({
                "sources": list(child_results.keys()),
                **child_results
            })
            agent.process_work()
            results["tier_results"][agent.state.agent_id] = agent.get_result()
        
        # Phase 3: T1 aggregates T2 outputs
        for i, agent in enumerate(agents["tier1"]):
            t2_parents = agents["tier2"][i*2:(i+1)*2]
            child_results = {t2.state.agent_id: t2.get_result() for t2 in t2_parents}
            
            agent.receive_input({
                "sources": list(child_results.keys()),
                **child_results
            })
            agent.process_work()
            results["tier_results"][agent.state.agent_id] = agent.get_result()
        
        # Phase 4: T0 final consolidation
        t0_agent = agents["tier0"][0]
        t1_parents = agents["tier1"]
        child_results = {t1.state.agent_id: t1.get_result() for t1 in t1_parents}
        
        t0_agent.receive_input({
            "sources": list(child_results.keys()),
            **child_results
        })
        t0_agent.process_work()
        results["final_output"] = t0_agent.get_result()
        
        return results

if __name__ == "__main__":
    orchestrator = PyramidOrchestrator()
    agents = orchestrator.create_pyramid()
    results = orchestrator.run_lifecycle(agents)
    
    print("=" * 60)
    print("PYRAMID LIFECYCLE COMPLETE")
    print("=" * 60)
    print(f"Final chunks: {len(results['final_output'].get('chunks', []))}")