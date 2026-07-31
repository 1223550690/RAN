# Channel Regular Results、当前结果与 Alignment

## 1. 文档目的

本文档统一说明：

1. 一个常规 system-level large-scale channel baseline 应产生什么结果。
2. 当前项目的 Coordinate Calibration、Propagation Geometry 和 3GPP
   Path-Loss 模块实际产生了什么结果。
3. 当前结果与预期之间哪些已经对齐、哪些只完成了一部分。
4. 如何复现现有测试和 debug 输出。
5. 在不深入完整物理层的前提下，还需要完成哪些集成工作。

当前代码位置：

```text
worktree: D:\AI_RAN_SANBOX\RAN_3GPP
branch:   zhiqian/3gpp
remote:   origin/zhiqian/3gpp
```

主要标准参考：

```text
3GPP TR 38.901 V19.4.0, Release 19
Clause 7.4.1
Table 7.4.1-1: Pathloss models
```

官方文档：

<https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf>

---

## 2. 先区分两种 Regular Result

### 2.1 3GPP Path-Loss 公式的结果

只看 3GPP TR 38.901 Table 7.4.1-1，regular result 主要是：

```text
deterministic basic mean path loss in dB
shadow-fading standard deviation for the selected scenario
```

它本身不直接输出：

```text
received power
noise power
interference power
SINR
CQI
BLER
PRB/MCS allocation
```

这些属于后续 link budget、channel state 和 scheduler。

### 2.2 完整 system-level large-scale channel 的结果

一个常规的系统级 baseline 通常应按以下顺序产生结果：

```text
1. Physical link description
   gNB/UE position, d2D, d3D, indoor/outdoor, LOS/NLOS

2. Basic path loss
   selected scenario and deterministic 3GPP mean path loss

3. Additional large-scale loss
   shadow fading, O2I penetration and other approved losses

4. Link budget
   total path loss, received power, noise, interference and SINR

5. Scheduler-facing state
   CQI, predicted BLER/PER and other scheduling inputs
```

因此：

```text
3GPP basic path-loss result
!=
complete end-to-end channel result
```

---

## 3. 项目中的对象与数据流

当前和计划的数据流如下：

```text
GnbSite.position + UE Position + scene
        |
        v
CoordinateCalibrationResult
        |
        | scale_x, scale_y, d2D, d3D
        v
CoordinateCalibrationView
        |
        v
PropagationGeometry
        |
        | link_type, los_state, distances, crossings
        v
read-only Geometry-to-3GPP adapter
        |
        v
PathLossRequest
        |
        v
PathLossResult
        |
        v
[future ChannelState/link-budget integration]
```

主要对象：

| 模块 | 输入对象 | 输出对象 |
| --- | --- | --- |
| Coordinate Calibration | `CalibrationDefinition`, `Position` | `CoordinateCalibrationResult`, `PhysicalPosition`, d2D/d3D |
| Propagation Geometry | scene, `GnbSite`, receiver `Position`, optional calibration view | `PropagationGeometry` |
| 3GPP Path Loss | `PathLossRequest` | `PathLossResult` |
| Future Channel | `GnbSite.tx_power_dbm`, path loss, noise/interference | existing `ChannelState` |

---

## 4. Coordinate Calibration

### 4.1 Regular expectation

坐标标定应：

- 把地图坐标转换为物理米制坐标。
- 支持 X/Y 不同比例。
- 输出物理 d2D。
- 在给出 gNB/UE 高度时输出 d3D。
- 记录标定来源、状态和锚点误差。
- 不把未经确认的比例静默当作真实值。

这里的 Coordinate Calibration 是项目的 map-to-metre 工程转换，不是
3GPP Clause 7.8 所说的 channel-model calibration。

### 4.2 当前结果

当前 Bristol 配置：

```text
map extent:                2000 x 2000 map units
provisional physical size: 300 m x 400 m
scale_x:                   0.15 m/map-unit
scale_y:                   0.20 m/map-unit
status:                    provisional
source:                    team_approximation
anchor_count:              0
```

计算：

```text
dx_m = dx_map * scale_x
dy_m = dy_map * scale_y
d2D  = sqrt(dx_m^2 + dy_m^2)
d3D  = sqrt(d2D^2 + (hBS-hUT)^2)
```

当前 debug 样例：

```text
gNB map position:      (90, 90)
receiver map position: (1000, 1000)
gNB physical position: (13.5 m, 18.0 m)
UE physical position:  (150.0 m, 200.0 m)
d2D:                   227.5 m
d3D:                   None, because gNB height was not supplied
warning:               provisional_calibration_has_no_reference_anchors
```

### 4.3 Alignment

已经符合：

- X/Y 独立比例。
- d2D/d3D 算法。
- 配置与算法分离。
- `provisional`/`confirmed` 状态。
- unknown scene 不猜测 `1 map unit = 1 m`。
- confirmed calibration 至少需要两个 anchors。
- confirmed calibration 最大相对 anchor error 不得超过 10%。

仍需改进：

- 提供至少两个真实距离 anchors。
- 记录 Google Earth 或其他测量来源。
- 根据 anchor residual 更新 physical extent。
- 通过误差检查后才能把状态改为 `confirmed`。

---

## 5. Propagation Geometry

### 5.1 Regular expectation

地图感知的传播几何应针对一条 gNB-to-UE link 输出：

```text
indoor/outdoor state
link type
deterministic LOS/NLOS state
total d2D/d3D
outdoor and indoor segments
crossed walls/exterior surfaces
crossed portals
blocking buildings
```

本模块是 map-aware computational geometry，不是完整 electromagnetic
ray tracing。它不计算反射、绕射、多径相位、delay spread 或 Doppler。

### 5.2 当前结果

当前支持的 link type：

```text
outdoor_los
outdoor_nlos
outdoor_to_indoor
indoor_to_outdoor
indoor_same_building
indoor_different_building
```

实现行为：

- 查询 gNB 和 receiver 所属 area。
- 判断 indoor/outdoor。
- 计算 link segment 与墙体、建筑边界和 portal 的交点。
- 去除重复 surface。
- 使用 portal open state 过滤对应 crossing。
- 区分目标建筑墙体和中间 blocking building。
- 输出 LOS/NLOS、meter distance 和 indoor/outdoor distance split。

带 provisional calibration 的 Bristol 样例：

| Case | Link type | LOS state | d2D | d3D | 关键结果 |
| --- | --- | --- | ---: | ---: | --- |
| `outdoor_green` | `outdoor_los` | LOS | 154.16 m | 154.40 m | 无有效 crossing |
| `outdoor_east_of_student_union` | `outdoor_nlos` | NLOS | 100.68 m | 101.04 m | Student Union 为 blocking building |
| `student_union_center` | `outdoor_to_indoor` | NLOS | 74.86 m | 75.34 m | outdoor 48.92 m，indoor 25.94 m |
| `gym_center` | `outdoor_to_indoor` | NLOS | 119.85 m | 120.15 m | Student Union blocker，Gym exterior crossing |

### 5.3 Alignment

已经符合：

- map-aware link classification。
- 明确的 wall/portal/blocking-building 语义。
- calibration 为只读输入。
- 无 calibration 时保留 map units，meter 字段为 `None`。
- 没有把材料 path loss 写进 Geometry。

需要明确说明的设计差异：

- 3GPP 可以按 LOS probability 随机生成 LOS/NLOS。
- 当前项目根据已知地图障碍物确定 LOS/NLOS。
- 这是 deterministic map-aware adaptation，不是对 3GPP LOS probability
  的直接实现。

当前 adapter 已完成：

- 把受支持的 Geometry 结果转换为 `PathLossRequest`。
- 对 O2I、I2O 和 different-building 链路明确返回 unsupported。
- 不把所有 NLOS 链路映射为同一个 3GPP 场景。
- 检查 Geometry 与 `GnbSite` 的 `gnb_id` 一致。
- 不修改传入的 Geometry。

---

## 6. 3GPP Large-Scale Path Loss

### 6.1 Regular expectation

对每条 BS-UT link，根据：

```text
scenario
LOS/NLOS state
carrier frequency
d2D
d3D
hBS
hUT
```

选择 3GPP 公式并返回 deterministic basic mean path loss。

当前 baseline 选择：

```text
UMi Street Canyon:
  outdoor LOS/NLOS

InH Office:
  indoor same-building LOS/NLOS
```

### 6.2 当前结果

已实现：

```text
UMi effective breakpoint
UMi LOS PL1 and PL2
UMi NLOS candidate and max guard
InH LOS
InH NLOS candidate and max guard
shadow-fading standard-deviation metadata
formula ID
strict unit and applicability validation
explicit extrapolation warnings
standalone FSPL comparison report
read-only Geometry-to-3GPP adapter
Bristol Stage 3 dry-run report
```

当前输出：

```text
mean_path_loss_db
shadow_fading_std_db
formula_id
breakpoint_distance_m
los_reference_path_loss_db
nlos_candidate_path_loss_db
is_extrapolated
warnings
```

### 6.3 固定数值结果

UMi，`fc=3500 MHz`、`hBS=10 m`、`hUT=1.5 m`：

| 检查点 | 当前结果 |
| --- | ---: |
| Effective breakpoint | 210.0 m |
| LOS, d2D=10 m | 66.7610328085 dB |
| LOS, d2D=100 m | 85.3141891025 dB |
| LOS, d2D=210 m | 92.0554308623 dB |
| LOS, d2D=300 m | 98.2442606638 dB |
| NLOS, d2D=100 m | 104.6438320117 dB |
| LOS SF std | 4.0 dB |
| NLOS SF std | 7.82 dB |

InH，`fc=3500 MHz`、`hBS=3 m`、`hUT=1 m`：

| 检查点 | 当前结果 |
| --- | ---: |
| LOS, d3D=10 m | 60.5813608870 dB |
| NLOS, d3D=10 m | 69.1472943043 dB |
| NLOS, d2D=0 m, d3D=2 m | 48.4891798120 dB |
| LOS SF std | 3.0 dB |
| NLOS SF std | 8.03 dB |

UMi 100 m NLOS 示例：

```text
LOS reference:  85.31 dB
NLOS candidate: 104.64 dB
final NLOS:      max(85.31, 104.64) = 104.64 dB
```

### 6.4 Alignment

已经符合：

- Table 7.4.1-1 的 UMi 和 InH deterministic mean path-loss 公式。
- UMi effective height 和 breakpoint。
- NLOS `max(LOS, candidate)`。
- 3GPP SF standard-deviation metadata。
- MHz API 输入以及内部 GHz/Hz 转换。
- d2D/d3D/高度一致性检查。
- 适用范围外默认失败，debug 必须显式允许 extrapolation。

尚未包含：

- 随机 shadow-fading realization。
- spatially correlated shadow fading。
- O2I building penetration。
- material-loss combination。
- small-scale fading、TDL/CDL、Doppler。
- runtime `ChannelState` integration。

---

## 7. Expected Result 与 Current Result 对照

| 项目 | Regular result | Current result | 状态 |
| --- | --- | --- | --- |
| 地图坐标 | 可信米制坐标 | provisional X/Y scale | 部分符合 |
| 标定验证 | 真实 anchors 与误差 | 0 anchors | 未完成 |
| d2D/d3D | 物理米制距离 | 已实现 | 符合 |
| 链路分类 | indoor/outdoor、LOS/NLOS | map-aware deterministic result | 符合项目设计 |
| 场景选择 | 根据部署选择模型 | UMi/InH adapter 已实现；复杂链路 unsupported | baseline 符合 |
| Basic path loss | 3GPP deterministic mean PL | 已实现并验证 | 符合 |
| Shadow fading | SF realization，最好空间相关 | 只有 SF std metadata | 部分符合 |
| O2I penetration | 外墙、频率、室内深度 | 未实现 | 未完成 |
| Total path loss | basic PL + approved losses | 尚未组合 | 未完成 |
| Received power | Tx power + gains - losses | 新模型尚未接入 | 未完成 |
| SINR/CQI | 新 channel result 驱动 | 当前仍来自旧 baseline | 未完成 |
| Scheduler linkage | 使用新 CQI/BLER | 尚未接入 | 未完成 |
| MVP stability | 原路径继续运行 | 72/72 tests，旧 MVP 保留 | 符合 |

当前最准确的结论：

```text
Our result matches the expected deterministic 3GPP basic path-loss result,
but it is not yet the complete end-to-end channel result.
```

---

## 8. 测试文件和覆盖范围

### 8.1 Coordinate Calibration

文件：

```text
tests/radio/test_coordinate_calibration.py
```

当前 14 项测试，覆盖：

- X/Y anisotropic distance。
- Y-axis direction。
- 配置 extent 修改。
- provisional/confirmed 状态。
- confirmed anchor 数量和误差。
- invalid status/config。
- 2D/3D distance。
- unknown scene。
- legacy uniform scalar。

### 8.2 Geometry-Calibration Compatibility

文件：

```text
tests/radio/test_geometry_coordinate_calibration.py
```

当前 5 项测试，覆盖：

- X/Y scale adapter。
- default UE height。
- anisotropic crossing distance。
- legacy scalar fallback。
- no-calibration compatibility。

### 8.3 Propagation Geometry

文件：

```text
tests/radio/test_propagation_geometry.py
```

当前 17 项测试，覆盖：

- 六类 link classification。
- Bristol smoke cases。
- duplicate wall de-duplication。
- exterior/interior crossing order。
- blocking building semantics。
- portal by `wall_id`。
- portal intersection matching。
- closed/open/locked portal RF semantics。

### 8.4 3GPP Path Loss

文件：

```text
tests/radio/test_pathloss_3gpp.py
```

当前 23 项测试，覆盖：

- request validation。
- finite and positive numeric inputs。
- frequency conversion。
- d2D/d3D/height consistency。
- applicability error and explicit extrapolation。
- UMi fixed values and breakpoint continuity。
- UMi NLOS max guard。
- InH fixed values。
- InH short-distance NLOS max guard。
- SF metadata and formula IDs。

### 8.5 Stage 2 Debug Report

文件：

```text
tests/radio/test_pathloss_3gpp_debug.py
```

当前 2 项测试，覆盖 deterministic report 和 3GPP/FSPL 固定对比值。

### 8.6 Stage 3 Adapter

文件：

```text
tests/radio/test_pathloss_3gpp_adapter.py
```

当前 9 项测试，覆盖：

- outdoor LOS/NLOS 到 UMi。
- same-building indoor LOS/NLOS 到 InH。
- 缺少 meter distance。
- O2I/I2O/different-building unsupported。
- 频率和高度原样传递。
- Geometry/GnbSite ID 一致性。
- adapter 不修改 Geometry。

### 8.7 Bristol Dry Run

文件：

```text
tests/radio/test_pathloss_3gpp_bristol.py
```

当前 2 项测试，覆盖 supported/unsupported case、provisional calibration、
formula ID 和 baseline comparison。

### 8.8 当前测试总数

```text
Coordinate Calibration:             14
Geometry-Calibration Compatibility:  5
Propagation Geometry:               17
3GPP Path Loss:                     23
Stage 2 Debug Report:                2
Stage 3 Adapter:                     9
Bristol Dry Run:                     2
Total:                              72
```

最近复现结果：

```text
Ran 72 tests
OK
```

---

## 9. Debug 和复现脚本

### 9.1 全量测试

```powershell
cd D:\AI_RAN_SANBOX\RAN_3GPP
python -m unittest discover
```

预期摘要：

```text
Ran 72 tests
OK
```

### 9.2 分模块运行

```powershell
python -m unittest tests.radio.test_coordinate_calibration -v
python -m unittest tests.radio.test_geometry_coordinate_calibration -v
python -m unittest tests.radio.test_propagation_geometry -v
python -m unittest tests.radio.test_pathloss_3gpp -v
python -m unittest tests.radio.test_pathloss_3gpp_debug -v
python -m unittest tests.radio.test_pathloss_3gpp_adapter -v
python -m unittest tests.radio.test_pathloss_3gpp_bristol -v
```

### 9.3 Coordinate Calibration Debug

```powershell
python -m experiments.debug_coordinate_calibration `
  --scene bristol_topology `
  --pretty
```

检查：

```text
status = provisional
physical_extent_m = 300 x 400
scale_x = 0.15
scale_y = 0.20
anchor_count = 0
warning = provisional_calibration_has_no_reference_anchors
```

指定样例位置和高度：

```powershell
python -m experiments.debug_coordinate_calibration `
  --x 520 `
  --y 280 `
  --gnb-height-m 10 `
  --ue-height-m 1.5 `
  --pretty
```

### 9.4 Propagation Geometry Debug

无 calibration，验证旧行为：

```powershell
python -m experiments.debug_propagation_geometry
```

显式 opt in provisional calibration：

```powershell
python -m experiments.debug_propagation_geometry `
  --with-calibration `
  --gnb-height-m 10
```

检查以下 case：

```text
outdoor_green
student_union_center
gym_center
outdoor_east_of_student_union
```

### 9.5 Standalone 3GPP/FSPL Comparison

```powershell
python -m experiments.debug_3gpp_pathloss `
  --scenario umi_street_canyon `
  --los-state nlos `
  --frequency-mhz 3500 `
  --distance-2d-m 100 `
  --bs-height-m 10 `
  --ut-height-m 1.5 `
  --pretty
```

### 9.6 Bristol Stage 3 Dry Run

```powershell
python -m experiments.debug_bristol_3gpp_pathloss `
  --gnb-height-m 10 `
  --pretty
```

预期：

```text
outdoor_green:                    supported, UMi LOS
outdoor_east_of_student_union:    supported, UMi NLOS
student_union_center:             unsupported, no path-loss value
gym_center:                       unsupported, no path-loss value
```

### 9.7 MVP Regression

```powershell
python -m simulation.main `
  -s bristol_topology `
  --ran-mvp `
  --ran-mvp-mode aggregate `
  --ticks 10
```

最近结果：

```text
delivered=104857600
undelivered=0
loss_rate=0.000000
```

这验证的是新增模块没有改变现有 MVP runtime；它不代表 3GPP 模型已经接入。

### 9.8 HTML Geometry Report

以下可视化脚本和报告目前只存在于原工作树：

```text
D:\AI_RAN_SANBOX\RAN\experiments\generate_geometry_test_report.py
D:\AI_RAN_SANBOX\RAN\reports\propagation_geometry_test_report.html
```

它们没有包含在当前 `zhiqian/3gpp` 分支中，也不应在汇报时描述为已推送
artifact。

---

## 10. Stage 3 完成状态与剩余工作

### 已完成：Read-only Geometry-to-3GPP Adapter

目标：

```text
PropagationGeometry + GnbSite + heights
→ PathLossRequest
```

第一版映射：

```text
outdoor_los                    → UMi LOS
outdoor_nlos                   → UMi NLOS
indoor_same_building + LOS     → InH LOS
indoor_same_building + NLOS    → InH NLOS
```

以下链路第一版返回 unsupported/fallback：

```text
outdoor_to_indoor
indoor_to_outdoor
indoor_different_building
missing meter distance
unapproved scenario
```

### 已完成：Standalone Comparison

对每个 Bristol case 输出：

```text
calibration status
geometry link type
LOS/NLOS state
d2D/d3D
selected model
3GPP formula ID
3GPP basic path loss
baseline path loss
fallback reason
```

### 下一步：Optional Runtime Integration

只有经过团队 review 后才修改 `channel.py`。

必须：

- 保留现有调用方式。
- 保留现有 `ChannelState` 字段。
- 保留 baseline fallback。
- unsupported/out-of-range 时明确 fallback。
- 重新运行全部 tests 和 MVP。

### 后续研究，不是 Stage 3 blocker

```text
confirmed real-distance anchors
O2I material penetration
spatial shadow fading
interference field
small-scale fading
TDL/CDL and Doppler
beamforming channel matrix
CKM
```

---

## 11. 汇报结论

推荐表述：

```text
The current implementation has completed the deterministic component-level
baseline. Coordinate calibration provides physical distances, propagation
geometry provides map-aware link context, and the 3GPP module provides
validated UMi and InH mean path loss.

The current 3GPP numerical results align with Table 7.4.1-1, and the read-only
Geometry adapter is complete for approved UMi and InH links. O2I penetration,
shadow-fading realization and runtime link-budget integration remain separate
later stages.

The existing MVP remains runnable and all 72 repository tests pass.
```

不应表述为：

```text
The complete 3GPP channel model is finished.
```

应表述为：

```text
The deterministic 3GPP basic path-loss core is implemented and validated.
```

---

## 12. 相关文档

```text
docs/coordinate_calibration_handoff_zh.md
docs/propagation_geometry_handoff_zh.md
docs/3gpp_pathloss_design_zh.md
docs/3gpp_pathloss_implementation_plan_zh.md
docs/3gpp_pathloss_stage1_report_zh.md
```
