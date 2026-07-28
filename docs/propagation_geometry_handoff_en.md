# Propagation Geometry Handoff

## Summary

This handoff documents propagation geometry module for the RAN MVP.
The implementation is intentionally additive and debug-first:

- New module: `ran/radio/geometry.py`
- Debug entry point: `experiments/debug_propagation_geometry.py`
- No changes to `ran/radio/channel.py`
- No changes to `ChannelState` or other shared contracts
- Coordinate calibration is implemented separately and is not embedded in this module
- No scheduler, protocol, path loss, CKM, beamforming, metrics, or editor-schema changes

The goal is to provide map-level geometric evidence for a future channel/path-loss model.
It does not replace the current MVP channel estimator.

## Ownership Boundary

Current channel-team boundary:

- Coordinate calibration and propagation geometry analysis.
- Calibration remains a separate module with its own configuration and tests.
- This geometry module may consume a read-only calibration view, but it must not infer or maintain map-to-meter scales itself.
- Other groups should not treat this module as a scheduler, QoS, RLC/PDCP, or final path-loss implementation.

## Main API

```python
from ran.contracts import Position
from ran.radio.coordinate_calibration import load_coordinate_calibration
from ran.radio.geometry import (
    analyze_propagation_geometry,
    coordinate_view_from_calibration,
    geometry_to_report,
)

calibration = load_coordinate_calibration("bristol_topology")
coordinate_view = (
    coordinate_view_from_calibration(calibration, gnb_height_m=10.0)
    if calibration is not None
    else None
)

geometry = analyze_propagation_geometry(
    scene=scene,
    receiver_position=Position(520.0, 280.0),
    gnb=gnb,
    coordinate_view=coordinate_view,
)

report = geometry_to_report(geometry)
```

### `analyze_propagation_geometry(...)`

Inputs:

- `scene`: the current scene object, usually from `structure.scene_registry.build_scene`.
- `receiver_position`: UE or receiver position as `Position(x, y)`.
- `gnb`: base station site as `GnbSite`.
- `coordinate_view`: optional read-only `CoordinateCalibrationView`. Use
`coordinate_view_from_calibration(...)` to adapt a
`CoordinateCalibrationResult`.
- `map_service`: optional `MapService` dependency injection for tests.

Output:

- `PropagationGeometry`, a dataclass containing link type, LOS/NLOS state, distance fields, wall/surface crossings, portal crossings, and blocking buildings.

### `geometry_to_report(...)`

Converts `PropagationGeometry` into a JSON-friendly `dict` for debug output, logging, or review.

## Processing Flow

1. Build the straight line from gNB position to UE position.
2. Compute map-unit distance. If a calibration view is provided, transform the
x/y coordinate differences before calculating meter distance.
3. Query `MapService.get_area_at(...)` for both gNB and UE positions.
4. Determine whether each endpoint is indoor or outdoor and identify the receiver building.
5. Query `MapService.get_walls_between(...)` for all wall and boundary intersections.
6. Normalize wall intersections into `PropagationSurfaceCrossing` objects.
7. Deduplicate overlapping surfaces, especially generated area boundaries and explicit walls at the same location.
8. Collect propagation-related portals from scene and area data.
9. If the link intersects an open portal, mark the matched wall crossing as ineffective with `ignored_reason="open_portal"`.
10. Classify the link as one of:

- `outdoor_los`
- `outdoor_nlos`
- `outdoor_to_indoor`
- `indoor_to_outdoor`
- `indoor_same_building`
- `indoor_different_building`

11. Separate target-building crossings from non-target blocking buildings.
12. Compute `los_state`.
13. Split the link distance into outdoor and indoor map-unit components.
14. Return a structured geometry object or JSON report.

## Important Output Fields

### Link classification

- `link_type`: coarse propagation scenario, such as `outdoor_to_indoor`.
- `los_state`: `los` or `nlos`.
- `blocking_building_ids`: buildings that block an outdoor path but should not be summed as target wall material loss.

### Distances

- `map_distance_units`: always available.
- `distance_2d_m`: calibrated horizontal distance, or `None` without calibration.
- `distance_3d_m`: `None` until both coordinate calibration and gNB/UE heights are supplied.
- `outdoor_distance_map_units`: outdoor part of the link in map units.
- `indoor_distance_map_units`: indoor part of the link in map units.
- `outdoor_distance_m` and `indoor_distance_m`: calibrated link sub-distances,
or `None` without calibration.

## Coordinate Calibration Compatibility

`CoordinateCalibrationView` preserves the original positional fields:

```python
meters_per_map_unit
gnb_height_m
ue_height_m
```

and appends two optional fields:

```python
meters_per_map_unit_x
meters_per_map_unit_y
```

The conversion precedence is:

1. When both x/y scales exist, use the anisotropic distance
`sqrt((dx * scale_x)^2 + (dy * scale_y)^2)`.
2. Otherwise, use the original scalar `meters_per_map_unit` path.
3. Without either calibration form, keep all meter fields as `None`.

The x/y fields take precedence when both new and legacy values are present.
Wall and portal crossing distances use their actual endpoints. Indoor and
outdoor meter distances are proportional sub-distances of the same straight
gNB-to-UE link, so their sum equals `distance_2d_m` apart from floating-point
rounding.

### Crossings

- `all_surface_crossings`: raw and debug surface crossings, including ignored duplicates, open-portal matches, and blocking-building crossings.
- `effective_surface_crossings`: crossings that are currently counted as material surfaces for this geometry context.
- `exterior_surfaces_crossed`: effective exterior wall or building-boundary crossings.
- `interior_walls_crossed`: effective interior wall crossings.
- `portals_crossed`: propagation-related portals intersected by the gNB-to-UE line.

## Portal Semantics

`Portal.open=True` is interpreted as a geometric opening. If the radio line crosses an open portal that matches a wall, that wall crossing is ignored for effective material-wall counting.

`Portal.locked=True` is currently preserved as metadata only. It does not add RF loss. In the current scene data, many doors are `locked=True` and `open=True`; this means "access controlled or fixed in the scene editor", not "closed RF obstacle".

Future work may add door or glass material loss, but that should be a separate path-loss or material-model task.

## Blocking Building Semantics

For an `outdoor_to_indoor` link, the target building is the receiver building. Crossings through other buildings are recorded as `blocking_building_ids` and marked as `ignored_reason="blocking_building_nlos_classification"`.

This avoids treating a non-target building's internal walls as if the signal physically enters that building and accumulates room-by-room loss. Instead, the geometry records that the link is NLOS because another building blocks the path.

## Debug Command

Run from the repository root:

```powershell
python -m experiments.debug_propagation_geometry --pretty
```

Run a custom receiver point:

```powershell
python -m experiments.debug_propagation_geometry --x 520 --y 280 --pretty
```

Explicitly opt into the configured coordinate calibration:

```powershell
python -m experiments.debug_propagation_geometry --with-calibration --gnb-height-m 10 --pretty
```

The default command deliberately keeps the previous no-calibration behavior.
The current Bristol calibration is provisional, so `--with-calibration` is an
explicit debug opt-in rather than a runtime default.

## Current Smoke-Test Expectations

The default debug script currently covers four cases:

| Case                            | Expected link type  | Expected LOS state | Notes                                                   |
| ------------------------------- | ------------------- | ------------------ | ------------------------------------------------------- |
| `outdoor_green`                 | `outdoor_los`       | `los`              | No wall crossing                                        |
| `student_union_center`          | `outdoor_to_indoor` | `nlos`             | Enters Student Union and crosses interior walls         |
| `gym_center`                    | `outdoor_to_indoor` | `nlos`             | Target Gym wall plus Student Union as blocking building |
| `outdoor_east_of_student_union` | `outdoor_nlos`      | `nlos`             | Outdoor receiver blocked by Student Union               |

Validation commands used before handoff:

```powershell
python -m unittest tests.radio.test_geometry_coordinate_calibration tests.radio.test_coordinate_calibration
python -m experiments.debug_propagation_geometry
python -m experiments.debug_propagation_geometry --with-calibration --gnb-height-m 10
```

The coordinate compatibility test performs these checks step by step:

1. Run geometry without calibration and assert all meter fields remain `None`.
2. Construct `CoordinateCalibrationView(2.0, 10.0, 4.0)` positionally and
verify the legacy scalar result remains unchanged.
3. Supply x/y scales and verify a `(100, 100)` map delta produces `25 m` with
`scale_x=0.15` and `scale_y=0.20`.
4. Adapt a `CoordinateCalibrationResult` and verify default UE height plus an
explicit gNB-height override.
5. Verify anisotropic wall-crossing distance and O2I indoor/outdoor split, and
assert `outdoor_distance_m + indoor_distance_m == distance_2d_m`.

## Integration Notes

This branch does not wire geometry into `estimate_channel()`. A later integration PR should:

1. Keep the current raw wall-loss behavior as a fallback.
2. Avoid changing `ChannelState` unless the team explicitly agrees.
3. If new shared fields are needed, add optional fields with safe defaults.
4. Use geometry output as evidence for path-loss classification, not as a full channel model by itself.
5. Treat provisional meter distances as debug-only until reference anchors
confirm the coordinate calibration.

## Known Limitations

- Calibration remains implemented in its separate module; geometry only
consumes an adapted read-only view.
- Meter distances are `None` without a supplied calibration view.
- Compatibility tests cover no-calibration, legacy scalar, anisotropic x/y,
height adaptation, crossing distance, and O2I distance split.
- Portal material loss is not modeled.
- Door locked state does not affect RF propagation.
- Child-area portal coordinate assumptions may need review if future scenes attach portals directly to child areas.
- This module does not implement 3GPP path loss, shadow fading, fast fading, MIMO, OFDM, scheduler feedback, or CQI changes.

## PR Review Checklist

- Does the existing MVP still run\?
- Does this change any shared interface\? Expected answer: only additive
optional x/y fields in the geometry-owned calibration view.
- Does this delete or rename any field\? Expected answer: no.
- Does this modify `channel.py` or `ChannelState`\? Expected answer: no.
- Are meter fields documented as optional and `None` without calibration\?
- Are blocking buildings separated from effective target-building wall crossings\?
- Are portal assumptions documented for the team\?

 
