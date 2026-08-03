from __future__ import annotations

import json
import re
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from threading import RLock
from typing import Iterable

from ran.contracts import IPTrafficBatch, PduSession, UERequest


class IPTrafficError(ValueError):
    """Raised when an IP flow cannot be constructed safely."""


@dataclass(frozen=True, slots=True)
class EndpointProfile:
    """A deterministic Data Network endpoint used by the simulation."""

    target: str
    dnn: str
    ip: str
    protocol: str
    port: int
    service_types: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.target or not self.dnn:
            raise ValueError("endpoint target and dnn must not be empty")
        ip_address(self.ip)
        if self.protocol not in {"TCP", "UDP"}:
            raise ValueError("endpoint protocol must be TCP or UDP")
        if not 1 <= self.port <= 65535:
            raise ValueError("endpoint port must be in the range 1..65535")

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> EndpointProfile:
        return cls(
            target=str(value["target"]),
            dnn=str(value["dnn"]),
            ip=str(value["ip"]),
            protocol=str(value["protocol"]).upper(),
            port=int(value["port"]),
            service_types=frozenset(str(item) for item in value.get("service_types", [])),
        )


DEFAULT_ENDPOINTS: tuple[EndpointProfile, ...] = (
    EndpointProfile(
        target="youtube_server",
        dnn="internet",
        ip="10.20.1.80",
        protocol="TCP",
        port=443,
        service_types=frozenset({"video_upload", "video_stream"}),
    ),
    EndpointProfile(
        target="web_server",
        dnn="internet",
        ip="10.20.1.10",
        protocol="TCP",
        port=443,
        service_types=frozenset({"web", "file_upload", "file_download"}),
    ),
    EndpointProfile(
        target="gaming_server",
        dnn="internet",
        ip="10.20.2.20",
        protocol="UDP",
        port=3074,
        service_types=frozenset({"game"}),
    ),
    EndpointProfile(
        target="message_server",
        dnn="internet",
        ip="10.20.3.30",
        protocol="TCP",
        port=443,
        service_types=frozenset({"message"}),
    ),
    EndpointProfile(
        target="video_call_server",
        dnn="internet",
        ip="10.20.4.40",
        protocol="UDP",
        port=3478,
        service_types=frozenset({"video_call", "voice_call", "live_video"}),
    ),
    EndpointProfile(
        target="campus_iot",
        dnn="campus",
        ip="10.30.1.20",
        protocol="UDP",
        port=5683,
        service_types=frozenset({"telemetry", "control"}),
    ),
)


class IPPacketFactory:
    """Build validated UL/DL IP flow batches from UE and PDU-session state."""

    def __init__(self, endpoints: Iterable[EndpointProfile] = DEFAULT_ENDPOINTS) -> None:
        endpoint_list = tuple(endpoints)
        endpoint_map = {endpoint.target: endpoint for endpoint in endpoint_list}
        if not endpoint_map:
            raise ValueError("at least one endpoint profile is required")
        if len(endpoint_map) != len(endpoint_list):
            raise ValueError("endpoint targets must be unique")
        self._endpoints = endpoint_map
        self._flow_ports: dict[tuple[str, int, str, str], int] = {}
        self._used_ports: dict[str, set[int]] = {}
        self._lock = RLock()

    @classmethod
    def from_json(cls, path: str | Path) -> IPPacketFactory:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(EndpointProfile.from_dict(item) for item in raw["endpoints"])

    def build(self, request: UERequest, session: PduSession) -> IPTrafficBatch:
        self._validate_request(request, session)
        endpoint = self._resolve_endpoint(request)
        ip_version = ip_address(session.ue_ip).version
        if ip_address(endpoint.ip).version != ip_version:
            raise IPTrafficError("endpoint and UE addresses must use the same IP version")

        ue_port = self._ue_port(request, session)
        if request.direction == "UL":
            src_ip, dst_ip = session.ue_ip, endpoint.ip
            src_port, dst_port = ue_port, endpoint.port
        else:
            src_ip, dst_ip = endpoint.ip, session.ue_ip
            src_port, dst_port = endpoint.port, ue_port

        ip_header_bytes = 20 if ip_version == 4 else 40
        transport_header_bytes = 20 if endpoint.protocol == "TCP" else 8
        service_id = self._service_id(request, session)
        metadata: dict[str, object] = {
            "ue_id": request.ue_id,
            "direction": request.direction,
            "dnn": request.dnn,
            "service_type": request.service_type,
            "target": request.target,
            "pdu_session_id": session.pdu_session_id,
            "slice_id": session.slice_id,
            "smf_id": session.smf_id,
            "upf_id": session.upf_id,
            "selected_access": request.selected_access,
            "access_type": request.access_type,
            "ip_version": ip_version,
            "server_port": endpoint.port,
        }
        traffic = IPTrafficBatch(
            service_id=service_id,
            src_ip=src_ip,
            dst_ip=dst_ip,
            protocol=endpoint.protocol,
            src_port=src_port,
            dst_port=dst_port,
            direction=request.direction,
            total_bytes=request.size_bytes,
            remaining_bytes=request.size_bytes,
            nominal_packet_size=1500,
            ip_header_bytes=ip_header_bytes,
            transport_header_bytes=transport_header_bytes,
            metadata=metadata,
        )
        traffic.metadata.update(
            {
                "packet_count": traffic.packet_count,
                "payload_bytes_per_packet": traffic.payload_bytes_per_packet,
                "network_bytes": traffic.network_bytes,
            }
        )
        return traffic

    def release_session(self, ue_id: str, pdu_session_id: int) -> None:
        """Release ephemeral ports owned by a completed PDU session."""

        with self._lock:
            released_ports = {
                port
                for key, port in self._flow_ports.items()
                if key[0] == ue_id and key[1] == pdu_session_id
            }
            self._flow_ports = {
                key: port
                for key, port in self._flow_ports.items()
                if not (key[0] == ue_id and key[1] == pdu_session_id)
            }
            used = self._used_ports.get(ue_id)
            if used is not None:
                used.difference_update(released_ports)
                if not used:
                    self._used_ports.pop(ue_id, None)

    def reset(self) -> None:
        """Clear runtime port allocation state."""

        with self._lock:
            self._flow_ports.clear()
            self._used_ports.clear()

    def _resolve_endpoint(self, request: UERequest) -> EndpointProfile:
        endpoint = self._endpoints.get(request.target)
        if endpoint is None:
            try:
                ip_address(request.target)
            except ValueError as exc:
                known = ", ".join(sorted(self._endpoints))
                raise IPTrafficError(f"unknown target {request.target!r}; configured targets: {known}") from exc
            protocol = "UDP" if request.service_type in {"game", "video_call", "voice_call", "telemetry"} else "TCP"
            port = 3478 if protocol == "UDP" else 443
            endpoint = EndpointProfile(
                target=request.target,
                dnn=request.dnn,
                ip=request.target,
                protocol=protocol,
                port=port,
            )
        if endpoint.dnn != request.dnn:
            raise IPTrafficError(
                f"target {endpoint.target!r} belongs to DNN {endpoint.dnn!r}, not {request.dnn!r}"
            )
        if endpoint.service_types and request.service_type not in endpoint.service_types:
            supported = ", ".join(sorted(endpoint.service_types))
            raise IPTrafficError(
                f"target {endpoint.target!r} does not support service {request.service_type!r}; "
                f"supported services: {supported}"
            )
        return endpoint

    @staticmethod
    def _validate_request(request: UERequest, session: PduSession) -> None:
        if session.state != "ACTIVE":
            raise IPTrafficError("IP traffic requires an ACTIVE PDU session")
        if request.ue_id != session.ue_id:
            raise IPTrafficError("UE request and PDU session refer to different UEs")
        if request.dnn != session.dnn:
            raise IPTrafficError("UE request and PDU session use different DNN values")
        if request.size_bytes <= 0:
            raise IPTrafficError("IP traffic size must be positive")

    @staticmethod
    def _service_id(request: UERequest, session: PduSession) -> str:
        safe_ue = re.sub(r"[^A-Za-z0-9_-]+", "_", request.ue_id).strip("_")
        safe_service = re.sub(r"[^A-Za-z0-9_-]+", "_", request.service_type).strip("_")
        safe_target = re.sub(r"[^A-Za-z0-9_-]+", "_", request.target).strip("_")
        return (
            f"{safe_ue}_{safe_service}_{session.pdu_session_id:03d}_"
            f"{request.direction.lower()}_{safe_target}"
        )

    def _ue_port(self, request: UERequest, session: PduSession) -> int:
        # Direction is deliberately excluded: UL and DL packets of one
        # connection use the same UE-side port.
        flow_key = (
            request.ue_id,
            session.pdu_session_id,
            request.service_type,
            request.target,
        )
        with self._lock:
            existing = self._flow_ports.get(flow_key)
            if existing is not None:
                return existing

            used = self._used_ports.setdefault(request.ue_id, set())
            preferred = 49_152 + session.pdu_session_id
            candidates = range(preferred, 65_536)
            for candidate in candidates:
                if candidate not in used:
                    used.add(candidate)
                    self._flow_ports[flow_key] = candidate
                    return candidate
        raise IPTrafficError(f"UE {request.ue_id} has exhausted all ephemeral source ports")


def _build_default_factory() -> IPPacketFactory:
    config = Path(__file__).resolve().parents[2] / "configs" / "ran" / "ip_endpoints.json"
    if config.is_file():
        return IPPacketFactory.from_json(config)
    return IPPacketFactory()


_DEFAULT_FACTORY = _build_default_factory()


def build_ip_traffic(
    request: UERequest,
    session: PduSession,
    *,
    factory: IPPacketFactory | None = None,
) -> IPTrafficBatch:
    """Compatibility entry point used by the existing scenario."""

    return (factory or _DEFAULT_FACTORY).build(request, session)


def reset_default_ip_packet_factory() -> None:
    _DEFAULT_FACTORY.reset()
