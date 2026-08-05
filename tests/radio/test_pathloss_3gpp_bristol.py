from __future__ import annotations

import unittest

from experiments.debug_bristol_3gpp_pathloss import build_bristol_report


class Bristol3gppDryRunTests(unittest.TestCase):
    def test_report_exposes_supported_and_unsupported_links(self) -> None:
        report = build_bristol_report(gnb_height_m=10.0)
        cases = {case["case_id"]: case for case in report["cases"]}

        self.assertEqual(report["calibration"]["status"], "provisional")
        self.assertIn(
            "provisional_calibration_has_no_reference_anchors",
            report["calibration"]["validation_warnings"],
        )
        self.assertEqual(
            cases["outdoor_green"]["adaptation"]["status"],
            "supported",
        )
        self.assertEqual(
            cases["outdoor_east_of_student_union"]["adaptation"]["status"],
            "supported",
        )
        self.assertEqual(
            cases["student_union_center"]["adaptation"]["status"],
            "unsupported",
        )
        self.assertEqual(
            cases["gym_center"]["adaptation"]["status"],
            "unsupported",
        )
        self.assertIsNone(
            cases["student_union_center"]["adaptation"]["path_loss"]
        )
        self.assertIsNone(cases["gym_center"]["adaptation"]["path_loss"])

    def test_supported_cases_include_formula_and_baseline_comparison(self) -> None:
        report = build_bristol_report(gnb_height_m=10.0)
        cases = {case["case_id"]: case for case in report["cases"]}

        outdoor_los = cases["outdoor_green"]["adaptation"]["path_loss"]
        outdoor_nlos = cases["outdoor_east_of_student_union"]["adaptation"][
            "path_loss"
        ]
        self.assertEqual(
            outdoor_los["formula_id"],
            "3gpp_38_901_v19_4_0_umi_los_pl1",
        )
        self.assertEqual(
            outdoor_nlos["formula_id"],
            "3gpp_38_901_v19_4_0_umi_nlos",
        )
        self.assertIn("baseline_fspl_db", outdoor_los)
        self.assertIn("difference_from_baseline_db", outdoor_nlos)


if __name__ == "__main__":
    unittest.main()
