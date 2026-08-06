from __future__ import annotations

from ran.contracts import ChannelState, GnbSite, MacAllocation, TransmissionResult, UEState
import math


def transmit(
    *,
    tick: int,
    allocation: MacAllocation,
    channel: ChannelState,
    rlc_mode: str = "AM",
    ue_state: UEState | None = None,
    gnb: GnbSite | None = None,
) -> TransmissionResult:
    """Execute the minimal PHY mock; before HARQ is implemented, final failures
    are explicitly handed to RLC or dropped.

    ue_state/gnb are the tr22068 PHR extension: when provided, the UE power
    headroom (power_report) is computed.
    """

    error_rate = max(allocation.expected_error_rate, channel.estimated_packet_error_rate)
    failed = int(allocation.scheduled_bytes * error_rate)
    successful = max(0, allocation.scheduled_bytes - failed)
    harq_retx = 0
    rlc_retx = failed if rlc_mode == "AM" else 0
    dropped = failed if rlc_mode != "AM" else 0
    power_report = 0.0
    if ue_state is not None and gnb is not None:
        if allocation.prbs != 0:
            power_report = ue_state.cmax_transmit - (10 * math.log(allocation.prbs, 10) + gnb.nominal_pusch + 0.8 * channel.total_path_loss_db)
        else:
            power_report = ue_state.cmax_transmit + gnb.nominal_pusch + 0.8 * channel.total_path_loss_db
    return TransmissionResult(
        tick=tick,
        ue_id=allocation.ue_id,
        gnb_id=channel.gnb_id,
        drb_id=allocation.drb_id,
        qfi=allocation.qfi,
        slice_id=allocation.slice_id,
        direction=allocation.direction,
        attempted_bytes=allocation.scheduled_bytes,
        successful_bytes=successful,
        failed_bytes=failed,
        effective_sinr_db=channel.sinr_db,
        mcs=allocation.mcs,
        prbs=allocation.prbs,
        layers=allocation.layers,
        harq_ack=failed == 0,
        harq_retx_bytes=harq_retx,
        rlc_retx_bytes=rlc_retx,
        dropped_bytes=dropped,
        transmission_delay_ms=1.0,
        power_report=power_report,
    )
