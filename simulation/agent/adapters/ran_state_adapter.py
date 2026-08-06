"""RAN state adapter: implements the ran.orchestration.AgentStateProvider protocol.

Reads each agent's runtime state from AgentRegistry and converts it to ran.contracts.AgentStateSnapshot.
Side-effect free: read-only snapshot; does not trigger LLM calls, movement, or intent submission.
"""

from __future__ import annotations

from ran.contracts import AgentStateSnapshot, Position

from ..registry import AgentRegistry


class SimulationAgentStateProvider:
    """Bridge the agent subsystem state into an AgentStateSnapshot readable by RAN."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        snapshots: list[AgentStateSnapshot] = []
        for runtime in self.registry.runtimes():
            snapshot = runtime.to_snapshot(tick)
            snapshots.append(
                AgentStateSnapshot(
                    agent_id=snapshot.agent_id,
                    tick=tick,
                    position=Position(snapshot.position[0], snapshot.position[1]),
                    status=snapshot.lifecycle_status,  # type: ignore[arg-type]
                    role=snapshot.role,
                    activity_state=snapshot.activity_state,
                    current_intent_id=snapshot.current_intent_id,
                    destination_id=snapshot.destination_id,
                    current_room_id=snapshot.current_room_id,
                    waypoint_index=snapshot.waypoint_index,
                    waypoint_count=snapshot.waypoint_count,
                    waypoints=[Position(x, y) for x, y in snapshot.waypoints],
                    last_transition_tick=snapshot.last_transition_tick,
                    error=snapshot.error,
                )
            )
        return snapshots
