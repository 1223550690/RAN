# 坐标标定 Handoff

## 范围

坐标标定和传播几何。坐标标定 core 保持为独立模块，
不把比例、真实参考点或高度标定逻辑写进 `geometry.py`。

第一版新增：

- `ran/radio/coordinate_calibration.py`
- `configs/ran/coordinate_calibration.json`
- `experiments/debug_coordinate_calibration.py`
- Python 标准库单元测试

第一版不修改 `geometry.py`、`channel.py`、`ChannelState`、scheduler、
path loss、metrics 或 editor schema。

## 当前 Bristol 假设

场景名义范围是 `2000 x 2000 map units`，暂定物理范围约为
`300 m x 400 m`：

```text
meters_per_map_unit_x = 0.15
meters_per_map_unit_y = 0.20
status = provisional
source = team_approximation
```

这些值只存在配置中，不是算法常量。真实单位确认后，只修改
`physical_extent_m`、`calibration_id`、`source` 和 `status`。

## 距离语义

x/y 比例不同时，必须先转换两个方向的坐标差，再计算距离：

```text
dx_m = (x2 - x1) * scale_x
dy_m = (y2 - y1) * scale_y
d2D_m = sqrt(dx_m^2 + dy_m^2)
d3D_m = sqrt(d2D_m^2 + (h1_m - h2_m)^2)
```

只有 x/y 比例相等时才输出 legacy `meters_per_map_unit`。这样可以避免
调用方把 map-space 欧氏距离错误地乘以一个统一比例。

## 配置状态

- `provisional`：只允许 debug 或显式 opt-in，可以暂时没有真实 anchors。
- `confirmed`：至少需要两个 anchors，最大相对误差不得超过 10%。
- 未配置的 scene 返回无标定，不会猜测 `1 unit = 1 m`。

物理矩形对应名义 `rendering.map_bounds`。部分道路为了裁剪会伸出该范围；
转换函数不会静默截断这些坐标。

## 调试命令

```powershell
python -m experiments.debug_coordinate_calibration --scene bristol_topology --pretty
```

指定样例 UE 和高度：

```powershell
python -m experiments.debug_coordinate_calibration --x 520 --y 280 --gnb-height-m 10 --ue-height-m 1.5 --pretty
```

## Geometry 兼容接口

传播几何现在通过 `coordinate_view_from_calibration(...)` 消费坐标标定结果。
兼容接口在原有 scalar 字段之后追加 X/Y 比例，保留旧 scalar fallback 和
无标定时 meter 字段为 `None` 的行为。

验证命令：

```powershell
python -m unittest tests.radio.test_geometry_coordinate_calibration tests.radio.test_coordinate_calibration
python -m experiments.debug_propagation_geometry
python -m experiments.debug_propagation_geometry --with-calibration --gnb-height-m 10
```

第三条命令是对当前 provisional 标定的显式 debug opt-in。主 channel runtime
接入仍然是后续独立的跨组变更。
