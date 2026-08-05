from __future__ import annotations

import math
import unittest

from ran.radio.pathloss_3gpp import (
    LOS,
    PathLossApplicabilityError,
    PathLossInputError,
    PathLossRequest,
    SCENARIO_INH_OFFICE,
    SCENARIO_UMI_STREET_CANYON,
)
from ran.radio.pathloss_3gpp_o2i import (
    HIGH_LOSS,
    LOW_LOSS,
    O2IPathLossRequest,
    estimate_o2i_path_loss_3gpp,
)


def _request(
    *,
    penetration_model: str = LOW_LOSS,
    indoor_distance_m: float = 10.0,
    penetration_residual_db: float = 0.0,
    include_external_wall_loss: bool = True,
    include_indoor_loss: bool = True,
) -> O2IPathLossRequest:
    return O2IPathLossRequest(
        basic_outdoor_request=PathLossRequest(
            scenario=SCENARIO_UMI_STREET_CANYON,
            los_state=LOS,
            carrier_frequency_mhz=3500.0,
            distance_2d_m=100.0,
            distance_3d_m=math.hypot(100.0, 8.5),
            bs_height_m=10.0,
            ut_height_m=1.5,
        ),
        indoor_distance_m=indoor_distance_m,
        penetration_model=penetration_model,
        penetration_residual_db=penetration_residual_db,
        indoor_distance_source="geometry_measured",
        include_external_wall_loss=include_external_wall_loss,
        include_indoor_loss=include_indoor_loss,
    )


class O2IPathLossTests(unittest.TestCase):
    def test_low_loss_profile_matches_release_19_formula(self) -> None:
        result = estimate_o2i_path_loss_3gpp(_request())

        glass_db = 2.0 + 0.2 * 3.5
        concrete_db = 5.0 + 4.0 * 3.5
        expected_wall_db = 5.0 - 10.0 * math.log10(
            0.3 * 10.0 ** (-glass_db / 10.0)
            + 0.7 * 10.0 ** (-concrete_db / 10.0)
        )
        self.assertAlmostEqual(result.external_wall_loss_db, expected_wall_db)
        self.assertAlmostEqual(result.indoor_loss_db, 5.0)
        self.assertEqual(result.penetration_loss_std_db, 4.4)
        self.assertAlmostEqual(
            result.mean_path_loss_db,
            result.basic_outdoor_path_loss_db + expected_wall_db + 5.0,
        )

    def test_high_loss_uses_release_19_irr_glass_coefficient(self) -> None:
        result = estimate_o2i_path_loss_3gpp(
            _request(penetration_model=HIGH_LOSS)
        )

        irr_glass_db = 25.4 + 0.11 * 3.5
        concrete_db = 5.0 + 4.0 * 3.5
        expected_wall_db = 5.0 - 10.0 * math.log10(
            0.7 * 10.0 ** (-irr_glass_db / 10.0)
            + 0.3 * 10.0 ** (-concrete_db / 10.0)
        )
        self.assertAlmostEqual(result.external_wall_loss_db, expected_wall_db)
        self.assertEqual(result.penetration_loss_std_db, 6.5)

    def test_penetration_residual_is_separate_from_mean(self) -> None:
        result = estimate_o2i_path_loss_3gpp(
            _request(penetration_residual_db=3.25)
        )

        self.assertAlmostEqual(
            result.total_path_loss_db,
            result.mean_path_loss_db + 3.25,
        )

    def test_components_can_be_disabled_for_baseline_comparison(self) -> None:
        result = estimate_o2i_path_loss_3gpp(
            _request(
                include_external_wall_loss=False,
                include_indoor_loss=False,
            )
        )

        self.assertEqual(result.external_wall_loss_db, 0.0)
        self.assertEqual(result.indoor_loss_db, 0.0)
        self.assertAlmostEqual(
            result.total_path_loss_db,
            result.basic_outdoor_path_loss_db,
        )

    def test_depth_over_25_m_requires_explicit_extrapolation(self) -> None:
        request = _request(indoor_distance_m=26.0)
        with self.assertRaisesRegex(PathLossApplicabilityError, "25 m"):
            estimate_o2i_path_loss_3gpp(request)

        result = estimate_o2i_path_loss_3gpp(
            request,
            allow_extrapolation=True,
        )
        self.assertTrue(result.is_extrapolated)
        self.assertTrue(
            any("d2D-in <= 25" in warning for warning in result.warnings)
        )

    def test_non_umi_basic_model_is_rejected(self) -> None:
        request = _request()
        invalid = O2IPathLossRequest(
            basic_outdoor_request=PathLossRequest(
                scenario=SCENARIO_INH_OFFICE,
                los_state=LOS,
                carrier_frequency_mhz=3500.0,
                distance_2d_m=10.0,
                distance_3d_m=math.hypot(10.0, 2.0),
                bs_height_m=3.0,
                ut_height_m=1.0,
            ),
            indoor_distance_m=request.indoor_distance_m,
            penetration_model=LOW_LOSS,
        )
        with self.assertRaisesRegex(PathLossInputError, "UMi Street Canyon"):
            estimate_o2i_path_loss_3gpp(invalid)


if __name__ == "__main__":
    unittest.main()
