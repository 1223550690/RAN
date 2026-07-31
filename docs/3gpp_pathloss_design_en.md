# 3GPP Large-Scale Path-Loss Module Design

## 1. Document Status

| Item | Details |
| --- | --- |
| Branch | `zhiqian/3gpp` |
| Module owner | Channel team / Zhiqian |
| Status | Stage 3 implemented; Stage 4B O2I has a separate design; no runtime integration |
| Main standard | 3GPP TR 38.901 V19.4.0, Release 19 |
| Initial scenarios | UMi Street Canyon and InH Office |
| Initial output | Deterministic mean path loss and shadow-fading standard deviation |
| Runtime integration | The initial phase does not modify `channel.py` |

This document covers only the 3GPP large-scale path-loss module. It does not
modify `ChannelState`, the scheduler, PHY, Geometry, Coordinate Calibration,
or the current MVP execution path.

> See [`3gpp_o2i_design_en.md`](3gpp_o2i_design_en.md) for the Stage 4A-4B O2I
> decisions, implementation, and results. Later statements that O2I is not
> implemented are retained as the historical Stage 1-3 boundary.

---

## 2. Objectives

The current MVP uses a simplified calculation in `ran/radio/channel.py`:

```text
straight-line distance in map coordinates
+ raw wall penetration_loss_db
-> total_path_loss_db
```

The new module aims to:

1. Implement the UMi Street Canyon and InH Office path-loss equations from
   3GPP TR 38.901.
2. Enforce a strict distinction between map units and physical metres.
3. Distinguish LOS, NLOS, scenario selection, formula branches, and
   applicability ranges explicitly.
4. Provide a stable and testable internal interface for later Geometry, O2I,
   shadow-fading, and `ChannelState` integration.
5. Retain the current channel calculation as a fallback and avoid replacing
   runtime behaviour before independent validation is complete.

### 2.1 Out of Scope for the Initial Phase

- Do not modify `ran/radio/channel.py`.
- Do not modify `ChannelState` or scheduler-facing contracts.
- Do not generate a random shadow-fading realization.
- Do not implement small-scale fading, TDL/CDL, delay spread, or Doppler.
- Do not implement MIMO, beamforming, OFDM, PRB, MCS, or CQI.
- Do not implement material penetration loss.
- Do not implement full O2I, indoor-to-outdoor, or cross-building composite
  models.
- Do not treat unconfirmed map units as metres.

---

## 3. Standards Basis

The main reference is
[ETSI / 3GPP TR 38.901 V19.4.0](https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf):

| Standard location | Material used |
| --- | --- |
| Clause 7.2 | UMi and Indoor-office scenario parameters |
| Clause 7.4.1 / Table 7.4.1-1 | UMi and InH LOS/NLOS path-loss equations and shadow-fading standard deviations |
| Clause 7.4.1 Note 1 | UMi effective breakpoint distance |
| Clause 7.4.1 Notes 2 and 6 | Frequency range and equation units |
| Clause 7.4.3 | Structure for later O2I building-penetration work |

Source docstrings and test descriptions must pin the standard version and
table location. A generic statement such as "based on 3GPP" is not sufficient
to identify which version supplied the equations.

---

## 4. Terminology and Units

| Symbol | Meaning | API unit |
| --- | --- | --- |
| `d2D` | Horizontal distance between gNB/BS and UE/UT | m |
| `d3D` | Three-dimensional distance including the height difference | m |
| `hBS` | gNB/BS antenna height | m |
| `hUT` | UE/UT antenna height | m |
| `fc` | Carrier centre frequency | MHz at the API boundary |
| `PL` | Mean large-scale path loss | dB |
| `SF` | Shadow-fading standard deviation | dB |
| `dBP'` | UMi effective breakpoint distance | m |

### 4.1 Frequency Conversion

The existing `GnbSite` contract uses `carrier_freq_mhz`, so the new API also
accepts MHz:

```text
fc_GHz = carrier_frequency_mhz / 1000
fc_Hz  = carrier_frequency_mhz * 1,000,000
```

- The path-loss equations in Table 7.4.1-1 use `fc_GHz`.
- The breakpoint equation uses `fc_Hz`.
- Callers must not pre-convert the API input to GHz.

### 4.2 Distance Source

`d2D` and `d3D` may only come from:

```text
Coordinate Calibration
-> CoordinateCalibrationView
-> PropagationGeometry.distance.distance_2d_m / distance_3d_m
```

If the Geometry metre fields are `None`, the 3GPP module must not fall back to
`map_distance_units`.

### 4.3 Uplink and Downlink Direction

This project treats large-scale path loss as reciprocal:

- Uplink and downlink use the same mean path loss.
- `hBS` always means the gNB antenna height.
- `hUT` always means the UE antenna height.
- Uplink must not swap `hBS` and `hUT` merely because the UE is transmitting.

Transmit power, receiver noise, and interference belong to the later link
budget/channel stage and are not inputs to the path-loss formula core.

---

## 5. Module Boundary

Proposed files:

```text
ran/radio/pathloss_3gpp.py
tests/radio/test_pathloss_3gpp.py
experiments/debug_3gpp_pathloss.py      # added in a second small commit
```

The initial formula core does not directly import:

- `MapService`
- `PropagationGeometry`
- `CoordinateCalibrationResult`
- `ChannelState`
- scheduler or PHY types

This makes it possible to validate the standard equations independently with
pure numeric inputs.

### 5.1 Data Flow

```text
Coordinate Calibration
        |
        v
physical d2D / d3D / heights
        |
Propagation Geometry
        |
        +-- link_type
        +-- los_state
        |
        v
3GPP request adapter (later stage)
        |
        v
pathloss_3gpp.py
        |
        +-- mean_path_loss_db
        +-- shadow_fading_std_db
        +-- formula_id
        +-- applicability metadata
```

The formula core owns only the final step. It does not perform map analysis or
coordinate fitting.

---

## 6. Initial Interface Design

The following types form an internal contract for the new module. They are not
the shared `ChannelState` contract.

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PathLossRequest:
    scenario: str
    los_state: str
    carrier_frequency_mhz: float
    distance_2d_m: float
    distance_3d_m: float
    bs_height_m: float
    ut_height_m: float


@dataclass(frozen=True, slots=True)
class PathLossResult:
    scenario: str
    los_state: str
    mean_path_loss_db: float
    shadow_fading_std_db: float
    formula_id: str
    breakpoint_distance_m: float | None
    los_reference_path_loss_db: float | None
    nlos_candidate_path_loss_db: float | None
    is_extrapolated: bool
    warnings: tuple[str, ...]


class PathLossInputError(ValueError):
    pass


class PathLossApplicabilityError(ValueError):
    pass


def estimate_path_loss_3gpp(
    request: PathLossRequest,
    *,
    allow_extrapolation: bool = False,
) -> PathLossResult:
    ...
```

### 6.1 Fixed String Values

The initial phase accepts only:

```text
scenario:
  umi_street_canyon
  inh_office

los_state:
  los
  nlos
```

Recommended `formula_id` values:

```text
3gpp_38_901_v19_4_0_umi_los_pl1
3gpp_38_901_v19_4_0_umi_los_pl2
3gpp_38_901_v19_4_0_umi_nlos
3gpp_38_901_v19_4_0_inh_los
3gpp_38_901_v19_4_0_inh_nlos
```

These identifiers allow debug reports to state exactly which formula branch
was used.

NLOS results return both the LOS reference and the NLOS candidate, allowing
tests and debug reports to verify `max(LOS, candidate)`. For LOS results,
`nlos_candidate_path_loss_db` is `None`.

---

## 7. Formula Design

All logarithms are base 10.

### 7.1 UMi Effective Breakpoint

UMi uses:

```text
hBS' = hBS - hE
hUT' = hUT - hE
hE   = 1.0 m

dBP' = 4 * hBS' * hUT' * fc_Hz / c
c    = 3.0 * 10^8 m/s
```

Required:

```text
hBS > 1.0 m
hUT > 1.0 m
```

Otherwise an effective height is non-positive and the calculation must be
rejected.

### 7.2 UMi Street Canyon LOS

For:

```text
10 m <= d2D <= dBP'
```

use:

```text
PL1 = 32.4
    + 21 * log10(d3D)
    + 20 * log10(fc_GHz)
```

For:

```text
dBP' < d2D <= 5000 m
```

use:

```text
PL2 = 32.4
    + 40 * log10(d3D)
    + 20 * log10(fc_GHz)
    - 9.5 * log10(dBP'^2 + (hBS - hUT)^2)
```

Returned shadow-fading standard deviation:

```text
SF = 4 dB
```

### 7.3 UMi Street Canyon NLOS

First calculate UMi LOS for the same inputs:

```text
PL_UMi_NLOS_candidate =
      35.3 * log10(d3D)
    + 22.4
    + 21.3 * log10(fc_GHz)
    - 0.3 * (hUT - 1.5)
```

Then:

```text
PL_UMi_NLOS = max(
    PL_UMi_LOS,
    PL_UMi_NLOS_candidate,
)
```

Return:

```text
SF = 7.82 dB
```

The implementation must not return the candidate alone;
`max(LOS, candidate)` is part of the standard equation.

### 7.4 InH Office LOS

```text
PL_InH_LOS =
      32.4
    + 17.3 * log10(d3D)
    + 20 * log10(fc_GHz)

SF = 3 dB
```

Applicable distance:

```text
1 m <= d3D <= 150 m
```

### 7.5 InH Office NLOS

```text
PL_InH_NLOS_candidate =
      38.3 * log10(d3D)
    + 17.30
    + 24.9 * log10(fc_GHz)

PL_InH_NLOS = max(
    PL_InH_LOS,
    PL_InH_NLOS_candidate,
)

SF = 8.03 dB
```

The initial phase uses the main NLOS equation in Table 7.4.1-1, not the
optional InH-NLOS equation.

---

## 8. Applicability and Error Handling

### 8.1 Inputs That Are Always Rejected

The following inputs raise `ValueError` regardless of
`allow_extrapolation`:

- Any input is `NaN` or infinity.
- `carrier_frequency_mhz <= 0`.
- `distance_2d_m < 0`.
- `distance_3d_m <= 0`.
- `distance_3d_m < distance_2d_m`.
- Either height is non-positive.
- A UMi effective height is non-positive.
- `scenario` or `los_state` is unknown.

### 8.2 2D/3D Consistency

Validate:

```text
expected_d3D = sqrt(d2D^2 + (hBS - hUT)^2)
```

Tolerance:

```text
max(0.05 m, expected_d3D * 1e-4)
```

An error beyond this tolerance suggests mixed coordinates, units, or heights
and must raise an input error.

### 8.3 Standard Applicability Ranges

| Scenario | Frequency | Distance | Reference heights |
| --- | --- | --- | --- |
| UMi | `0.5 < fc_GHz < 100` | `10 <= d2D <= 5000 m` | `hBS=10 m`, `1.5 <= hUT <= 22.5 m` |
| InH | `0.5 < fc_GHz < 100` | `1 <= d3D <= 150 m` | Indoor-office reference configuration: `hBS=3 m`, `hUT=1 m` |

Default:

```python
allow_extrapolation = False
```

Frequency, distance, or UT height outside the applicable range must raise
`PathLossApplicabilityError`; values must not be silently clamped.

When antenna heights differ from the standard reference defaults:

- the equation may still be evaluated;
- `warnings` must include `non_reference_height`;
- debug reports must show the warning;
- the result must not be described as a full 3GPP reference configuration.

Only an explicit setting of:

```python
allow_extrapolation = True
```

allows an out-of-range debug result, and the result must contain:

```text
is_extrapolated = True
warnings include the specific applicability violation
```

This option must not become the default for future runtime integration.

---

## 9. Geometry-to-Scenario Mapping

### 9.1 Automatic Mapping Allowed in the Initial Phase

| Geometry `link_type` | Geometry LOS | 3GPP scenario | Status |
| --- | --- | --- | --- |
| `outdoor_los` | `los` | UMi Street Canyon LOS | Supported |
| `outdoor_nlos` | `nlos` | UMi Street Canyon NLOS | Supported |
| `indoor_same_building` | `los` | InH Office LOS | Supported |
| `indoor_same_building` | `nlos` | InH Office NLOS | Supported |

This mapping uses LOS/NLOS determined by Geometry rather than stochastic LOS
probability sampling from TR 38.901 Clause 7.4.2. This is an explicit project
simplification that uses map geometry as prior information. Reports should
label it `geometry_determined`; it must not be described as a complete
reproduction of 3GPP stochastic scenario generation.

### 9.2 Automatic Mapping Rejected in the Initial Phase

| Geometry `link_type` | Reason |
| --- | --- |
| `outdoor_to_indoor` | Requires outdoor basic PL, exterior-wall `PLtw`, indoor-depth `PLin`, and a penetration random term |
| `indoor_to_outdoor` | An indoor gNB does not match the reference O2I assumption of an outdoor BS |
| `indoor_different_building` | Cannot be represented by one InH or UMi equation; composite boundaries must be defined |

In particular:

```text
geometry.los_state == nlos for an outdoor_to_indoor link
```

must not be interpreted directly as "use UMi NLOS". It only means that the
whole map link contains an effective penetration surface. Whether the outdoor
basic path is LOS or NLOS requires a separate outdoor-segment classification
or an explicit project assumption. The initial phase must not guess.

---

## 10. Boundary for Later O2I Design

The structure in TR 38.901 Clause 7.4.3 is:

```text
PL_total =
    PL_basic_outdoor
  + PL_through_external_wall
  + PL_indoor_depth
  + penetration_random_term
```

Geometry already provides:

- `outdoor_distance_m`
- `indoor_distance_m`
- exterior-wall and interior-wall crossings
- material names
- blocking-building IDs

It does not yet provide:

- independent LOS/NLOS state for the outdoor segment
- exterior-wall material ratios
- incidence-angle correction
- standard high-loss/low-loss building profiles
- a penetration randomness policy

O2I must therefore be a separate later stage. The current raw
`penetration_loss_db` must not simply be added to the 3GPP O2I equation, as
that could double-count penetration loss.

---

## 11. Shadow-Fading Strategy

The initial phase returns only:

```text
shadow_fading_std_db
```

It does not generate:

```text
shadow_fading_db ~ Normal(0, SF^2)
```

Reasons:

1. A random term requires a seed and reproducibility policy.
2. Shadow fading for a moving UE should account for spatial correlation.
3. A later CKM stage may replace independent random sampling with a
   location-based prior.
4. Formula unit tests should validate deterministic mean path loss first.

If a random term is added later, it should be an explicit new component and
must not be hidden inside `estimate_path_loss_3gpp()`.

---

## 12. Test Design

### 12.1 Fixed Test Configurations

Outdoor UMi:

```text
fc   = 3500 MHz
hBS  = 10 m
hUT  = 1.5 m
hE   = 1 m
dBP' = 210 m
```

Indoor InH:

```text
fc  = 3500 MHz
hBS = 3 m
hUT = 1 m
```

### 12.2 Formula Reference Values

Tests use independent fixed values rather than duplicating the production
function in test code.

| Test | Input | Expected path loss |
| --- | --- | ---: |
| UMi LOS PL1 | `d2D=10 m`, `d3D≈13.124405 m` | `66.761033 dB` |
| UMi LOS PL1 | `d2D=100 m`, `d3D≈100.360600 m` | `85.314189 dB` |
| UMi LOS breakpoint | `d2D=210 m` | `92.055431 dB` |
| UMi LOS PL2 | `d2D=300 m`, `d3D≈300.120393 m` | `98.244261 dB` |
| UMi NLOS | `d2D=100 m` | `104.643832 dB` |
| InH LOS | `d3D=10 m` | `60.581361 dB` |
| InH NLOS | `d3D=10 m` | `69.147294 dB` |
| InH NLOS max guard | `d2D=0 m`, `d3D=2 m` | `48.489180 dB` |

Recommended floating-point assertion:

```python
self.assertAlmostEqual(actual, expected, places=6)
```

### 12.3 Required Test Categories

Equations:

1. UMi breakpoint evaluates to `210 m`.
2. UMi LOS selects PL1 before the breakpoint.
3. UMi LOS selects PL2 after the breakpoint.
4. PL1 and PL2 are continuous at the breakpoint.
5. UMi NLOS uses `max(LOS, candidate)`.
6. The InH LOS equation is correct.
7. InH NLOS uses `max(LOS, candidate)`.
8. Each scenario returns the correct SF standard deviation and `formula_id`.

Units and inputs:

9. `3500 MHz` is converted to `3.5 GHz`.
10. Inconsistent 2D distance, 3D distance, and heights are rejected.
11. `None` metre distances are not allowed into the adapter.
12. Map distance cannot be used as a metre fallback.
13. NaN, infinity, zero frequency, and negative distances are rejected.

Applicability:

14. UMi `d2D < 10 m` is rejected by default.
15. InH `d3D > 150 m` is rejected by default.
16. Out-of-range input with `allow_extrapolation=True` is marked as
    extrapolated.
17. Non-reference heights produce a warning.

Regression:

18. The original 36 tests continue to pass when the new module is present.
19. The 10-tick MVP output remains unchanged because the initial phase is not
    integrated into runtime.

---

## 13. Staged Commit Plan

### PR/Commit 1: Formula Core

```text
add pathloss_3gpp.py
add test_pathloss_3gpp.py
implement UMi LOS/NLOS
implement InH LOS/NLOS
implement input and applicability validation
do not connect Geometry
do not connect channel.py
```

### PR/Commit 2: Debug Adapter

```text
add an explicit Geometry -> PathLossRequest adapter
add debug_3gpp_pathloss.py
report baseline FSPL and 3GPP mean-PL comparison
fail explicitly when metre fields are None
still do not modify channel.py
```

### PR/Commit 3: O2I Design and Material Prior

```text
define outdoor-segment LOS/NLOS
define low-loss/high-loss building profiles
define exterior-wall material and incidence angle
avoid double-counting raw wall loss
```

### PR/Commit 4: Shadow Fading / CKM

```text
define deterministic seed
define spatial correlation
define the relationship between CKM prior and random residual
```

### PR/Commit 5: Runtime Integration

This requires team approval before implementation:

```text
add an optional model selector to estimate_channel
retain the existing baseline fallback
preserve all ChannelState fields
run full scheduler/PHY/MVP regression
```

---

## 14. Interface-Stability Check

Expected answers for the initial phase:

| Question | Answer |
| --- | --- |
| Does this modify a shared contract? | No |
| Does this modify `ChannelState`? | No |
| Does this modify scheduler/PHY? | No |
| Does this modify Geometry/Calibration? | No |
| Does this replace the current `estimate_channel()`? | No |
| Is the MVP baseline retained? | Yes |
| Are map units allowed into the 3GPP equations? | No |
| Does this implement O2I or random fading? | No |

---

## 15. Decisions Required from the Team

The following must be agreed before O2I or runtime integration begins:

1. Is the actual gNB height fixed at `10 m`?
2. Are indoor gNBs present? If so, how should InH and I2O be defined?
3. Will the Bristol scenario use UMi Street Canyon as the common Capstone
   outdoor assumption?
4. How will LOS/NLOS for an O2I outdoor segment be obtained?
5. Will buildings use low-loss, high-loss, or map-material profiles?
6. Will shadow fading be independent random, spatially correlated, or based
   on a CKM prior?
7. Will the project add an optional channel-model selector, or only provide
   offline comparison?

---

## 16. Initial Acceptance Criteria

The formula core is complete only when all of the following hold:

- All fixed reference-value tests pass.
- Breakpoint continuity passes.
- The NLOS `max` rule passes.
- All unit and out-of-range tests pass.
- No map-unit fallback exists.
- The original 36 tests pass.
- The 10-tick MVP passes with an unchanged output structure.
- No shared interface is modified.
- Source and tests identify the standard version and clause explicitly.

---

## 17. References

1. [3GPP Specification 38.901 portal](https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx?specificationId=3173)
2. [ETSI TR 138 901 V19.4.0 PDF](https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf)
3. Project Geometry handoff: `docs/propagation_geometry_handoff_en.md`
4. Project Coordinate Calibration handoff: `docs/coordinate_calibration_handoff_en.md`
5. Current baseline channel: `ran/radio/channel.py`
