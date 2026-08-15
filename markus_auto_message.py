#!/usr/bin/env python3
"""
Auto-Message Sender for MARKUS RNG Pilot
Reads the latest dispatch JSON from markus_private/ipc/ and sends the prompt
text as a self-contained message to the MARKUS autonomous agent.
"""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Optional

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.AutoMessage")

class AutoMessageSender:
    """
    Reads the most recent RNG-pilot dispatch payload and constructs a prompt
    for immediate execution by the MARKUS OS agent.
    """

    def __init__(self, ipc_dir: Optional[Path] = None, cortex: Optional[PersistentCortexDB] = None) -> None:
        self.ipc_dir = ipc_dir or (Path(__file__).parent / "markus_private" / "ipc")
        self.cortex = cortex or PersistentCortexDB()

    def latest_dispatch(self) -> Optional[dict]:
        dispatches = sorted(self.ipc_dir.glob("dispatch_*.json"), reverse=True)
        if not dispatches:
            return None
        return json.loads(dispatches[0].read_text(encoding="utf-8"))

    def build_agent_prompt(self, dispatch: dict) -> str:
        choice = dispatch["choice"]
        action = dispatch["action"]
        return f"""
You are MARKUS OS running in **AUTONOMOUS AUTO-PILOT MODE**.

A random development selector has dispatched the following task:

## 🎯 Auto-Pilot Instruction (Action #{choice}: {action})

**Generated Prompt:**
{dispatch['prompt']}

**Cycle ID:** {dispatch['cycle_id']}
**Timestamp:** {dispatch['timestamp']}

Execute this task immediately. Record outcomes to the L3 cortex. Report results via the integration test framework.

Respond with a JSON object containing:
{{"cycle_id": "...", "status": "COMPLETED|SKIPPED", "artifact_path": "...", "notes": "..."}}
"""

    def send_current(self) -> dict:
        dispatch = self.latest_dispatch()
        if not dispatch:
            return {"status": "NO_DISPATCH_FOUND", "message": "No dispatch file in markus_private/ipc/"}
        prompt = self.build_agent_prompt(dispatch)
        self.cortex.append_thought(
            f"auto_msg_{dispatch['cycle_id']}",
            "MARKUS_AUTO_MESSAGE_SENDER",
            "Sent auto-pilot prompt to MARKUS OS agent for execution.",
            {"cycle_id": dispatch["cycle_id"], "choice": dispatch["choice"], "action": dispatch["action"]}
        )
        return {
            "status": "DISPATCHED",
            "cycle_id": dispatch["cycle_id"],
            "choice": dispatch["choice"],
            "action": dispatch["action"],
            "prompt_length": len(prompt),
            "prompt": prompt
        }

if __name__ == "__main__":
    sender = AutoMessageSender()
    result = sender.send_current()
    print("=== MARKUS Auto-Message Sender ===")
    print(json.dumps({k: v for k, v in result.items() if k != "prompt"}, indent=2))
    if "prompt" in result:
        print(f"\n[DISPATCHED PROMPT (Action #{result['choice']}): {result['action']}]")
