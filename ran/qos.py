from __future__ import annotations

from ran.contracts import PduSession, QoSFlow, UERequest
from ran.traffic.service_profile import service_profile_for


def build_qos_flow(request: UERequest, session: PduSession) -> QoSFlow:
    """Project implementation detail."""

    profile = service_profile_for(request.service_type)
    return QoSFlow(
        pdu_session_id=session.pdu_session_id,
        qfi=int(profile["qfi"]),
        five_qi=int(profile["five_qi"]),
        direction=request.direction,
        service_type=request.service_type,
        priority=int(profile["priority"]),
        packet_delay_budget_ms=float(profile["packet_delay_budget_ms"]),
        packet_error_rate=float(profile["packet_error_rate"]),
        resource_type=str(profile["resource_type"]),
        slice_id=str(profile["slice_id"]),
    )
