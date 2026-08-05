from __future__ import annotations

from dataclasses import dataclass, field

from .common import Direction, Position


@dataclass(slots=True)
class GnbSite:
    """Project implementation detail."""

    gnb_id: str
    position: Position
    carrier_freq_mhz: float
    bandwidth_mhz: float
    tx_power_dbm: float
    total_prbs: int
    antenna_elements: int
    mimo_layers: int


@dataclass(slots=True)
class ChannelState:
    """Project implementation detail."""

    tick: int
    ue_id: str
    gnb_id: str
    direction: Direction
    distance_m: float
    ue_area_id: str | None
    ue_space_type: str  # ue_space_type: indoor/outdoor。
    walls_crossed: list[str] = field(default_factory=list)
    wall_loss_db: float = 0.0
    total_path_loss_db: float = 0.0
    received_power_dbm: float = 0.0
    sinr_db: float = 0.0
    cqi: int = 1
    estimated_packet_error_rate: float = 0.0


@dataclass(slots=True)
class MacAllocation:
    """Scheduler 为一个 UE DRB 返回的 MAC 资源分配。"""

    allocation_id: str  # allocation_id: 全局可追踪的分配标识。
    ue_id: str
    drb_id: int
    qfi: int  # qfi: QoS Flow。
    slice_id: str
    direction: Direction
    prbs: int
    mcs: int
    layers: int
    scheduled_bytes: int
    expected_error_rate: float
    is_retransmission: bool = False


@dataclass(slots=True)
class TransmissionResult:
    """Project implementation detail."""

    tick: int
    ue_id: str
    gnb_id: str
    drb_id: int
    qfi: int  # qfi: QoS Flow。
    slice_id: str
    direction: Direction
    attempted_bytes: int
    successful_bytes: int
    failed_bytes: int
    effective_sinr_db: float
    mcs: int
    prbs: int
    layers: int
    harq_ack: bool
    harq_retx_bytes: int
    rlc_retx_bytes: int
    dropped_bytes: int
    transmission_delay_ms: float
