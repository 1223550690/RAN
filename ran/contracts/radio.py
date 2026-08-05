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
    channel_model_mode: str = "legacy"
    path_loss_model: str = "legacy"
    path_loss_formula_id: str = "legacy_fspl_plus_raw_wall_loss"
    evaluated_path_loss_model: str | None = None
    evaluated_total_path_loss_db: float | None = None
    evaluated_formula_id: str | None = None
    link_type: str = "unknown"
    los_state: str = "unknown"
    map_distance_units: float | None = None
    distance_2d_m: float | None = None
    distance_3d_m: float | None = None
    outdoor_distance_m: float | None = None
    indoor_distance_m: float | None = None
    effective_walls_crossed: list[str] = field(default_factory=list)
    portals_crossed: list[str] = field(default_factory=list)
    external_wall_loss_db: float | None = None
    indoor_loss_db: float | None = None
    shadow_fading_std_db: float | None = None
    penetration_loss_std_db: float | None = None
    is_extrapolated: bool = False
    path_loss_warnings: list[str] = field(default_factory=list)
    fallback_reason: str | None = None
    calibration_id: str | None = None
    calibration_status: str | None = None
    meters_per_map_unit_x: float | None = None
    meters_per_map_unit_y: float | None = None
    bs_height_m: float | None = None
    bs_height_source: str | None = None
    bs_height_status: str | None = None
    ut_height_m: float | None = None
    ut_height_source: str | None = None
    ut_height_status: str | None = None
    height_reference: str | None = None
    penetration_model: str | None = None
    penetration_model_source: str | None = None
    penetration_model_status: str | None = None


@dataclass(slots=True)
class MacAllocation:
    """Scheduler 为一个 UE DRB 返回的 MAC 资源分配。"""

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
    allocation_id: str = ""  # allocation_id: 全局可追踪的分配标识(可选,向后兼容旧构造)。


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
