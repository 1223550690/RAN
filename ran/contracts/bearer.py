from __future__ import annotations

from dataclasses import dataclass

from .common import Direction


@dataclass(slots=True)
class Drb:
    """Project implementation detail."""

    drb_id: int
    ue_id: str
    pdu_session_id: int
    qfi: int
    slice_id: str
    direction: Direction
    rlc_mode: str  # rlc_mode: TM/UM/AM。
    priority: int


@dataclass(slots=True)
class RlcQueue:
    """Project implementation detail."""

    ue_id: str
    drb_id: int
    qfi: int
    slice_id: str
    direction: Direction
    rlc_mode: str
    queued_bytes: int
    retransmission_bytes: int
    head_of_line_delay_ms: float
