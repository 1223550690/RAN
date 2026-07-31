from __future__ import annotations

import unittest

from experiments.debug_bristol_3gpp_o2i import build_bristol_o2i_report


class BristolO2IReportTests(unittest.TestCase):
    def test_student_union_and_gym_have_decomposed_o2i_results(self) -> None:
        report = build_bristol_o2i_report(
            gnb_height_m=10.0,
            allow_extrapolation=True,
        )
        cases = {case["case_id"]: case for case in report["cases"]}

        for case_id in ("student_union_center", "gym_center"):
            with self.subTest(case_id=case_id):
                case = cases[case_id]
                result = case["adaptation"]["result"]
                self.assertEqual(case["adaptation"]["status"], "supported")
                self.assertGreater(result["basic_outdoor_path_loss_db"], 0.0)
                self.assertGreater(result["external_wall_loss_db"], 0.0)
                self.assertGreater(result["indoor_loss_db"], 0.0)
                self.assertEqual(result["penetration_residual_db"], 0.0)
                self.assertFalse(
                    case["double_counting_guard"]["used_in_3gpp_o2i_total"]
                )

    def test_blocking_building_changes_only_outdoor_basic_los_selection(self) -> None:
        report = build_bristol_o2i_report(
            gnb_height_m=10.0,
            allow_extrapolation=True,
        )
        cases = {case["case_id"]: case for case in report["cases"]}

        student_request = cases["student_union_center"]["adaptation"]["request"]
        gym_request = cases["gym_center"]["adaptation"]["request"]
        self.assertEqual(
            student_request["basic_outdoor_request"]["los_state"],
            "los",
        )
        self.assertEqual(
            gym_request["basic_outdoor_request"]["los_state"],
            "nlos",
        )


if __name__ == "__main__":
    unittest.main()
