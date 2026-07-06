from __future__ import annotations

from dataclasses import dataclass, field

from .common import Direction, Position


@dataclass(slots=True)
class GnbSite:
    """gNB 站点与天线配置。

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


@dataclass(slots=True)
class ChannelState:
    """信道状态。

    输入字段:
    - UE 位置、gNB 位置、地图墙体查询结果。

    输出字段:
    - sinr/cqi/error_rate 供 scheduler 和 PHY 使用。
    """

    tick: int  # tick: 当前仿真 tick。
    ue_id: str  # ue_id: UE 标识。
    gnb_id: str  # gnb_id: 服务 gNB。
    direction: Direction  # direction: UL 或 DL。
    distance_m: float  # distance_m: UE 与 gNB 距离。
    ue_area_id: str | None  # ue_area_id: UE 所在区域。
    ue_space_type: str  # ue_space_type: indoor/outdoor。
    walls_crossed: list[str] = field(default_factory=list)  # walls_crossed: 穿过墙体 ID。
    wall_loss_db: float = 0.0  # wall_loss_db: 墙体穿透损耗。
    total_path_loss_db: float = 0.0  # total_path_loss_db: 总路径损耗。
    received_power_dbm: float = 0.0  # received_power_dbm: 接收功率。
    sinr_db: float = 0.0  # sinr_db: 信干噪比。
    cqi: int = 1  # cqi: 信道质量指示 1-15。
    estimated_packet_error_rate: float = 0.0  # estimated_packet_error_rate: 估计包错误率。


@dataclass(slots=True)
class MacAllocation:
    """MAC 调度结果。

    输入字段:
    - SchedulerResult。

    输出用途:
    - PHY/OFDM 计算本 tick 尝试发送、成功、失败字节。
    """

    ue_id: str  # ue_id: 被调度 UE。
    drb_id: int  # drb_id: 被调度 DRB。
    qfi: int  # qfi: QoS Flow。
    slice_id: str  # slice_id: 切片标识。
    direction: Direction  # direction: UL 或 DL。
    prbs: int  # prbs: 分配 PRB 数。
    mcs: int  # mcs: 调制编码等级。
    layers: int  # layers: MIMO 层数。
    scheduled_bytes: int  # scheduled_bytes: 调度器预计发送字节。
    expected_error_rate: float  # expected_error_rate: 预计错误率。
    is_retransmission: bool = False  # is_retransmission: 是否重传调度。


@dataclass(slots=True)
class TransmissionResult:
    """PHY 传输结果。

    输入字段:
    - MACAllocation + ChannelState。

    输出字段:
    - successful/failed/dropped bytes 供 RLC、N3、QoS 统计使用。
    """

    tick: int  # tick: 当前 tick。
    ue_id: str  # ue_id: UE 标识。
    gnb_id: str  # gnb_id: gNB 标识。
    drb_id: int  # drb_id: DRB 标识。
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
