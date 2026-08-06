"""Agent subsystem: LLM/template-guided agents that move and produce network intents.

Module boundaries:
- Contracts and definitions: contracts.py / definitions.py
- Plan sources: planning/ (deterministic templates, LLM auto-direction)
- Navigation: navigation/ (semantic index, room graph, A*, collision, scoring)
- Runtime: state_machine.py / runtime.py / registry.py
- RAN integration: adapters/ (read-only state adaptation, intent submission gateway)
"""

from .contracts import (
    AgentPlan,
    AgentPlanStep,
    AgentSimulationDefinition,
    AgentSnapshot,
    AgentSpawnDefinition,
    AgentStateFrame,
)
from .definitions import (
    build_default_three_agent_definition,
    load_agent_simulation_definition,
)
from .registry import AgentRegistry
from .runtime import AgentRuntime
from .state_machine import AgentStateMachine

__all__ = [
    "AgentPlan",
    "AgentPlanStep",
    "AgentRegistry",
    "AgentRuntime",
    "AgentSimulationDefinition",
    "AgentSnapshot",
    "AgentSpawnDefinition",
    "AgentStateFrame",
    "AgentStateMachine",
    "build_default_three_agent_definition",
    "load_agent_simulation_definition",
]
