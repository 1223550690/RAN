"""UPF / N3 GTP 隧道实体测试:隧道管理、N6 接收缓冲、N3 转发、开销统计、UL 交付。"""
from __future__ import annotations

import unittest

from ran.core.upf import GtpTunnel, Upf, forward_via_upf
from ran.contracts import N3ForwardingResult, PduSession


class UpfTunnelTests(unittest.TestCase):
    def test_create_tunnel_unique_teid_and_idempotent(self) -> None:
        upf = Upf()
        t1 = upf.create_tunnel(1, "DL")
        t2 = upf.create_tunnel(2, "DL")
        t3 = upf.create_tunnel(1, "UL")
        self.assertEqual(t1.tunnel_id, "dl_1")
        self.assertEqual(t2.tunnel_id, "dl_2")
        self.assertEqual(t3.tunnel_id, "ul_1")
        self.assertNotEqual(t1.teid, t2.teid)
        self.assertNotEqual(t1.teid, t3.teid)
        # 幂等:同一 session+方向复用隧道
        self.assertIs(upf.create_tunnel(1, "DL"), t1)

    def test_receive_from_dn_buffers(self) -> None:
        upf = Upf()
        upf.receive_from_dn(7, 1000)
        self.assertEqual(upf.buffered_bytes(7), 1000)
        upf.receive_from_dn(7, 500)
        self.assertEqual(upf.buffered_bytes(7), 1500)

    def test_forward_to_gnb_consumes_buffer_and_counts_overhead(self) -> None:
        upf = Upf()
        upf.receive_from_dn(7, 10000)
        tunnel = upf.create_tunnel(7, "DL")
        tx = upf.forward_to_gnb(tunnel)
        self.assertEqual(tx, 10000)  # 瞬时到达
        self.assertEqual(upf.buffered_bytes(7), 0)
        # 开销:10000/1500 → 7 包 × 36 = 252
        self.assertEqual(tunnel.overhead_total_bytes, 7 * 36)

    def test_forward_to_gnb_n3_bandwidth_limits(self) -> None:
        upf = Upf(n3_bandwidth_mbps=1.0)  # 1 Mbps = 125 KB/s;tick_ms=200 → 25KB/tick
        upf.receive_from_dn(7, 100_000)
        tunnel = upf.create_tunnel(7, "DL")
        tx1 = upf.forward_to_gnb(tunnel, tick_ms=200.0)
        self.assertEqual(tx1, 25_000)
        self.assertEqual(upf.buffered_bytes(7), 75_000)
        tx2 = upf.forward_to_gnb(tunnel, tick_ms=200.0)
        self.assertEqual(tx2, 25_000)
        self.assertEqual(upf.buffered_bytes(7), 50_000)

    def test_max_bytes_caps_transfer(self) -> None:
        upf = Upf()
        upf.receive_from_dn(7, 5000)
        tunnel = upf.create_tunnel(7, "DL")
        tx = upf.forward_to_gnb(tunnel, max_bytes=2000)
        self.assertEqual(tx, 2000)
        self.assertEqual(upf.buffered_bytes(7), 3000)

    def _session(self) -> PduSession:
        return PduSession(
            pdu_session_id=3,
            ue_id="ue_1",
            dnn="internet",
            slice_id="embb",
            pdu_session_type="IPv4",
            ue_ip="10.0.0.2",
            smf_id="smf_001",
            upf_id="upf_001",
        )

    def test_forward_to_dn_via_tunnel(self) -> None:
        upf = Upf()
        tunnel = upf.create_tunnel(3, "UL")
        session = self._session()
        n3 = N3ForwardingResult(
            tunnel_id=tunnel.tunnel_id,
            teid=tunnel.teid,
            ue_id="ue_1",
            pdu_session_id=3,
            upf_id="upf_001",
            forwarded_bytes=4000,
            n3_delay_ms=2.0,
            n3_loss_bytes=0,
        )
        result = upf.forward_to_dn(n3, session, target="video_server")
        self.assertEqual(result.delivered_bytes, 4000)
        self.assertEqual(result.dnn, "internet")
        self.assertEqual(result.target, "video_server")
        # 开销统计:4000/1500 → 3 包 × 36 = 108
        self.assertEqual(tunnel.overhead_total_bytes, 3 * 36)

    def test_module_function_compat(self) -> None:
        session = self._session()
        n3 = N3ForwardingResult(
            tunnel_id="ul_1",
            teid=1,
            ue_id="ue_1",
            pdu_session_id=1,
            upf_id="upf_001",
            forwarded_bytes=100,
            n3_delay_ms=1.0,
            n3_loss_bytes=0,
        )
        result = forward_via_upf(n3, session, target="dn")
        self.assertEqual(result.delivered_bytes, 100)


if __name__ == "__main__":
    unittest.main()
