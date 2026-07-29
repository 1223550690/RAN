from __future__ import annotations

import math
from dataclasses import dataclass, field
from ipaddress import ip_address

from .common import Direction


@dataclass(slots=True)
class IPTrafficBatch:
    """Application payload represented as an IP traffic flow.

    ``total_bytes`` and ``remaining_bytes`` are application payload bytes.
    Packet counts and IP/transport overhead remain available through computed
    properties so later PDCP/RLC and metrics work can retain both byte- and
    packet-level evidence without materialising millions of packet objects.
    """

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
    ip_header_bytes: int = 20
    transport_header_bytes: int = 20
    src_port: int | None = None

    def __post_init__(self) -> None:
        if not self.service_id:
            raise ValueError("service_id must not be empty")
        try:
            src_version = ip_address(self.src_ip).version
            dst_version = ip_address(self.dst_ip).version
        except ValueError as exc:
            raise ValueError("src_ip and dst_ip must be valid IP addresses") from exc
        if src_version != dst_version:
            raise ValueError("src_ip and dst_ip must use the same IP version")
        if self.protocol not in {"TCP", "UDP"}:
            raise ValueError("protocol must be TCP or UDP")
        if not 1 <= self.dst_port <= 65535:
            raise ValueError("dst_port must be in the range 1..65535")
        if self.src_port is not None and not 1 <= self.src_port <= 65535:
            raise ValueError("src_port must be in the range 1..65535 when provided")
        if self.total_bytes <= 0:
            raise ValueError("total_bytes must be positive")
        if not 0 <= self.remaining_bytes <= self.total_bytes:
            raise ValueError("remaining_bytes must be between 0 and total_bytes")
        if self.ip_header_bytes <= 0 or self.transport_header_bytes <= 0:
            raise ValueError("header sizes must be positive")
        if self.nominal_packet_size <= self.header_bytes:
            raise ValueError("nominal_packet_size must exceed combined header bytes")

    @property
    def header_bytes(self) -> int:
        return self.ip_header_bytes + self.transport_header_bytes

    @property
    def payload_bytes_per_packet(self) -> int:
        return self.nominal_packet_size - self.header_bytes

    @property
    def packet_count(self) -> int:
        return math.ceil(self.total_bytes / self.payload_bytes_per_packet)

    @property
    def remaining_packet_count(self) -> int:
        return math.ceil(self.remaining_bytes / self.payload_bytes_per_packet) if self.remaining_bytes else 0

    @property
    def network_bytes(self) -> int:
        return self.total_bytes + self.packet_count * self.header_bytes

    def take_payload(self, max_bytes: int) -> int:
        """Consume at most ``max_bytes`` of application payload."""

        if max_bytes < 0:
            raise ValueError("max_bytes must not be negative")
        consumed = min(self.remaining_bytes, max_bytes)
        self.remaining_bytes -= consumed
        return consumed
