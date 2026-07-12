from __future__ import annotations


def estimate_transport_bytes(*, prbs: int, mcs: int, layers: int, slot_ms: float = 1.0) -> int:
    """Project implementation detail."""

    spectral_efficiency = max(0.15, min(7.4, 0.25 + 0.32 * mcs))
    resource_elements_per_prb = 12 * 14
    bits = prbs * resource_elements_per_prb * spectral_efficiency * max(1, layers)
    return max(0, int(bits / 8 * max(0.1, slot_ms)))
