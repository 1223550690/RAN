from __future__ import annotations

import math
import unittest

from experiments.debug_3gpp_pathloss import build_debug_report
from ran.radio.pathloss_3gpp import (
    NLOS,
    PathLossRequest,
    SCENARIO_UMI_STREET_CANYON,
)


class PathLossDebugReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = PathLossRequest(
            scenario=SCENARIO_UMI_STREET_CANYON,
            los_state=NLOS,
            carrier_frequency_mhz=3500.0,
            distance_2d_m=100.0,
            distance_3d_m=math.hypot(100.0, 8.5),
            bs_height_m=10.0,
            ut_height_m=1.5,
        )

    def test_report_compares_3gpp_with_physical_fspl_baseline(self) -> None:
        report = build_debug_report(self.request)

        self.assertAlmostEqual(report["mean_path_loss_db"], 104.6438320117)
        self.assertAlmostEqual(report["baseline_fspl_db"], 83.3126258541)
        self.assertAlmostEqual(
            report["difference_from_baseline_db"],
            21.3312061575,
        )
        self.assertEqual(report["breakpoint_distance_m"], 210.0)
        self.assertEqual(report["shadow_fading_std_db"], 7.82)

    def test_report_is_deterministic_for_the_same_request(self) -> None:
        self.assertEqual(
            build_debug_report(self.request),
            build_debug_report(self.request),
        )


if __name__ == "__main__":
    unittest.main()
