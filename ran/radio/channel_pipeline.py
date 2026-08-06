from __future__ import annotations

from dataclasses import dataclass

from ran.contracts import GnbSite, Position
from ran.radio.channel_policy import (
    MODE_3GPP_PREFERRED,
    MODE_HYBRID,
    MODE_LEGACY,
    MODE_SHADOW,
    ChannelModelPolicy,
)
from ran.radio.coordinate_calibration import load_coordinate_calibration
from ran.radio.geometry import (
    LINK_OUTDOOR_TO_INDOOR,
    PropagationGeometry,
    analyze_propagation_geometry,
    coordinate_view_from_calibration,
)
from ran.radio.pathloss_3gpp import (
    PathLossApplicabilityError,
    PathLossInputError,
    estimate_path_loss_3gpp,
)
from ran.radio.pathloss_3gpp_adapter import (
    GeometryPathLossAdapterError,
    o2i_path_loss_request_from_geometry,
    path_loss_request_from_geometry,
)
from ran.radio.pathloss_3gpp_o2i import estimate_o2i_path_loss_3gpp


LEGACY_FORMULA_ID = "legacy_fspl_plus_raw_wall_loss"


@dataclass(frozen=True, slots=True)
class ChannelPathLossEvaluation:
    mode: str
    selected_model: str
    selected_total_path_loss_db: float
    selected_formula_id: str
    evaluated_model: str | None = None
    evaluated_total_path_loss_db: float | None = None
    evaluated_formula_id: str | None = None
    geometry: PropagationGeometry | None = None
    external_wall_loss_db: float | None = None
    indoor_loss_db: float | None = None
    shadow_fading_std_db: float | None = None
    penetration_loss_std_db: float | None = None
    is_extrapolated: bool = False
    warnings: tuple[str, ...] = ()
    fallback_reason: str | None = None
    calibration_id: str | None = None
    calibration_status: str | None = None
    meters_per_map_unit_x: float | None = None
    meters_per_map_unit_y: float | None = None
    bs_height_m: float | None = None
    bs_height_source: str | None = None
    bs_height_status: str | None = None
    ut_height_m: float | None = None
    ut_height_source: str | None = None
    ut_height_status: str | None = None
    height_reference: str | None = None
    penetration_model: str | None = None
    penetration_model_source: str | None = None
    penetration_model_status: str | None = None


def evaluate_channel_path_loss(
    *,
    scene,
    receiver_position: Position,
    gnb: GnbSite,
    legacy_total_path_loss_db: float,
    policy: ChannelModelPolicy,
    geometry=None,
) -> ChannelPathLossEvaluation:
    """Evaluate Calibration -> Geometry -> 3GPP with a legacy-safe selection.

    geometry: 可选——调用方已算好传播几何时复用(避免重复计算,CKM 批量构建用)。
    """

    if policy.mode == MODE_LEGACY:
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            fallback_reason="mode_legacy",
        )

    scene_id = getattr(scene, "node_id", None)
    if not isinstance(scene_id, str) or not scene_id:
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            fallback_reason="missing_scene_id",
        )
    calibration = load_coordinate_calibration(scene_id)
    if calibration is None:
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            fallback_reason="missing_coordinate_calibration",
        )
    if (
        calibration.status == "provisional"
        and policy.mode == MODE_3GPP_PREFERRED
        and policy.require_confirmed_calibration_when_active
    ):
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            fallback_reason="provisional_calibration_not_allowed_in_active_mode",
            calibration=calibration,
        )
    if (
        calibration.status == "provisional"
        and not policy.allow_provisional_calibration_in_shadow
        and policy.mode not in (MODE_3GPP_PREFERRED, MODE_SHADOW, MODE_HYBRID)
    ):
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            fallback_reason="provisional_calibration_not_allowed_in_shadow_mode",
            calibration=calibration,
        )

    gnb_height = policy.gnb_heights.get(gnb.gnb_id)
    if gnb_height is None:
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            fallback_reason=f"missing_gnb_height:{gnb.gnb_id}",
            calibration=calibration,
        )
    if policy.default_ue_height is None:
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            fallback_reason="missing_default_ue_height",
            calibration=calibration,
        )
    ue_height_m = policy.default_ue_height.height_m
    coordinate_view = coordinate_view_from_calibration(
        calibration,
        gnb_height_m=gnb_height.height_m,
        ue_height_m=ue_height_m,
    )
    if geometry is None:
        geometry = analyze_propagation_geometry(
            scene=scene,
            receiver_position=receiver_position,
            gnb=gnb,
            coordinate_view=coordinate_view,
        )

    try:
        if geometry.link_type == LINK_OUTDOOR_TO_INDOOR:
            profile = policy.o2i_profiles.get(geometry.receiver_building_id or "")
            if profile is None:
                return _legacy_evaluation(
                    policy=policy,
                    legacy_total_path_loss_db=legacy_total_path_loss_db,
                    geometry=geometry,
                    calibration=calibration,
                    gnb_height=gnb_height,
                    ue_height=policy.default_ue_height,
                    fallback_reason=(
                        "missing_o2i_profile:"
                        + str(geometry.receiver_building_id or "unknown_building")
                    ),
                )
            request = o2i_path_loss_request_from_geometry(
                geometry=geometry,
                gnb=gnb,
                bs_height_m=gnb_height.height_m,
                ut_height_m=ue_height_m,
                penetration_model=profile.penetration_model,
                penetration_residual_db=policy.penetration_residual_db,
            )
            result = estimate_o2i_path_loss_3gpp(
                request,
                allow_extrapolation=policy.allow_extrapolation,
            )
            return _evaluated(
                policy=policy,
                legacy_total_path_loss_db=legacy_total_path_loss_db,
                model="3gpp_o2i",
                total_path_loss_db=result.total_path_loss_db,
                formula_id=result.formula_id,
                geometry=geometry,
                external_wall_loss_db=result.external_wall_loss_db,
                indoor_loss_db=result.indoor_loss_db,
                shadow_fading_std_db=(
                    result.basic_outdoor_path_loss.shadow_fading_std_db
                ),
                penetration_loss_std_db=result.penetration_loss_std_db,
                is_extrapolated=result.is_extrapolated,
                warnings=result.warnings,
                calibration=calibration,
                gnb_height=gnb_height,
                ue_height=policy.default_ue_height,
                penetration_profile=profile,
            )

        request = path_loss_request_from_geometry(
            geometry=geometry,
            gnb=gnb,
            bs_height_m=gnb_height.height_m,
            ut_height_m=ue_height_m,
        )
        result = estimate_path_loss_3gpp(
            request,
            allow_extrapolation=policy.allow_extrapolation,
        )
        return _evaluated(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            model=f"3gpp_{result.scenario}",
            total_path_loss_db=result.mean_path_loss_db,
            formula_id=result.formula_id,
            geometry=geometry,
            shadow_fading_std_db=result.shadow_fading_std_db,
            is_extrapolated=result.is_extrapolated,
            warnings=result.warnings,
            calibration=calibration,
            gnb_height=gnb_height,
            ue_height=policy.default_ue_height,
        )
    except (
        GeometryPathLossAdapterError,
        PathLossApplicabilityError,
        PathLossInputError,
    ) as exc:
        return _legacy_evaluation(
            policy=policy,
            legacy_total_path_loss_db=legacy_total_path_loss_db,
            geometry=geometry,
            calibration=calibration,
            gnb_height=gnb_height,
            ue_height=policy.default_ue_height,
            fallback_reason=f"{type(exc).__name__}:{exc}",
        )


def _evaluated(
    *,
    policy: ChannelModelPolicy,
    legacy_total_path_loss_db: float,
    model: str,
    total_path_loss_db: float,
    formula_id: str,
    geometry: PropagationGeometry,
    external_wall_loss_db: float | None = None,
    indoor_loss_db: float | None = None,
    shadow_fading_std_db: float | None = None,
    penetration_loss_std_db: float | None = None,
    is_extrapolated: bool = False,
    warnings: tuple[str, ...] = (),
    calibration=None,
    gnb_height=None,
    ue_height=None,
    penetration_profile=None,
) -> ChannelPathLossEvaluation:
    active = policy.mode == MODE_3GPP_PREFERRED
    return ChannelPathLossEvaluation(
        mode=policy.mode,
        selected_model=model if active else MODE_LEGACY,
        selected_total_path_loss_db=(
            total_path_loss_db if active else legacy_total_path_loss_db
        ),
        selected_formula_id=formula_id if active else LEGACY_FORMULA_ID,
        evaluated_model=model,
        evaluated_total_path_loss_db=total_path_loss_db,
        evaluated_formula_id=formula_id,
        geometry=geometry,
        external_wall_loss_db=external_wall_loss_db,
        indoor_loss_db=indoor_loss_db,
        shadow_fading_std_db=shadow_fading_std_db,
        penetration_loss_std_db=penetration_loss_std_db,
        is_extrapolated=is_extrapolated,
        warnings=warnings,
        **_provenance_fields(
            policy=policy,
            calibration=calibration,
            gnb_height=gnb_height,
            ue_height=ue_height,
            penetration_profile=penetration_profile,
        ),
    )


def _legacy_evaluation(
    *,
    policy: ChannelModelPolicy,
    legacy_total_path_loss_db: float,
    fallback_reason: str,
    geometry: PropagationGeometry | None = None,
    calibration=None,
    gnb_height=None,
    ue_height=None,
) -> ChannelPathLossEvaluation:
    return ChannelPathLossEvaluation(
        mode=policy.mode,
        selected_model=MODE_LEGACY,
        selected_total_path_loss_db=legacy_total_path_loss_db,
        selected_formula_id=LEGACY_FORMULA_ID,
        geometry=geometry,
        fallback_reason=fallback_reason,
        **_provenance_fields(
            policy=policy,
            calibration=calibration,
            gnb_height=gnb_height,
            ue_height=ue_height,
        ),
    )


def _provenance_fields(
    *,
    policy: ChannelModelPolicy,
    calibration=None,
    gnb_height=None,
    ue_height=None,
    penetration_profile=None,
) -> dict[str, object]:
    return {
        "calibration_id": (
            calibration.calibration_id if calibration is not None else None
        ),
        "calibration_status": (
            calibration.status if calibration is not None else None
        ),
        "meters_per_map_unit_x": (
            calibration.meters_per_map_unit_x if calibration is not None else None
        ),
        "meters_per_map_unit_y": (
            calibration.meters_per_map_unit_y if calibration is not None else None
        ),
        "bs_height_m": gnb_height.height_m if gnb_height is not None else None,
        "bs_height_source": gnb_height.source if gnb_height is not None else None,
        "bs_height_status": gnb_height.status if gnb_height is not None else None,
        "ut_height_m": ue_height.height_m if ue_height is not None else None,
        "ut_height_source": ue_height.source if ue_height is not None else None,
        "ut_height_status": ue_height.status if ue_height is not None else None,
        "height_reference": policy.height_reference,
        "penetration_model": (
            penetration_profile.penetration_model
            if penetration_profile is not None
            else None
        ),
        "penetration_model_source": (
            penetration_profile.source if penetration_profile is not None else None
        ),
        "penetration_model_status": (
            penetration_profile.status if penetration_profile is not None else None
        ),
    }
