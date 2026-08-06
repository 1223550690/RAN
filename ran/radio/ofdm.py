from __future__ import annotations

from ran.radio.mcs_tables import mcs_spectral_efficiency


def estimate_transport_bytes(*, prbs: int, mcs: int, layers: int, slot_ms: float = 1.0) -> int:
    """按标准 MCS 表计算传输字节(环节十一:频谱效率来自 TS 38.214)。"""

    spectral_efficiency = mcs_spectral_efficiency(mcs)
    resource_elements_per_prb = 12 * 14
    bits = prbs * resource_elements_per_prb * spectral_efficiency * max(1, layers)
    return max(0, int(bits / 8 * max(0.1, slot_ms)))
