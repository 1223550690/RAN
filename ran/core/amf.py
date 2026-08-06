"""AMF control plane: RM / CM / RRC state machines (simplified 3GPP semantics).

States:
- RM (Registration Management): DEREGISTERED → REGISTERED → DEREGISTERED.
- CM (Connection Management, TS 24.501): CM_IDLE → CM_CONNECTED → CM_IDLE.
- RRC (Radio Resource Control, TS 38.331): RRC_IDLE → RRC_CONNECTED;
  RRC_CONNECTED → RRC_INACTIVE (suspend) → RRC_CONNECTED (resume) → RRC_IDLE (release).

Design principles:
- All state is stored on UEState (rm_state/cm_state/rrc_state fields); Amf holds no instance state,
  methods are pure state-transition functions -- invalid transitions raise ValueError.
- Compatibility: module-level register_ue is kept (equivalent to Amf().register_ue).
"""
from __future__ import annotations

from ran.contracts import UEState

# State constants (kept in sync with the simplified values in contracts.ue)
RM_DEREGISTERED = "DEREGISTERED"
RM_REGISTERED = "REGISTERED"
CM_IDLE = "CM_IDLE"
CM_CONNECTED = "CM_CONNECTED"
RRC_IDLE = "RRC_IDLE"
RRC_INACTIVE = "RRC_INACTIVE"
RRC_CONNECTED = "RRC_CONNECTED"


class Amf:
    """AMF control plane state machine service (pure functional; state lives on UEState)."""

    # ---------------------------------------------------------------- Compatibility normalization

    @staticmethod
    def _normalize_cm(state: str) -> str:
        """Compatibility for legacy values: "IDLE"→CM_IDLE, "CONNECTED"→CM_CONNECTED."""

        return {"IDLE": CM_IDLE, "CONNECTED": CM_CONNECTED}.get(state, state)

    @staticmethod
    def _normalize_rrc(state: str) -> str:
        """Compatibility for legacy values: "IDLE"→RRC_IDLE, "CONNECTED"→RRC_CONNECTED."""

        return {"IDLE": RRC_IDLE, "CONNECTED": RRC_CONNECTED}.get(state, state)

    # ---------------------------------------------------------------- RM

    def register_ue(self, ue: UEState) -> UEState:
        """Register: RM DEREGISTERED→REGISTERED, CM IDLE→CONNECTED (NAS connection established)."""

        if not ue.ue_id.strip():
            raise ValueError("UE ID cannot be empty.")
        if not ue.agent_id.strip():
            raise ValueError("Agent ID cannot be empty.")
        if ue.rm_state == RM_REGISTERED:
            return ue
        if ue.rm_state != RM_DEREGISTERED:
            raise ValueError(f"Invalid RM state before registration: {ue.rm_state}")
        ue.rm_state = RM_REGISTERED
        ue.cm_state = self._cm_transition(self._normalize_cm(ue.cm_state), "registration")
        ue.rrc_state = self._normalize_rrc(ue.rrc_state)  # keep IDLE (semantics), unify to the new constants
        return ue

    def deregister_ue(self, ue: UEState) -> UEState:
        """Deregister: RM REGISTERED→DEREGISTERED, CM/RRC all back to IDLE."""

        if ue.rm_state != RM_REGISTERED:
            raise ValueError(f"Cannot deregister UE in RM state {ue.rm_state}")
        ue.rm_state = RM_DEREGISTERED
        ue.cm_state = self._cm_transition(self._normalize_cm(ue.cm_state), "deregistration")
        ue.rrc_state = self._rrc_transition(self._normalize_rrc(ue.rrc_state), "release")
        return ue

    # ---------------------------------------------------------------- CM

    def _cm_transition(self, state: str, event: str) -> str:
        transitions: dict[tuple[str, str], str] = {
            (CM_IDLE, "registration"): CM_CONNECTED,
            (CM_CONNECTED, "deregistration"): CM_IDLE,
        }
        key = (state, event)
        if key not in transitions:
            raise ValueError(f"Invalid CM transition: {state} --{event}--> ?")
        return transitions[key]

    # ---------------------------------------------------------------- RRC

    def _rrc_transition(self, state: str, event: str) -> str:
        transitions: dict[tuple[str, str], str] = {
            (RRC_IDLE, "setup"): RRC_CONNECTED,
            (RRC_IDLE, "resume"): RRC_INACTIVE,  # resume via INACTIVE (fallback path)
            (RRC_INACTIVE, "resume"): RRC_CONNECTED,
            (RRC_INACTIVE, "release"): RRC_IDLE,
            (RRC_CONNECTED, "suspend"): RRC_INACTIVE,
            (RRC_CONNECTED, "release"): RRC_IDLE,
        }
        key = (state, event)
        if key not in transitions:
            raise ValueError(f"Invalid RRC transition: {state} --{event}--> ?")
        return transitions[key]

    def establish_rrc(self, ue: UEState, *, via_inactive: bool = False) -> UEState:
        """RRC Setup: IDLE→CONNECTED (via INACTIVE when via_inactive=True). Idempotent when already connected."""

        state = self._normalize_rrc(ue.rrc_state)
        if state == RRC_CONNECTED:
            return ue
        if state == RRC_INACTIVE:
            ue.rrc_state = self._rrc_transition(state, "resume")
            return ue
        if via_inactive:
            ue.rrc_state = self._rrc_transition(state, "resume")  # IDLE→INACTIVE
            state = RRC_INACTIVE
        ue.rrc_state = self._rrc_transition(state, "setup")
        return ue

    def suspend_rrc(self, ue: UEState) -> UEState:
        """RRC Suspend: CONNECTED→INACTIVE (suspend during service gaps). Idempotent when already INACTIVE."""

        state = self._normalize_rrc(ue.rrc_state)
        if state == RRC_INACTIVE:
            return ue
        ue.rrc_state = self._rrc_transition(state, "suspend")
        return ue

    def resume_rrc(self, ue: UEState) -> UEState:
        """RRC Resume: INACTIVE→CONNECTED."""

        state = self._normalize_rrc(ue.rrc_state)
        ue.rrc_state = self._rrc_transition(state, "resume")
        return ue

    def release_rrc(self, ue: UEState, *, to_inactive: bool = False) -> UEState:
        """RRC Release: CONNECTED/INACTIVE→IDLE (CONNECTED→INACTIVE when to_inactive=True)."""

        state = self._normalize_rrc(ue.rrc_state)
        if state == RRC_IDLE:
            return ue
        if to_inactive and state == RRC_CONNECTED:
            ue.rrc_state = self._rrc_transition(state, "suspend")
            return ue
        ue.rrc_state = self._rrc_transition(state, "release")
        return ue

    # ---------------------------------------------------------------- Queries

    def state_of(self, ue: UEState) -> dict[str, str]:
        """Return a snapshot of the three states {rm, cm, rrc}."""

        return {"rm": ue.rm_state, "cm": ue.cm_state, "rrc": ue.rrc_state}


# ---------------------------------------------------------------- Compatibility entry point


def register_ue(ue: UEState) -> UEState:
    """Compatibility entry point: equivalent to Amf().register_ue(ue)."""

    return Amf().register_ue(ue)
