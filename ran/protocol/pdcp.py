from __future__ import annotations

from dataclasses import dataclass

from ran.contracts import Drb, IPTrafficBatch
from .sdap import SdapOutput


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
    source_service_id: str = ""
    sdap_payload_bytes: int = 0
    sdap_header_bytes: int = 0


def build_pdcp_batch(
    traffic: SdapOutput | IPTrafficBatch,
    drb: Drb | None = None,
    *,
    max_batch_bytes: int | None = None,
) -> PdcpBatch:
    """Build a PDCP batch from formal SDAP output.

    ``IPTrafficBatch`` plus ``Drb`` remains accepted as a compatibility path
    for older callers, while the integrated scenario uses ``SdapOutput``.
    """

    if max_batch_bytes is not None and max_batch_bytes <= 0:
        raise ValueError("max_batch_bytes must be positive when provided")

    source = traffic
    if isinstance(source, SdapOutput):
        selected_drb = source.drb
        available_bytes = source.output_bytes
        source_service_id = source.service_id
        sdap_header_bytes = source.header_bytes
    else:
        if drb is None:
            raise TypeError("legacy IPTrafficBatch input also requires a Drb")
        selected_drb = drb
        available_bytes = source.remaining_bytes
        source_service_id = source.service_id
        sdap_header_bytes = 0

    payload = min(
        available_bytes,
        max_batch_bytes if max_batch_bytes is not None else available_bytes,
    )
    transferred_header_bytes = min(sdap_header_bytes, payload)
    transferred_sdap_payload_bytes = payload - transferred_header_bytes
    pdu_count = (payload + 1499) // 1500 if payload else 0
    overhead = pdu_count * 2
    return PdcpBatch(
        drb_id=selected_drb.drb_id,
        qfi=selected_drb.qfi,
        slice_id=selected_drb.slice_id,
        payload_bytes=payload,
        overhead_bytes=overhead,
        output_bytes=payload + overhead,
        sn_start=0,
        sn_end=pdu_count - 1 if pdu_count else -1,
        source_service_id=source_service_id,
        sdap_payload_bytes=transferred_sdap_payload_bytes,
        sdap_header_bytes=transferred_header_bytes,
    )
