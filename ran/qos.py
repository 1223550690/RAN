from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Iterable

from ran.contracts import Direction, IPTrafficBatch, PduSession, QoSFlow, UERequest
from ran.traffic.service_profile import SERVICE_QOS_TABLE, service_profile_for


class QoSClassificationError(ValueError):
    """Raised when a QoS flow cannot be classified consistently."""


@dataclass(frozen=True, slots=True)
class QoSRule:
    """Packet-filter-like rule that selects a named service profile."""

    rule_id: int
    profile_name: str
    service_type: str | None = None
    target: str | None = None
    protocol: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    direction: Direction | None = None
    precedence: int = 100

    def __post_init__(self) -> None:
        if self.rule_id <= 0:
            raise ValueError("QoS rule_id must be positive")
        if not self.profile_name:
            raise ValueError("QoS profile_name must not be empty")
        if self.protocol is not None and self.protocol not in {"TCP", "UDP"}:
            raise ValueError("QoS rule protocol must be TCP or UDP")
        for port in (self.src_port, self.dst_port):
            if port is not None and not 1 <= port <= 65535:
                raise ValueError("QoS rule ports must be in the range 1..65535")

    def matches(self, request: UERequest, traffic: IPTrafficBatch | None) -> bool:
        if self.service_type is not None and self.service_type != request.service_type:
            return False
        if self.target is not None and self.target != request.target:
            return False
        if self.direction is not None and self.direction != request.direction:
            return False
        if self.protocol is not None and (traffic is None or self.protocol != traffic.protocol):
            return False
        if self.src_port is not None and (traffic is None or self.src_port != traffic.src_port):
            return False
        if self.dst_port is not None and (traffic is None or self.dst_port != traffic.dst_port):
            return False
        return True


def _default_rules() -> tuple[QoSRule, ...]:
    return tuple(
        QoSRule(
            rule_id=index,
            profile_name=service_type,
            service_type=service_type,
            precedence=10,
        )
        for index, service_type in enumerate(
            sorted(name for name in SERVICE_QOS_TABLE if name != "default"),
            start=1,
        )
    )


class QoSFlowClassifier:
    """Classify traffic and allocate QFIs within each PDU session."""

    def __init__(self, rules: Iterable[QoSRule] | None = None) -> None:
        selected_rules = _default_rules() if rules is None else tuple(rules)
        self._rules = tuple(
            sorted(selected_rules, key=lambda rule: (rule.precedence, rule.rule_id))
        )
        self._flows: dict[tuple[str, int, str], QoSFlow] = {}
        self._qfi_owners: dict[tuple[str, int], dict[int, str]] = {}
        self._lock = RLock()

    def build(
        self,
        request: UERequest,
        session: PduSession,
        *,
        traffic: IPTrafficBatch | None = None,
    ) -> QoSFlow:
        self._validate_inputs(request, session, traffic)
        profile_name = self._select_profile(request, traffic)
        profile = service_profile_for(profile_name)
        flow_identity = traffic.service_id if traffic is not None else self._fallback_flow_identity(request)
        flow_key = (session.ue_id, session.pdu_session_id, flow_identity)

        with self._lock:
            existing = self._flows.get(flow_key)
            if existing is not None:
                return existing
            qfi = self._allocate_qfi(
                session_key=(session.ue_id, session.pdu_session_id),
                flow_identity=flow_identity,
                preferred=int(profile["qfi"]),
            )

            packet_delay_budget_ms = float(profile["packet_delay_budget_ms"])
            requested_budget = request.qos_hint.get("latency_budget_ms")
            if requested_budget is not None:
                requested_budget_value = float(requested_budget)
                if requested_budget_value <= 0:
                    raise QoSClassificationError("qos_hint.latency_budget_ms must be positive")
                packet_delay_budget_ms = min(packet_delay_budget_ms, requested_budget_value)

            gbr_value = profile.get("gbr_mbps")
            mbr_value = profile.get("mbr_mbps")
            flow = QoSFlow(
                pdu_session_id=session.pdu_session_id,
                qfi=qfi,
                five_qi=int(profile["five_qi"]),
                direction=request.direction,
                service_type=request.service_type,
                priority=int(profile["priority"]),
                packet_delay_budget_ms=packet_delay_budget_ms,
                packet_error_rate=float(profile["packet_error_rate"]),
                resource_type=str(profile["resource_type"]),
                slice_id=session.slice_id,
                gbr_mbps=float(gbr_value) if gbr_value is not None else None,
                mbr_mbps=float(mbr_value) if mbr_value is not None else None,
            )
            self._flows[flow_key] = flow
            return flow

    def list_flows(self, *, ue_id: str | None = None, pdu_session_id: int | None = None) -> list[QoSFlow]:
        with self._lock:
            items = list(self._flows.items())
        flows = [
            flow
            for (flow_ue_id, flow_session_id, _), flow in items
            if (ue_id is None or flow_ue_id == ue_id)
            and (pdu_session_id is None or flow_session_id == pdu_session_id)
        ]
        return sorted(flows, key=lambda flow: (flow.pdu_session_id, flow.qfi))

    def release_session(self, ue_id: str, pdu_session_id: int) -> None:
        with self._lock:
            self._flows = {
                key: flow
                for key, flow in self._flows.items()
                if not (key[0] == ue_id and key[1] == pdu_session_id)
            }
            self._qfi_owners.pop((ue_id, pdu_session_id), None)

    def reset(self) -> None:
        with self._lock:
            self._flows.clear()
            self._qfi_owners.clear()

    def _select_profile(self, request: UERequest, traffic: IPTrafficBatch | None) -> str:
        for rule in self._rules:
            if rule.matches(request, traffic):
                if rule.profile_name not in SERVICE_QOS_TABLE:
                    raise QoSClassificationError(
                        f"QoS rule {rule.rule_id} references unknown profile {rule.profile_name!r}"
                    )
                return rule.profile_name
        return request.service_type if request.service_type in SERVICE_QOS_TABLE else "default"

    def _allocate_qfi(
        self,
        *,
        session_key: tuple[str, int],
        flow_identity: str,
        preferred: int,
    ) -> int:
        owners = self._qfi_owners.setdefault(session_key, {})
        if preferred not in owners or owners[preferred] == flow_identity:
            owners[preferred] = flow_identity
            return preferred
        for candidate in range(1, 64):
            if candidate not in owners:
                owners[candidate] = flow_identity
                return candidate
        raise QoSClassificationError(f"PDU session {session_key} has exhausted all QFI values")

    @staticmethod
    def _validate_inputs(
        request: UERequest,
        session: PduSession,
        traffic: IPTrafficBatch | None,
    ) -> None:
        if session.state != "ACTIVE":
            raise QoSClassificationError("QoS classification requires an ACTIVE PDU session")
        if request.ue_id != session.ue_id:
            raise QoSClassificationError("UE request and PDU session refer to different UEs")
        if request.dnn != session.dnn:
            raise QoSClassificationError("UE request and PDU session use different DNN values")
        if traffic is not None:
            if traffic.metadata.get("pdu_session_id") != session.pdu_session_id:
                raise QoSClassificationError("IP traffic and PDU session identities do not match")
            if traffic.metadata.get("ue_id") != request.ue_id:
                raise QoSClassificationError("IP traffic and UE request identities do not match")
            if traffic.metadata.get("dnn") != request.dnn:
                raise QoSClassificationError("IP traffic and UE request DNN values do not match")
            if traffic.metadata.get("service_type") != request.service_type:
                raise QoSClassificationError("IP traffic and UE request service types do not match")
            if traffic.direction != request.direction:
                raise QoSClassificationError("IP traffic and UE request directions do not match")

    @staticmethod
    def _fallback_flow_identity(request: UERequest) -> str:
        return f"{request.ue_id}:{request.direction}:{request.service_type}:{request.target}"


_DEFAULT_CLASSIFIER = QoSFlowClassifier()


def build_qos_flow(
    request: UERequest,
    session: PduSession,
    *,
    traffic: IPTrafficBatch | None = None,
    classifier: QoSFlowClassifier | None = None,
) -> QoSFlow:
    """Compatibility entry point used by the existing scenario."""

    return (classifier or _DEFAULT_CLASSIFIER).build(request, session, traffic=traffic)


def reset_default_qos_classifier() -> None:
    _DEFAULT_CLASSIFIER.reset()
