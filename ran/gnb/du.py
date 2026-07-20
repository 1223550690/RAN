from __future__ import annotations

from ran.contracts import ChannelState, Drb, QoSFlow, RlcQueue, SchedulerRequest, SlicePolicy, TransmissionResult


def build_scheduler_request(
    *,
    tick: int,
    total_prbs: int,
    rlc_queues: list[RlcQueue],
    qos_flows: list[QoSFlow],
    drbs: list[Drb],
    channel_states: list[ChannelState],
    slice_policies: list[SlicePolicy],
    power_report: float
) -> SchedulerRequest:
    """构造 gNB-DU MAC scheduler 输入。

    输入:
    - RLC queue、QoS、DRB、信道、切片策略。

    输出:
    - SchedulerRequest。
    """

    return SchedulerRequest(
        tick=tick,
        direction="UL",
        total_prbs=total_prbs,
        rlc_queues=rlc_queues,
        qos_flows=qos_flows,
        drbs=drbs,
        channel_states=channel_states,
        slice_policies=slice_policies,
        phr=power_report if power_report else 0.0
    )
