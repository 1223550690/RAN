from __future__ import annotations

from ran.traffic.service_profile import service_profile_for


def classify_slice(service_type: str) -> str:
    """Project implementation detail."""

    return str(service_profile_for(service_type)["slice_id"])
