from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from ran.contracts import Direction, Drb, QoSFlow, UERequest


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


_AM_SERVICES = frozenset(
    {
        "default",
        "video_upload",
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
        self._lock = RLock()

    def map(self, qos_flow: QoSFlow, request: UERequest) -> Drb:
        self._validate_inputs(qos_flow, request)
        flow_key = (request.ue_id, qos_flow.pdu_session_id, qos_flow.direction, qos_flow.qfi)
        with self._lock:
            existing = self._flow_drbs.get(flow_key)
            if existing is not None:
                return existing

            rlc_mode = self._select_rlc_mode(qos_flow)
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
            return flow_drb

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
            self._used_drb_ids.setdefault(ue_id, set()).difference_update(removed_ids)

    def reset(self) -> None:
        with self._lock:
            self._flow_drbs.clear()
            self._bearers.clear()
            self._used_drb_ids.clear()
            self._default_bearers.clear()

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
    def _validate_inputs(qos_flow: QoSFlow, request: UERequest) -> None:
        if qos_flow.direction != request.direction:
            raise SdapMappingError("QoS flow and UE request directions do not match")
        if qos_flow.service_type != request.service_type:
            raise SdapMappingError("QoS flow and UE request service types do not match")
        if not 1 <= qos_flow.qfi <= 63:
            raise SdapMappingError("QFI must be in the range 1..63")
        if not 1 <= qos_flow.pdu_session_id <= 15:
            raise SdapMappingError("PDU session identity must be in the range 1..15")


_DEFAULT_MAPPER = SdapMapper()


def map_qos_flow_to_drb(
    qos_flow: QoSFlow,
    request: UERequest,
    *,
    mapper: SdapMapper | None = None,
) -> Drb:
    """Compatibility entry point used by the existing scenario."""

    return (mapper or _DEFAULT_MAPPER).map(qos_flow, request)


def reset_default_sdap_mapper() -> None:
    _DEFAULT_MAPPER.reset()
