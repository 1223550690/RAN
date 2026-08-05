"""AMF 控制面:RM / CM / RRC 状态机(3GPP 语义简化)。

状态:
- RM(注册管理):DEREGISTERED → REGISTERED → DEREGISTERED。
- CM(连接管理,TS 24.501):CM_IDLE → CM_CONNECTED → CM_IDLE。
- RRC(无线资源控制,TS 38.331):RRC_IDLE → RRC_CONNECTED;
  RRC_CONNECTED → RRC_INACTIVE(挂起)→ RRC_CONNECTED(恢复)→ RRC_IDLE(释放)。

设计原则:
- 所有状态保存在 UEState 上(rm_state/cm_state/rrc_state 字段),Amf 无实例状态,
  方法为纯状态迁移函数——非法迁移抛 ValueError。
- 兼容:模块级 register_ue 保留(等价于 Amf().register_ue)。
"""
from __future__ import annotations

from ran.contracts import UEState

# 状态常量(与 contracts.ue 的简化值保持映射)
RM_DEREGISTERED = "DEREGISTERED"
RM_REGISTERED = "REGISTERED"
CM_IDLE = "CM_IDLE"
CM_CONNECTED = "CM_CONNECTED"
RRC_IDLE = "RRC_IDLE"
RRC_INACTIVE = "RRC_INACTIVE"
RRC_CONNECTED = "RRC_CONNECTED"


class Amf:
    """AMF 控制面状态机服务(纯函数式,状态存于 UEState)。"""

    # ---------------------------------------------------------------- 兼容归一化

    @staticmethod
    def _normalize_cm(state: str) -> str:
        """兼容旧值:"IDLE"→CM_IDLE、"CONNECTED"→CM_CONNECTED。"""

        return {"IDLE": CM_IDLE, "CONNECTED": CM_CONNECTED}.get(state, state)

    @staticmethod
    def _normalize_rrc(state: str) -> str:
        """兼容旧值:"IDLE"→RRC_IDLE、"CONNECTED"→RRC_CONNECTED。"""

        return {"IDLE": RRC_IDLE, "CONNECTED": RRC_CONNECTED}.get(state, state)

    # ---------------------------------------------------------------- RM

    def register_ue(self, ue: UEState) -> UEState:
        """注册:RM DEREGISTERED→REGISTERED,CM IDLE→CONNECTED(NAS 连接建立)。"""

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
        ue.rrc_state = self._normalize_rrc(ue.rrc_state)  # 保持 IDLE(语义),统一为新常量
        return ue

    def deregister_ue(self, ue: UEState) -> UEState:
        """去注册:RM REGISTERED→DEREGISTERED,CM/RRC 全部回 IDLE。"""

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
            (RRC_IDLE, "resume"): RRC_INACTIVE,  # 经 INACTIVE 恢复(备用路径)
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
        """RRC Setup:IDLE→CONNECTED(via_inactive=True 时经 INACTIVE)。已连接则幂等。"""

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
        """RRC Suspend:CONNECTED→INACTIVE(业务间隙挂起)。已在 INACTIVE 则幂等。"""

        state = self._normalize_rrc(ue.rrc_state)
        if state == RRC_INACTIVE:
            return ue
        ue.rrc_state = self._rrc_transition(state, "suspend")
        return ue

    def resume_rrc(self, ue: UEState) -> UEState:
        """RRC Resume:INACTIVE→CONNECTED。"""

        state = self._normalize_rrc(ue.rrc_state)
        ue.rrc_state = self._rrc_transition(state, "resume")
        return ue

    def release_rrc(self, ue: UEState, *, to_inactive: bool = False) -> UEState:
        """RRC Release:CONNECTED/INACTIVE→IDLE(to_inactive=True 时 CONNECTED→INACTIVE)。"""

        state = self._normalize_rrc(ue.rrc_state)
        if state == RRC_IDLE:
            return ue
        if to_inactive and state == RRC_CONNECTED:
            ue.rrc_state = self._rrc_transition(state, "suspend")
            return ue
        ue.rrc_state = self._rrc_transition(state, "release")
        return ue

    # ---------------------------------------------------------------- 查询

    def state_of(self, ue: UEState) -> dict[str, str]:
        """返回 {rm, cm, rrc} 三状态快照。"""

        return {"rm": ue.rm_state, "cm": ue.cm_state, "rrc": ue.rrc_state}


# ---------------------------------------------------------------- 兼容入口


def register_ue(ue: UEState) -> UEState:
    """兼容入口:等价于 Amf().register_ue(ue)。"""

    return Amf().register_ue(ue)
