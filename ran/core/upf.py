"""核心网用户面:UPF 实体 + GTP-U 隧道(3GPP 语义简化)。

路径:DN → N6 → UPF → N3(GTP-U)→ gNB → 无线 → UE(下行)
     UE → 无线 → gNB → N3(GTP-U)→ UPF → N6 → DN(上行)

实体:
- GtpTunnel:隧道(teid 唯一、GTP-U 开销统计)。
- Upf:每场景一个;N6 接收(DL 缓冲)、N3 转发、N6 交付(UL 统计)。
  纯进程内对象,零第三方依赖;GTP-U 只做字节/开销计数,不真正改包。

兼容:模块级 forward_via_upf 保留(等价于无状态统计,旧调用零破坏)。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ran.contracts import N3ForwardingResult, N6DeliveryResult, PduSession

# GTP-U 开销:外层 IP(20)+ UDP(8)+ GTP-U(8)= 36 字节/包
GTP_OVERHEAD_BYTES = 36
# 仿真 MTU:按 1500B 估算包数(仅用于开销统计)
MTU_BYTES = 1500


@dataclass(slots=True)
class GtpTunnel:
    """一条 GTP-U 隧道(承载一个 PDU Session 的一个方向)。"""

    tunnel_id: str  # tunnel_id: "dl_{pdu_session_id}" / "ul_{pdu_session_id}"。
    teid: int  # teid: 隧道端点标识(分配器保证唯一)。
    direction: str  # direction: UL / DL。
    pdu_session_id: int
    peer_address: str = "gnb"  # peer_address: 对端(仿真符号地址)。
    gtp_overhead_bytes: int = GTP_OVERHEAD_BYTES  # gtp_overhead_bytes: 每包 GTP-U 开销。
    overhead_total_bytes: int = 0  # overhead_total_bytes: 累计开销(统计用)。


class Upf:
    """核心网用户面功能:隧道管理、DL 缓冲(N6 接收)、N3 转发、UL 交付。"""

    def __init__(self, *, n3_bandwidth_mbps: float | None = None) -> None:
        self.tunnels: dict[str, GtpTunnel] = {}
        self.buffers: dict[str, int] = {}  # pdu_session_id -> UPF 侧 DL 缓冲字节
        self._next_teid = 1000
        self.n3_bandwidth_mbps = n3_bandwidth_mbps  # None=瞬时到达

    # ---------------------------------------------------------------- 隧道

    def create_tunnel(self, pdu_session_id: int, direction: str) -> GtpTunnel:
        """为 PDU Session 的一个方向建立 GTP-U 隧道。"""

        tunnel_id = f"{direction.lower()}_{pdu_session_id}"
        if tunnel_id in self.tunnels:
            return self.tunnels[tunnel_id]
        teid = self._next_teid
        self._next_teid += 1
        tunnel = GtpTunnel(
            tunnel_id=tunnel_id,
            teid=teid,
            direction=direction.upper(),
            pdu_session_id=pdu_session_id,
        )
        self.tunnels[tunnel_id] = tunnel
        return tunnel

    def tunnel_of(self, pdu_session_id: int, direction: str) -> GtpTunnel | None:
        return self.tunnels.get(f"{direction.lower()}_{pdu_session_id}")

    # ---------------------------------------------------------------- N6 / N3

    def receive_from_dn(self, pdu_session_id: int, bytes_total: int) -> None:
        """N6:DN 数据到达 → 进入 UPF 缓冲(下行;UE 挂起期间数据不丢)。"""

        self.buffers[str(pdu_session_id)] = self.buffers.get(str(pdu_session_id), 0) + bytes_total

    def buffered_bytes(self, pdu_session_id: int) -> int:
        return self.buffers.get(str(pdu_session_id), 0)

    def forward_to_gnb(
        self,
        tunnel: GtpTunnel,
        *,
        tick_ms: float = 200.0,
        max_bytes: int | None = None,
    ) -> int:
        """N3:UPF 缓冲 → gNB(下行)。返回实际转发业务字节;受 N3 带宽与缓冲量约束。"""

        session_id = str(tunnel.pdu_session_id)
        available = self.buffers.get(session_id, 0)
        if available <= 0:
            return 0
        limit = max_bytes if max_bytes is not None else available
        if self.n3_bandwidth_mbps is not None:
            capacity = int(self.n3_bandwidth_mbps * 1_000_000 / 8 * tick_ms / 1000)
            limit = min(limit, capacity)
        tx = min(available, limit)
        self.buffers[session_id] = available - tx
        # GTP-U 开销统计:按 MTU 估算包数
        packets = (tx + MTU_BYTES - 1) // MTU_BYTES
        tunnel.overhead_total_bytes += packets * tunnel.gtp_overhead_bytes
        return tx

    def forward_to_dn(
        self,
        n3_result: N3ForwardingResult,
        session: PduSession,
        *,
        target: str,
    ) -> N6DeliveryResult:
        """N3 到达 UPF(上行)→ N6 交付 DN。走隧道实例(存在时),语义同模块函数。"""

        tunnel = self.tunnel_of(session.pdu_session_id, "UL")
        if tunnel is not None:
            packets = (n3_result.forwarded_bytes + MTU_BYTES - 1) // MTU_BYTES
            tunnel.overhead_total_bytes += packets * tunnel.gtp_overhead_bytes
        return N6DeliveryResult(
            dnn=session.dnn,
            target=target,
            delivered_bytes=n3_result.forwarded_bytes,
            n6_delay_ms=8.0,
            n6_loss_bytes=0,
        )


def forward_via_upf(n3_result: N3ForwardingResult, session: PduSession, *, target: str) -> N6DeliveryResult:
    """兼容入口:无状态 UPF 统计(等价于 Upf().forward_to_dn)。"""

    return Upf().forward_to_dn(n3_result, session, target=target)
