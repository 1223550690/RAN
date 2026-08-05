# 通道抽象与 Bristol 全图导航重构报告(2026-08-06)

## 背景

Bristol 2000×2000 场景全图规划不可用(单条 43s+):① 场景数据中同一物理通道有多个
门(编辑器多视角),导致重复穿越与归属歧义;② 2000×2000 尺度、数百条碰撞线段下,
网格 A* 常数过大;③ 相邻建筑共享边界被建墙,门出口被堵。

## 通道(Channel)抽象

- `structure/scene_schema.py`:`Portal.channel_id` 数据合同(向后兼容,缺省 None)。
- 几何合并兜底:开口段**共线且区间重叠**的多个门自动归并为同一通道
  (`segments_collinear_overlap`),无需改场景文件。
- `RoomGraph` 以通道为图边:BFS 门序列返回合并后的通道(虚拟 Portal,
  segment 为成员开口段并集),一次穿越只计一次。
- 实测归并:塔北门/塔北右门/wills 南门/new_portal_1 → `ch_wills_south_service_entry`;
  student_union 西入口/餐饮南门 → `ch_student_union_west_entry`。

## 分层网格与性能

| 网格 | 用途 | cell |
|---|---|---|
| 建筑局部网格(max_cells=600) | 建筑内部段(细、精确) | 0.25-0.8m |
| 全局粗网格(max_cells=400) | 跨建筑/户外段(绕行规划) | ≈6.6m |
| (全局细网格保留作兜底) | — | — |

另加两项 A* 加速:
- **网格空间索引**:墙/障碍按 cell 光栅化,点判定只查所在 cell 邻域(常数 354→个位数)。
- **连通性预检**:从起点 flood fill 标记可达格,目标不可达立即失败(消除无解候选
  探索整个网格的 16s 开销)。

## 共享边界无墙

- 相邻室内区域共享边界(共线重叠区间)整段不建墙(通道语义,相邻建筑连通)。
- 非共享边界扣除门开口区间(两端按 agent 半径扩张)后建墙。
- 实测墙数 469 → 354。

## 正确性修复(本轮)

1. area 级 portal/wall 的局部坐标转换(用 area 自身而非父区域)。
2. `{area}_open_space` 归一化到父区域;`outside` 作为虚拟户外枢纽参与 BFS。
3. BFS 回溯从实际到达节点开始(goal 经子区域到达时不在回溯链上)。
4. A* 目标格松弛(门/边界点所在格子中心不可行时邻域搜索)。

## 验证

- potions 室内:导航 4-81ms,端到端闭环 tick 17 全部 DONE,服务全 COMPLETED。
- Bristol:Block 09 2.5s、Gym 1.2s、Student Clinic 0.25s、Football Ground 0.16s、
  Wills 0.13s、跨场景 2.0s(原 43.5s)。

## Bristol 场景数据缺陷清单(部署全局导航需修复)

1. **Football Ground 无任何门**:区域图不连通,规划退化为粗网格直穿(doors=0)。
   需在编辑器中补入口门(至少一个连 outside 的门)。
2. **显式墙覆盖门开口**:如 block_09 内 `(371,279)-(412,279)` 显式墙横跨
   student_union 西通道,已由"任何墙在门开口处让路"规则兜底(显式墙扣除开口)。
3. **open_space 命名不统一**(`student_union_open_space` vs `block_09_student_union`),
   已由空间推断兜底;建议编辑器后续统一命名或写入 channel_id。
4. **重复门定义**(wills 南门/塔北门/new_portal_1 同一通道三份),已由通道合并
   收敛;建议编辑器后续用 channel_id 显式分组。

## Bristol 可复现模板

`configs/agents/deterministic_three_agents_bristol.json`:3 agent(学生/教师/员工),
出生点 Block 09 / Physics Central Tower / Gym,共 6 步计划(跨 5 个建筑)。
端到端验证:600 ticks 内规划→行走→意图→完成→下一目标闭环通过;
student 实际行走 906m 与规划路线长度完全一致。
