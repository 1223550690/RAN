from __future__ import annotations

from ran.contracts import UEState


def register_ue(ue: UEState) -> UEState:
    """Project implementation detail."""

    ue.rm_state = "REGISTERED"
    ue.cm_state = "CONNECTED"
    ue.rrc_state = "CONNECTED"
    return ue
