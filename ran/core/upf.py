"""Core network user plane: UPF entity + GTP-U tunnels (simplified 3GPP semantics).

Path: DN → N6 → UPF → N3 (GTP-U) → gNB → radio → UE (downlink)
      UE → radio → gNB → N3 (GTP-U) → UPF → N6 → DN (uplink)

Entities:
- GtpTunnel: tunnel (unique teid, GTP-U overhead accounting).
- Upf: one per scenario; N6 reception (DL buffering), N3 forwarding, N6 delivery (UL accounting).
  Pure in-process object, zero third-party dependencies; GTP-U only counts bytes/overhead, never modifies packets.

Compatibility: module-level forward_via_upf is kept (equivalent to stateless accounting; zero breakage for legacy callers).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ran.contracts import N3ForwardingResult, N6DeliveryResult, PduSession

# GTP-U overhead: outer IP (20) + UDP (8) + GTP-U (8) = 36 bytes/packet
GTP_OVERHEAD_BYTES = 36
# Simulated MTU: estimate packet count at 1500B (for overhead accounting only)
MTU_BYTES = 1500


@dataclass(slots=True)
class GtpTunnel:
    """A single GTP-U tunnel (one (UE, PDU Session, direction) combination)."""

    tunnel_id: str  # tunnel_id: "{direction}_{ue_id}_{pdu_session_id}".
    teid: int
    direction: str
    pdu_session_id: int
    ue_id: str = ""  # ue_id: UE owning the tunnel (isolation key for multiple UEs).
    peer_address: str = "gnb"  # peer_address: peer (symbolic address in simulation).
    gtp_overhead_bytes: int = GTP_OVERHEAD_BYTES  # gtp_overhead_bytes: GTP-U overhead per packet.
    overhead_total_bytes: int = 0  # overhead_total_bytes: cumulative overhead (for statistics).


class Upf:
    """Core network user plane function: tunnel management, DL buffering (N6 receive), N3 forwarding, UL delivery."""

    def __init__(self, *, n3_bandwidth_mbps: float | None = None) -> None:
        self.tunnels: dict[str, GtpTunnel] = {}
        self.buffers: dict[str, int] = {}  # (ue_id, pdu_session_id) -> DL buffered bytes on the UPF side
        self._next_teid = 1000
        self.n3_bandwidth_mbps = n3_bandwidth_mbps  # None=instant arrival

    # ---------------------------------------------------------------- Tunnels

    def create_tunnel(self, ue_id: str, pdu_session_id: int, direction: str) -> GtpTunnel:
        """Create a GTP-U tunnel for (UE, PDU Session, direction).

        Note: the key must include ue_id -- in multi-UE scenarios each UE's
        pdu_session_id is allocated from 1, so using only the session id would
        make tunnels/buffers overwrite each other (data from three concurrent
        video_download flows in template 2 would mix into the same queue).
        """

        tunnel_id = self._tunnel_key(ue_id, pdu_session_id, direction)
        if tunnel_id in self.tunnels:
            return self.tunnels[tunnel_id]
        teid = self._next_teid
        self._next_teid += 1
        tunnel = GtpTunnel(
            tunnel_id=tunnel_id,
            teid=teid,
            direction=direction.upper(),
            pdu_session_id=pdu_session_id,
            ue_id=ue_id,
        )
        self.tunnels[tunnel_id] = tunnel
        return tunnel

    @staticmethod
    def _tunnel_key(ue_id: str, pdu_session_id: int, direction: str) -> str:
        return f"{direction.lower()}_{ue_id}_{pdu_session_id}"

    def tunnel_of(self, ue_id: str, pdu_session_id: int, direction: str) -> GtpTunnel | None:
        return self.tunnels.get(self._tunnel_key(ue_id, pdu_session_id, direction))

    # ---------------------------------------------------------------- N6 / N3

    def receive_from_dn(self, ue_id: str, pdu_session_id: int, bytes_total: int) -> None:
        """N6: data from DN arrives → enters UPF buffer (downlink; no data loss while UE is suspended)."""

        key = f"{ue_id}:{pdu_session_id}"
        self.buffers[key] = self.buffers.get(key, 0) + bytes_total

    def buffered_bytes(self, ue_id: str, pdu_session_id: int) -> int:
        return self.buffers.get(f"{ue_id}:{pdu_session_id}", 0)

    def forward_to_gnb(
        self,
        tunnel: GtpTunnel,
        *,
        tick_ms: float = 200.0,
        max_bytes: int | None = None,
    ) -> int:
        """N3: UPF buffer → gNB (downlink). Returns the actually forwarded traffic bytes; bounded by N3 bandwidth and buffer contents."""

        key = f"{tunnel.ue_id}:{tunnel.pdu_session_id}"
        available = self.buffers.get(key, 0)
        if available <= 0:
            return 0
        limit = max_bytes if max_bytes is not None else available
        if self.n3_bandwidth_mbps is not None:
            capacity = int(self.n3_bandwidth_mbps * 1_000_000 / 8 * tick_ms / 1000)
            limit = min(limit, capacity)
        tx = min(available, limit)
        self.buffers[key] = available - tx
        # GTP-U overhead accounting: estimate packet count by MTU
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
        """N3 arrival at UPF (uplink) → N6 delivery to DN. Uses the tunnel instance (when present); semantics match the module function."""

        tunnel = self.tunnel_of(session.ue_id, session.pdu_session_id, "UL")
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
    """Compatibility entry point: stateless UPF accounting (equivalent to Upf().forward_to_dn)."""

    return Upf().forward_to_dn(n3_result, session, target=target)
