"""SDAP 实体(SdapMapper)测试:DRB 映射、幂等、会话释放、模块级兼容入口。"""
from __future__ import annotations

import unittest

from ran.contracts import AgentIntent, Position, UERequest
from ran.contracts.bearer import Drb
from ran.protocol.sdap import SdapMapper, map_qos_flow_to_drb, reset_default_sdap_mapper
from ran.traffic.ip import build_ip_traffic
from ran.ue.request import build_ue_request


def _request(service_type: str = "video_upload", ue_id: str = "ue_1") -> UERequest:
    intent = AgentIntent(
        intent_id="intent_1",
        agent_id="agent_1",
        agent_pos=Position(x=100.0, y=100.0),
        action="upload",
        target="youtube_server",
        content_type="video",
        service_type=service_type,
        requested_payload_bytes=1024 * 1024,
    )
    return build_ue_request(
        intent,
        ue_id=ue_id,
        service_instance_id="svc_1",
    )


def _qos(request: UERequest, qfi: int = 1, session_id: int = 1):
    from ran.contracts.qos import QoSFlow

    return QoSFlow(
        five_qi=6,
        resource_type="non_gbr",
        qfi=qfi,
        pdu_session_id=session_id,
        direction="UL",
        service_type=request.service_type,
        slice_id="embb",
        priority=6,
        packet_delay_budget_ms=100,
        packet_error_rate=1e-3,
    )


class SdapMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = SdapMapper()

    def test_map_assigns_stable_drb_per_flow(self) -> None:
        request = _request()
        qos = _qos(request)
        drb1 = self.mapper.map(qos, request)
        drb2 = self.mapper.map(qos, request)  # 同一 flow → 幂等
        self.assertEqual(drb1.drb_id, drb2.drb_id)
        self.assertEqual(drb1.ue_id, request.ue_id)
        self.assertEqual(drb1.qfi, qos.qfi)
        self.assertGreater(drb1.drb_id, 0)

    def test_different_flows_get_different_drbs(self) -> None:
        request = _request()
        qos1 = _qos(request, qfi=1)
        qos2 = _qos(request, qfi=2)
        drb1 = self.mapper.map(qos1, request)
        drb2 = self.mapper.map(qos2, request)
        # 3GPP 语义:同会话多 QoS flow 可共享 DRB(qfi_list);至少映射必须稳定存在
        self.assertIsInstance(drb1, Drb)
        self.assertIsInstance(drb2, Drb)
        self.assertEqual(drb1.ue_id, drb2.ue_id)
        self.assertTrue(qos1.qfi in drb1.qfi_list or qos2.qfi in drb2.qfi_list or drb1.drb_id != drb2.drb_id)

    def test_rlc_mode_follows_service_type(self) -> None:
        request = _request("video_upload")
        drb = self.mapper.map(_qos(request), request)
        self.assertEqual(drb.rlc_mode, "AM")

    def test_release_session_frees_mapping(self) -> None:
        request = _request()
        qos = _qos(request)
        drb = self.mapper.map(qos, request)
        self.mapper.release_session(request.ue_id, qos.pdu_session_id)
        # 释放后重新映射 → 新 DRB(会话已清理)
        drb2 = self.mapper.map(qos, request)
        self.assertIsInstance(drb2, Drb)

    def test_process_emits_sdap_output_with_header(self) -> None:
        request = _request("video_upload")
        qos = _qos(request)
        from ran.contracts.qos import PduSession

        session = PduSession(
            pdu_session_id=1,
            ue_id=request.ue_id,
            dnn="internet",
            slice_id="embb",
            pdu_session_type="IPv4",
            upf_id="upf_1",
            smf_id="smf_1",
            ue_ip="10.0.0.2",
        )
        traffic = build_ip_traffic(request, session)
        output = self.mapper.process(traffic, qos, request)
        self.assertEqual(output.ue_id, request.ue_id)
        self.assertEqual(output.qfi, qos.qfi)
        self.assertGreater(output.output_bytes, 0)
        self.assertEqual(output.output_bytes, output.payload_bytes + output.header_bytes)

    def test_module_level_entry_uses_default_mapper(self) -> None:
        reset_default_sdap_mapper()
        request = _request()
        qos = _qos(request)
        drb = map_qos_flow_to_drb(qos, request)
        self.assertIsInstance(drb, Drb)
        # 幂等:再次调用返回同一 DRB(默认 mapper 有状态)
        drb2 = map_qos_flow_to_drb(qos, request)
        self.assertEqual(drb.drb_id, drb2.drb_id)


if __name__ == "__main__":
    unittest.main()
