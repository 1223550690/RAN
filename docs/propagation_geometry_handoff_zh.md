# 传播几何分析 Handoff

## 总结

这份文档说明 RAN MVP 传播几何分析模块。
本次实现是“新增模块 + debug first”的小步提交：

- 新增模块：`ran/radio/geometry.py`
- 新增调试入口：`experiments/debug_propagation_geometry.py`
- 不修改 `ran/radio/channel.py`
- 不修改 `ChannelState` 或其他共享 contract
- 坐标标定在独立模块中实现，不嵌入本模块
- 不修改 scheduler、protocol、path loss、CKM、beamforming、metrics 或 editor schema

这个模块的目标是：基于 2D 地图，给未来信道模型或 path-loss 模型提供几何证据。
它不是完整的信道模型，也不会替换当前 MVP 的 `estimate_channel()`。

## 责任边界

当前信道组边界：

- 坐标标定和传播几何分析。
- 坐标标定保持为独立模块，使用独立配置和测试。
- 本模块可以读取只读坐标标定结果，但不能在内部推断或维护 map unit 到 meter 的比例。
- 其他组不要把这个模块理解成 scheduler、QoS、RLC/PDCP 或最终 path-loss 实现。

## 主要接口

```python
from ran.contracts import Position
from ran.radio.geometry import analyze_propagation_geometry, geometry_to_report

geometry = analyze_propagation_geometry(
    scene=scene,
    receiver_position=Position(520.0, 280.0),
    gnb=gnb,
)

report = geometry_to_report(geometry)
```

### `analyze_propagation_geometry(...)`

输入：

- `scene`：当前地图场景，一般来自 `structure.scene_registry.build_scene`。
- `receiver_position`：UE 或接收端位置，类型为 `Position(x, y)`。
- `gnb`：基站信息，类型为 `GnbSite`。
- `coordinate_view`：可选，只读坐标标定视图；当前不需要传。
- `map_service`：可选，用于测试时注入 `MapService`。

输出：

- `PropagationGeometry`，其中包含链路类型、LOS/NLOS 状态、距离、墙体/表面穿越、portal 穿越、遮挡建筑等信息。

### `geometry_to_report(...)`

把 `PropagationGeometry` 转成适合 JSON 输出的 `dict`，方便 debug、日志记录和 code review。

## 实现流程

1. 从 gNB 坐标到 UE 坐标生成一条二维直线。
2. 计算 map unit 距离；如果没有坐标标定，meter 字段保持 `None`。
3. 用 `MapService.get_area_at(...)` 查询 gNB 和 UE 分别在哪个区域。
4. 判断两端是 indoor 还是 outdoor，并识别 UE 所在建筑。
5. 用 `MapService.get_walls_between(...)` 查询直线穿过的墙体和建筑边界。
6. 把 wall intersection 标准化为 `PropagationSurfaceCrossing`。
7. 去重：同一位置如果同时有自动生成的 area boundary 和手工定义的 wall，优先保留手工 wall。
8. 从 scene 和 area 中收集和无线传播相关的 portal。
9. 如果直线穿过 open portal，并且 portal 匹配某段墙，则把该墙标记为无效穿墙，`ignored_reason="open_portal"`。
10. 分类链路类型：

- `outdoor_los`
- `outdoor_nlos`
- `outdoor_to_indoor`
- `indoor_to_outdoor`
- `indoor_same_building`
- `indoor_different_building`

11. 区分目标建筑和非目标遮挡建筑。
12. 计算 `los_state`。
13. 拆分 outdoor 和 indoor 的 map unit 距离。
14. 返回结构化几何结果，或转为 JSON report。

## 重要输出字段

### 链路分类

- `link_type`：粗粒度传播场景，例如 `outdoor_to_indoor`。
- `los_state`：`los` 或 `nlos`。
- `blocking_building_ids`：遮挡 outdoor 路径的非目标建筑。这些建筑不应该直接当作目标建筑的材料墙损耗来累加。

### 距离

- `map_distance_units`：始终存在，单位是地图坐标单位。
- `distance_2d_m`：没有坐标标定时为 `None`。
- `distance_3d_m`：没有坐标标定和 gNB/UE 高度时为 `None`。
- `outdoor_distance_map_units`：链路中 outdoor 部分的 map unit 距离。
- `indoor_distance_map_units`：链路中 indoor 部分的 map unit 距离。
- `outdoor_distance_m` 和 `indoor_distance_m`：没有坐标标定时为 `None`。

### 穿越对象

- `all_surface_crossings`：原始 debug 信息，包括重复墙、open portal 忽略的墙、遮挡建筑中的墙。
- `effective_surface_crossings`：当前几何上下文中真正算作有效材料表面的 crossing。
- `exterior_surfaces_crossed`：有效的外墙或建筑边界 crossing。
- `interior_walls_crossed`：有效的室内墙 crossing。
- `portals_crossed`：gNB 到 UE 直线穿过的传播相关 portal。

## Portal 语义

`Portal.open=True` 当前被解释为几何开口。如果无线直线穿过这个 open portal，并且它匹配某段墙，那么这段墙不会计入有效材料穿透。

`Portal.locked=True` 当前只保留为元数据，不增加无线损耗。现在地图里很多门同时是 `locked=True` 和 `open=True`，这里更像是“编辑器中锁定/通行受控”，不是“关门导致 RF 衰减”。

如果以后需要模拟门、玻璃门、门禁门等材料损耗，应该在 material/path-loss 模型里单独实现，不应该混进这次几何 PR。

## 遮挡建筑语义

对于 `outdoor_to_indoor` 链路，目标建筑是 UE 所在建筑。
如果 gNB 到 UE 的直线中间穿过其他建筑，这些建筑会被记录到 `blocking_building_ids`，并把相关 crossing 标记为 `ignored_reason="blocking_building_nlos_classification"`。

这样做的原因是：信号并不是真的进入非目标建筑再逐个房间累加损耗。更合理的 MVP 表达是：中间建筑让这条链路变成 NLOS，而不是把中间建筑内部所有墙都算成目标链路材料损耗。

## 调试命令

在 repo 根目录运行：

```powershell
python -m experiments.debug_propagation_geometry --pretty
```

自定义 UE 坐标：

```powershell
python -m experiments.debug_propagation_geometry --x 520 --y 280 --pretty
```

## 当前 Smoke Test 预期

debug 脚本默认覆盖四个案例：

| Case                            | 预期 link type        | 预期 LOS state | 说明                             |
| ------------------------------- | ------------------- | ------------ | ------------------------------ |
| `outdoor_green`                 | `outdoor_los`       | `los`        | 不穿墙                            |
| `student_union_center`          | `outdoor_to_indoor` | `nlos`       | 进入 Student Union 并穿过室内墙        |
| `gym_center`                    | `outdoor_to_indoor` | `nlos`       | 目标 Gym 外墙，同时被 Student Union 遮挡 |
| `outdoor_east_of_student_union` | `outdoor_nlos`      | `nlos`       | outdoor UE 被 Student Union 遮挡  |

handoff 前使用过的验证命令：

```powershell
python -m unittest tests.radio.test_geometry_coordinate_calibration tests.radio.test_coordinate_calibration
python -m experiments.debug_propagation_geometry
python -m experiments.debug_propagation_geometry --with-calibration --gnb-height-m 10
```

## 后续集成建议

这个分支不会把几何结果接入 `estimate_channel()`。
后续如果要集成进信道模型，建议：

1. 保留当前 raw wall-loss 行为作为 fallback。
2. 不要直接修改 `ChannelState`，除非团队明确同意。
3. 如果需要新增共享字段，优先使用有默认值的 optional 字段。
4. 把 geometry output 当成 path-loss 分类证据，而不是完整 channel model。
5. provisional meter 距离只用于 debug，真实锚点确认后才能作为物理模型输入。

## 已知限制

- 坐标标定仍由独立模块实现；geometry 只消费适配后的只读 view。
- 没有 calibration view 时，meter 距离字段为 `None`。
- 已有兼容性 unittest 覆盖无标定、旧 scalar、非等比例 X/Y、高度、墙体交点和 O2I 距离拆分。
- 没有 portal material loss。
- 门的 `locked` 状态不会影响无线传播。
- 如果未来 scene 把 portal 直接挂在 child area 上，child-area portal 坐标假设需要重新 review。
- 本模块不实现 3GPP path loss、shadow fading、fast fading、MIMO、OFDM、scheduler feedback 或 CQI 变化。

## 坐标标定兼容接口

`CoordinateCalibrationView` 保留原来的三个字段及其顺序：

```python
meters_per_map_unit
gnb_height_m
ue_height_m
```

并在末尾追加两个可选字段：

```python
meters_per_map_unit_x
meters_per_map_unit_y
```

换算优先级如下：

1. X/Y 比例都存在时，先分别转换 `dx` 和 `dy`，再计算非等比例物理距离。
2. 否则回退到原有 `meters_per_map_unit` 单比例路径。
3. 两种标定都没有时，所有 meter 字段继续为 `None`。

从独立标定模块接入时，使用：

```python
from ran.radio.coordinate_calibration import load_coordinate_calibration
from ran.radio.geometry import coordinate_view_from_calibration

calibration = load_coordinate_calibration("bristol_topology")
coordinate_view = coordinate_view_from_calibration(
    calibration,
    gnb_height_m=10.0,
)
```

几何模块不拟合、不推断也不保存比例，只消费这个只读 view。墙体和 portal
交点使用起点到实际交点的 X/Y 向量计算物理距离。indoor/outdoor 是同一条
gNB 到 UE 直线的子距离，因此按物理总距离的比例拆分，两者之和应等于
`distance_2d_m`（浮点误差除外）。

## 坐标兼容测试步骤

在 repo 根目录运行：

```powershell
python -m unittest tests.radio.test_geometry_coordinate_calibration tests.radio.test_coordinate_calibration
```

测试按以下步骤检查：

1. 不传标定时，meter 字段保持 `None`。
2. 使用旧的 positional scalar view，确认旧结果不变。
3. 使用 `scale_x=0.15`、`scale_y=0.20`，确认 `(100, 100)` 的地图差值换算为 `25 m`。
4. 从 `CoordinateCalibrationResult` 构造 view，确认默认 UE 高度和显式 gNB 高度覆盖。
5. 检查非等比例 wall crossing 和 O2I indoor/outdoor 距离，并确认子距离之和等于 `distance_2d_m`。

对比无标定和显式标定 debug：

```powershell
python -m experiments.debug_propagation_geometry
python -m experiments.debug_propagation_geometry --with-calibration --gnb-height-m 10
```

第一个命令必须保留旧行为。第二个命令明确 opt in 当前 provisional 标定，
用于 debug，不代表坐标已经通过真实锚点确认。

## PR Review Checklist

- 现有 MVP 是否还能运行？
- 是否改变了共享接口？预期答案：没有。
- 是否删除或重命名了字段？预期答案：没有。
- 是否修改了 `channel.py` 或 `ChannelState`？预期答案：没有。
- meter 字段是否清楚说明为 optional 且当前可能为 `None`？
- blocking building 是否和有效目标建筑墙体 crossing 分开？
- portal 假设是否已经在文档里说明？

 
