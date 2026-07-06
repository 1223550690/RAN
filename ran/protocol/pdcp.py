from __future__ import annotations

from dataclasses import dataclass

from ran.contracts import Drb, IPTrafficBatch


@dataclass(slots=True)
class PdcpBatch:
    """PDCP 输出批次。

    输入字段:
    - DRB 与 IP traffic batch。

    输出字段:
    - output_bytes: 加上 PDCP header 后交给 RLC 的字节数。
    """

    drb_id: int  # drb_id: 所属 DRB。
    qfi: int  # qfi: 所属 QoS Flow。
    slice_id: str  # slice_id: 切片标识。
    payload_bytes: int  # payload_bytes: 上层业务字节。
    overhead_bytes: int  # overhead_bytes: PDCP 头部开销。
    output_bytes: int  # output_bytes: 交给 RLC 的总字节。
    sn_start: int  # sn_start: 起始序号。
    sn_end: int  # sn_end: 结束序号。


def build_pdcp_batch(traffic: IPTrafficBatch, drb: Drb, *, max_batch_bytes: int | None = None) -> PdcpBatch:
    """生成 PDCP 批次。

    输入:
    - traffic: IP 业务批次。
    - drb: SDAP 映射出的 DRB。
    - max_batch_bytes: 本次最多处理字节，MVP 默认处理全部业务。

    输出:
    - PdcpBatch。
    """

    payload = min(traffic.remaining_bytes, max_batch_bytes or traffic.remaining_bytes)
    # MVP 最小实现：按每 1500 bytes 一个 PDCP PDU 估算 header，不实现真实加密/重排序。
    pdu_count = max(1, (payload + 1499) // 1500)
    overhead = pdu_count * 2
    return PdcpBatch(
        drb_id=drb.drb_id,
        qfi=drb.qfi,
        slice_id=drb.slice_id,
        payload_bytes=payload,
        overhead_bytes=overhead,
        output_bytes=payload + overhead,
        sn_start=0,
        sn_end=pdu_count - 1,
    )
