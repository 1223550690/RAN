from __future__ import annotations

from ran.contracts import Drb, RlcQueue, TransmissionResult
from .pdcp import PdcpBatch


def build_rlc_queue(batch: PdcpBatch, drb: Drb) -> RlcQueue:
    """生成 RLC 队列。

    输入:
    - batch: PDCP 输出批次。
    - drb: DRB 配置。

    输出:
    - RlcQueue: scheduler 的主要输入。
    """

    # MVP 最小实现：不做真实分段，只把 PDCP 输出字节放入 RLC 队列。
    return RlcQueue(
        ue_id=drb.ue_id,
        drb_id=drb.drb_id,
        qfi=drb.qfi,
        slice_id=drb.slice_id,
        direction=drb.direction,
        rlc_mode=drb.rlc_mode,
        queued_bytes=batch.output_bytes,
        retransmission_bytes=0,
        head_of_line_delay_ms=0.0,
    )


def apply_transmission_to_rlc(queue: RlcQueue, result: TransmissionResult) -> RlcQueue:
    """根据 PHY 结果更新 RLC 队列。

    输入:
    - queue: 原 RLC 队列。
    - result: PHY 传输结果。

    输出:
    - RlcQueue: 更新后的队列快照。
    """

    queue.queued_bytes = max(0, queue.queued_bytes - result.successful_bytes - result.failed_bytes)
    if queue.rlc_mode == "AM":
        queue.retransmission_bytes += result.rlc_retx_bytes
    # MVP 最小实现：队首时延按单次 tick 粗略增加；后续应按 PDU/segment 维护。
    if queue.queued_bytes > 0 or queue.retransmission_bytes > 0:
        queue.head_of_line_delay_ms += result.transmission_delay_ms
    return queue
