"""AMF CM/RRC 状态机测试(3GPP 语义简化)。"""
import unittest

from ran.contracts import UEState, Position
from ran.core.amf import (
    Amf,
    CM_CONNECTED,
    CM_IDLE,
    RRC_CONNECTED,
    RRC_IDLE,
    RRC_INACTIVE,
    RM_REGISTERED,
    RM_DEREGISTERED,
)


def make_ue() -> UEState:
    return UEState(ue_id="ue_001", agent_id="agent_001", position=Position(1.0, 2.0))


class TestAmfCmRrc(unittest.TestCase):
    def test_register_ue_establishes_cm(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        self.assertEqual(ue.rm_state, RM_REGISTERED)
        self.assertEqual(ue.cm_state, CM_CONNECTED)
        self.assertEqual(ue.rrc_state, RRC_IDLE)  # RRC 不随注册建立

    def test_register_ue_validation(self):
        amf = Amf()
        with self.assertRaises(ValueError):
            amf.register_ue(UEState(ue_id="", agent_id="a", position=Position(0, 0)))
        ue = amf.register_ue(make_ue())
        with self.assertRaises(ValueError):
            amf.register_ue(UEState(ue_id="ue_001", agent_id="agent_001",
                                    position=Position(0, 0), rm_state="CONNECTED"))

    def test_register_ue_idempotent(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        again = amf.register_ue(ue)
        self.assertIs(ue, again)

    def test_rrc_lifecycle(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        # 业务开始:RRC Setup
        amf.establish_rrc(ue)
        self.assertEqual(ue.rrc_state, RRC_CONNECTED)
        # 业务结束:RRC Suspend → INACTIVE
        amf.suspend_rrc(ue)
        self.assertEqual(ue.rrc_state, RRC_INACTIVE)
        # 下一业务:RRC Resume → CONNECTED
        amf.establish_rrc(ue)
        self.assertEqual(ue.rrc_state, RRC_CONNECTED)
        # 显式释放 → IDLE
        amf.release_rrc(ue)
        self.assertEqual(ue.rrc_state, RRC_IDLE)

    def test_rrc_release_to_inactive(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        amf.establish_rrc(ue)
        amf.release_rrc(ue, to_inactive=True)
        self.assertEqual(ue.rrc_state, RRC_INACTIVE)

    def test_rrc_establish_idempotent(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        amf.establish_rrc(ue)
        amf.establish_rrc(ue)  # 已 CONNECTED,幂等
        self.assertEqual(ue.rrc_state, RRC_CONNECTED)

    def test_invalid_rrc_transition(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        # IDLE 不能直接挂起
        with self.assertRaises(ValueError):
            amf.suspend_rrc(ue)
        # INACTIVE 不能直接释放到…(release 合法);测试非法:INACTIVE 时 setup 已由 establish_rrc 处理为 resume
        amf.establish_rrc(ue)
        amf.suspend_rrc(ue)
        # 已 IDLE 时 release 幂等
        ue2 = amf.release_rrc(ue)
        self.assertEqual(ue2.rrc_state, RRC_IDLE)

    def test_deregister_resets_all(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        amf.establish_rrc(ue)
        amf.deregister_ue(ue)
        self.assertEqual(ue.rm_state, RM_DEREGISTERED)
        self.assertEqual(ue.cm_state, CM_IDLE)
        self.assertEqual(ue.rrc_state, RRC_IDLE)

    def test_deregister_requires_registered(self):
        amf = Amf()
        with self.assertRaises(ValueError):
            amf.deregister_ue(make_ue())

    def test_state_of(self):
        amf = Amf()
        ue = amf.register_ue(make_ue())
        amf.establish_rrc(ue)
        snap = amf.state_of(ue)
        self.assertEqual(snap["rm"], RM_REGISTERED)
        self.assertEqual(snap["cm"], CM_CONNECTED)
        self.assertEqual(snap["rrc"], RRC_CONNECTED)

    def test_compat_register_ue_function(self):
        from ran.core.amf import register_ue as compat_register

        ue = compat_register(make_ue())
        self.assertEqual(ue.rm_state, RM_REGISTERED)
        self.assertEqual(ue.cm_state, CM_CONNECTED)

    def test_legacy_values_normalized(self):
        # 旧值 "IDLE"/"CONNECTED" 可进入迁移(兼容 boyu 测试构造)
        amf = Amf()
        ue = make_ue()
        ue.rm_state = "REGISTERED"
        ue.cm_state = "CONNECTED"
        ue.rrc_state = "CONNECTED"
        amf.release_rrc(ue)  # CONNECTED → IDLE(经归一化)
        self.assertEqual(ue.rrc_state, RRC_IDLE)


if __name__ == "__main__":
    unittest.main()
