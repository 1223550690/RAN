# 多 Agent 编排模块接口

## 模块职责

本模块负责在场景建立时冻结 Agent 集合，并为 RAN 主循环提供场景定义、Agent 状态来源和四类运行上下文。它不负责 QoS、协议处理、资源决策或无线执行。

## 输入

### `RanScenarioDefinition`

- `simulation_id`：一次仿真的全局标识。
- `agents`：不可变的 `AgentScenarioDefinition` 元组。
- 每个 Agent 定义包含 `agent_id`、`ue_id`、初始 `AgentIntent` 和预选接入方式。

Agent 总数由 `len(definition.agents)` 确定，场景运行期间不可改变。

### `AgentStateProvider`

```python
get_agent_states(*, tick: int) -> list[AgentStateSnapshot]
```

Provider 每 tick 返回全部 Agent 的位置和状态。返回的 Agent ID 集合必须与场景定义一致。

## 输出

- `AgentContext`：Agent 与 Intent、UE 的关联。
- `IntentContext`：Intent 生命周期和 Service 集合。
- `UeContext`：UE 状态和活跃 Service 集合。
- `ServiceContext`：业务在 session、QoS、DRB、PDCP、RLC 和 metrics 之间的连续状态。

## 当前 mock

`MockAgentStateProvider` 返回静态位置：tick 0 为 `READY`，后续 tick 为 `ACTIVE`。它仅用于整体链路测试，后续可替换为真实 Agent 系统接口。

默认场景由 `build_default_three_agent_definition()` 创建：

| Agent | 意图 | 应用数据量 | 业务类型 |
| --- | --- | ---: | --- |
| `student_a` | 上传视频 | 100 MiB | `video_upload` |
| `student_b` | 发送即时消息 | 4 KiB | `message` |
| `student_c` | 上传语音片段 | 1 MiB | `voice_upload` |

这些数据量属于测试场景配置，不是协议模块固定值。

## 后续扩展边界

- 多 Intent 或多 UE 通过扩展场景定义创建，不修改 Context 身份规则。
- 动态 Agent 加入/离开需要显式 lifecycle event，不允许 Provider 静默改变集合。
- Wi-Fi 当前只保留 `selected_access` 和 `access_type` 字段。
- 编排层只汇总合同对象，不能读取成员模块内部私有状态。

