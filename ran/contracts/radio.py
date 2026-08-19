from __future__ import annotations

from dataclasses import dataclass, field

from .common import Direction, Position
from typing import Literal



@dataclass(slots=True)
class GnbSite:
    """Project implementation detail.

    Input fields:
    - Mainly from the gnb_001 element.state_details in the map editor.

    Output usage:
    - Consumed by ChannelModel, OFDM/PHY, and scheduler resource totals.
    """

    gnb_id: str  # gnb_id: base station identifier.
    position: Position  # position: global coordinates of the base station on the map.
    carrier_freq_mhz: float  # carrier_freq_mhz: carrier frequency.
    bandwidth_mhz: float  # bandwidth_mhz: bandwidth.
    tx_power_dbm: float  # tx_power_dbm: transmit power.
    total_prbs: int  # total_prbs: total PRBs available on the current carrier.
    antenna_elements: int  # antenna_elements: number of antenna elements; MVP uses it only for simplified gain.
    mimo_layers: int  # mimo_layers: maximum number of MIMO layers.
    nominal_pusch: int = 0  # nominal_pusch: nominal PUSCH transmit power (tr22068 extension, optional).
    gscn: int = 0  # gscn: GSCN frequency point (tr22068 extension, optional).


@dataclass(slots=True)
class ChannelState:
    """Project implementation detail."""

    tick: int
    ue_id: str
    gnb_id: str
    direction: Direction
    distance_m: float
    ue_area_id: str | None
    ue_space_type: str  # ue_space_type: indoor/outdoor.
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
    prediction_std_db: float | None = None  # prediction_std_db: hybrid CKM prediction uncertainty (hybrid mode).
    beam_id: str | None = None  # beam_id: selected beam (hybrid mode).
    beam_gain_db: float = 0.0  # beam_gain_db: beam directional gain (hybrid mode).
    beam_azimuth_deg: float | None = None  # beam_azimuth_deg: azimuth of the selected beam.
    beam_margin_db: float | None = None  # beam_margin_db: gain difference between the first/second beam.
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
    """MAC resource allocation returned by the Scheduler for one UE DRB."""

    ue_id: str
    drb_id: int
    qfi: int  # qfi: QoS Flow.
    slice_id: str
    direction: Direction
    prbs: int
    mcs: int
    layers: int
    scheduled_bytes: int
    expected_error_rate: float
    is_retransmission: bool = False
    allocation_id: str = ""  # allocation_id: globally traceable allocation identifier (optional, backward compatible with legacy constructors).


@dataclass(slots=True)
class TransmissionResult:
    """Project implementation detail."""

    tick: int
    ue_id: str
    gnb_id: str
    drb_id: int
    qfi: int  # qfi: QoS Flow.
    slice_id: str  # slice_id: slice identifier.
    direction: Direction  # direction: UL or DL.
    attempted_bytes: int  # attempted_bytes: bytes attempted to send.
    successful_bytes: int  # successful_bytes: bytes successfully delivered to the radio receiver.
    failed_bytes: int  # failed_bytes: bytes failed over the radio.
    effective_sinr_db: float  # effective_sinr_db: effective SINR of this transmission.
    mcs: int  # mcs: MCS used.
    prbs: int  # prbs: PRBs used.
    layers: int  # layers: MIMO layers used.
    harq_ack: bool  # harq_ack: whether no HARQ retransmission is needed.
    harq_retx_bytes: int  # harq_retx_bytes: bytes entering HARQ fast retransmission.
    rlc_retx_bytes: int  # rlc_retx_bytes: bytes entering RLC retransmission.
    dropped_bytes: int  # dropped_bytes: bytes finally dropped.
    transmission_delay_ms: float  # transmission_delay_ms: base PHY/MAC latency.
    power_report: float = 0.0  # power_report: UE power headroom (tr22068 extension, optional).

@dataclass(slots=True)
class SignalPayload:
    data:str
    service_type: str
    destinationUe:str = None
    senderUe:str = None
    endOfMessage: bool = False



@dataclass(slots=True)
class SignalHeader:
    senderIp: str
    destinationIp:str
    size: int
    sessionId: int
    

@dataclass(slots=True)
class Signal:
    tickSent: int
    estimatedArrivalTick: int
    arrived: bool
    direction: Direction  # direction: UL or DL.
    ticksInTransit: int
    payload: SignalPayload
    header: SignalHeader



