# 3GPP Path-Loss Stage 2-3 验收记录

## 1. 结论

截至 `2026-07-31`，本地分支 `zhiqian/3gpp` 已完成：

```text
Stage 2: standalone 3GPP/FSPL debug comparison
Stage 3: read-only Geometry/Calibration adapter and Bristol dry run
```

本阶段没有修改：

```text
ran/radio/channel.py
ran/radio/geometry.py
ran/radio/coordinate_calibration.py
ChannelState
scheduler / PHY / metrics / editor schema
```

## 2. Stage 2 结果

新增：

```text
experiments/debug_3gpp_pathloss.py
tests/radio/test_pathloss_3gpp_debug.py
```

CLI 接收纯物理参数，不读取 scene、Geometry 或 `ChannelState`。输出包括：

```text
3GPP mean path loss
formula ID
shadow-fading standard deviation
UMi breakpoint
LOS reference and NLOS candidate
FSPL baseline
difference from baseline
applicability warnings
```

固定样例：

```text
scenario:             UMi NLOS
fc:                   3500 MHz
d2D:                  100 m
hBS/hUT:              10 m / 1.5 m
3GPP path loss:       104.643832 dB
FSPL baseline:         83.312626 dB
difference:            21.331206 dB
breakpoint:           210 m
SF std:                 7.82 dB
```

同一输入重复运行返回完全相同的 JSON 数据，不包含随机项。

## 3. Stage 3 Adapter

新增：

```text
ran/radio/pathloss_3gpp_adapter.py
tests/radio/test_pathloss_3gpp_adapter.py
```

入口：

```text
path_loss_request_from_geometry(...)
```

允许的映射：

| Geometry | 3GPP request |
| --- | --- |
| `outdoor_los` | UMi LOS |
| `outdoor_nlos` | UMi NLOS |
| `indoor_same_building` + LOS | InH LOS |
| `indoor_same_building` + NLOS | InH NLOS |

明确 unsupported：

```text
outdoor_to_indoor
indoor_to_outdoor
indoor_different_building
unknown link type
```

Adapter 还会拒绝：

```text
missing distance_2d_m / distance_3d_m
contradictory outdoor link_type and los_state
Geometry gnb_id != GnbSite.gnb_id
```

Adapter 不推断 map units，不交换上下行高度，也不修改传入 Geometry。

## 4. Bristol Dry Run

新增：

```text
experiments/debug_bristol_3gpp_pathloss.py
tests/radio/test_pathloss_3gpp_bristol.py
```

命令：

```powershell
python -m experiments.debug_bristol_3gpp_pathloss `
  --gnb-height-m 10 `
  --pretty
```

当前 calibration：

```text
status:       provisional
source:       team_approximation
extent:       300 m x 400 m
scale_x/y:    0.15 / 0.20 m per map unit
anchors:      0
warning:      provisional_calibration_has_no_reference_anchors
```

结果：

| Case | Geometry | Stage 3 result |
| --- | --- | --- |
| `outdoor_green` | outdoor LOS | UMi LOS, `89.242790 dB` |
| `outdoor_east_of_student_union` | outdoor NLOS | UMi NLOS, `104.746827 dB` |
| `student_union_center` | O2I | unsupported, `path_loss=null` |
| `gym_center` | O2I | unsupported, `path_loss=null` |

这证明 Stage 3 不会把 O2I 偷偷当作 UMi NLOS。

## 5. 测试结果

```text
Stage 1 path-loss tests:     23
Stage 2 debug tests:          2
Stage 3 adapter tests:        9
Stage 3 Bristol tests:        2
All repository tests:        72/72 passed
MVP aggregate, 10 ticks:     passed
delivered/undelivered:       104857600 / 0 bytes
loss_rate:                   0.000000
```

MVP regression 仍使用原 baseline，并成功完成，因为 Stage 3 没有接入
`channel.py`。

## 6. Stage 3 后仍未完成

```text
confirmed real-distance anchors
O2I/I2O/cross-building path-loss composition
material penetration model
shadow-fading realization and spatial correlation
runtime ChannelState/link-budget integration
scheduler linkage
CKM and small-scale fading
```

Stage 3 的完成不等于完整 3GPP channel 已完成。准确表述是：

```text
The standalone 3GPP basic path-loss core and its read-only Geometry adapter
are implemented and validated for approved UMi and InH links.
```

## 7. 本地提交与 Push 状态

```text
0eb2323 Add standalone 3GPP path-loss debug report
ed18d4f Add read-only Geometry adapter for 3GPP path loss
```

提交作者：

```text
Zhiqian He <xa25139@bristol.ac.uk>
```

截至本报告更新时，这两个提交尚未 push。
