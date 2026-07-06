from __future__ import annotations

from ran.contracts import N3ForwardingResult, N6DeliveryResult, PduSession


def forward_via_upf(n3_result: N3ForwardingResult, session: PduSession, *, target: str) -> N6DeliveryResult:
    """UPF 用户面转发。

    输入:
    - n3_result: gNB CU-UP 经 N3/GTP-U 送达 UPF 的结果。
    - session: PDU Session 上下文。
    - target: 应用目标服务。

    输出:
    - N6DeliveryResult: 送往 Data Network 的结果。
    """

    # MVP 最小实现：UPF 不执行 PDR/FAR/QER，只按 DNN 转发并增加固定 N6 时延。
    return N6DeliveryResult(
        dnn=session.dnn,
        target=target,
        delivered_bytes=n3_result.forwarded_bytes,
        n6_delay_ms=8.0,
        n6_loss_bytes=0,
    )
