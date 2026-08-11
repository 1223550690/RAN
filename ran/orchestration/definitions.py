from __future__ import annotations

from dataclasses import dataclass

from ran.contracts import AgentIntent, Position
from ran.contracts.ue import SelectedAccess


@dataclass(frozen=True, slots=True)
class AgentScenarioDefinition:
    """Definition of a single Agent, UE, and optional initial Intent, frozen at scenario setup."""

    agent_id: str  # agent_id: global identifier of the Agent.
    ue_id: str  # ue_id: identifier of the UE this Agent uses by default.
    intent: AgentIntent | None = None  # intent: initial intent submitted at scenario start; when None, the runtime submits intents dynamically via submit_intent.
    selected_access: SelectedAccess = "5g"  # selected_access: V1 defaults to 5G.


@dataclass(frozen=True, slots=True)
class RanScenarioDefinition:
    """Immutable scenario definition; the total Agent count is fixed by the agents tuple at instance creation."""

    simulation_id: str  # simulation_id: global identifier of one simulation run.
    agents: tuple[AgentScenarioDefinition, ...]  # agents: fixed set of Agents in the scenario.

    def __post_init__(self) -> None:
        if not self.simulation_id:
            raise ValueError("simulation_id must not be empty")
        if not self.agents:
            raise ValueError("A RAN scenario must contain at least one agent")

        agent_ids = [item.agent_id for item in self.agents]
        ue_ids = [item.ue_id for item in self.agents]
        intent_ids = [item.intent.intent_id for item in self.agents if item.intent is not None]
        _require_unique("agent_id", agent_ids)
        _require_unique("ue_id", ue_ids)
        _require_unique("intent_id", intent_ids)
        for item in self.agents:
            if item.intent is None:
                continue
            if item.intent.agent_id != item.agent_id:
                raise ValueError(
                    f"Intent {item.intent.intent_id!r} belongs to {item.intent.agent_id!r}, "
                    f"not scenario agent {item.agent_id!r}"
                )
            if item.intent.requested_payload_bytes <= 0:
                raise ValueError(f"Intent {item.intent.intent_id!r} must request positive payload bytes")

    @property
    def agent_count(self) -> int:
        """Return the number of Agents frozen at scenario setup."""

        return len(self.agents)


def build_default_three_agent_definition() -> RanScenarioDefinition:
    """Build the three static Agents and three service types used by the current end-to-end tests."""

    definitions = (
        AgentScenarioDefinition(
            agent_id="student_a",
            ue_id="student_a_phone",
            intent=AgentIntent(
                intent_id="intent_video_upload_001",
                agent_id="student_a",
                agent_pos=Position(520.0, 430.0),
                action="upload",
                target="youtube_server",
                content_type="video",
                service_type="video_upload",
                requested_payload_bytes=100 * 1024 * 1024,
            ),
        ),
        AgentScenarioDefinition(
            agent_id="student_b",
            ue_id="student_b_phone",
            intent=AgentIntent(
                intent_id="intent_chat_message_001",
                agent_id="student_b",
                agent_pos=Position(340.0, 300.0),
                action="send_message",
                target="chat_server",
                content_type="text",
                service_type="message",
                requested_payload_bytes=4 * 1024,
            ),
        ),
        AgentScenarioDefinition(
            agent_id="student_c",
            ue_id="student_c_phone",
            intent=AgentIntent(
                intent_id="intent_voice_upload_001",
                agent_id="student_c",
                agent_pos=Position(200.0, 480.0),
                action="upload",
                target="video_call_server",
                content_type="video",
                service_type="video_call",
                requested_payload_bytes=1 * 1024 * 1024,
            ),
        ),
    )
    return RanScenarioDefinition(simulation_id="ran_multi_agent_demo_001", agents=definitions)


def _require_unique(field_name: str, values: list[str]) -> None:
    if any(not value for value in values):
        raise ValueError(f"{field_name} must not be empty")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} values must be unique")


def build_runtime_agent_definition(
    simulation_id: str,
    agents: list[tuple[str, str]],
) -> RanScenarioDefinition:
    """Build a scenario definition without initial intents; intents are submitted dynamically by the runtime via submit_intent.

    agents: (agent_id, ue_id) list, frozen after scenario setup.
    """
    definitions = tuple(
        AgentScenarioDefinition(agent_id=agent_id, ue_id=ue_id, intent=None)
        for agent_id, ue_id in agents
    )
    return RanScenarioDefinition(simulation_id=simulation_id, agents=definitions)

