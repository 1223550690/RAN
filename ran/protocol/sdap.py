from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from ran.contracts import Direction, Drb, IPTrafficBatch, QoSFlow, UERequest


class SdapMappingError(ValueError):
    """Raised when a QoS flow cannot be mapped to a valid DRB."""


@dataclass(frozen=True, slots=True)
class SdapMapping:
    """Observable QFI-to-DRB mapping state."""

    ue_id: str
    pdu_session_id: int
    qfi: int
    drb_id: int
    direction: Direction
    default_drb: bool
    sdap_header_present: bool


@dataclass(frozen=True, slots=True)
class SdapOutput:
    """A formal SDAP output handoff contract for downstream integration.

    ``application_bytes`` records the original service payload, while
    ``payload_bytes`` records the complete IP packets presented to SDAP.
    One octet of SDAP header is accounted for per represented PDU when an
    explicit QFI header is required.
    """

    service_id: str
    ue_id: str
    pdu_session_id: int
    qfi: int
    slice_id: str
    direction: Direction
    drb: Drb
    application_bytes: int
    ip_transport_header_bytes: int
    payload_bytes: int
    pdu_count: int
    sdap_header_present: bool
    header_bytes: int
    output_bytes: int

    def __post_init__(self) -> None:
        if not self.service_id:
            raise ValueError("service_id must not be empty")
        if min(
            self.application_bytes,
            self.ip_transport_header_bytes,
            self.payload_bytes,
            self.pdu_count,
        ) < 0:
            raise ValueError("SDAP byte counts and PDU count must not be negative")
        if self.payload_bytes != self.application_bytes + self.ip_transport_header_bytes:
            raise ValueError("SDAP payload bytes must include application and IP/transport bytes")
        if self.header_bytes < 0:
            raise ValueError("SDAP header bytes must not be negative")
        if self.sdap_header_present != self.drb.sdap_header_present:
            raise ValueError("SDAP header flag and DRB state do not match")
        expected_header_bytes = self.pdu_count if self.sdap_header_present else 0
        if self.header_bytes != expected_header_bytes:
            raise ValueError("SDAP header bytes do not match the represented PDU count")
        if self.output_bytes != self.payload_bytes + self.header_bytes:
            raise ValueError("SDAP output bytes must equal payload plus header bytes")
        if self.drb.ue_id != self.ue_id:
            raise ValueError("SDAP output UE and DRB UE do not match")
        if self.drb.pdu_session_id != self.pdu_session_id:
            raise ValueError("SDAP output session and DRB session do not match")
        if self.drb.qfi != self.qfi or self.drb.direction != self.direction:
            raise ValueError("SDAP output QFI/direction and DRB do not match")
        if self.drb.slice_id != self.slice_id:
            raise ValueError("SDAP output slice and DRB slice do not match")


_AM_SERVICES = frozenset(
    {
        "default",
        "video_upload",
        "voice_upload",
        "web",
        "file_upload",
        "file_download",
        "message",
        "telemetry",
    }
)
_UM_SERVICES = frozenset({"game", "video_call", "voice_call", "live_video", "video_stream", "control"})


class SdapMapper:
    """Stateful SDAP mapping and DRB allocator.

    GBR and latency-sensitive flows receive dedicated DRBs.  Compatible
    non-GBR flows may share a DRB while retaining an explicit ``qfi_list``.
    DRB identifiers are allocated per UE and remain stable for the session.
    """

    def __init__(self) -> None:
        self._flow_drbs: dict[tuple[str, int, Direction, int], Drb] = {}
        self._bearers: dict[tuple[str, int, Direction, str], Drb] = {}
        self._used_drb_ids: dict[str, set[int]] = {}
        self._default_bearers: set[tuple[str, int, Direction]] = set()
        self._flow_contexts: dict[
            tuple[str, int, Direction, int],
            tuple[str, str, str, int, str],
        ] = {}
        self._session_slices: dict[tuple[str, int, Direction], str] = {}
        self._lock = RLock()

    def map(self, qos_flow: QoSFlow, request: UERequest) -> Drb:
        self._validate_inputs(qos_flow, request)
        flow_key = (request.ue_id, qos_flow.pdu_session_id, qos_flow.direction, qos_flow.qfi)
        session_key = (request.ue_id, qos_flow.pdu_session_id, qos_flow.direction)
        rlc_mode = self._select_rlc_mode(qos_flow)
        flow_context = (
            qos_flow.service_type,
            qos_flow.slice_id,
            rlc_mode,
            qos_flow.priority,
            qos_flow.resource_type,
        )
        with self._lock:
            previous_slice = self._session_slices.get(session_key)
            if previous_slice is not None and previous_slice != qos_flow.slice_id:
                self._release_session_locked(request.ue_id, qos_flow.pdu_session_id)
            self._session_slices[session_key] = qos_flow.slice_id

            existing = self._flow_drbs.get(flow_key)
            if existing is not None and self._flow_contexts.get(flow_key) == flow_context:
                return existing
            if existing is not None:
                # A QFI has been reused for a different flow generation.
                self._release_session_locked(request.ue_id, qos_flow.pdu_session_id)
                self._session_slices[session_key] = qos_flow.slice_id

            group = self._bearer_group(qos_flow, rlc_mode)
            bearer_key = (request.ue_id, qos_flow.pdu_session_id, qos_flow.direction, group)
            canonical = self._bearers.get(bearer_key)
            if canonical is None:
                session_key = (request.ue_id, qos_flow.pdu_session_id, qos_flow.direction)
                default_drb = session_key not in self._default_bearers
                canonical = Drb(
                    drb_id=self._allocate_drb_id(request.ue_id),
                    ue_id=request.ue_id,
                    pdu_session_id=qos_flow.pdu_session_id,
                    qfi=qos_flow.qfi,
                    qfi_list=[qos_flow.qfi],
                    slice_id=qos_flow.slice_id,
                    direction=qos_flow.direction,
                    rlc_mode=rlc_mode,
                    priority=qos_flow.priority,
                    default_drb=default_drb,
                    sdap_header_present=not default_drb,
                )
                self._bearers[bearer_key] = canonical
                self._default_bearers.add(session_key)
                flow_drb = canonical
            else:
                if qos_flow.qfi not in canonical.qfi_list:
                    canonical.qfi_list.append(qos_flow.qfi)
                    canonical.qfi_list.sort()
                canonical.priority = min(canonical.priority, qos_flow.priority)
                canonical.sdap_header_present = True
                flow_drb = Drb(
                    drb_id=canonical.drb_id,
                    ue_id=canonical.ue_id,
                    pdu_session_id=canonical.pdu_session_id,
                    qfi=qos_flow.qfi,
                    qfi_list=canonical.qfi_list,
                    slice_id=canonical.slice_id,
                    direction=canonical.direction,
                    rlc_mode=canonical.rlc_mode,
                    priority=canonical.priority,
                    default_drb=canonical.default_drb,
                    sdap_header_present=canonical.sdap_header_present,
                )

            self._flow_drbs[flow_key] = flow_drb
            self._flow_contexts[flow_key] = flow_context
            return flow_drb

    def process(
        self,
        traffic: IPTrafficBatch,
        qos_flow: QoSFlow,
        request: UERequest,
    ) -> SdapOutput:
        """Map a complete IP traffic batch and emit a formal SDAP output."""

        self._validate_transfer_inputs(traffic, qos_flow, request)
        drb = self._snapshot_drb(self.map(qos_flow, request))
        application_bytes = traffic.remaining_bytes
        pdu_count = traffic.remaining_packet_count
        ip_transport_header_bytes = pdu_count * traffic.header_bytes
        payload_bytes = application_bytes + ip_transport_header_bytes
        header_bytes = pdu_count if drb.sdap_header_present else 0
        return SdapOutput(
            service_id=traffic.service_id,
            ue_id=request.ue_id,
            pdu_session_id=qos_flow.pdu_session_id,
            qfi=qos_flow.qfi,
            slice_id=qos_flow.slice_id,
            direction=qos_flow.direction,
            drb=drb,
            application_bytes=application_bytes,
            ip_transport_header_bytes=ip_transport_header_bytes,
            payload_bytes=payload_bytes,
            pdu_count=pdu_count,
            sdap_header_present=drb.sdap_header_present,
            header_bytes=header_bytes,
            output_bytes=payload_bytes + header_bytes,
        )

    def get_mapping(
        self,
        *,
        ue_id: str,
        pdu_session_id: int,
        direction: Direction,
        qfi: int,
    ) -> SdapMapping | None:
        with self._lock:
            drb = self._flow_drbs.get((ue_id, pdu_session_id, direction, qfi))
            if drb is None:
                return None
            return SdapMapping(
                ue_id=ue_id,
                pdu_session_id=pdu_session_id,
                qfi=qfi,
                drb_id=drb.drb_id,
                direction=direction,
                default_drb=drb.default_drb,
                sdap_header_present=drb.sdap_header_present,
            )

    def list_mappings(self, *, ue_id: str | None = None) -> list[SdapMapping]:
        with self._lock:
            keys = list(self._flow_drbs)
        mappings: list[SdapMapping] = []
        for key in keys:
            if ue_id is not None and key[0] != ue_id:
                continue
            mapping = self.get_mapping(
                ue_id=key[0],
                pdu_session_id=key[1],
                direction=key[2],
                qfi=key[3],
            )
            if mapping is not None:
                mappings.append(mapping)
        return sorted(
            mappings,
            key=lambda item: (item.ue_id, item.pdu_session_id, item.direction, item.qfi),
        )

    def release_session(self, ue_id: str, pdu_session_id: int) -> None:
        with self._lock:
            self._release_session_locked(ue_id, pdu_session_id)

    def _release_session_locked(self, ue_id: str, pdu_session_id: int) -> None:
        removed_ids = {
            drb.drb_id
            for key, drb in self._flow_drbs.items()
            if key[0] == ue_id and key[1] == pdu_session_id
        }
        self._flow_drbs = {
            key: drb
            for key, drb in self._flow_drbs.items()
            if not (key[0] == ue_id and key[1] == pdu_session_id)
        }
        self._bearers = {
            key: drb
            for key, drb in self._bearers.items()
            if not (key[0] == ue_id and key[1] == pdu_session_id)
        }
        self._default_bearers = {
            key
            for key in self._default_bearers
            if not (key[0] == ue_id and key[1] == pdu_session_id)
        }
        self._flow_contexts = {
            key: context
            for key, context in self._flow_contexts.items()
            if not (key[0] == ue_id and key[1] == pdu_session_id)
        }
        self._session_slices = {
            key: slice_id
            for key, slice_id in self._session_slices.items()
            if not (key[0] == ue_id and key[1] == pdu_session_id)
        }
        used = self._used_drb_ids.get(ue_id)
        if used is not None:
            used.difference_update(removed_ids)
            if not used:
                self._used_drb_ids.pop(ue_id, None)

    def reset(self) -> None:
        with self._lock:
            self._flow_drbs.clear()
            self._bearers.clear()
            self._used_drb_ids.clear()
            self._default_bearers.clear()
            self._flow_contexts.clear()
            self._session_slices.clear()

    def _allocate_drb_id(self, ue_id: str) -> int:
        used = self._used_drb_ids.setdefault(ue_id, set())
        for candidate in range(1, 33):
            if candidate not in used:
                used.add(candidate)
                return candidate
        raise SdapMappingError(f"UE {ue_id} has exhausted all DRB identifiers")

    @staticmethod
    def _select_rlc_mode(qos_flow: QoSFlow) -> str:
        if qos_flow.service_type in _UM_SERVICES:
            return "UM"
        if qos_flow.service_type in _AM_SERVICES:
            return "AM"
        return "UM" if qos_flow.resource_type != "non_gbr" or qos_flow.priority <= 2 else "AM"

    @staticmethod
    def _bearer_group(qos_flow: QoSFlow, rlc_mode: str) -> str:
        dedicated = (
            qos_flow.resource_type != "non_gbr"
            or qos_flow.service_type in _UM_SERVICES
            or qos_flow.priority <= 2
        )
        if dedicated:
            return f"dedicated:{qos_flow.qfi}"
        return f"shared:{qos_flow.slice_id}:{rlc_mode}"

    @staticmethod
    def _snapshot_drb(drb: Drb) -> Drb:
        """Detach an emitted SDAP result from later mutable mapping updates."""

        return Drb(
            drb_id=drb.drb_id,
            ue_id=drb.ue_id,
            pdu_session_id=drb.pdu_session_id,
            qfi=drb.qfi,
            qfi_list=list(drb.qfi_list),
            slice_id=drb.slice_id,
            direction=drb.direction,
            rlc_mode=drb.rlc_mode,
            priority=drb.priority,
            default_drb=drb.default_drb,
            sdap_header_present=drb.sdap_header_present,
        )

    @staticmethod
    def _validate_inputs(qos_flow: QoSFlow, request: UERequest) -> None:
        if qos_flow.direction != request.direction:
            raise SdapMappingError("QoS flow and UE request directions do not match")
        if qos_flow.service_type != request.service_type:
            raise SdapMappingError("QoS flow and UE request service types do not match")
        if not 1 <= qos_flow.qfi <= 63:
            raise SdapMappingError("QFI must be in the range 1..63")
        if not 1 <= qos_flow.pdu_session_id <= 15:
            raise SdapMappingError("PDU session identity must be in the range 1..15")

    @staticmethod
    def _validate_transfer_inputs(
        traffic: IPTrafficBatch,
        qos_flow: QoSFlow,
        request: UERequest,
    ) -> None:
        if traffic.direction != qos_flow.direction:
            raise SdapMappingError("IP traffic and QoS flow directions do not match")
        if traffic.direction != request.direction:
            raise SdapMappingError("IP traffic and UE request directions do not match")
        metadata = traffic.metadata
        ue_id = metadata.get("ue_id")
        if ue_id is not None and ue_id != request.ue_id:
            raise SdapMappingError("IP traffic and UE request identities do not match")
        session_id = metadata.get("pdu_session_id")
        if session_id is not None and session_id != qos_flow.pdu_session_id:
            raise SdapMappingError("IP traffic and QoS flow sessions do not match")
        slice_id = metadata.get("slice_id")
        if slice_id is not None and slice_id != qos_flow.slice_id:
            raise SdapMappingError("IP traffic and QoS flow slices do not match")
        service_type = metadata.get("service_type")
        if service_type is not None and service_type != request.service_type:
            raise SdapMappingError("IP traffic and UE request service types do not match")


_DEFAULT_MAPPER = SdapMapper()


def map_qos_flow_to_drb(
    qos_flow: QoSFlow,
    request: UERequest,
    *,
    mapper: SdapMapper | None = None,
) -> Drb:
    """Compatibility entry point used by the existing scenario."""

    return (mapper or _DEFAULT_MAPPER).map(qos_flow, request)


def process_sdap(
    traffic: IPTrafficBatch,
    qos_flow: QoSFlow,
    request: UERequest,
    *,
    mapper: SdapMapper | None = None,
) -> SdapOutput:
    """Create the formal SDAP output for the downstream handoff boundary."""

    return (mapper or _DEFAULT_MAPPER).process(traffic, qos_flow, request)


def reset_default_sdap_mapper() -> None:
    _DEFAULT_MAPPER.reset()
