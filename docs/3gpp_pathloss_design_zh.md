# 3GPP 大尺度路径损耗模块设计

## 1. 文档状态

| 项目 | 内容 |
| --- | --- |
| 分支 | `zhiqian/3gpp` |
| 模块所有者 | Channel team / Zhiqian |
| 状态 | Stage 3 已实现并通过测试，尚未接入 runtime |
| 主要标准 | 3GPP TR 38.901 V19.4.0，Release 19 |
| 第一阶段场景 | UMi Street Canyon、InH Office |
| 第一阶段输出 | 确定性平均 path loss 和 shadow-fading 标准差 |
| Runtime 接入 | 第一阶段不接入 `channel.py` |

本文档只设计 3GPP large-scale path-loss 模块。它不修改
`ChannelState`、scheduler、PHY、Geometry、Coordinate Calibration 或当前 MVP
执行路径。

---

## 2. 目标

当前 MVP 在 `ran/radio/channel.py` 中使用一条简化公式：

```text
地图坐标直线距离
+ 原始墙体 penetration_loss_db
→ total_path_loss_db
```

新模块的目标是：

1. 使用 3GPP TR 38.901 的 UMi Street Canyon 和 InH Office path-loss
   公式。
2. 强制区分地图单位和物理米制单位。
3. 明确区分 LOS、NLOS、场景、公式分支和适用范围。
4. 为后续 Geometry、O2I、shadow fading 和 `ChannelState` 接入提供稳定、
   可测试的内部接口。
5. 保留现有 channel 计算作为 fallback，在独立验证完成前不替换 runtime。

### 2.1 第一阶段不做

- 不修改 `ran/radio/channel.py`。
- 不修改 `ChannelState` 或 scheduler-facing contract。
- 不实现随机 shadow fading realization。
- 不实现 small-scale fading、TDL/CDL、delay spread 或 Doppler。
- 不实现 MIMO、beamforming、OFDM、PRB、MCS 或 CQI。
- 不实现材料 penetration loss。
- 不实现完整 O2I、indoor-to-outdoor 或跨建筑组合模型。
- 不把未经确认的地图单位当作米。

---

## 3. 标准依据

主要依据是
[ETSI / 3GPP TR 38.901 V19.4.0](https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf)：

| 标准位置 | 使用内容 |
| --- | --- |
| Clause 7.2 | UMi 和 Indoor-office 场景参数 |
| Clause 7.4.1 / Table 7.4.1-1 | UMi、InH LOS/NLOS path-loss 公式和 shadow-fading 标准差 |
| Clause 7.4.1 Note 1 | UMi effective breakpoint distance |
| Clause 7.4.1 Note 2、6 | 频率范围和公式单位 |
| Clause 7.4.3 | 后续 O2I building penetration 结构 |

实现时必须在源码 docstring 和测试说明中固定版本与表格位置，避免以后只写
“参考 3GPP”却无法确认公式来自哪个版本。

---

## 4. 术语和单位

| 符号 | 含义 | API 单位 |
| --- | --- | --- |
| `d2D` | gNB/BS 与 UE/UT 的水平距离 | m |
| `d3D` | 包含高度差的三维距离 | m |
| `hBS` | gNB/BS 天线高度 | m |
| `hUT` | UE/UT 天线高度 | m |
| `fc` | 载波中心频率 | API 使用 MHz |
| `PL` | 平均大尺度路径损耗 | dB |
| `SF` | shadow fading 的标准差 | dB |
| `dBP'` | UMi effective breakpoint distance | m |

### 4.1 频率转换规则

现有 `GnbSite` 使用 `carrier_freq_mhz`，所以新模块 API 也使用 MHz：

```text
fc_GHz = carrier_frequency_mhz / 1000
fc_Hz  = carrier_frequency_mhz × 1,000,000
```

- Table 7.4.1-1 的 path-loss 公式使用 `fc_GHz`。
- breakpoint 公式使用 `fc_Hz`。
- 调用者不得预先传入 GHz。

### 4.2 距离来源规则

`d2D` 和 `d3D` 只能来自：

```text
Coordinate Calibration
→ CoordinateCalibrationView
→ PropagationGeometry.distance.distance_2d_m / distance_3d_m
```

如果 Geometry 的 meter 字段为 `None`，3GPP 模块不得回退使用
`map_distance_units`。

### 4.3 上下行方向

大尺度 path loss 在本项目中按链路互易处理：

- 下行和上行使用相同的平均 path loss。
- `hBS` 始终表示 gNB 天线高度。
- `hUT` 始终表示 UE 天线高度。
- 上行时不得因为 UE 是发射端就交换 `hBS` 和 `hUT`。

发射功率、接收机噪声和干扰属于后续 link-budget/channel 阶段，不进入本
path-loss 公式核心。

---

## 5. 模块边界

建议新增：

```text
ran/radio/pathloss_3gpp.py
tests/radio/test_pathloss_3gpp.py
experiments/debug_3gpp_pathloss.py      # 第二个小提交再增加
```

第一阶段的公式核心不直接 import：

- `MapService`
- `PropagationGeometry`
- `CoordinateCalibrationResult`
- `ChannelState`
- scheduler 或 PHY 类型

这样可以用纯数值输入独立验证标准公式。

### 5.1 数据流

```text
Coordinate Calibration
        │
        ▼
physical d2D / d3D / heights
        │
Propagation Geometry
        │
        ├── link_type
        └── los_state
        │
        ▼
3GPP request adapter（后续阶段）
        │
        ▼
pathloss_3gpp.py
        │
        ├── mean_path_loss_db
        ├── shadow_fading_std_db
        ├── formula_id
        └── applicability metadata
```

公式核心只负责最后一格，不负责地图分析或坐标拟合。

---

## 6. 第一阶段接口设计

以下接口是新模块内部 contract，不是共享 `ChannelState`。

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

### 6.1 固定字符串

第一阶段只接受：

```text
scenario:
  umi_street_canyon
  inh_office

los_state:
  los
  nlos
```

`formula_id` 建议使用：

```text
3gpp_38_901_v19_4_0_umi_los_pl1
3gpp_38_901_v19_4_0_umi_los_pl2
3gpp_38_901_v19_4_0_umi_nlos
3gpp_38_901_v19_4_0_inh_los
3gpp_38_901_v19_4_0_inh_nlos
```

这些字符串使 debug report 能明确说明实际使用了哪个公式分支。

NLOS 结果同时返回 LOS reference 和 NLOS candidate，便于测试和 debug
确认最终结果确实执行了 `max(LOS, candidate)`。LOS 结果的
`nlos_candidate_path_loss_db` 为 `None`。

---

## 7. 公式设计

所有 `log` 均为 `log10`。

### 7.1 UMi effective breakpoint

UMi 使用：

```text
hBS' = hBS - hE
hUT' = hUT - hE
hE   = 1.0 m

dBP' = 4 × hBS' × hUT' × fc_Hz / c
c    = 3.0 × 10^8 m/s
```

要求：

```text
hBS > 1.0 m
hUT > 1.0 m
```

否则 effective height 非正，必须拒绝计算。

### 7.2 UMi Street Canyon LOS

当：

```text
10 m ≤ d2D ≤ dBP'
```

使用：

```text
PL1 = 32.4
    + 21 × log10(d3D)
    + 20 × log10(fc_GHz)
```

当：

```text
dBP' < d2D ≤ 5000 m
```

使用：

```text
PL2 = 32.4
    + 40 × log10(d3D)
    + 20 × log10(fc_GHz)
    - 9.5 × log10(dBP'^2 + (hBS - hUT)^2)
```

返回的 shadow-fading 标准差：

```text
SF = 4 dB
```

### 7.3 UMi Street Canyon NLOS

先计算同一输入下的 UMi LOS：

```text
PL_UMi_NLOS_candidate =
      35.3 × log10(d3D)
    + 22.4
    + 21.3 × log10(fc_GHz)
    - 0.3 × (hUT - 1.5)
```

最终：

```text
PL_UMi_NLOS = max(
    PL_UMi_LOS,
    PL_UMi_NLOS_candidate,
)
```

返回：

```text
SF = 7.82 dB
```

不能只返回 candidate；`max(LOS, candidate)` 是标准公式的一部分。

### 7.4 InH Office LOS

```text
PL_InH_LOS =
      32.4
    + 17.3 × log10(d3D)
    + 20 × log10(fc_GHz)

SF = 3 dB
```

适用距离：

```text
1 m ≤ d3D ≤ 150 m
```

### 7.5 InH Office NLOS

```text
PL_InH_NLOS_candidate =
      38.3 × log10(d3D)
    + 17.30
    + 24.9 × log10(fc_GHz)

PL_InH_NLOS = max(
    PL_InH_LOS,
    PL_InH_NLOS_candidate,
)

SF = 8.03 dB
```

第一阶段使用 Table 7.4.1-1 的主 NLOS 公式，不使用表中的 optional
InH-NLOS 公式。

---

## 8. 适用范围和错误处理

### 8.1 永远拒绝的输入

以下输入无论 `allow_extrapolation` 是什么都应抛出 `ValueError`：

- 任意输入是 `NaN` 或 infinity。
- `carrier_frequency_mhz <= 0`。
- `distance_2d_m < 0`。
- `distance_3d_m <= 0`。
- `distance_3d_m < distance_2d_m`。
- 高度不是正数。
- UMi effective height 非正。
- 未知 `scenario` 或 `los_state`。

### 8.2 2D/3D 一致性

应验证：

```text
expected_d3D = sqrt(d2D^2 + (hBS - hUT)^2)
```

允许误差：

```text
max(0.05 m, expected_d3D × 1e-4)
```

超过误差说明调用者可能混用了坐标、单位或高度，应抛出输入错误。

### 8.3 标准适用范围

| 场景 | 频率 | 距离 | 参考高度 |
| --- | --- | --- | --- |
| UMi | `0.5 < fc_GHz < 100` | `10 ≤ d2D ≤ 5000 m` | `hBS=10 m`，`1.5 ≤ hUT ≤ 22.5 m` |
| InH | `0.5 < fc_GHz < 100` | `1 ≤ d3D ≤ 150 m` | Indoor-office 参考配置 `hBS=3 m`、`hUT=1 m` |

默认：

```python
allow_extrapolation=False
```

超出公式距离、频率或 UT 高度范围时，应抛出
`PathLossApplicabilityError`，不能静默 clamp。

参考高度与标准默认值不一致时：

- 仍可计算公式；
- 在 `warnings` 中写入 `non_reference_height`；
- debug report 必须显示；
- 不得称为完整 3GPP reference configuration。

只有显式设置：

```python
allow_extrapolation=True
```

才允许在公式适用范围外产生 debug 结果，同时必须：

```text
is_extrapolated = True
warnings 包含具体越界原因
```

该选项不得成为未来 runtime integration 的默认值。

---

## 9. Geometry 到场景的映射

### 9.1 第一阶段允许自动映射

| Geometry `link_type` | Geometry LOS | 3GPP 场景 | 状态 |
| --- | --- | --- | --- |
| `outdoor_los` | `los` | UMi Street Canyon LOS | 支持 |
| `outdoor_nlos` | `nlos` | UMi Street Canyon NLOS | 支持 |
| `indoor_same_building` | `los` | InH Office LOS | 支持 |
| `indoor_same_building` | `nlos` | InH Office NLOS | 支持 |

这里采用 Geometry 确定的 LOS/NLOS，而不执行 TR 38.901 Clause 7.4.2 的
LOS probability 随机抽样。这是本项目利用地图几何先验的明确简化，报告中
应标注为 `geometry_determined`，不能描述成完整复现了 3GPP 的随机场景生成。

### 9.2 第一阶段拒绝自动映射

| Geometry `link_type` | 原因 |
| --- | --- |
| `outdoor_to_indoor` | 需要 outdoor basic PL、外墙 `PLtw`、室内深度 `PLin` 和 penetration 随机项 |
| `indoor_to_outdoor` | 室内 gNB 不等同于标准 outdoor BS 的 O2I 参考场景 |
| `indoor_different_building` | 不是单个 InH 或 UMi 公式，需要明确组合边界 |

特别注意：

```text
outdoor_to_indoor 的 geometry.los_state == nlos
```

不能直接解释成“使用 UMi NLOS”。它只说明整条地图链路存在有效穿透面。
O2I 的 outdoor basic path 是 LOS 还是 NLOS，需要单独的 outdoor-segment
判断或明确的项目假设。第一阶段不得猜测。

---

## 10. O2I 后续设计边界

TR 38.901 Clause 7.4.3 的结构是：

```text
PL_total =
    PL_basic_outdoor
  + PL_through_external_wall
  + PL_indoor_depth
  + penetration_random_term
```

Geometry 已经能提供：

- `outdoor_distance_m`
- `indoor_distance_m`
- 外墙与内墙 crossing
- material name
- blocking building IDs

但尚未提供：

- outdoor segment 独立 LOS/NLOS 状态
- 外墙材料比例
- 入射角修正
- 标准 high-loss / low-loss building profile
- penetration randomness policy

因此 O2I 应是后续独立阶段，不能在第一阶段把现有
`penetration_loss_db` 直接加到 3GPP O2I 公式上，否则容易双重计算。

---

## 11. Shadow fading 策略

第一阶段只返回：

```text
shadow_fading_std_db
```

不生成：

```text
shadow_fading_db ~ Normal(0, SF^2)
```

原因：

1. 随机项需要 seed 和可复现策略。
2. 移动 UE 的 shadow fading 应考虑 spatial correlation。
3. CKM 阶段可能以位置先验替代独立随机采样。
4. 公式单元测试应先验证 deterministic mean path loss。

后续若加入随机项，应采用新的显式组件，不能隐藏在
`estimate_path_loss_3gpp()` 内部。

---

## 12. 测试设计

### 12.1 固定测试配置

室外 UMi：

```text
fc  = 3500 MHz
hBS = 10 m
hUT = 1.5 m
hE  = 1 m
dBP' = 210 m
```

室内 InH：

```text
fc  = 3500 MHz
hBS = 3 m
hUT = 1 m
```

### 12.2 公式参考值

实现测试使用独立固定数值，不在测试中复制生产函数。

| 测试 | 输入 | 预期 path loss |
| --- | --- | ---: |
| UMi LOS PL1 | `d2D=10 m`, `d3D≈13.124405 m` | `66.761033 dB` |
| UMi LOS PL1 | `d2D=100 m`, `d3D≈100.360600 m` | `85.314189 dB` |
| UMi LOS breakpoint | `d2D=210 m` | `92.055431 dB` |
| UMi LOS PL2 | `d2D=300 m`, `d3D≈300.120393 m` | `98.244261 dB` |
| UMi NLOS | `d2D=100 m` | `104.643832 dB` |
| InH LOS | `d3D=10 m` | `60.581361 dB` |
| InH NLOS | `d3D=10 m` | `69.147294 dB` |
| InH NLOS max guard | `d2D=0 m`, `d3D=2 m` | `48.489180 dB` |

建议浮点断言：

```python
self.assertAlmostEqual(actual, expected, places=6)
```

### 12.3 必须覆盖的测试类别

公式：

1. UMi breakpoint 正确计算为 `210 m`。
2. UMi LOS 在 breakpoint 前选择 PL1。
3. UMi LOS 在 breakpoint 后选择 PL2。
4. PL1 和 PL2 在 breakpoint 连续。
5. UMi NLOS 使用 `max(LOS, candidate)`。
6. InH LOS 公式正确。
7. InH NLOS 使用 `max(LOS, candidate)`。
8. 各场景返回正确 SF 标准差和 `formula_id`。

单位与输入：

9. `3500 MHz` 正确转换为 `3.5 GHz`。
10. 2D/3D/高度不一致时拒绝计算。
11. `None` meter distance 不允许进入 adapter。
12. 不允许把 map distance 作为 meter fallback。
13. NaN、infinity、零频率、负距离全部拒绝。

适用范围：

14. UMi `d2D < 10 m` 默认拒绝。
15. InH `d3D > 150 m` 默认拒绝。
16. 超范围且 `allow_extrapolation=True` 时标记 extrapolated。
17. 非参考高度产生 warning。

回归：

18. 新模块存在时，原 36 项测试继续通过。
19. 10-tick MVP 输出保持不变，因为第一阶段尚未接入 runtime。

---

## 13. 分阶段提交计划

### PR/Commit 1：公式核心

```text
新增 pathloss_3gpp.py
新增 test_pathloss_3gpp.py
实现 UMi LOS/NLOS
实现 InH LOS/NLOS
实现输入与 applicability validation
不接 Geometry
不接 channel.py
```

### PR/Commit 2：debug adapter

```text
新增 geometry → PathLossRequest 的显式 adapter
新增 debug_3gpp_pathloss.py
输出 baseline FSPL 与 3GPP mean PL 对比
meter 字段为 None 时明确失败
仍不修改 channel.py
```

### PR/Commit 3：O2I 设计与材料先验

```text
明确 outdoor segment LOS/NLOS
定义 low-loss/high-loss building profile
定义外墙材料与入射角
避免与 raw wall loss 双重计数
```

### PR/Commit 4：shadow fading / CKM

```text
定义 deterministic seed
定义 spatial correlation
定义 CKM prior 与随机 residual 的关系
```

### PR/Commit 5：runtime integration

必须经过团队确认后才可以：

```text
给 estimate_channel 增加可选 model selector
保留现有 baseline fallback
保持 ChannelState 字段不变
运行 scheduler/PHY/MVP 全回归
```

---

## 14. 接口稳定性检查

第一阶段预期答案：

| 问题 | 答案 |
| --- | --- |
| 是否修改共享 contract？ | 否 |
| 是否修改 `ChannelState`？ | 否 |
| 是否修改 scheduler/PHY？ | 否 |
| 是否修改 Geometry/Calibration？ | 否 |
| 是否替换当前 `estimate_channel()`？ | 否 |
| 是否保留 MVP baseline？ | 是 |
| 是否允许 map units 进入 3GPP 公式？ | 否 |
| 是否实现 O2I 或随机 fading？ | 否 |

---

## 15. 待团队确认

开始 O2I 或 runtime integration 前必须确认：

1. gNB 实际高度是否固定为 `10 m`。
2. indoor gNB 是否存在；如果存在，如何定义 InH 与 I2O。
3. Bristol 场景采用 UMi Street Canyon 是否作为 Capstone 的统一室外假设。
4. O2I 的 outdoor segment LOS/NLOS 如何获取。
5. 建筑采用 low-loss、high-loss，还是地图 material profile。
6. shadow fading 是独立随机、spatially correlated，还是由 CKM 提供先验。
7. 未来是增加可选 channel model selector，还是仅提供离线 comparison。

---

## 16. 第一阶段验收标准

只有同时满足以下条件，公式核心才算完成：

- 所有固定参考值测试通过。
- breakpoint 前后连续性通过。
- NLOS `max` 规则通过。
- 所有输入单位和越界测试通过。
- 不存在 map-unit fallback。
- 原有 36 项测试通过。
- 10-tick MVP 通过且输出结构不变。
- 没有修改共享接口。
- 源码和测试明确写出标准版本及 clause。

---

## 17. 参考资料

1. [3GPP Specification 38.901 portal](https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx?specificationId=3173)
2. [ETSI TR 138 901 V19.4.0 PDF](https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf)
3. 项目 Geometry handoff：`docs/propagation_geometry_handoff_zh.md`
4. 项目 Coordinate Calibration handoff：`docs/coordinate_calibration_handoff_zh.md`
5. 当前 baseline channel：`ran/radio/channel.py`
