from __future__ import annotations

from ran.contracts import GnbSite
from ran.radio.geometry import (
    LINK_INDOOR_SAME_BUILDING,
    LINK_OUTDOOR_LOS,
    LINK_OUTDOOR_NLOS,
    LOS as GEOMETRY_LOS,
    NLOS as GEOMETRY_NLOS,
    PropagationGeometry,
)
from ran.radio.pathloss_3gpp import (
    LOS,
    NLOS,
    PathLossRequest,
    SCENARIO_INH_OFFICE,
    SCENARIO_UMI_STREET_CANYON,
)


class GeometryPathLossAdapterError(ValueError):
    """Base error for invalid Geometry-to-3GPP adaptation."""


class UnsupportedGeometryLinkError(GeometryPathLossAdapterError):
    """Raised when a geometry link needs a model not approved in Stage 3."""


class MissingCalibratedDistanceError(GeometryPathLossAdapterError):
    """Raised when Geometry has no calibrated physical distances."""


class InconsistentGeometryLinkError(GeometryPathLossAdapterError):
    """Raised when link_type and LOS state contradict each other."""


def path_loss_request_from_geometry(
    *,
    geometry: PropagationGeometry,
    gnb: GnbSite,
    bs_height_m: float,
    ut_height_m: float,
) -> PathLossRequest:
    """Build one 3GPP request without mutating Geometry or inferring metres."""

    scenario, los_state = _scenario_and_los_state(geometry)
    if geometry.gnb_id != gnb.gnb_id:
        raise InconsistentGeometryLinkError(
            "Geometry gnb_id does not match the GnbSite supplying frequency: "
            f"{geometry.gnb_id!r} != {gnb.gnb_id!r}."
        )
    distance_2d_m = geometry.distance.distance_2d_m
    distance_3d_m = geometry.distance.distance_3d_m
    if distance_2d_m is None or distance_3d_m is None:
        missing = []
        if distance_2d_m is None:
            missing.append("distance_2d_m")
        if distance_3d_m is None:
            missing.append("distance_3d_m")
        raise MissingCalibratedDistanceError(
            "Geometry is missing calibrated physical distance fields: "
            + ", ".join(missing)
        )

    return PathLossRequest(
        scenario=scenario,
        los_state=los_state,
        carrier_frequency_mhz=gnb.carrier_freq_mhz,
        distance_2d_m=distance_2d_m,
        distance_3d_m=distance_3d_m,
        bs_height_m=bs_height_m,
        ut_height_m=ut_height_m,
    )


def _scenario_and_los_state(
    geometry: PropagationGeometry,
) -> tuple[str, str]:
    if geometry.link_type == LINK_OUTDOOR_LOS:
        if geometry.los_state != GEOMETRY_LOS:
            raise InconsistentGeometryLinkError(
                "outdoor_los geometry must have los_state='los'."
            )
        return SCENARIO_UMI_STREET_CANYON, LOS

    if geometry.link_type == LINK_OUTDOOR_NLOS:
        if geometry.los_state != GEOMETRY_NLOS:
            raise InconsistentGeometryLinkError(
                "outdoor_nlos geometry must have los_state='nlos'."
            )
        return SCENARIO_UMI_STREET_CANYON, NLOS

    if geometry.link_type == LINK_INDOOR_SAME_BUILDING:
        if geometry.los_state == GEOMETRY_LOS:
            return SCENARIO_INH_OFFICE, LOS
        if geometry.los_state == GEOMETRY_NLOS:
            return SCENARIO_INH_OFFICE, NLOS
        raise InconsistentGeometryLinkError(
            "indoor_same_building geometry must have los_state='los' or 'nlos'."
        )

    raise UnsupportedGeometryLinkError(
        f"Geometry link_type {geometry.link_type!r} is not supported by the "
        "Stage 3 3GPP adapter; O2I, I2O, and cross-building links require "
        "separate approved models or baseline fallback."
    )
