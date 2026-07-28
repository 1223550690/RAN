from __future__ import annotations

from dataclasses import replace
import math
import unittest

from ran.radio.pathloss_3gpp import (
    LOS,
    NLOS,
    PathLossApplicabilityError,
    PathLossInputError,
    PathLossRequest,
    SCENARIO_INH_OFFICE,
    SCENARIO_UMI_STREET_CANYON,
    _validate_request,
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


if __name__ == "__main__":
    unittest.main()
