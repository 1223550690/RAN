from __future__ import annotations

from dataclasses import replace
import math
import unittest

from ran.radio.pathloss_3gpp import (
    FORMULA_INH_LOS,
    FORMULA_INH_NLOS,
    FORMULA_UMI_LOS_PL1,
    FORMULA_UMI_LOS_PL2,
    FORMULA_UMI_NLOS,
    LOS,
    NLOS,
    PathLossApplicabilityError,
    PathLossInputError,
    PathLossRequest,
    SCENARIO_INH_OFFICE,
    SCENARIO_UMI_STREET_CANYON,
    _umi_los_path_loss_db,
    _validate_request,
    estimate_path_loss_3gpp,
)


def _umi_request(**changes) -> PathLossRequest:
    request = PathLossRequest(
        scenario=SCENARIO_UMI_STREET_CANYON,
        los_state=LOS,
        carrier_frequency_mhz=3500.0,
        distance_2d_m=100.0,
        distance_3d_m=math.hypot(100.0, 8.5),
        bs_height_m=10.0,
        ut_height_m=1.5,
    )
    return replace(request, **changes)


def _inh_request(**changes) -> PathLossRequest:
    request = PathLossRequest(
        scenario=SCENARIO_INH_OFFICE,
        los_state=NLOS,
        carrier_frequency_mhz=3500.0,
        distance_2d_m=math.sqrt(96.0),
        distance_3d_m=10.0,
        bs_height_m=3.0,
        ut_height_m=1.0,
    )
    return replace(request, **changes)


def _umi_request_at(
    distance_2d_m: float,
    *,
    los_state: str = LOS,
) -> PathLossRequest:
    return _umi_request(
        los_state=los_state,
        distance_2d_m=distance_2d_m,
        distance_3d_m=math.hypot(distance_2d_m, 8.5),
    )


def _inh_request_at(
    distance_3d_m: float,
    *,
    los_state: str = LOS,
) -> PathLossRequest:
    height_difference_m = 2.0
    return _inh_request(
        los_state=los_state,
        distance_2d_m=math.sqrt(
            distance_3d_m**2 - height_difference_m**2
        ),
        distance_3d_m=distance_3d_m,
    )


class PathLossValidationTests(unittest.TestCase):
    def test_valid_umi_request_normalizes_frequency_units(self) -> None:
        validated = _validate_request(_umi_request())

        self.assertEqual(validated.frequency_ghz, 3.5)
        self.assertEqual(validated.frequency_hz, 3_500_000_000.0)
        self.assertFalse(validated.is_extrapolated)
        self.assertEqual(validated.warnings, ())

    def test_valid_inh_request_passes_reference_configuration(self) -> None:
        validated = _validate_request(_inh_request())

        self.assertFalse(validated.is_extrapolated)
        self.assertEqual(validated.warnings, ())

    def test_unknown_scenario_is_rejected(self) -> None:
        with self.assertRaises(PathLossInputError):
            _validate_request(_umi_request(scenario="unknown"))

    def test_unknown_los_state_is_rejected(self) -> None:
        with self.assertRaises(PathLossInputError):
            _validate_request(_umi_request(los_state="maybe"))

    def test_non_finite_numeric_inputs_are_rejected(self) -> None:
        cases = {
            "carrier_frequency_mhz": math.nan,
            "distance_2d_m": math.inf,
            "distance_3d_m": -math.inf,
            "bs_height_m": math.nan,
            "ut_height_m": math.inf,
        }
        for field_name, value in cases.items():
            with self.subTest(field_name=field_name):
                with self.assertRaises(PathLossInputError):
                    _validate_request(_umi_request(**{field_name: value}))

    def test_non_numeric_input_is_rejected(self) -> None:
        with self.assertRaises(PathLossInputError):
            _validate_request(_umi_request(carrier_frequency_mhz="3500"))

    def test_non_positive_frequency_is_rejected(self) -> None:
        for value in (0.0, -1.0):
            with self.subTest(value=value):
                with self.assertRaises(PathLossInputError):
                    _validate_request(_umi_request(carrier_frequency_mhz=value))

    def test_invalid_distances_are_rejected(self) -> None:
        cases = (
            _umi_request(distance_2d_m=-1.0),
            _umi_request(distance_3d_m=0.0),
            _umi_request(distance_3d_m=99.0),
        )
        for request in cases:
            with self.subTest(request=request):
                with self.assertRaises(PathLossInputError):
                    _validate_request(request)

    def test_non_positive_heights_are_rejected(self) -> None:
        for changes in ({"bs_height_m": 0.0}, {"ut_height_m": -1.0}):
            with self.subTest(changes=changes):
                with self.assertRaises(PathLossInputError):
                    _validate_request(_umi_request(**changes))

    def test_inconsistent_2d_3d_distance_and_heights_are_rejected(self) -> None:
        with self.assertRaisesRegex(PathLossInputError, "inconsistent"):
            _validate_request(_umi_request(distance_3d_m=110.0))

    def test_umi_non_positive_effective_height_is_rejected(self) -> None:
        request = _umi_request(
            distance_2d_m=100.0,
            distance_3d_m=math.hypot(100.0, 9.0),
            ut_height_m=1.0,
        )

        with self.assertRaisesRegex(PathLossInputError, "effective"):
            _validate_request(request)

    def test_outside_applicability_is_rejected_by_default(self) -> None:
        request = _umi_request(
            distance_2d_m=5.0,
            distance_3d_m=math.hypot(5.0, 8.5),
        )

        with self.assertRaises(PathLossApplicabilityError):
            _validate_request(request)

    def test_explicit_extrapolation_returns_warning(self) -> None:
        request = _umi_request(
            distance_2d_m=5.0,
            distance_3d_m=math.hypot(5.0, 8.5),
        )
        validated = _validate_request(request, allow_extrapolation=True)

        self.assertTrue(validated.is_extrapolated)
        self.assertTrue(
            any(
                warning.startswith("umi_distance_outside_applicability")
                for warning in validated.warnings
            )
        )

    def test_non_reference_height_returns_warning_without_extrapolation(self) -> None:
        request = _inh_request(
            distance_2d_m=math.sqrt(91.0),
            bs_height_m=4.0,
        )
        validated = _validate_request(request)

        self.assertFalse(validated.is_extrapolated)
        self.assertIn(
            "non_reference_height: InH reference hBS=3 m and hUT=1 m",
            validated.warnings,
        )


class PathLossUmiTests(unittest.TestCase):
    def test_los_reference_points_and_formula_selection(self) -> None:
        cases = (
            (10.0, 66.7610328085, FORMULA_UMI_LOS_PL1),
            (100.0, 85.3141891025, FORMULA_UMI_LOS_PL1),
            (210.0, 92.0554308623, FORMULA_UMI_LOS_PL1),
            (300.0, 98.2442606638, FORMULA_UMI_LOS_PL2),
        )
        for distance_2d_m, expected_db, formula_id in cases:
            with self.subTest(distance_2d_m=distance_2d_m):
                result = estimate_path_loss_3gpp(
                    _umi_request_at(distance_2d_m)
                )

                self.assertAlmostEqual(
                    result.mean_path_loss_db,
                    expected_db,
                    places=9,
                )
                self.assertEqual(result.formula_id, formula_id)
                self.assertEqual(result.shadow_fading_std_db, 4.0)
                self.assertAlmostEqual(result.breakpoint_distance_m, 210.0)

    def test_los_formulas_are_continuous_at_breakpoint(self) -> None:
        request = _umi_request_at(210.0)
        validated = _validate_request(request)
        pl1_db, pl1_formula = _umi_los_path_loss_db(
            request,
            validated,
            210.0,
        )
        pl2_db, pl2_formula = _umi_los_path_loss_db(
            replace(request, distance_2d_m=210.0 + 1e-9),
            validated,
            210.0,
        )

        self.assertEqual(pl1_formula, FORMULA_UMI_LOS_PL1)
        self.assertEqual(pl2_formula, FORMULA_UMI_LOS_PL2)
        self.assertAlmostEqual(pl1_db, pl2_db, places=6)

    def test_nlos_uses_maximum_of_los_and_candidate(self) -> None:
        result = estimate_path_loss_3gpp(
            _umi_request_at(100.0, los_state=NLOS)
        )

        self.assertAlmostEqual(result.mean_path_loss_db, 104.6438320117)
        self.assertAlmostEqual(result.los_reference_path_loss_db, 85.3141891025)
        self.assertAlmostEqual(
            result.nlos_candidate_path_loss_db,
            104.6438320117,
        )
        self.assertGreaterEqual(
            result.mean_path_loss_db,
            result.los_reference_path_loss_db,
        )
        self.assertEqual(result.formula_id, FORMULA_UMI_NLOS)
        self.assertEqual(result.shadow_fading_std_db, 7.82)

    def test_los_metadata_does_not_report_nlos_candidate(self) -> None:
        result = estimate_path_loss_3gpp(_umi_request_at(100.0))

        self.assertEqual(
            result.mean_path_loss_db,
            result.los_reference_path_loss_db,
        )
        self.assertIsNone(result.nlos_candidate_path_loss_db)
        self.assertFalse(result.is_extrapolated)
        self.assertEqual(result.warnings, ())

    def test_explicit_umi_extrapolation_is_visible_in_result(self) -> None:
        result = estimate_path_loss_3gpp(
            _umi_request_at(5.0),
            allow_extrapolation=True,
        )

        self.assertTrue(result.is_extrapolated)
        self.assertTrue(
            any(
                warning.startswith("umi_distance_outside_applicability")
                for warning in result.warnings
            )
        )


class PathLossInhTests(unittest.TestCase):
    def test_los_reference_point_and_metadata(self) -> None:
        result = estimate_path_loss_3gpp(_inh_request_at(10.0))

        self.assertAlmostEqual(result.mean_path_loss_db, 60.5813608870)
        self.assertEqual(
            result.mean_path_loss_db,
            result.los_reference_path_loss_db,
        )
        self.assertIsNone(result.nlos_candidate_path_loss_db)
        self.assertIsNone(result.breakpoint_distance_m)
        self.assertEqual(result.formula_id, FORMULA_INH_LOS)
        self.assertEqual(result.shadow_fading_std_db, 3.0)

    def test_nlos_reference_point_uses_candidate(self) -> None:
        result = estimate_path_loss_3gpp(
            _inh_request_at(10.0, los_state=NLOS)
        )

        self.assertAlmostEqual(result.mean_path_loss_db, 69.1472943043)
        self.assertAlmostEqual(result.los_reference_path_loss_db, 60.5813608870)
        self.assertAlmostEqual(
            result.nlos_candidate_path_loss_db,
            69.1472943043,
        )
        self.assertEqual(result.formula_id, FORMULA_INH_NLOS)
        self.assertEqual(result.shadow_fading_std_db, 8.03)

    def test_short_range_nlos_is_never_below_los(self) -> None:
        result = estimate_path_loss_3gpp(
            _inh_request_at(2.0, los_state=NLOS)
        )

        self.assertAlmostEqual(result.mean_path_loss_db, 48.4891798120)
        self.assertLess(
            result.nlos_candidate_path_loss_db,
            result.los_reference_path_loss_db,
        )
        self.assertEqual(
            result.mean_path_loss_db,
            result.los_reference_path_loss_db,
        )

    def test_inh_distance_outside_range_requires_explicit_extrapolation(
        self,
    ) -> None:
        request = _inh_request_at(200.0)

        with self.assertRaises(PathLossApplicabilityError):
            estimate_path_loss_3gpp(request)

        result = estimate_path_loss_3gpp(
            request,
            allow_extrapolation=True,
        )
        self.assertTrue(result.is_extrapolated)
        self.assertTrue(
            any(
                warning.startswith("inh_distance_outside_applicability")
                for warning in result.warnings
            )
        )


if __name__ == "__main__":
    unittest.main()
