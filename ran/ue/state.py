from __future__ import annotations

from ran.contracts import Position, UEState, ApplicationManager


def build_demo_ue_state(*, agent_id: str, ue_id: str, position: Position) -> UEState:
    """Project implementation detail."""

    return UEState(
        ue_id=ue_id,
        agent_id=agent_id,
        position=position,
        allowed_slices=["embb", "urllc", "mmtc"],
        cmax_transmit = 23,
        ue_pusch = 0,
        signalBuffer = [],
        applicationLayer= ApplicationManager()
    )
