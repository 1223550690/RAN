from __future__ import annotations

from dataclasses import dataclass, field

from .common import Direction


@dataclass(slots=True)
class IPTrafficBatch:
    """IP 业务批次。

    输入字段:
    - UERequest 与 PduSession。

    输出字段:
    - total_bytes/remaining_bytes: MVP 不逐包建模，按批次推进。
    - metadata: 保留 UE、DNN、slice、PDU session 等上下文。
    """

    service_id: str  # service_id: 本次业务批次标识。
    src_ip: str  # src_ip: UE IP。
    dst_ip: str  # dst_ip: 目标服务 IP 或模拟地址。
    protocol: str  # protocol: TCP/UDP。
    dst_port: int  # dst_port: 目标端口。
    direction: Direction  # direction: UL 或 DL。
    total_bytes: int  # total_bytes: 业务总字节数。
    remaining_bytes: int  # remaining_bytes: 尚未送达的字节数。
    nominal_packet_size: int = 1500  # nominal_packet_size: 名义 IP 包大小。
    metadata: dict[str, object] = field(default_factory=dict)  # metadata: 业务上下文。
