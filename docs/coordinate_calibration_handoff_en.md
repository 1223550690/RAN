# Coordinate Calibration Handoff

## Scope

Coordinate calibration and propagation geometry. The calibration
core remains separate from `geometry.py` so that physical units can change
without changing map topology or geometry classification.

The coordinate-calibration work adds:

- `ran/radio/coordinate_calibration.py`
- `configs/ran/coordinate_calibration.json`
- `experiments/debug_coordinate_calibration.py`
- standard-library unit tests

Geometry now consumes the result through an additive read-only adapter. This
does not change `channel.py`, `ChannelState`, the scheduler, path loss,
metrics, or the editor schema.

## Current Bristol Assumption

The configured scene bounds are `2000 x 2000 map units`. The provisional
physical extent is approximately `300 m x 400 m`, producing:

```text
meters_per_map_unit_x = 0.15
meters_per_map_unit_y = 0.20
status = provisional
source = team_approximation
```

These values are configuration data, not algorithm constants. Update
`physical_extent_m`, `calibration_id`, `source`, and `status` when better
measurements are agreed.

## Distance Semantics

Anisotropic calibration requires coordinate differences to be transformed
before distance is calculated:

```text
dx_m = (x2 - x1) * scale_x
dy_m = (y2 - y1) * scale_y
d2D_m = sqrt(dx_m^2 + dy_m^2)
d3D_m = sqrt(d2D_m^2 + (h1_m - h2_m)^2)
```

A legacy scalar is exposed only when x and y scales are equal. This prevents
callers from incorrectly multiplying a map-space Euclidean distance by one
number when the two axes use different scales.

## Configuration Status

- `provisional`: usable only for debug or explicit opt-in; real anchors may be absent.
- `confirmed`: requires at least two anchors and a maximum relative anchor error of 10%.
- Unknown scenes return no calibration instead of assuming `1 unit = 1 m`.

The nominal `rendering.map_bounds` define the physical rectangle. Some road
geometry extends outside those bounds for clipping; positions are converted
without silent clamping.

## Debug Command

```powershell
python -m experiments.debug_coordinate_calibration --scene bristol_topology --pretty
```

Optional sample receiver and heights:

```powershell
python -m experiments.debug_coordinate_calibration --x 520 --y 280 --gnb-height-m 10 --ue-height-m 1.5 --pretty
```

## Geometry Compatibility Adapter

`coordinate_view_from_calibration(...)` converts this module's result into the
geometry-owned `CoordinateCalibrationView`. Geometry now supports optional x/y
scales while preserving both the old scalar path and no-calibration behavior.

Run the focused compatibility tests:

```powershell
python -m unittest tests.radio.test_geometry_coordinate_calibration tests.radio.test_coordinate_calibration
```

Then compare the two debug modes:

```powershell
python -m experiments.debug_propagation_geometry
python -m experiments.debug_propagation_geometry --with-calibration --gnb-height-m 10
```

The first command must keep meter fields as `None`. The second explicitly opts
into the current provisional calibration and must populate 2D/crossing/link
sub-distance meter fields. Runtime channel integration remains a separate
cross-group change.
