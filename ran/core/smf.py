from __future__ import annotations

import json
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from pathlib import Path
from threading import RLock
from typing import Iterable

from ran.contracts import PduSession, UERequest, UEState


class SmfSessionError(ValueError):
    """Raised when an SMF session request violates the simplified 5GS model."""


@dataclass(frozen=True, slots=True)
class UpfProfile:
    """UPF selection and addressing information for one DNN."""

    dnn: str
    upf_id: str
    ipv4_pool: IPv4Network
    allowed_slices: frozenset[str]
    gateway: IPv4Address | None = None

    def __post_init__(self) -> None:
        if not self.dnn or not self.upf_id:
            raise ValueError("UPF dnn and upf_id must not be empty")
        if self.gateway is not None and self.gateway not in self.ipv4_pool:
            raise ValueError(f"gateway {self.gateway} is outside address pool {self.ipv4_pool}")

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> UpfProfile:
        pool = ip_network(str(value["ipv4_pool"]), strict=False)
        if not isinstance(pool, IPv4Network):
            raise SmfSessionError("the current MVP supports IPv4 address pools only")
        gateway_value = value.get("gateway")
        gateway = IPv4Address(str(gateway_value)) if gateway_value else None
        if gateway is not None and gateway not in pool:
            raise SmfSessionError(f"gateway {gateway} is outside address pool {pool}")
        return cls(
            dnn=str(value["dnn"]),
            upf_id=str(value["upf_id"]),
            ipv4_pool=pool,
            allowed_slices=frozenset(str(item) for item in value.get("allowed_slices", [])),
            gateway=gateway,
        )


DEFAULT_UPF_PROFILES: tuple[UpfProfile, ...] = (
    UpfProfile(
        dnn="internet",
        upf_id="internet_upf",
        ipv4_pool=IPv4Network("10.20.0.0/24"),
        allowed_slices=frozenset({"embb", "urllc", "mmtc"}),
        gateway=IPv4Address("10.20.0.1"),
    ),
    UpfProfile(
        dnn="campus",
        upf_id="campus_upf",
        ipv4_pool=IPv4Network("10.30.0.0/24"),
        allowed_slices=frozenset({"embb", "urllc", "mmtc"}),
        gateway=IPv4Address("10.30.0.1"),
    ),
    UpfProfile(
        dnn="ims",
        upf_id="ims_upf",
        ipv4_pool=IPv4Network("10.40.0.0/24"),
        allowed_slices=frozenset({"embb", "urllc"}),
        gateway=IPv4Address("10.40.0.1"),
    ),
)


class SessionManagementFunction:
    """Stateful, deterministic SMF model for the single-cell simulator.

    It allocates per-UE PDU session identities, selects a UPF from the DNN and
    slice, assigns unique UE IPv4 addresses, and keeps an in-memory session
    registry.  Repeating an identical establishment request is idempotent.
    """

    def __init__(
        self,
        *,
        smf_id: str = "smf_001",
        upf_profiles: Iterable[UpfProfile] = DEFAULT_UPF_PROFILES,
    ) -> None:
        if not smf_id:
            raise ValueError("smf_id must not be empty")
        profile_list = tuple(upf_profiles)
        profiles = {profile.dnn: profile for profile in profile_list}
        if not profiles:
            raise ValueError("at least one UPF profile is required")
        if len(profiles) != len(profile_list):
            raise ValueError("UPF profile DNN values must be unique")
        self.smf_id = smf_id
        self._profiles = profiles
        self._sessions: dict[tuple[str, int], PduSession] = {}
        self._session_keys: dict[tuple[str, str, str, str], tuple[str, int]] = {}
        self._ip_owners: dict[IPv4Address, tuple[str, int]] = {}
        self._lock = RLock()

    @classmethod
    def from_json(cls, path: str | Path) -> SessionManagementFunction:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        profiles = tuple(UpfProfile.from_dict(item) for item in raw["upfs"])
        return cls(smf_id=str(raw.get("smf_id", "smf_001")), upf_profiles=profiles)

    def establish(self, ue: UEState, request: UERequest, slice_id: str) -> PduSession:
        self._validate_request(ue, request, slice_id)
        profile = self._select_upf(request.dnn, slice_id)
        logical_key = (ue.ue_id, request.dnn, slice_id, request.pdu_session_type)

        with self._lock:
            existing_key = self._session_keys.get(logical_key)
            if existing_key is not None:
                existing = self._sessions[existing_key]
                if existing.state == "ACTIVE":
                    ue.ue_ip = existing.ue_ip
                    return existing

            session_id = self._allocate_session_id(ue.ue_id)
            ue_ip = self._allocate_ipv4(profile, ue.ue_ip)
            session = PduSession(
                pdu_session_id=session_id,
                ue_id=ue.ue_id,
                dnn=request.dnn,
                slice_id=slice_id,
                pdu_session_type=request.pdu_session_type,
                ue_ip=str(ue_ip),
                smf_id=self.smf_id,
                upf_id=profile.upf_id,
            )
            registry_key = (ue.ue_id, session_id)
            self._sessions[registry_key] = session
            self._session_keys[logical_key] = registry_key
            self._ip_owners[ue_ip] = registry_key
            ue.ue_ip = str(ue_ip)
            return session

    def get_session(self, ue_id: str, pdu_session_id: int) -> PduSession | None:
        with self._lock:
            return self._sessions.get((ue_id, pdu_session_id))

    def list_sessions(self, *, ue_id: str | None = None, active_only: bool = True) -> list[PduSession]:
        with self._lock:
            sessions = list(self._sessions.values())
        if ue_id is not None:
            sessions = [session for session in sessions if session.ue_id == ue_id]
        if active_only:
            sessions = [session for session in sessions if session.state == "ACTIVE"]
        return sorted(sessions, key=lambda session: (session.ue_id, session.pdu_session_id))

    def release(self, ue_id: str, pdu_session_id: int) -> PduSession:
        registry_key = (ue_id, pdu_session_id)
        with self._lock:
            session = self._sessions.get(registry_key)
            if session is None:
                raise SmfSessionError(f"PDU session {pdu_session_id} does not exist for UE {ue_id}")
            if session.state == "RELEASED":
                return session
            session.state = "RELEASED"
            self._ip_owners.pop(IPv4Address(session.ue_ip), None)
            logical_key = (session.ue_id, session.dnn, session.slice_id, session.pdu_session_type)
            self._session_keys.pop(logical_key, None)
            return session

    def reset(self) -> None:
        """Clear runtime state; intended for isolated simulations and tests."""

        with self._lock:
            self._sessions.clear()
            self._session_keys.clear()
            self._ip_owners.clear()

    def _validate_request(self, ue: UEState, request: UERequest, slice_id: str) -> None:
        if ue.ue_id != request.ue_id:
            raise SmfSessionError("UE state and request refer to different ue_id values")
        if ue.agent_id != request.agent_id:
            raise SmfSessionError("UE state and request refer to different agent_id values")
        if ue.rm_state != "REGISTERED":
            raise SmfSessionError(f"UE {ue.ue_id} must be REGISTERED before PDU session establishment")
        if not slice_id:
            raise SmfSessionError("slice_id must not be empty")
        if ue.allowed_slices and slice_id not in ue.allowed_slices:
            raise SmfSessionError(f"slice {slice_id!r} is not allowed for UE {ue.ue_id}")
        if request.pdu_session_type != "IPv4":
            raise SmfSessionError("the current SMF MVP supports IPv4 PDU sessions only")

    def _select_upf(self, dnn: str, slice_id: str) -> UpfProfile:
        profile = self._profiles.get(dnn)
        if profile is None:
            raise SmfSessionError(f"no UPF is configured for DNN {dnn!r}")
        if profile.allowed_slices and slice_id not in profile.allowed_slices:
            raise SmfSessionError(f"UPF {profile.upf_id} does not serve slice {slice_id!r}")
        return profile

    def _allocate_session_id(self, ue_id: str) -> int:
        used = {
            session_id
            for (registered_ue_id, session_id), session in self._sessions.items()
            if registered_ue_id == ue_id and session.state == "ACTIVE"
        }
        for candidate in range(1, 16):
            if candidate not in used:
                return candidate
        raise SmfSessionError(f"UE {ue_id} has exhausted all PDU session identities")

    def _allocate_ipv4(self, profile: UpfProfile, requested_ip: str | None) -> IPv4Address:
        if requested_ip is not None:
            try:
                parsed = ip_address(requested_ip)
            except ValueError as exc:
                raise SmfSessionError(f"UE requested an invalid IP address: {requested_ip!r}") from exc
            is_usable = (
                isinstance(parsed, IPv4Address)
                and parsed in profile.ipv4_pool
                and parsed not in {profile.ipv4_pool.network_address, profile.ipv4_pool.broadcast_address}
                and parsed != profile.gateway
            )
            if is_usable and parsed not in self._ip_owners:
                return parsed

        for candidate in profile.ipv4_pool.hosts():
            if candidate == profile.gateway or candidate in self._ip_owners:
                continue
            return candidate
        raise SmfSessionError(f"IPv4 pool {profile.ipv4_pool} is exhausted")


def _build_default_smf() -> SessionManagementFunction:
    config = Path(__file__).resolve().parents[2] / "configs" / "ran" / "smf.json"
    if config.is_file():
        return SessionManagementFunction.from_json(config)
    return SessionManagementFunction()


_DEFAULT_SMF = _build_default_smf()


def establish_pdu_session(
    ue: UEState,
    request: UERequest,
    *,
    slice_id: str,
    ue_ip: str | None = None,
    smf: SessionManagementFunction | None = None,
) -> PduSession:
    """Compatibility entry point used by the existing scenario.

    ``ue_ip`` is an integration extension: multi-UE mock scenarios pin a
    deterministic UE address (the SMF's allocation prefers an existing
    ``ue.ue_ip`` when present).
    """

    if ue_ip is not None and not ue.ue_ip:
        ue.ue_ip = ue_ip
    return (smf or _DEFAULT_SMF).establish(ue, request, slice_id=slice_id)


def reset_default_smf() -> None:
    _DEFAULT_SMF.reset()
