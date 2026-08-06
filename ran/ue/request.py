from __future__ import annotations

from ran.contracts import AgentIntent, UERequest


def build_ue_request(
    intent: AgentIntent,
    *,
    ue_id: str,
    service_instance_id: str,
    selected_access: str = "5g",
) -> UERequest:
    """Convert an AgentIntent into a UERequest with full service identity."""

    access_type = "non_3gpp" if selected_access == "wifi" else "3gpp"
    qos_hint = dict(intent.qos_hint) if intent.qos_hint else {
        "latency_budget_ms": 10000,
        "reliability": "normal",
        "throughput_preference": "high",
    }
    return UERequest(
        intent_id=intent.intent_id,
        service_instance_id=service_instance_id,
        ue_id=ue_id,
        agent_id=intent.agent_id,
        position=intent.agent_pos,
        direction=intent.direction,
        selected_access=selected_access,  # type: ignore[arg-type]
        access_type=access_type,  # type: ignore[arg-type]
        target=intent.target,
        dnn="internet",
        pdu_session_type="IPv4",
        service_type=intent.service_type,
        requested_payload_bytes=intent.requested_payload_bytes,
        qos_hint=qos_hint,
    )
