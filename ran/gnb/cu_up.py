from __future__ import annotations

from ran.contracts import N3ForwardingResult, PduSession, TransmissionResult


def forward_to_n3(result: TransmissionResult, session: PduSession) -> N3ForwardingResult:
    """Project implementation detail."""

    return N3ForwardingResult(
        tunnel_id=f"n3_tunnel_{session.pdu_session_id}",
        teid=1000 + session.pdu_session_id,
        ue_id=session.ue_id,
        pdu_session_id=session.pdu_session_id,
        upf_id=session.upf_id,
        forwarded_bytes=result.successful_bytes,
        n3_delay_ms=2.0,
        n3_loss_bytes=0,
    )
