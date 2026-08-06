"""RAN intent gateway: converts AgentPlan into AgentIntent and submits it to MultiAgentRanScenario.

Traffic-volume conversion rules (P1, consistent with the Q2 decision):
- video_upload / file_transfer: bytes mapped from size_profile; service ends by data volume.
- video_call: bytes derived from duration_seconds x bitrate_kbps, while keeping duration_seconds
  and the real-time qos_hint; the RAN side still advances by byte conservation, without extending the service contract.
- message: fixed small byte count.
"""

from __future__ import annotations

from ran.contracts import AgentIntent, Position

from ..contracts import AgentPlan

# Default intent profiles; can be overridden via configs/agents/intent_profiles.json.
DEFAULT_INTENT_PROFILES: dict = {
    "video_upload": {
        "size_profiles": {"small": 20 * 1024 * 1024, "medium": 100 * 1024 * 1024, "large": 500 * 1024 * 1024},
        "target": "youtube_server",
        "content_type": "video",
        "action": "upload",
        "direction": "UL",
    },
    "video_download": {
        "size_profiles": {"small": 20 * 1024 * 1024, "medium": 100 * 1024 * 1024, "large": 500 * 1024 * 1024},
        "target": "video_server",
        "content_type": "video",
        "action": "download",
        "direction": "DL",
    },
    "file_transfer": {
        "size_profiles": {"small": 10 * 1024 * 1024, "medium": 50 * 1024 * 1024, "large": 200 * 1024 * 1024},
        "target": "file_server",
        "content_type": "file",
        "action": "upload",
        "direction": "UL",
    },
    "video_call": {
        "target": "video_call_server",
        "content_type": "video",
        "action": "video_call",
        "direction": "UL",
        "qos_hint": {"latency_budget_ms": 150, "reliability": "high", "throughput_preference": "high"},
    },
    "message": {
        "fixed_bytes": 4 * 1024,
        "target": "chat_server",
        "content_type": "text",
        "action": "send_message",
        "direction": "UL",
    },
    "web_browse": {
        "size_profiles": {"small": 2 * 1024 * 1024, "medium": 10 * 1024 * 1024, "large": 50 * 1024 * 1024},
        "target": "web_server",
        "content_type": "web",
        "action": "browse",
        "direction": "DL",
        "qos_hint": {"latency_budget_ms": 500, "reliability": "normal", "throughput_preference": "low"},
    },
    "gaming": {
        "size_profiles": {"small": 5 * 1024 * 1024, "medium": 20 * 1024 * 1024, "large": 100 * 1024 * 1024},
        "target": "gaming_server",
        "content_type": "game",
        "action": "play",
        "direction": "DL",
        "qos_hint": {"latency_budget_ms": 80, "reliability": "high", "throughput_preference": "high"},
    },
}


class RanIntentGateway:
    def __init__(self, scenario, intent_profiles: dict | None = None) -> None:
        self.scenario = scenario
        self.intent_profiles = {**DEFAULT_INTENT_PROFILES, **(intent_profiles or {})}
        self._counter = 0

    def submit(
        self,
        *,
        agent_id: str,
        plan: AgentPlan,
        position: tuple[float, float],
        tick: int,
        ue_id: str,
    ) -> str:
        """Convert the semantic plan into an AgentIntent and submit it; returns service_instance_id."""

        intent = self._build_intent(agent_id, plan, position, tick)
        service_instance_id = self.scenario.submit_intent(
            intent,
            selected_access="5g",
        )
        return service_instance_id

    def _build_intent(
        self,
        agent_id: str,
        plan: AgentPlan,
        position: tuple[float, float],
        tick: int,
    ) -> AgentIntent:
        profile = self.intent_profiles.get(plan.intent_type)
        if profile is None:
            raise ValueError(f"unknown intent_type: {plan.intent_type!r}")
        self._counter += 1
        intent_id = f"intent_{agent_id}_{tick}_{self._counter}"
        parameters = plan.intent_parameters or {}

        if plan.intent_type == "video_call":
            duration = float(parameters.get("duration_seconds", 30))
            bitrate_kbps = float(parameters.get("bitrate_kbps", 2048))
            payload_bytes = max(1, int(duration * bitrate_kbps * 1000 / 8))
            return AgentIntent(
                intent_id=intent_id,
                agent_id=agent_id,
                agent_pos=Position(position[0], position[1]),
                action=str(profile.get("action", "video_call")),
                target=str(profile.get("target", "video_call_server")),
                content_type=str(profile.get("content_type", "video")),
                service_type="video_call",
                requested_payload_bytes=payload_bytes,
                created_tick=tick,
                duration_seconds=duration,
                qos_hint=dict(profile.get("qos_hint", {})),
                direction=str(profile.get("direction", "UL")),
            )

        if plan.intent_type == "message":
            payload_bytes = int(profile.get("fixed_bytes", 4 * 1024))
            return AgentIntent(
                intent_id=intent_id,
                agent_id=agent_id,
                agent_pos=Position(position[0], position[1]),
                action=str(profile.get("action", "send_message")),
                target=str(profile.get("target", "chat_server")),
                content_type=str(profile.get("content_type", "text")),
                service_type="message",
                requested_payload_bytes=payload_bytes,
                created_tick=tick,
                direction=str(profile.get("direction", "UL")),
            )

        size_profiles = profile.get("size_profiles", {})
        size_profile = str(parameters.get("size_profile", "medium"))
        payload_bytes = int(size_profiles.get(size_profile, size_profiles.get("medium", 100 * 1024 * 1024)))
        return AgentIntent(
            intent_id=intent_id,
            agent_id=agent_id,
            agent_pos=Position(position[0], position[1]),
            action=str(profile.get("action", "upload")),
            target=str(profile.get("target", "server")),
            content_type=str(profile.get("content_type", "data")),
            service_type=plan.intent_type,
            requested_payload_bytes=payload_bytes,
            created_tick=tick,
            direction=str(profile.get("direction", "UL")),
        )
