from __future__ import annotations

from typing import Protocol

from ran.contracts import AgentStateSnapshot, AgentStatus, Position

from .definitions import RanScenarioDefinition


class AgentStateProvider(Protocol):
    """Provides Agent state at a given tick to the RAN orchestration layer; does not make network decisions."""

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        """Return the state of all Agents in the scenario; Agents must not be added or removed dynamically."""
        ...


class MockAgentStateProvider:
    """Static mock used by current tests; can later be replaced by a real Agent system interface."""

    def __init__(self, definition: RanScenarioDefinition) -> None:
        self._initial_positions = {
            item.agent_id: Position(item.intent.agent_pos.x, item.intent.agent_pos.y) for item in definition.agents
        }

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        """Return Agent state at fixed positions; the Agent ID set stays unchanged after construction."""

        status: AgentStatus = "READY" if tick <= 0 else "ACTIVE"
        return [
            AgentStateSnapshot(
                agent_id=agent_id,
                tick=tick,
                position=Position(position.x, position.y),
                status=status,
            )
            for agent_id, position in self._initial_positions.items()
        ]
