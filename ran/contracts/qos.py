from __future__ import annotations

from dataclasses import dataclass

from .common import Direction


@dataclass(slots=True)
class PduSession:
    """PDU Session。

    输入字段:
    - UERequest 中的 dnn/pdu_session_type/slice_id。

    输出字段:
    - ue_ip/upf_id/state: 后续 IP traffic 与 UPF 转发使用。
    """

    pdu_session_id: int  # pdu_session_id: PDU 会话 ID。
    ue_id: str  # ue_id: 所属 UE。
    dnn: str  # dnn: 目标数据网络。
    slice_id: str  # slice_id: S-NSSAI 的 MVP 简化字段。
    pdu_session_type: str  # pdu_session_type: IPv4/IPv6/IPv4v6。
    ue_ip: str  # ue_ip: 分配给 UE 的 IP。
    smf_id: str  # smf_id: 会话管理功能标识。
    upf_id: str  # upf_id: 用户面功能标识。
    state: str = "ACTIVE"  # state: 会话状态。


@dataclass(slots=True)
class QoSFlow:
    """QoS Flow。

    输入字段:
    - service_type/qos_hint 和 service profile。

    输出字段:
    - qfi/five_qi/priority/delay_budget: SDAP、scheduler 和 QoS 统计使用。
    """

    pdu_session_id: int  # pdu_session_id: 所属 PDU Session。
    qfi: int  # qfi: QoS Flow Identifier。
    five_qi: int  # five_qi: 5G QoS Identifier 模板。
    direction: Direction  # direction: UL 或 DL。
    service_type: str  # service_type: 业务类型。
    priority: int  # priority: 数字越小优先级越高。
    packet_delay_budget_ms: float  # packet_delay_budget_ms: 包时延预算。
    packet_error_rate: float  # packet_error_rate: 目标错误率。
    resource_type: str  # resource_type: gbr 或 non_gbr。
    slice_id: str  # slice_id: 关联网络切片。
    gbr_mbps: float | None = None  # gbr_mbps: 保证速率，非 GBR 可为空。
    mbr_mbps: float | None = None  # mbr_mbps: 最大速率，可为空。


@dataclass(slots=True)
class SlicePolicy:
    """切片策略。

    输入字段:
    - 由 slicing policy 或未来 AI controller 产生。

    输出用途:
    - 作为 scheduler 的策略约束，而不是独立传输层。
    """

    slice_id: str  # slice_id: 切片标识。
    priority: int  # priority: 切片优先级，数字越小越高。
    min_prb_ratio: float  # min_prb_ratio: PRB 保底比例。
    max_prb_ratio: float  # max_prb_ratio: PRB 上限比例。
    delay_budget_ms: float  # delay_budget_ms: 切片时延目标。
