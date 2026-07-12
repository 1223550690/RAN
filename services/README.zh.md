# Services

`services/` 包含供仿真代码和实时预览使用的应用层封装。这些模块在底层场景数据之上提供稳定的项目接口。

## MapService

`MapService` 定义在 `services/map_service.py`，用于对已注册场景对象执行只读地图查询。

### `get_area_at(scene, x, y)`

返回某个全局地图坐标所在的区域信息。

输入：

```python
scene
x: float
y: float
```

输出包括：

- `scene_id`
- `position`
- 位于 area 内时的 `local_position`
- `area`
- `child_area`
- `space`
- `area_type`

如果坐标位于建筑内，但不在已定义 child area 内，则返回该建筑的自动 open space。

控制台命令：

```text
area <x> <y>
```

### `get_object_position(scene, object_id)`

返回已知对象 id 的全局位置信息。

支持的对象类型包括：

- 顶层 area
- child area
- element
- wall
- portal
- road segment
- road intersection

child area 和室内 element 坐标会从建筑局部坐标转换为全局地图坐标。

控制台命令：

```text
pos <object_id>
```

### `get_walls_between(scene, start, end)`

返回两个全局地图坐标连线穿过的所有墙体片段。

输入：

```python
scene
start: tuple[float, float]
end: tuple[float, float]
```

返回的 wall 条目包括：

- `wall_id`
- `name`
- `area_id`
- `area_name`
- `scope`
- `wall_type`
- `material`
- `thickness_m`
- `penetration_loss_db`
- `blocks_signal`
- `blocks_movement`
- `segment`
- `intersection`
- `distance_from_start`

规则：

- 室内顶层建筑边界会作为外墙纳入。
- 显式定义的场景级和建筑级 wall 会纳入。
- child area 的逻辑边界不会被视为 wall，除非显式定义了 wall。
- 结果按 `distance_from_start` 排序。

该接口面向后续无线信道逻辑，信道模型需要估算 UE 坐标与基站坐标之间的墙体穿透损耗。
