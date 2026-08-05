from __future__ import annotations

from ran.contracts import UEState


def register_ue(ue: UEState) -> UEState:
    """Register a UE and update its registration state."""

    if not ue.ue_id.strip():
        raise ValueError("UE ID cannot be empty.")

    if not ue.agent_id.strip():
        raise ValueError("Agent ID cannot be empty.")

    if ue.rm_state == "REGISTERED":
        return ue

    if ue.rm_state != "DEREGISTERED":
        raise ValueError(
            f"Invalid RM state before registration: {ue.rm_state}"
        )

    ue.rm_state = "REGISTERED"
    ue.cm_state = "CONNECTED"
    ue.rrc_state = "CONNECTED"

    return ue
