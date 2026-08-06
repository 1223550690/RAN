from __future__ import annotations

from ran.radio.mcs_tables import mcs_spectral_efficiency


def estimate_transport_bytes(*, prbs: int, mcs: int, layers: int, slot_ms: float = 1.0) -> int:
    """Compute transport bytes from the standard MCS table (phase 11: spectral efficiency from TS 38.214)."""

    spectral_efficiency = mcs_spectral_efficiency(mcs)
    resource_elements_per_prb = 12 * 14
    bits = prbs * resource_elements_per_prb * spectral_efficiency * max(1, layers)
    return max(0, int(bits / 8 * max(0.1, slot_ms)))
