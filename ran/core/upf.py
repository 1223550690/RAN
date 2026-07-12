from __future__ import annotations

from ran.contracts import N3ForwardingResult, N6DeliveryResult, PduSession


def forward_via_upf(n3_result: N3ForwardingResult, session: PduSession, *, target: str) -> N6DeliveryResult:
    """Project implementation detail."""

    return N6DeliveryResult(
        dnn=session.dnn,
        target=target,
        delivered_bytes=n3_result.forwarded_bytes,
        n6_delay_ms=8.0,
        n6_loss_bytes=0,
    )
