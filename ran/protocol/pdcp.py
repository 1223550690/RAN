from __future__ import annotations

import math
from dataclasses import dataclass

from ran.contracts import Drb, IPTrafficBatch


@dataclass(slots=True)
class PdcpBatch:
    """Project implementation detail."""

    drb_id: int
    qfi: int
    slice_id: str
    payload_bytes: int
    overhead_bytes: int
    output_bytes: int
    sn_start: int
    sn_end: int


@dataclass(slots=True)
class PdcpEntity:
    """Project implementation detail."""

    drb_id: int
    qfi: int
    slice_id: str
    next_sn: int = 0
    sn_size_bits: int = 18
    header_overhead_bytes: int = 2
    nominal_packet_size: int = 1500
    per_tick_inflow_bytes: int | None = None
    # reserved interfaces (no-op, not yet implemented)
    ciphering_enabled: bool = False
    integrity_enabled: bool = False
    header_compression_enabled: bool = False
    reordering_buffer_bytes: int = 0
    delivered_bytes: int = 0
    dropped_bytes: int = 0

    def process(self, traffic: IPTrafficBatch, *, tick: int) -> PdcpBatch:
        """Project implementation detail."""

        capacity = self.per_tick_inflow_bytes if self.per_tick_inflow_bytes is not None else traffic.remaining_bytes
        payload = max(0, min(traffic.remaining_bytes, capacity))
        if payload <= 0:
            return PdcpBatch(
                drb_id=self.drb_id,
                qfi=self.qfi,
                slice_id=self.slice_id,
                payload_bytes=0,
                overhead_bytes=0,
                output_bytes=0,
                sn_start=self.next_sn,
                sn_end=self.next_sn,
            )

        pdu_count = max(1, math.ceil(payload / self.nominal_packet_size))
        modulus = 2 ** self.sn_size_bits
        sn_start = self.next_sn
        sn_end = (self.next_sn + pdu_count - 1) % modulus
        self.next_sn = (self.next_sn + pdu_count) % modulus

        overhead = pdu_count * self.header_overhead_bytes
        overhead = self._compress_header(overhead)
        overhead = self._apply_integrity(overhead)
        payload = self._apply_ciphering(payload)

        traffic.remaining_bytes -= payload
        return PdcpBatch(
            drb_id=self.drb_id,
            qfi=self.qfi,
            slice_id=self.slice_id,
            payload_bytes=payload,
            overhead_bytes=overhead,
            output_bytes=payload + overhead,
            sn_start=sn_start,
            sn_end=sn_end,
        )

    def _apply_ciphering(self, payload_bytes: int) -> int:
        """Project implementation detail. TODO: reserved for ciphering."""
        return payload_bytes

    def _apply_integrity(self, overhead_bytes: int) -> int:
        """Project implementation detail. TODO: reserved for integrity protection (MAC-I)."""
        return overhead_bytes

    def _compress_header(self, overhead_bytes: int) -> int:
        """Project implementation detail. TODO: reserved for header compression (ROHC)."""
        return overhead_bytes

    def reorder(self, batch: PdcpBatch) -> PdcpBatch:
        """Project implementation detail. TODO: reserved for receive-side reordering."""
        return batch

    def deduplicate(self, batch: PdcpBatch) -> PdcpBatch:
        """Project implementation detail. TODO: reserved for receive-side deduplication."""
        return batch


def build_pdcp_batch(
    traffic: IPTrafficBatch, drb: Drb, *, max_batch_bytes: int | None = None
) -> PdcpBatch:
    """Project implementation detail.

    Compatibility wrapper — delegates to PdcpEntity.process.  Preserves the
    original call signature and return type.  Note: this mutates
    ``traffic.remaining_bytes`` (same as the original implementation).
    """
    entity = PdcpEntity(
        drb_id=drb.drb_id,
        qfi=drb.qfi,
        slice_id=drb.slice_id,
        per_tick_inflow_bytes=max_batch_bytes,
    )
    return entity.process(traffic, tick=0)
