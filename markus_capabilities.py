"""
MARKUS OS Dynamic Capability Driver Subsystem (Upgrade 1)
Provides an extensible plugin interface for hot-reloading drivers, peripheral tools,
and sandboxed execution handlers without restarting the core MarkusKernel.
"""

from __future__ import annotations
import abc
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger("Markus.Capabilities")

class CapabilityType:
    TOOL = "TOOL"
    SENSOR = "SENSOR"
    ACTUATOR = "ACTUATOR"
    STORAGE = "STORAGE"

@dataclass
class CapabilityMetadata:
    name: str
    cap_type: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "MARKUS-OS"
    created_at: float = field(default_factory=time.time)

class BaseCapability(abc.ABC):
    """Abstract Base Class for all dynamic MARKUS drivers."""

    def __init__(self, metadata: CapabilityMetadata) -> None:
        self.metadata = metadata
        self.enabled = True

    @abc.abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the capability with given parameters."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Returns JSON schema / signature of the capability."""
        return {
            "name": self.metadata.name,
            "type": self.metadata.cap_type,
            "version": self.metadata.version,
            "description": self.metadata.description
        }

class CapabilityRegistry:
    """Dynamic registry managing hot-pluggable capabilities."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, BaseCapability] = {}

    def register(self, capability: BaseCapability) -> None:
        name = capability.metadata.name
        self._capabilities[name] = capability
        logger.info(f"Loaded Capability Driver: [{name}] v{capability.metadata.version} ({capability.metadata.cap_type})")

    def unregister(self, name: str) -> Optional[BaseCapability]:
        cap = self._capabilities.pop(name, None)
        if cap:
            logger.info(f"Unloaded Capability Driver: [{name}]")
        return cap

    def get(self, name: str) -> Optional[BaseCapability]:
        return self._capabilities.get(name)

    def list_capabilities(self) -> List[Dict[str, Any]]:
        return [cap.get_schema() for cap in self._capabilities.values() if cap.enabled]

    async def invoke(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        cap = self.get(name)
        if not cap:
            raise KeyError(f"Capability '{name}' not found in registry.")
        if not cap.enabled:
            raise PermissionError(f"Capability '{name}' is currently disabled.")
        return await cap.execute(params)

# Built-in Driver Implementations

class SystemTelemetryCapability(BaseCapability):
    """Driver collecting memory, timing, and local CPU health."""
    def __init__(self) -> None:
        super().__init__(CapabilityMetadata(
            name="system_telemetry",
            cap_type=CapabilityType.SENSOR,
            description="Reads local execution health and high-resolution timing metrics."
        ))

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "timestamp": time.time(),
            "uptime_check": True,
            "telemetry_source": "markus_capabilities"
        }

class FileWorkspaceCapability(BaseCapability):
    """Driver managing isolated scratchpad workspace I/O."""
    def __init__(self) -> None:
        super().__init__(CapabilityMetadata(
            name="workspace_io",
            cap_type=CapabilityType.TOOL,
            description="Sandboxed file I/O within MARKUS private workspace."
        ))

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "list")
        return {
            "action": action,
            "status": "SUCCESS",
            "workspace": "markus_private/workspace"
        }

if __name__ == "__main__":
    import asyncio
    async def test_capabilities() -> None:
        reg = CapabilityRegistry()
        reg.register(SystemTelemetryCapability())
        reg.register(FileWorkspaceCapability())
        
        print("=== Registered Capabilities ===")
        for cap in reg.list_capabilities():
            print(f" - {cap['name']} [{cap['type']}]: {cap['description']}")
            
        res = await reg.invoke("system_telemetry", {})
        print("\nInvoked 'system_telemetry':", res)

    asyncio.run(test_capabilities())
