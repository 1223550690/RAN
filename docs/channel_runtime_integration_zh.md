# 信道 runtime 全链路接入说明

## 当前状态

`estimate_channel()` 已接通以下链路：

```text
地图坐标
  -> coordinate_calibration（map unit -> metre）
  -> propagation geometry（LOS/NLOS、墙体、室内外距离）
  -> 3GPP UMi/InH 或 Stage 4B O2I
  -> ChannelState
  -> scheduler / PHY
```

原有 `estimate_channel()` 签名和旧 `ChannelState` 字段语义保持不变。新增字段均有默认值，未配置场景、缺少高度、缺少建筑 profile、不支持的几何链路或超出模型适用范围时，使用 legacy path-loss fallback。

## runtime 模式

模式由 `configs/ran/channel_model.json` 的场景配置控制：

- `legacy`：不执行新链路，只使用原模型。
- `shadow`：执行完整新链路并写入 `evaluated_*` 诊断字段，但 scheduler/PHY 仍使用 legacy loss。这是 Bristol 当前默认值。
- `3gpp_preferred`：支持的链路使用 3GPP loss，其他链路使用 legacy fallback。

当前 Bristol 标定仍为 `provisional`。安全默认要求 active 模式只能使用 confirmed 标定，所以只把 `mode` 改成 `3gpp_preferred` 时会回退。工程试验若要显式接受 provisional 标定，需要同时将 `require_confirmed_calibration_when_active` 设为 `false`。

## 坐标标定决策

Bristol 地图边界为 2000 × 2000 map units，物理范围暂定为 275 m × 275 m，即 x/y 都使用 0.1375 m/map-unit。保持统一尺度是为了避免地图形状、射线方向、建筑相对位置和室内深度因 x/y 不同缩放而失真。

目前记录的参照为：

| 参照 | 定义 | 275 m 统一尺度下的估算 | 用途 |
|---|---|---:|---|
| 110 m | 左侧顶部路口/道路端点到左侧第二个 junction 拐点 | 109.36 m | 待补精确 map 端点后验证 |
| 约 236 m | 顶部参照 | 231.69 m | 待补精确 map 端点后验证 |
| 362.95 m | 与 110 m 相同起点，到 220 m 终点延长线与最右 junction 延长线交点 | 364.42 m | 待补精确 map 端点后验证 |
| 220 m | 110 m 终点到左下道路终点 | 当前图形仅约 168–175 m | schematic-map known deviation，不参与拟合 |

前三个参照支持约 275 m 的统一尺度。220 m 参照与当前示意地图局部几何明显不一致，因此不能通过 x/y 非等比例缩放强行拟合；如果它必须严格成立，应确认端点或重绘/延长道路。精确端点坐标尚未确认，所以配置只记录语义和预期残差，不伪造 `anchors`。拿到端点后应写入 `anchors`，重新计算 residual，并在满足 confirmed 验收规则后提升标定状态。

## 高度和 O2I 预设

3GPP 路损中的 `bs_height_m` 和 `ut_height_m` 是天线相对本地地面的高度，不是地图 x/y，也不是建筑层数。正常的数据优先级是：部署/测量数据 > 场景资产元数据 > 明确标注的仿真预设。

当前 `GnbSite` 和 UE request 没有高度字段，因此 Bristol runtime 使用外部策略配置，不修改共享接口：

- `gnb_001`: 10.0 m，来源 `3gpp_umi_reference`，状态 `assumed`。
- 默认 UE: 1.5 m，来源 `3gpp_umi_reference_handheld`，状态 `assumed`。
- 高度参考：`local_ground`。
- Student Union、Gym: `low_loss` O2I profile，来源 `simulation_assumption`，状态 `assumed`。
- penetration residual: 0 dB，保持确定性均值；随机残差以后单独接入。

这些数值适合可重复的系统仿真，但不是 Bristol 实测结论。以后获得真实站点天线中心高度、UE 类型/楼层或建筑材料数据时，应替换配置并把状态改为 `confirmed`。`ChannelState` 会输出本次使用的高度、标定和 penetration profile provenance。

## 已验证边界

- 默认 UE `(520, 430)`：d2D 75.37 m、d3D 75.85 m、室内深度 26.12 m；shadow 模式评估 O2I 108.52 dB，legacy 仍选择 130.06 dB。
- 默认 UE 的室内深度超过标准 UMi O2I 25 m 支持范围；shadow 可显式记录外推，active 严格模式会回退。
- Student Union 中心点：室内深度约 22.4 m，可在 active 严格模式且显式接受 provisional 标定时使用 O2I，不需要外推。
- Stage 4B 使用 3GPP external-wall penetration loss，不再叠加地图 raw wall loss；legacy raw wall loss 仅保留在 legacy 分支。
- 94 个单元测试通过，Bristol 10-tick RAN runtime 通过。

## 提升为默认 active 前仍需确认

1. 三个有效标定参照的精确 map 起止坐标，并据此生成真实 anchors/residuals。
2. 是否接受 275 m × 275 m 为 confirmed；220 m 局部偏差是修图还是更正端点定义。
3. gNB 10 m 和 UE 1.5 m 是否只作为长期仿真 preset，还是将来由 topology/UE 状态提供每实体高度。
4. Student Union 和 Gym 的 `low_loss` 是否符合目标仿真假设；若模拟具体材料，需要确认 low/high-loss 或更细材料映射。
5. 对室内到室外、跨建筑等 Stage 3 adapter 尚不支持的链路，是继续 legacy fallback，还是进入下一阶段实现专用模型。
6. 是否允许 active 模式进行超范围外推。当前安全默认是不允许。

