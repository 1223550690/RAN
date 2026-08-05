from __future__ import annotations

from ran.contracts import CONTRACT_VERSION, ChannelState, Drb, QoSFlow, RlcQueue, SchedulerRequest, SlicePolicy


def build_scheduler_request(
    *,
    simulation_id: str,
    tick: int,
    gnb_id: str,
    total_prbs: int,
    rlc_queues: list[RlcQueue],
    qos_flows: list[QoSFlow],
    drbs: list[Drb],
    channel_states: list[ChannelState],
    slice_policies: list[SlicePolicy],
    power_report: list[float] | None = None,
    requirements: list[str] | None = None,
) -> SchedulerRequest:
    """汇总所有活跃 UE/DRB，构造一次 UL SchedulerRequest。

    power_report / requirements 为 tr22068 调度扩展字段，缺省为空列表。
    """

    return SchedulerRequest(
        contract_version=CONTRACT_VERSION,
        simulation_id=simulation_id,
        scheduler_request_id=f"scheduler_request_{simulation_id}_{tick}_UL",
        tick=tick,
        gnb_id=gnb_id,
        direction="UL",
        total_prbs=total_prbs,
        rlc_queues=rlc_queues,
        qos_flows=qos_flows,
        drbs=drbs,
        channel_states=channel_states,
        slice_policies=slice_policies,
        phr=list(power_report or []),
        requirements=list(requirements or []),
    )
