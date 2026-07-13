from __future__ import annotations

from dataclasses import dataclass, field

from .common import Direction


@dataclass(slots=True)
class IPTrafficBatch:
    """Project implementation detail."""

    service_id: str
    src_ip: str  # src_ip: UE IP。
    dst_ip: str
    protocol: str  # protocol: TCP/UDP。
    dst_port: int
    direction: Direction
    total_bytes: int
    remaining_bytes: int
    nominal_packet_size: int = 1500
    metadata: dict[str, object] = field(default_factory=dict)
