from __future__ import annotations

import math
import unittest

from ran.contracts import IPTrafficBatch, PduSession, Position, QoSFlow, UERequest, UEState
from ran.core import SessionManagementFunction, SmfSessionError, reset_default_smf
from ran.protocol import (
    SdapMapper,
    SdapMappingError,
    SdapOutput,
    build_pdcp_batch,
    reset_default_sdap_mapper,
)
from ran.qos import (
    QoSClassificationError,
    QoSFlowClassifier,
    QoSRule,
    reset_default_qos_classifier,
)
from ran.scenario import RanUploadScenario
from ran.traffic import IPPacketFactory, IPTrafficError
from services.scene_service import SceneService


def build_ue(
    ue_id: str = "ue_001",
    *,
    registered: bool = True,
    allowed_slices: list[str] | None = None,
) -> UEState:
    return UEState(
        ue_id=ue_id,
        agent_id=f"agent_{ue_id}",
        position=Position(10.0, 20.0),
        rm_state="REGISTERED" if registered else "DEREGISTERED",
        cm_state="CONNECTED" if registered else "IDLE",
        rrc_state="CONNECTED" if registered else "IDLE",
        allowed_slices=allowed_slices or ["embb", "urllc", "mmtc"],
    )


def build_request(
    ue_id: str = "ue_001",
    *,
    direction: str = "UL",
    target: str = "youtube_server",
    dnn: str = "internet",
    service_type: str = "video_upload",
    size_bytes: int = 10_000,
    qos_hint: dict[str, object] | None = None,
) -> UERequest:
    return UERequest(
        ue_id=ue_id,
        agent_id=f"agent_{ue_id}",
        position=Position(10.0, 20.0),
        direction=direction,  # type: ignore[arg-type]
        selected_access="5g",
        access_type="3gpp",
        target=target,
        dnn=dnn,
        pdu_session_type="IPv4",
        service_type=service_type,
        size_bytes=size_bytes,
        qos_hint=qos_hint or {},
    )


class SessionManagementFunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.smf = SessionManagementFunction()

    def test_allocates_unique_addresses_and_per_ue_session_ids(self) -> None:
        first_ue = build_ue("ue_a")
        second_ue = build_ue("ue_b")
        first = self.smf.establish(first_ue, build_request("ue_a"), slice_id="embb")
        second = self.smf.establish(second_ue, build_request("ue_b"), slice_id="embb")

        self.assertEqual(first.pdu_session_id, 1)
        self.assertEqual(second.pdu_session_id, 1)
        self.assertNotEqual(first.ue_ip, second.ue_ip)
        self.assertEqual(first.upf_id, "internet_upf")

    def test_repeated_establishment_is_idempotent(self) -> None:
        ue = build_ue()
        request = build_request()
        first = self.smf.establish(ue, request, slice_id="embb")
        second = self.smf.establish(ue, request, slice_id="embb")
        self.assertIs(first, second)
        self.assertEqual(len(self.smf.list_sessions()), 1)

    def test_selects_upf_and_new_pool_for_another_dnn(self) -> None:
        ue = build_ue()
        internet = self.smf.establish(ue, build_request(), slice_id="embb")
        campus_request = build_request(
            dnn="campus",
            target="campus_iot",
            service_type="telemetry",
        )
        campus = self.smf.establish(ue, campus_request, slice_id="mmtc")

        self.assertEqual(campus.pdu_session_id, 2)
        self.assertEqual(campus.upf_id, "campus_upf")
        self.assertTrue(internet.ue_ip.startswith("10.20."))
        self.assertTrue(campus.ue_ip.startswith("10.30."))

    def test_rejects_unregistered_ue_and_disallowed_slice(self) -> None:
        with self.assertRaises(SmfSessionError):
            self.smf.establish(build_ue(registered=False), build_request(), slice_id="embb")
        with self.assertRaises(SmfSessionError):
            self.smf.establish(
                build_ue(allowed_slices=["embb"]),
                build_request(service_type="game", target="gaming_server"),
                slice_id="urllc",
            )

    def test_release_frees_address_and_registry_entry(self) -> None:
        first = self.smf.establish(build_ue("ue_a"), build_request("ue_a"), slice_id="embb")
        released = self.smf.release("ue_a", first.pdu_session_id)
        second = self.smf.establish(build_ue("ue_b"), build_request("ue_b"), slice_id="embb")

        self.assertEqual(released.state, "RELEASED")
        self.assertEqual(first.ue_ip, second.ue_ip)
        self.assertIsNone(self.smf.get_session("missing", 1))


class IPPacketFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.smf = SessionManagementFunction()
        self.factory = IPPacketFactory()

    def _session(self, request: UERequest, *, slice_id: str = "embb") -> PduSession:
        return self.smf.establish(build_ue(request.ue_id), request, slice_id=slice_id)

    def test_builds_ul_tcp_flow_with_packet_evidence(self) -> None:
        request = build_request(size_bytes=10_000)
        traffic = self.factory.build(request, self._session(request))

        self.assertEqual(traffic.src_ip, "10.20.0.2")
        self.assertEqual(traffic.dst_ip, "10.20.1.80")
        self.assertEqual((traffic.protocol, traffic.dst_port), ("TCP", 443))
        self.assertEqual(traffic.src_port, 49_153)
        self.assertEqual(traffic.packet_count, math.ceil(10_000 / 1460))
        self.assertEqual(traffic.network_bytes, 10_000 + traffic.packet_count * 40)
        self.assertEqual(traffic.metadata["pdu_session_id"], 1)
        self.assertEqual(traffic.metadata["packet_count"], traffic.packet_count)

    def test_builds_dl_flow_with_reversed_ip_endpoints(self) -> None:
        request = build_request(direction="DL", service_type="video_stream")
        traffic = self.factory.build(request, self._session(request))
        self.assertEqual(traffic.src_ip, "10.20.1.80")
        self.assertEqual(traffic.dst_ip, "10.20.0.2")
        self.assertEqual((traffic.src_port, traffic.dst_port), (443, 49_153))

    def test_selects_udp_for_game_service(self) -> None:
        request = build_request(target="gaming_server", service_type="game")
        traffic = self.factory.build(request, self._session(request, slice_id="urllc"))
        self.assertEqual((traffic.protocol, traffic.dst_port), ("UDP", 3074))
        self.assertEqual(traffic.transport_header_bytes, 8)

    def test_rejects_unknown_symbolic_target_and_session_mismatch(self) -> None:
        request = build_request(target="not_configured")
        session = self._session(request)
        with self.assertRaises(IPTrafficError):
            self.factory.build(request, session)
        with self.assertRaises(IPTrafficError):
            self.factory.build(build_request("another_ue"), session)

    def test_take_payload_tracks_remaining_bytes_and_packets(self) -> None:
        request = build_request(size_bytes=3_000)
        traffic = self.factory.build(request, self._session(request))
        consumed = traffic.take_payload(1_500)
        self.assertEqual(consumed, 1_500)
        self.assertEqual(traffic.remaining_bytes, 1_500)
        self.assertEqual(traffic.remaining_packet_count, math.ceil(1_500 / 1460))


class QoSFlowClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.smf = SessionManagementFunction()
        self.factory = IPPacketFactory()
        self.classifier = QoSFlowClassifier()

    def _classify(self, request: UERequest, *, slice_id: str) -> QoSFlow:
        session = self.smf.establish(build_ue(request.ue_id), request, slice_id=slice_id)
        traffic = self.factory.build(request, session)
        return self.classifier.build(request, session, traffic=traffic)

    def test_keeps_qfi_distinct_from_five_qi(self) -> None:
        flow = self._classify(
            build_request(target="gaming_server", service_type="game"),
            slice_id="urllc",
        )
        self.assertEqual(flow.qfi, 7)
        self.assertEqual(flow.five_qi, 80)
        self.assertLessEqual(flow.qfi, 63)

    def test_builds_gbr_video_call_profile(self) -> None:
        flow = self._classify(
            build_request(target="video_call_server", service_type="video_call"),
            slice_id="urllc",
        )
        self.assertEqual(flow.resource_type, "gbr")
        self.assertEqual(flow.gbr_mbps, 2.0)
        self.assertEqual(flow.mbr_mbps, 5.0)

    def test_session_slice_is_authoritative(self) -> None:
        request = build_request()
        session = PduSession(
            pdu_session_id=1,
            ue_id=request.ue_id,
            dnn=request.dnn,
            slice_id="research_slice",
            pdu_session_type="IPv4",
            ue_ip="10.20.0.9",
            smf_id="smf_test",
            upf_id="upf_test",
        )
        flow = self.classifier.build(request, session)
        self.assertEqual(flow.slice_id, "research_slice")

    def test_allocates_unique_qfi_when_profiles_collide(self) -> None:
        ue = build_ue()
        first_request = build_request()
        session = self.smf.establish(ue, first_request, slice_id="embb")
        first_traffic = self.factory.build(first_request, session)
        first = self.classifier.build(first_request, session, traffic=first_traffic)
        second_request = build_request(target="web_server", service_type="web")
        second_traffic = self.factory.build(second_request, session)
        second = self.classifier.build(second_request, session, traffic=second_traffic)

        self.assertEqual(first.qfi, 9)
        self.assertNotEqual(first.qfi, second.qfi)

    def test_latency_hint_can_tighten_but_not_relax_profile(self) -> None:
        tight = self._classify(
            build_request(qos_hint={"latency_budget_ms": 100}),
            slice_id="embb",
        )
        self.assertEqual(tight.packet_delay_budget_ms, 100)

        classifier = QoSFlowClassifier()
        request = build_request("ue_relaxed", qos_hint={"latency_budget_ms": 10_000})
        session = self.smf.establish(build_ue("ue_relaxed"), request, slice_id="embb")
        relaxed = classifier.build(request, session)
        self.assertEqual(relaxed.packet_delay_budget_ms, 300)

    def test_rule_with_unknown_profile_is_rejected(self) -> None:
        classifier = QoSFlowClassifier(
            [QoSRule(rule_id=1, profile_name="missing", service_type="video_upload")]
        )
        request = build_request()
        session = self.smf.establish(build_ue(), request, slice_id="embb")
        with self.assertRaises(QoSClassificationError):
            classifier.build(request, session)


class SdapMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = SdapMapper()

    def test_reliable_flow_uses_am_default_drb(self) -> None:
        request = build_request()
        drb = self.mapper.map(self._flow(service_type="video_upload", qfi=9), request)
        self.assertEqual(drb.rlc_mode, "AM")
        self.assertTrue(drb.default_drb)
        self.assertFalse(drb.sdap_header_present)
        self.assertEqual(drb.qfi_list, [9])

    def test_latency_sensitive_flow_uses_dedicated_um_drb(self) -> None:
        request = build_request(target="gaming_server", service_type="game")
        drb = self.mapper.map(
            self._flow(
                service_type="game",
                qfi=7,
                five_qi=80,
                priority=2,
                slice_id="urllc",
            ),
            request,
        )
        self.assertEqual(drb.rlc_mode, "UM")
        self.assertEqual(drb.qfi, 7)

    def test_compatible_non_gbr_flows_share_drb_and_qfi_list(self) -> None:
        first = self.mapper.map(self._flow(service_type="video_upload", qfi=9), build_request())
        second = self.mapper.map(
            self._flow(service_type="web", qfi=10, priority=7),
            build_request(target="web_server", service_type="web"),
        )
        self.assertEqual(first.drb_id, second.drb_id)
        self.assertEqual(first.qfi_list, [9, 10])
        self.assertEqual(second.qfi, 10)
        self.assertTrue(first.sdap_header_present)

    def test_gbr_flows_receive_distinct_dedicated_drbs(self) -> None:
        first = self.mapper.map(
            self._flow(
                service_type="video_call",
                qfi=2,
                five_qi=2,
                resource_type="gbr",
                gbr_mbps=2.0,
                mbr_mbps=5.0,
                slice_id="urllc",
            ),
            build_request(target="video_call_server", service_type="video_call"),
        )
        second = self.mapper.map(
            self._flow(
                service_type="voice_call",
                qfi=1,
                five_qi=1,
                resource_type="gbr",
                gbr_mbps=0.064,
                mbr_mbps=0.128,
                slice_id="urllc",
            ),
            build_request(target="video_call_server", service_type="voice_call"),
        )
        self.assertNotEqual(first.drb_id, second.drb_id)

    def test_mapping_is_idempotent_and_queryable(self) -> None:
        request = build_request()
        flow = self._flow(service_type="video_upload", qfi=9)
        first = self.mapper.map(flow, request)
        second = self.mapper.map(flow, request)
        mapping = self.mapper.get_mapping(
            ue_id=request.ue_id,
            pdu_session_id=1,
            direction="UL",
            qfi=9,
        )
        self.assertIs(first, second)
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.drb_id, first.drb_id)  # type: ignore[union-attr]
        self.assertEqual(len(self.mapper.list_mappings(ue_id=request.ue_id)), 1)

        self.mapper.release_session(request.ue_id, 1)
        self.assertEqual(self.mapper.list_mappings(ue_id=request.ue_id), [])

    def test_emits_formal_output_that_pdcp_consumes(self) -> None:
        request = build_request(size_bytes=3_000)
        traffic = self._traffic(request)
        output = self.mapper.process(
            traffic,
            self._flow(service_type="video_upload", qfi=9),
            request,
        )
        pdcp = build_pdcp_batch(output)

        self.assertIsInstance(output, SdapOutput)
        self.assertEqual(output.payload_bytes, 3_000)
        self.assertEqual(output.output_bytes, 3_000)
        self.assertFalse(output.sdap_header_present)
        self.assertEqual(pdcp.source_service_id, traffic.service_id)
        self.assertEqual(pdcp.drb_id, output.drb.drb_id)
        self.assertEqual(pdcp.qfi, output.qfi)
        self.assertEqual(pdcp.payload_bytes, output.output_bytes)

    def test_sdap_header_bytes_are_transferred_to_pdcp(self) -> None:
        first_request = build_request()
        first_output = self.mapper.process(
            self._traffic(first_request),
            self._flow(service_type="video_upload", qfi=9),
            first_request,
        )
        second_request = build_request(
            target="web_server",
            service_type="web",
            size_bytes=3_000,
        )
        second_output = self.mapper.process(
            self._traffic(second_request),
            self._flow(service_type="web", qfi=10, priority=7),
            second_request,
        )
        pdcp = build_pdcp_batch(second_output)

        self.assertFalse(first_output.sdap_header_present)
        self.assertFalse(first_output.drb.sdap_header_present)
        self.assertTrue(second_output.sdap_header_present)
        self.assertEqual(second_output.pdu_count, math.ceil(3_000 / 1_460))
        self.assertEqual(second_output.header_bytes, second_output.pdu_count)
        self.assertEqual(pdcp.sdap_header_bytes, second_output.header_bytes)
        self.assertEqual(pdcp.payload_bytes, second_output.output_bytes)

    def test_rejects_mismatched_ip_to_sdap_transfer(self) -> None:
        request = build_request()
        traffic = self._traffic(request)
        traffic.metadata["pdu_session_id"] = 2
        with self.assertRaises(SdapMappingError):
            self.mapper.process(
                traffic,
                self._flow(service_type="video_upload", qfi=9),
                request,
            )

    def test_legacy_pdcp_entry_point_remains_compatible(self) -> None:
        request = build_request(size_bytes=3_000)
        traffic = self._traffic(request)
        drb = self.mapper.map(self._flow(service_type="video_upload", qfi=9), request)
        pdcp = build_pdcp_batch(traffic=traffic, drb=drb)

        self.assertEqual(pdcp.drb_id, drb.drb_id)
        self.assertEqual(pdcp.qfi, drb.qfi)
        self.assertEqual(pdcp.payload_bytes, traffic.remaining_bytes)
        self.assertEqual(pdcp.sdap_header_bytes, 0)

    @staticmethod
    def _traffic(request: UERequest) -> IPTrafficBatch:
        return IPTrafficBatch(
            service_id=f"{request.ue_id}_{request.service_type}_test",
            src_ip="10.20.0.2",
            dst_ip="10.20.1.80",
            protocol="TCP",
            dst_port=443,
            direction=request.direction,
            total_bytes=request.size_bytes,
            remaining_bytes=request.size_bytes,
            metadata={
                "pdu_session_id": 1,
                "slice_id": "embb",
                "service_type": request.service_type,
            },
        )

    @staticmethod
    def _flow(
        *,
        service_type: str,
        qfi: int,
        five_qi: int = 9,
        priority: int = 5,
        resource_type: str = "non_gbr",
        gbr_mbps: float | None = None,
        mbr_mbps: float | None = None,
        slice_id: str = "embb",
    ) -> QoSFlow:
        return QoSFlow(
            pdu_session_id=1,
            qfi=qfi,
            five_qi=five_qi,
            direction="UL",
            service_type=service_type,
            priority=priority,
            packet_delay_budget_ms=300,
            packet_error_rate=1e-6,
            resource_type=resource_type,
            slice_id=slice_id,
            gbr_mbps=gbr_mbps,
            mbr_mbps=mbr_mbps,
        )


class ContractValidationTests(unittest.TestCase):
    def test_rejects_invalid_qfi_even_when_five_qi_is_valid(self) -> None:
        with self.assertRaises(ValueError):
            QoSFlow(
                pdu_session_id=1,
                qfi=80,
                five_qi=80,
                direction="UL",
                service_type="game",
                priority=2,
                packet_delay_budget_ms=50,
                packet_error_rate=1e-3,
                resource_type="non_gbr",
                slice_id="urllc",
            )

    def test_ip_contract_validates_headers_and_addresses(self) -> None:
        with self.assertRaises(ValueError):
            IPTrafficBatch(
                service_id="invalid",
                src_ip="not-an-ip",
                dst_ip="10.0.0.2",
                protocol="TCP",
                dst_port=443,
                direction="UL",
                total_bytes=100,
                remaining_bytes=100,
            )


class ScenarioIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_default_smf()
        reset_default_qos_classifier()
        reset_default_sdap_mapper()

    def test_first_tick_carries_consistent_session_qfi_and_drb_state(self) -> None:
        scene = SceneService().load_scene("bristol_topology")
        scenario = RanUploadScenario(scene)
        state = scenario.step(1)

        self.assertEqual(state["status"], "running")
        self.assertEqual(scenario.session.pdu_session_id, scenario.qos_flow.pdu_session_id)
        self.assertEqual(scenario.qos_flow.qfi, scenario.drb.qfi)
        self.assertIn(scenario.qos_flow.qfi, scenario.drb.qfi_list)
        self.assertEqual(scenario.sdap_output.qfi, scenario.qos_flow.qfi)
        self.assertEqual(scenario.sdap_output.drb.drb_id, scenario.drb.drb_id)
        self.assertEqual(scenario.pdcp_batch.drb_id, scenario.sdap_output.drb.drb_id)
        self.assertEqual(scenario.pdcp_batch.payload_bytes, scenario.sdap_output.output_bytes)
        self.assertEqual(scenario.session.slice_id, scenario.qos_flow.slice_id)
        self.assertEqual(scenario.traffic.metadata["smf_id"], scenario.session.smf_id)
        self.assertGreater(scenario.traffic.packet_count, 0)
        self.assertEqual(state["traffic"]["metadata"]["packet_count"], scenario.traffic.packet_count)
        self.assertEqual(state["sdap_output"]["qfi"], scenario.qos_flow.qfi)
        self.assertEqual(state["pdcp_batch"]["drb_id"], scenario.drb.drb_id)


if __name__ == "__main__":
    unittest.main()
