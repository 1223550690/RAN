# 3GPP O2I Building Penetration Design \(Stages 4A-4B\)

## 1. Status and Boundary

| Item                | Detail                                                          |
| ------------------- | --------------------------------------------------------------- |
| Status              | O2I Gate frozen; O2I Stage standalone implementation tested     |
| Standard            | 3GPP TR 38.901 V19.4.0 Clause 7.4.3.1                           |
| Supported link      | Outdoor gNB to indoor UE \(`outdoor_to_indoor`\)                |
| Scenario            | UMi Street Canyon with low-loss or high-loss building profile   |
| Runtime             | Not integrated into `channel.py`; the MVP path is unchanged     |
| Explicitly excluded | I2O, cross-building indoor links, random fields, SF realization |

Official source: [ETSI TR 138 901 V19.4.0](https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf).

## 2. Standard Model

The deterministic mean O2I path loss is decomposed as:

```text
mean PL = PLb + PLtw + PLin
total PL = mean PL + penetration residual
```

- `PLb` is the UMi outdoor basic path loss from Clause 7.4.1.
- `PLtw` is the external-wall material mixture from Table 7.4.3-2.
- `PLin = 0.5 × d2D-in` is the loss due to depth inside the building.
- The penetration residual is a zero-mean Gaussian term. Stage 4B keeps its
realization at 0 and exposes only its standard deviation as metadata.

At 3.5 GHz:

| Profile   | Material mixture                             | `PLtw`   | `sigmaP` |
| --------- | -------------------------------------------- | -------- | -------- |
| low-loss  | 30% standard multi-pane glass + 70% concrete | 12.70 dB | 4.4 dB   |
| high-loss | 70% IRR glass + 30% concrete                 | 27.50 dB | 6.5 dB   |

Release 19 uses `L_IRRglass = 25.4 + 0.11f`, with `f` in GHz. Older IRR-glass
coefficients must not be substituted silently.

## 3. O2I Gate Decisions

1. **Outdoor LOS/NLOS:** use UMi NLOS when `blocking_building_ids` is non-empty;
otherwise use UMi LOS. The target exterior wall does not drive this choice.
2. **Geometry contract:** do not extend or modify Geometry. Consume its existing
distances, link type, blocker list, and target exterior crossing read-only.
3. **Building profile:** the caller explicitly selects `low_loss` or `high_loss`.
The Bristol dry-run uses `low_loss`; this is not a measured material claim.
4. **Material proportions:** use Table 7.4.3-2 exactly. Do not improvise a profile
from map labels such as `brick` or `drywall`.
5. **Incidence term:** use the fixed 5 dB term in Table 7.4.3-2. Stage 4B adds no
custom ray-incidence-angle correction.
6. **Indoor depth:** use Geometry `indoor_distance_m` instead of UT-specific
random depth. This map-aware project deviation is reported as a warning.
7. **Random term:** use a 0 dB residual and expose `sigmaP`. Spatially correlated
random realization belongs to Stage 5, not an independent draw every tick.
8. **No double counting:** raw map `penetration_loss_db` is debug-only and is not
added to the 3GPP O2I result.

The standard UMi O2I depth generation has support up to 25 m. A measured Geometry
depth above 25 m fails in strict mode and requires explicit
`allow_extrapolation=True`, which also marks the result as extrapolated.

## 4. Data Flow and Interface

```text
PropagationGeometry + GnbSite + heights + building profile
    -> o2i_path_loss_request_from_geometry()
    -> O2IPathLossRequest
    -> estimate_o2i_path_loss_3gpp()
    -> O2IPathLossResult
       {PLb, PLtw, PLin, residual, mean, total, sigmaP, warnings}
```

`PLb` uses the full straight-line 3D gNB-to-UE distance. In the current 2.5D
straight-line geometry this is equivalent to the standard `d3D-out + d3D-in`.
The adapter does not copy raw map wall loss into the request.

The existing `path_loss_request_from_geometry()` retains its Stage 3 behavior and
still rejects O2I. The new O2I entry point is additive and does not alter existing
callers.

## 5. Bristol Results

With provisional `300 m × 400 m` calibration, 3.5 GHz, 10 m gNB, 1.5 m UE, and
the low-loss profile:

| Case                 | Outdoor state                  | `PLb`  | `PLtw` | `PLin` | Mean total |
| -------------------- | ------------------------------ | ------ | ------ | ------ | ---------- |
| Student Union centre | LOS                            | 82.70  | 12.70  | 12.97  | 108.37 dB  |
| Gym centre           | NLOS \(Student Union blocker\) | 107.40 | 12.70  | 10.66  | 130.76 dB  |

The Student Union Geometry depth is 25.94 m, just outside standard random-depth
support, so this dry-run explicitly enables extrapolation. Calibration remains
provisional; these values validate engineering flow rather than final field data.

## 6. Reproduction

```bash
python -m unittest tests.radio.test_pathloss_3gpp_o2i -v
python -m unittest tests.radio.test_pathloss_3gpp_adapter -v
python -m unittest tests.radio.test_pathloss_3gpp_o2i_bristol -v
python -m experiments.debug_bristol_3gpp_o2i --gnb-height-m 10 --allow-extrapolation --pretty
```

Completing Stage 4B does not switch the runtime. Integration with `channel.py`,
`ChannelState`, or the scheduler remains a later cross-module review item.
