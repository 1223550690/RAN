from __future__ import annotations

from ran.contracts import ChannelState, MacAllocation, TransmissionResult, UEState, GnbSite
import math


def transmit(*, tick: int, allocation: MacAllocation, channel: ChannelState, ue_state: UEState, gnb:GnbSite) -> TransmissionResult:
    """Project implementation detail."""

    error_rate = max(allocation.expected_error_rate, channel.estimated_packet_error_rate)
    failed = int(allocation.scheduled_bytes * error_rate)
    successful = max(0, allocation.scheduled_bytes - failed)
    harq_retx = failed if error_rate <= 0.15 else int(failed * 0.5)
    rlc_retx = failed - harq_retx
    power_report = ue_state.cmax_transmit - (10*math.log(allocation.prbs,10) + gnb.nominal_pusch + channel.total_path_loss_db)
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
        dropped_bytes=0,
        transmission_delay_ms=1.0,
        power_report=power_report
    )
