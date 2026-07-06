from __future__ import annotations


def estimate_transport_bytes(*, prbs: int, mcs: int, layers: int, slot_ms: float = 1.0) -> int:
    """估算 OFDM/PRB 可承载字节数。

    输入:
    - prbs: 分配 PRB 数。
    - mcs: 调制编码等级。
    - layers: MIMO 层数。
    - slot_ms: 当前 tick 对应的 slot 时间。

    输出:
    - 可承载字节数估计值。
    """

    # MVP 最小实现：用 MCS 查表近似 spectral efficiency，不模拟真实 OFDM symbol/subcarrier。
    spectral_efficiency = max(0.15, min(7.4, 0.25 + 0.32 * mcs))
    resource_elements_per_prb = 12 * 14
    bits = prbs * resource_elements_per_prb * spectral_efficiency * max(1, layers)
    return max(0, int(bits / 8 * max(0.1, slot_ms)))
