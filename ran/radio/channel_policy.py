from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHANNEL_MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "ran" / "channel_model.json"
SUPPORTED_SCHEMA_VERSION = "1"
MODE_LEGACY = "legacy"
MODE_SHADOW = "shadow"
MODE_3GPP_PREFERRED = "3gpp_preferred"
MODE_HYBRID = "hybrid"
SUPPORTED_MODES = {MODE_LEGACY, MODE_SHADOW, MODE_3GPP_PREFERRED, MODE_HYBRID}
SUPPORTED_FALLBACKS = {MODE_LEGACY, MODE_SHADOW}


class ChannelModelConfigError(ValueError):
    """Raised when the runtime channel-model policy is invalid."""


@dataclass(frozen=True, slots=True)
class HeightPreset:
    height_m: float
    source: str
    status: str


@dataclass(frozen=True, slots=True)
class O2IBuildingProfile:
    penetration_model: str
    source: str
    status: str


@dataclass(frozen=True, slots=True)
class ChannelModelPolicy:
    scene_id: str
    mode: str = MODE_LEGACY
    fallback_model: str = MODE_LEGACY
    allow_provisional_calibration_in_shadow: bool = False
    require_confirmed_calibration_when_active: bool = True
    allow_extrapolation_in_shadow: bool = False
    allow_extrapolation_when_active: bool = False
    height_reference: str = "local_ground"
    gnb_heights: dict[str, HeightPreset] = field(default_factory=dict)
    default_ue_height: HeightPreset | None = None
    o2i_profiles: dict[str, O2IBuildingProfile] = field(default_factory=dict)
    penetration_residual_db: float = 0.0
    unconfigured_building_policy: str = "legacy_fallback"
    noise_figure_db: float = 7.0  # noise_figure_db: receiver noise figure (phase 10, default 3GPP typical value).
    ckm_config: dict | None = None  # ckm_config: hybrid CKM configuration (used in hybrid mode).

    @property
    def allow_extrapolation(self) -> bool:
        if self.mode in (MODE_SHADOW, MODE_HYBRID):
            return self.allow_extrapolation_in_shadow
        if self.mode == MODE_3GPP_PREFERRED:
            return self.allow_extrapolation_when_active
        return False

    @property
    def is_hybrid(self) -> bool:
        return self.mode == MODE_HYBRID


def load_channel_model_policy(
    scene_id: str,
    config_path: str | Path | None = None,
) -> ChannelModelPolicy:
    """Load one scene policy; unknown scenes safely use the legacy model."""

    path = Path(config_path) if config_path is not None else DEFAULT_CHANNEL_MODEL_CONFIG_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ChannelModelPolicy(scene_id=scene_id)
    except json.JSONDecodeError as exc:
        raise ChannelModelConfigError(f"Invalid channel-model JSON in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ChannelModelConfigError("Channel-model config root must be an object.")
    schema_version = str(raw.get("schema_version", ""))
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ChannelModelConfigError(
            f"Unsupported channel-model schema_version {schema_version!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION!r}."
        )
    scenes = raw.get("scenes")
    if not isinstance(scenes, dict):
        raise ChannelModelConfigError("Channel-model config 'scenes' must be an object.")
    scene_data = scenes.get(scene_id)
    if scene_data is None:
        return ChannelModelPolicy(scene_id=scene_id)
    if not isinstance(scene_data, dict):
        raise ChannelModelConfigError(f"Channel policy for {scene_id!r} must be an object.")

    mode = str(scene_data.get("mode", raw.get("default_mode", MODE_LEGACY)))
    if mode not in SUPPORTED_MODES:
        raise ChannelModelConfigError(
            f"Unsupported channel-model mode {mode!r}; expected one of {sorted(SUPPORTED_MODES)}."
        )
    fallback_model = str(scene_data.get("fallback_model", MODE_LEGACY))
    if fallback_model not in SUPPORTED_FALLBACKS:
        raise ChannelModelConfigError(
            f"Unsupported fallback_model {fallback_model!r}; expected one of {sorted(SUPPORTED_FALLBACKS)}."
        )

    height_reference = _nonempty_string(
        scene_data.get("height_reference", "local_ground"),
        "height_reference",
    )
    if height_reference != "local_ground":
        raise ChannelModelConfigError(
            "Only height_reference='local_ground' is currently supported."
        )

    gnb_heights_data = _object(scene_data.get("gnb_heights", {}), "gnb_heights")
    gnb_heights = {
        str(gnb_id): _height_preset(value, f"gnb_heights.{gnb_id}")
        for gnb_id, value in gnb_heights_data.items()
    }
    default_ue_data = scene_data.get("default_ue_height")
    default_ue_height = (
        _height_preset(default_ue_data, "default_ue_height")
        if default_ue_data is not None
        else None
    )

    o2i = _object(scene_data.get("o2i", {}), "o2i")
    profile_data = _object(o2i.get("building_profiles", {}), "o2i.building_profiles")
    profiles = {
        str(building_id): _o2i_profile(value, f"o2i.building_profiles.{building_id}")
        for building_id, value in profile_data.items()
    }
    residual = _finite_number(o2i.get("penetration_residual_db", 0.0), "penetration_residual_db")
    unconfigured_building_policy = _nonempty_string(
        o2i.get("unconfigured_building_policy", "legacy_fallback"),
        "o2i.unconfigured_building_policy",
    )
    if unconfigured_building_policy != "legacy_fallback":
        raise ChannelModelConfigError(
            "Only unconfigured_building_policy='legacy_fallback' is currently supported."
        )

    return ChannelModelPolicy(
        scene_id=scene_id,
        mode=mode,
        fallback_model=fallback_model,
        allow_provisional_calibration_in_shadow=_boolean(
            scene_data.get("allow_provisional_calibration_in_shadow", False),
            "allow_provisional_calibration_in_shadow",
        ),
        require_confirmed_calibration_when_active=_boolean(
            scene_data.get("require_confirmed_calibration_when_active", True),
            "require_confirmed_calibration_when_active",
        ),
        allow_extrapolation_in_shadow=_boolean(
            scene_data.get("allow_extrapolation_in_shadow", False),
            "allow_extrapolation_in_shadow",
        ),
        allow_extrapolation_when_active=_boolean(
            scene_data.get("allow_extrapolation_when_active", False),
            "allow_extrapolation_when_active",
        ),
        height_reference=height_reference,
        gnb_heights=gnb_heights,
        default_ue_height=default_ue_height,
        o2i_profiles=profiles,
        penetration_residual_db=residual,
        unconfigured_building_policy=unconfigured_building_policy,
        noise_figure_db=_finite_number(
            scene_data.get("noise_figure_db", 7.0),
            "noise_figure_db",
        ),
        ckm_config=(scene_data.get("ckm") if isinstance(scene_data.get("ckm"), dict) else None),
    )


def _height_preset(value: object, name: str) -> HeightPreset:
    data = _object(value, name)
    height_m = _finite_number(data.get("height_m"), f"{name}.height_m")
    if height_m <= 0.0:
        raise ChannelModelConfigError(f"{name}.height_m must be positive.")
    return HeightPreset(
        height_m=height_m,
        source=_nonempty_string(data.get("source"), f"{name}.source"),
        status=_nonempty_string(data.get("status"), f"{name}.status"),
    )


def _o2i_profile(value: object, name: str) -> O2IBuildingProfile:
    data = _object(value, name)
    model = _nonempty_string(data.get("penetration_model"), f"{name}.penetration_model")
    if model not in {"low_loss", "high_loss"}:
        raise ChannelModelConfigError(
            f"{name}.penetration_model must be 'low_loss' or 'high_loss'."
        )
    return O2IBuildingProfile(
        penetration_model=model,
        source=_nonempty_string(data.get("source"), f"{name}.source"),
        status=_nonempty_string(data.get("status"), f"{name}.status"),
    )


def _object(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ChannelModelConfigError(f"{name} must be an object.")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ChannelModelConfigError(f"{name} must be a boolean.")
    return value


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ChannelModelConfigError(f"{name} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise ChannelModelConfigError(f"{name} must be finite.")
    return number


def _nonempty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChannelModelConfigError(f"{name} must be a non-empty string.")
    return value.strip()
