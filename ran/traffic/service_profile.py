from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class ServiceProfileError(ValueError):
    """Raised when a configured service-to-QoS profile is invalid."""


_BUILTIN_SERVICE_QOS_TABLE: dict[str, dict[str, object]] = {
    "default": {
        "qfi": 9,
        "five_qi": 9,
        "priority": 9,
        "packet_delay_budget_ms": 300.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "embb",
    },
    "video_upload": {
        "qfi": 9,
        "five_qi": 9,
        "priority": 5,
        "packet_delay_budget_ms": 300.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "embb",
    },
    "video_stream": {
        "qfi": 8,
        "five_qi": 6,
        "priority": 6,
        "packet_delay_budget_ms": 300.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "embb",
    },
    "web": {
        "qfi": 9,
        "five_qi": 9,
        "priority": 7,
        "packet_delay_budget_ms": 300.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "embb",
    },
    "file_upload": {
        "qfi": 9,
        "five_qi": 9,
        "priority": 8,
        "packet_delay_budget_ms": 500.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "embb",
    },
    "file_download": {
        "qfi": 9,
        "five_qi": 9,
        "priority": 8,
        "packet_delay_budget_ms": 500.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "embb",
    },
    "game": {
        "qfi": 7,
        "five_qi": 80,
        "priority": 2,
        "packet_delay_budget_ms": 50.0,
        "packet_error_rate": 1e-3,
        "resource_type": "non_gbr",
        "slice_id": "urllc",
    },
    "video_call": {
        "qfi": 2,
        "five_qi": 2,
        "priority": 2,
        "packet_delay_budget_ms": 150.0,
        "packet_error_rate": 1e-3,
        "resource_type": "gbr",
        "slice_id": "urllc",
        "gbr_mbps": 2.0,
        "mbr_mbps": 5.0,
    },
    "voice_call": {
        "qfi": 1,
        "five_qi": 1,
        "priority": 1,
        "packet_delay_budget_ms": 100.0,
        "packet_error_rate": 1e-2,
        "resource_type": "gbr",
        "slice_id": "urllc",
        "gbr_mbps": 0.064,
        "mbr_mbps": 0.128,
    },
    "live_video": {
        "qfi": 3,
        "five_qi": 3,
        "priority": 3,
        "packet_delay_budget_ms": 50.0,
        "packet_error_rate": 1e-3,
        "resource_type": "gbr",
        "slice_id": "urllc",
        "gbr_mbps": 5.0,
        "mbr_mbps": 20.0,
    },
    "message": {
        "qfi": 6,
        "five_qi": 9,
        "priority": 7,
        "packet_delay_budget_ms": 500.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "mmtc",
    },
    "telemetry": {
        "qfi": 5,
        "five_qi": 9,
        "priority": 8,
        "packet_delay_budget_ms": 1000.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "mmtc",
    },
    "control": {
        "qfi": 4,
        "five_qi": 82,
        "priority": 1,
        "packet_delay_budget_ms": 10.0,
        "packet_error_rate": 1e-5,
        "resource_type": "delay_critical_gbr",
        "slice_id": "urllc",
        "gbr_mbps": 0.1,
        "mbr_mbps": 1.0,
    },
}


def _validate_profile(name: str, profile: Mapping[str, object]) -> dict[str, object]:
    required = {
        "qfi",
        "five_qi",
        "priority",
        "packet_delay_budget_ms",
        "packet_error_rate",
        "resource_type",
        "slice_id",
    }
    missing = sorted(required - profile.keys())
    if missing:
        raise ServiceProfileError(f"service profile {name!r} is missing fields: {', '.join(missing)}")

    value = dict(profile)
    qfi = int(value["qfi"])
    five_qi = int(value["five_qi"])
    priority = int(value["priority"])
    delay = float(value["packet_delay_budget_ms"])
    error_rate = float(value["packet_error_rate"])
    resource_type = str(value["resource_type"])
    slice_id = str(value["slice_id"])
    if not 1 <= qfi <= 63:
        raise ServiceProfileError(f"service profile {name!r} has invalid QFI {qfi}; expected 1..63")
    if not 1 <= five_qi <= 255:
        raise ServiceProfileError(f"service profile {name!r} has invalid 5QI {five_qi}")
    if not 1 <= priority <= 127:
        raise ServiceProfileError(f"service profile {name!r} has invalid priority {priority}")
    if delay <= 0 or not 0 <= error_rate <= 1:
        raise ServiceProfileError(f"service profile {name!r} has invalid delay/error characteristics")
    if resource_type not in {"non_gbr", "gbr", "delay_critical_gbr"}:
        raise ServiceProfileError(f"service profile {name!r} has invalid resource_type {resource_type!r}")
    if not slice_id:
        raise ServiceProfileError(f"service profile {name!r} has an empty slice_id")

    gbr = value.get("gbr_mbps")
    mbr = value.get("mbr_mbps")
    if resource_type != "non_gbr" and gbr is None:
        raise ServiceProfileError(f"service profile {name!r} requires gbr_mbps")
    if gbr is not None and float(gbr) <= 0:
        raise ServiceProfileError(f"service profile {name!r} has non-positive gbr_mbps")
    if mbr is not None and float(mbr) <= 0:
        raise ServiceProfileError(f"service profile {name!r} has non-positive mbr_mbps")
    if gbr is not None and mbr is not None and float(gbr) > float(mbr):
        raise ServiceProfileError(f"service profile {name!r} has GBR greater than MBR")
    return value


def load_service_profiles(path: str | Path | None = None) -> dict[str, dict[str, object]]:
    """Load and validate service profiles, falling back to built-in defaults."""

    if path is None:
        path = Path(__file__).resolve().parents[2] / "configs" / "ran" / "service_profiles.json"
    config_path = Path(path)
    if config_path.is_file():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        raw_profiles = raw.get("profiles", raw)
        profiles = {
            str(name): _validate_profile(str(name), value)
            for name, value in raw_profiles.items()
            if isinstance(value, dict)
        }
    else:
        profiles = {
            name: _validate_profile(name, profile)
            for name, profile in _BUILTIN_SERVICE_QOS_TABLE.items()
        }
    if "default" not in profiles:
        raise ServiceProfileError("service profile configuration must contain a 'default' profile")
    return profiles


SERVICE_QOS_TABLE = load_service_profiles()


def service_profile_for(service_type: str) -> dict[str, object]:
    """Return an isolated profile copy; unknown services use ``default``."""

    profile = SERVICE_QOS_TABLE.get(service_type, SERVICE_QOS_TABLE["default"])
    return dict(profile)
