from __future__ import annotations

from dataclasses import dataclass, field

from .common import Direction


@dataclass(slots=True)
class Drb:
    """A Data Radio Bearer and its SDAP mapping evidence."""

    drb_id: int
    ue_id: str
    pdu_session_id: int
    qfi: int
    slice_id: str
    direction: Direction
    rlc_mode: str  # rlc_mode: TM/UM/AM。
    priority: int
    qfi_list: list[int] = field(default_factory=list)
    default_drb: bool = False
    sdap_header_present: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.drb_id <= 32:
            raise ValueError("drb_id must be in the range 1..32")
        if not 1 <= self.qfi <= 63:
            raise ValueError("qfi must be in the range 1..63")
        if self.rlc_mode not in {"TM", "UM", "AM"}:
            raise ValueError("rlc_mode must be TM, UM, or AM")
        if not self.qfi_list:
            self.qfi_list.append(self.qfi)
        elif self.qfi not in self.qfi_list:
            self.qfi_list.insert(0, self.qfi)
        if any(not 1 <= qfi <= 63 for qfi in self.qfi_list):
            raise ValueError("every qfi_list entry must be in the range 1..63")
        self.qfi_list[:] = list(dict.fromkeys(self.qfi_list))


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
