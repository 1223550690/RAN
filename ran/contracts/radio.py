from __future__ import annotations

from dataclasses import dataclass, field

from .common import Direction, Position


@dataclass(slots=True)
class GnbSite:
    """Project implementation detail.

    输入字段:
    - 主要来自地图编辑器中的 gnb_001 element.state_details。

    输出用途:
    - ChannelModel、OFDM/PHY、scheduler 资源总量使用。
    """

    gnb_id: str  # gnb_id: 基站标识。
    position: Position  # position: 基站在地图中的全局坐标。
    carrier_freq_mhz: float  # carrier_freq_mhz: 载波频率。
    bandwidth_mhz: float  # bandwidth_mhz: 带宽。
    tx_power_dbm: float  # tx_power_dbm: 发射功率。
    total_prbs: int  # total_prbs: 当前载波可用 PRB 总数。
    antenna_elements: int  # antenna_elements: 天线阵元数，MVP 只用于简化增益。
    mimo_layers: int  # mimo_layers: 最大 MIMO 层数。
    nominal_pusch: int
    gscn: int


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
    slice_id: str  # slice_id: 切片标识。
    direction: Direction  # direction: UL 或 DL。
    attempted_bytes: int  # attempted_bytes: 尝试发送字节。
    successful_bytes: int  # successful_bytes: 成功送达无线接收端字节。
    failed_bytes: int  # failed_bytes: 无线失败字节。
    effective_sinr_db: float  # effective_sinr_db: 本次有效 SINR。
    mcs: int  # mcs: 使用 MCS。
    prbs: int  # prbs: 使用 PRB。
    layers: int  # layers: 使用 MIMO 层数。
    harq_ack: bool  # harq_ack: 是否无需 HARQ 重传。
    harq_retx_bytes: int  # harq_retx_bytes: 进入 HARQ 快速重传字节。
    rlc_retx_bytes: int  # rlc_retx_bytes: 进入 RLC 重传字节。
    dropped_bytes: int  # dropped_bytes: 最终丢弃字节。
    transmission_delay_ms: float  # transmission_delay_ms: PHY/MAC 基础时延。
    power_report: float
