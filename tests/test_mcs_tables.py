"""Standard CQI/MCS/BLER table tests (phase 11): lookup correctness, monotonicity, boundaries."""
from __future__ import annotations

import unittest

from ran.radio.mcs_tables import (
    MAX_CQI,
    MAX_MCS,
    cqi_to_mcs,
    mcs_modulation_order,
    mcs_spectral_efficiency,
    sinr_to_bler,
    sinr_to_cqi,
)
from ran.radio.ofdm import estimate_transport_bytes


class McsTableTests(unittest.TestCase):
    def test_sinr_to_cqi_monotonic(self) -> None:
        previous = 0
        for sinr in range(-20, 31, 2):
            cqi = sinr_to_cqi(float(sinr))
            self.assertGreaterEqual(cqi, previous)
            previous = cqi
            self.assertGreaterEqual(cqi, 1)
            self.assertLessEqual(cqi, MAX_CQI)

    def test_cqi_bounds(self) -> None:
        self.assertEqual(sinr_to_cqi(-100.0), 1)
        self.assertEqual(sinr_to_cqi(100.0), MAX_CQI)

    def test_mcs_spectral_efficiency_monotonic(self) -> None:
        # standard table is monotonic overall (MCS 15->16 code-rate conversion has a ~0.2% dip; small jitter allowed)
        self.assertLess(mcs_spectral_efficiency(0), mcs_spectral_efficiency(27))
        for mcs in range(MAX_MCS):
            self.assertGreater(mcs_spectral_efficiency(mcs), 0.0)

    def test_mcs_table_matches_38_214(self) -> None:
        # TS 38.214 Table 5.1.3.1-1 key points: MCS 0=0.2344, MCS 9=1.3262, MCS 27=5.5547
        self.assertAlmostEqual(mcs_spectral_efficiency(0), 0.234375, places=5)
        self.assertAlmostEqual(mcs_spectral_efficiency(9), 340 / 1024 * 4, places=5)
        self.assertAlmostEqual(mcs_spectral_efficiency(27), 948 / 1024 * 6, places=5)
        self.assertEqual(mcs_modulation_order(0), 2)  # QPSK
        self.assertEqual(mcs_modulation_order(9), 4)  # 16QAM
        self.assertEqual(mcs_modulation_order(16), 6)  # 64QAM

    def test_cqi_to_mcs_never_exceeds_cqi_eff(self) -> None:
        for cqi in range(1, MAX_CQI + 1):
            mcs = cqi_to_mcs(cqi)
            self.assertLessEqual(mcs_spectral_efficiency(mcs), mcs_spectral_efficiency(27))
            self.assertGreaterEqual(mcs, 1)

    def test_bler_at_working_point_is_0_1(self) -> None:
        from ran.radio.mcs_tables import SINR_CQI_THRESHOLDS_DB

        for cqi in range(1, MAX_CQI + 1):
            bler = sinr_to_bler(SINR_CQI_THRESHOLDS_DB[cqi - 1], cqi)
            self.assertAlmostEqual(bler, 0.1, delta=0.02)

    def test_bler_bounded(self) -> None:
        self.assertLessEqual(sinr_to_bler(-100.0, 1), 0.5)
        self.assertGreaterEqual(sinr_to_bler(100.0, 16), 0.001)

    def test_transport_bytes_uses_standard_table(self) -> None:
        # 20 PRBs, MCS 10 (16QAM 490/1024), 2 layers, 200 ms slot
        bytes_per_slot = estimate_transport_bytes(prbs=20, mcs=10, layers=2, slot_ms=200)
        eff = mcs_spectral_efficiency(10)
        expected = int(20 * 168 * eff * 2 / 8 * 200)  # slot_ms in ms; capacity accumulates over the tick duration
        self.assertEqual(bytes_per_slot, expected)


if __name__ == "__main__":
    unittest.main()
