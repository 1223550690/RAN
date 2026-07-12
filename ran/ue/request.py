from __future__ import annotations

from ran.contracts import AgentIntent, UERequest


def build_ue_request(intent: AgentIntent, *, ue_id: str, selected_access: str = "5g") -> UERequest:
    """Project implementation detail."""

    access_type = "non_3gpp" if selected_access == "wifi" else "3gpp"
    return UERequest(
        ue_id=ue_id,
        agent_id=intent.agent_id,
        position=intent.agent_pos,
        direction="UL",
        selected_access=selected_access,  # type: ignore[arg-type]
        access_type=access_type,  # type: ignore[arg-type]
        target=intent.target,
        dnn="internet",
        pdu_session_type="IPv4",
        service_type="video_upload" if intent.action == "upload" else intent.action,
        size_bytes=intent.size_bytes,
        qos_hint={
            "latency_budget_ms": 10000,
            "reliability": "normal",
            "throughput_preference": "high",
        },
    )
