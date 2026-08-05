# Agent 状态生成与 LLM 引导子系统集成报告(2026-08-04)

## 范围

实现"Agent 状态生成函数"完整链路:LLM/模板决定语义目标 → 场景解析器生成合法坐标 →
导航器生成路径 → Agent Runtime 移动 → 静止后生成网络意图 → RAN 处理 → 业务完成事件 →
再次规划。集成位置:`final_version` worktree。

## 新增模块

```
simulation/agent/
  contracts.py            # AgentPlan/Spawn/SimulationDefinition/StateFrame/快照(含 to_dict)
  definitions.py          # JSON 模板加载 + 默认三 Agent 定义
  state_machine.py        # READY→PLANNING→WALKING→NETWORK_PENDING→NETWORK_ACTIVE→PLANNING
  runtime.py              # 位置推进、意图提交、终态回调、快照
  registry.py             # 冻结 Agent 集合;attach_gateway 解决构建环
  planning/               # provider(协议)/template(确定性)/llm(自动指挥,urllib,记录+重放)/validator
  navigation/             # semantic_index/room_graph(BFS 门序)/walkability(膨胀碰撞)/
                          # astar(八方向+净空惩罚+禁斜穿夹角+目标格松弛)/endpoint_sampler(≤48)/
                          # route_scorer(评分)/path_smoothing(视线简化)/geometry
  adapters/               # ran_state_adapter(只读)/ran_intent_gateway(意图折算+提交)
simulation/orchestrator.py    # 每 tick:终态通知→Agent 推进→RAN step→状态帧
configs/agents/               # roles/intent_profiles/deterministic_three_agents
```

## 跨模块改动

| 文件 | 改动 |
|---|---|
| `ran/contracts/agent.py` | `AgentStateSnapshot` +9 个默认字段;`AgentIntent` +`duration_seconds`/`qos_hint` |
| `ran/orchestration/definitions.py` | `intent` 可选;新增 `build_runtime_agent_definition` |
| `ran/scenario.py` | 新增 `submit_intent()`;无初始 intent 的 agent 仅注册 UE;`_compose_state` 空 service 兼容;`_refresh_lifecycle_states` 保留扩展字段 |
| `ran/ue/request.py` | `qos_hint` 从 intent 派生 |
| `structure/scene_schema.py` | `Home.spawn_points`(P1 数据合同,编辑器 UI 待 P2) |
| `simulation/main.py` / `simulation_loop.py` | `--agent-sim` 入口,orchestrator 接入,preview 输出真实 agents |

## 决策落实

- Q1:LLM 只返回语义目标,坐标由导航器生成;解析失败重试 1 次后 FAILED。
- Q2:video_call 折算 duration×bitrate→bytes + 实时 qos_hint,RAN 合同未扩展。
- Q3:spawn_points 数据合同入 schema,编辑器 UI 分期。
- Q4:`submit_intent` 支持运行中提交,`completed` 可被新意图重新激活。

## 验证结果(2026-08-04 已获授权执行)

- CLI 冒烟:`python -m simulation.main -s potions_teacher_office --agent-sim` 正常。
- 修复 3 个 bug:`_compose_state` 空 service_states IndexError;orchestrator 缺 ran_state;A* 目标格松弛(门/边界线上的点所在格子中心不可行导致路径失败)。
- 小业务闭环测试(3 agent × message/video_call,tick 52 全部 DONE):
  - 意图完成→回 PLANNING→执行下一计划 ✓;跨房间移动 ✓;WALKING 无流量 ✓;
    NETWORK_ACTIVE 坐标冻结 ✓;单活跃意图 ✓;字节守恒(交付/请求≈99%)✓。

## 已知事项(未在本轮处理)

1. **调度器小业务饿死**:PythonBaselineScheduler 按队列字节加权分配 PRB,未实现
   slice_policies 的 min_prb_ratio 保障;4KB message 与 100MB+ 队列共存时权重≈0,
   长期 WAITING_FOR_ALLOCATION。属 RAN 既有缺口,建议后续在调度器实现切片最小保障。
2. 默认模板 staff_001 出生点 (7.5,4.5) 落在阻挡元素(iron_cauldron)上;
   `find_safe_start` 会修正到 (8.1,4.5),行为正确,但建议后续把出生点挪到合法位置。
3. 未运行:单元测试、Java round-trip、LLM 真实调用(自动模式)、bristol 大地图端到端。
