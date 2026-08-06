"""Loading and default templates for agent simulation definitions.

- load_agent_simulation_definition: loads a reproducible template from configs/agents/*.json.
- build_default_three_agent_definition: default definition aligned with the legacy three-agent
  tests (fixed spawn points + ordered plans), used for flow measurement and result reproduction in template mode.
"""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import (
    AgentPlanStep,
    AgentSimulationDefinition,
    AgentSpawnDefinition,
)


def load_agent_simulation_definition(path: str | Path) -> AgentSimulationDefinition:
    """Load an agent simulation definition from a JSON file.

    File structure:
    {
      "simulation_id": str,
      "seed": int,
      "loop_policy": "stop" | "repeat",
      "llm_mode": bool,
      "agents": [{"agent_id": str, "role": str, "spawn_position": [x, y], "ue_id": str | null}],
      "plans": {"agent_id": [{"destination_ref": str, "intent_type": str, "intent_parameters": {...}}]}
    }
    """

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    agents = tuple(
        AgentSpawnDefinition(
            agent_id=item["agent_id"],
            role=item["role"],
            spawn_position=tuple(item["spawn_position"]),
            ue_id=item.get("ue_id"),
        )
        for item in data["agents"]
    )
    plans = {
        agent_id: tuple(
            AgentPlanStep(
                destination_ref=step["destination_ref"],
                intent_type=step["intent_type"],
                intent_parameters=dict(step.get("intent_parameters", {})),
                stay=bool(step.get("stay", False)),
            )
            for step in steps
        )
        for agent_id, steps in data.get("plans", {}).items()
    }
    return AgentSimulationDefinition(
        simulation_id=data.get("simulation_id", "agent_simulation"),
        agents=agents,
        plans=plans,
        seed=int(data.get("seed", 42)),
        loop_policy=data.get("loop_policy", "stop"),
        llm_mode=bool(data.get("llm_mode", False)),
    )


def build_default_three_agent_definition() -> AgentSimulationDefinition:
    """Default three-agent definition: roles cover student/teacher/staff, with spawn points spread across the potions_teacher_office scene."""

    agents = (
        AgentSpawnDefinition(
            agent_id="student_001",
            role="student",
            spawn_position=(1.5, 1.5),
            ue_id="student_001_phone",
        ),
        AgentSpawnDefinition(
            agent_id="teacher_001",
            role="teacher",
            spawn_position=(4.5, 2.0),
            ue_id="teacher_001_phone",
        ),
        AgentSpawnDefinition(
            agent_id="staff_001",
            role="staff",
            spawn_position=(7.5, 4.5),
            ue_id="staff_001_phone",
        ),
    )
    plans = {
        "student_001": (
            AgentPlanStep(
                destination_ref="Teacher Work Area",
                intent_type="video_upload",
                intent_parameters={"size_profile": "medium"},
            ),
            AgentPlanStep(
                destination_ref="Entrance Area",
                intent_type="video_call",
                intent_parameters={"duration_seconds": 30, "bitrate_kbps": 2048},
            ),
        ),
        "teacher_001": (
            AgentPlanStep(
                destination_ref="Lore Display Area",
                intent_type="file_transfer",
                intent_parameters={"size_profile": "large"},
            ),
        ),
        "staff_001": (
            AgentPlanStep(
                destination_ref="Cleanup Area",
                intent_type="message",
                intent_parameters={},
            ),
        ),
    }
    return AgentSimulationDefinition(
        simulation_id="deterministic_three_agents",
        agents=agents,
        plans=plans,
        seed=42,
        loop_policy="stop",
        llm_mode=False,
    )
