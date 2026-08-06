# RAN 完整版本冻结合同 V1

合同版本：`1.0`  
冻结日期：2026-08-02  
适用分支：`final_version`

## 1. 目标与边界

本文档是后续成员代码进入 `final_version` 的共同依据。当前优先冻结身份、时间、业务状态、Scheduler 边界和守恒规则；暂不要求一次完成全部 3GPP 细节。

冻结表示：

- 字段名称和含义不得在成员模块中自行改变。
- 新增可选字段可以保持 V1；删除字段、修改类型或重新解释含义必须升级合同版本。
- Python 内部可以建立 dict 索引，但跨模块 DTO 和 Python/Java JSON 必须使用本文规定的 record/list。
- 旧 MVP 字段可以短期保留为兼容别名，但新实现不得继续依赖旧含义。

## 2. 命名规则

| 对象 | 规则 | 示例 |
| --- | --- | --- |
| Python 类 | `PascalCase` | `ServiceContext` |
| Python/JSON 字段 | `snake_case` | `service_instance_id` |
| 全局业务身份 | 字符串 | `intent_video_upload_001` |
| 3GPP 局部编号 | 整数 | `qfi=9`、`drb_id=3` |
| 字节 | `_bytes` | `requested_payload_bytes` |
| 时延 | `_ms` | `packet_delay_budget_ms` |
| 资源比例 | `_ratio`，范围 `[0, 1]` | `min_prb_ratio` |
| 标准错误/丢包率 | `_rate`，范围 `[0, 1]` | `packet_error_rate` |
| 功率 | `_dbm` | `received_power_dbm` |
| 增益、损耗和 SINR | `_db` | `path_loss_db` |
| 吞吐率 | `_mbps` | `throughput_mbps` |
| 布尔值 | `is_`、`has_`、`can_` | `is_retransmission` |

`Direction` 固定为 `"UL" | "DL"`。状态常量使用大写字符串，例如 `ACTIVE`、`COMPLETED`、`FAILED`。

## 3. 时间合同

- `simulation_id`：一次仿真的全局身份，场景建立后不变。
- `tick`：非负整数，同一次仿真内单调递增。
- `tick_duration_ms`：由 simulation clock 提供，不由协议模块自行假设。
- `created_tick`、`arrival_tick`、`completed_tick` 都使用 simulation tick。
- 任何“上一 tick 报告”必须同时携带来源 `tick`，不能通过列表位置推断。

## 4. 身份链与作用域

```text
simulation_id
  -> agent_id
  -> intent_id
  -> service_instance_id
  -> ue_id
  -> (ue_id, pdu_session_id)
  -> flow_id / packet_batch_id
  -> (ue_id, pdu_session_id, qfi)
  -> (ue_id, drb_id)
  -> sdap_pdu_id
  -> pdcp_pdu_id / pdcp_sn
  -> rlc_sdu_id
  -> rlc_sn + segment_offset_bytes
  -> scheduler_request_id
  -> allocation_id
  -> transport_block_id / harq_process_id
```

全局唯一字符串：

- `simulation_id`
- `agent_id`
- `intent_id`
- `service_instance_id`
- `flow_id`
- `packet_batch_id`
- 各层 PDU/SDU/segment、request、allocation 和 transport block ID

作用域编号：

- `pdu_session_id` 只在 UE 内唯一，完整键为 `(ue_id, pdu_session_id)`。
- `qfi` 只在 PDU Session 内唯一，完整键为 `(ue_id, pdu_session_id, qfi)`。
- `drb_id` 只在 UE 内唯一，完整键为 `(ue_id, drb_id)`。
- `pdcp_sn`、`rlc_sn` 属于对应协议实体，并按配置的 SN 位宽取模。
- `harq_process_id` 属于 UE、方向和 cell 的 MAC/PHY 上下文。

禁止使用列表下标、Agent 名字拼接或成员本机路径作为隐式身份。

## 5. 场景与多 Agent 合同

### 5.1 场景定义

`RanScenarioDefinition` 在场景构造时一次性提供：

- `simulation_id`
- `agents: tuple[AgentScenarioDefinition, ...]`
- `agent_count`，由 `agents` 长度确定

场景运行期间不得增加或删除 Agent。未来若支持动态进入/离开，必须通过显式 lifecycle event 和新合同版本实现。

### 5.2 Agent 状态来源

`AgentStateProvider` 接口：

```python
get_agent_states(*, tick: int) -> list[AgentStateSnapshot]
```

返回字段：

- `agent_id`
- `tick`
- `position`
- `status`

每 tick 返回的 Agent ID 集合必须与场景建立时完全一致。Provider 可以更新位置和状态，但不能隐式改变 Agent 总数。

### 5.3 运行上下文

- `AgentContext`：Agent 当前状态、Intent ID 和 UE ID 集合。
- `IntentContext`：Intent 生命周期和产生的 Service ID。
- `UeContext`：UE 注册/连接状态和活跃 Service ID。
- `ServiceContext`：一个业务实例在 PDU session、QoS、DRB、PDCP、RLC、执行和 metrics 中的连续状态。

V1 默认一个 Agent、一个 UE、一个 Intent 和一个 Service，但数据结构必须允许一对多，不能用 `agent_id == ue_id == service_id` 的方式简化身份。

## 6. Agent、Intent 与 UE 请求合同

### AgentIntent

```text
intent_id
agent_id
agent_pos
created_tick
action
target
content_type
service_type
requested_payload_bytes
```

### UERequest

```text
intent_id
service_instance_id
ue_id
agent_id
position
direction
selected_access
access_type
target
dnn
pdu_session_type
service_type
requested_payload_bytes
qos_hint
```

`selected_access` 当前允许 `5g | wifi | auto`；`access_type` 允许 `3gpp | non_3gpp`。Wi-Fi 在 V1 只冻结字段，不建立独立执行线路。

## 7. Packet/PDU 合同

后续协议模块必须保留上游身份，不实例化真实 payload 内容。

### IpPacketBatch

```text
packet_batch_id
flow_id
service_instance_id
intent_id
ue_id
pdu_session_id
arrival_tick
direction
five_tuple
packet_count
app_payload_bytes
transport_header_bytes
ip_header_bytes
ip_network_bytes
nominal_packet_size_bytes
final_packet_size_bytes
```

### 通用层转换

SDAP、PDCP、RLC 输出至少携带：

```text
本层对象ID
parent_ids
ue_id / pdu_session_id / qfi / drb_id
pdu_count 或 segment_count
payload_bytes
header_bytes
total_bytes
```

RLC segment 额外携带：

```text
rlc_sdu_id
rlc_sn
segment_offset_bytes
is_first_segment
is_last_segment
is_retransmission
attempts
```

## 8. Scheduler 冻结合同

Scheduler 是 RLC queue/无线状态到 MAC allocation 的唯一决策边界。

### SchedulerRequest

```text
contract_version
simulation_id
scheduler_request_id
tick
gnb_id
direction
total_prbs
rlc_queues[]
qos_flows[]
drbs[]
channel_states[]
slice_policies[]
phr_reports[]
bsr_reports[]
harq_feedback[]
```

### SchedulerResult

```text
contract_version
simulation_id
scheduler_request_id
tick
allocations[]
debug
```

### MacAllocation

```text
allocation_id
ue_id
drb_id
qfi
slice_id
direction
prbs
mcs
layers
transport_capacity_bytes
expected_error_rate
is_retransmission
```

过渡期代码中的 `scheduled_bytes` 表示 Scheduler 估计的 transport capacity；RLC 实际输出必须使用独立的 `actual_rlc_pdu_bytes`，PHY 不得直接假设队列一定能填满 capacity。

`channel_states` 必须是 list。Scheduler 内部可以构造：

```python
channel_by_link = {
    (state.ue_id, state.gnb_id, state.direction): state
    for state in request.channel_states
}
```

## 9. 输出状态合同

每 tick 场景状态包含：

```text
contract_version
simulation_id
tick
status
agent_count
agent_states[]
service_states[]
results[]
progress                 # 全局聚合
scheduler_request
scheduler_result
gnb
```

每份 `service_state` 必须以 `agent_id + intent_id + service_instance_id + ue_id` 标识。旧 MVP 的顶层 `result/ue_request/channel/transmission` 仅作为首个 Service 的临时兼容视图。

## 10. 守恒规则

### 10.1 应用 payload 守恒

对每个 `service_instance_id`：

```text
requested_payload_bytes
= not_arrived_payload_bytes
 + queued_payload_bytes
 + inflight_payload_bytes
 + delivered_payload_bytes
 + permanently_dropped_payload_bytes
```

业务完成度只使用应用 payload：

```text
completion_ratio = delivered_payload_bytes / requested_payload_bytes
```

协议 header、padding 和重传字节不能增加业务完成度。

### 10.2 层转换守恒

```text
output_total_bytes = input_payload_bytes + generated_header_bytes + padding_bytes
```

一层移除 header 后，交给上层的 payload 必须等于其成功接收的下层 payload。禁止同时把 header 和 payload 都计入最终业务交付。

### 10.3 RLC 守恒

```text
queue_before
+ enqueued_sdu_bytes
+ rlc_retransmission_added_bytes
- granted_actual_payload_bytes
- permanently_dropped_bytes
= queue_after
```

- 所有 segment payload 总和等于其消费的 RLC SDU payload。
- `RlcGrantResult.actual_total_bytes` 不得超过 MAC transport capacity。
- 同一 SDU 的 segment 保留同一 RLC SN，并通过 offset 区分。

### 10.4 PRB 与 allocation 守恒

```text
0 <= sum(allocation.prbs) <= total_prbs
```

- allocation 必须指向 request 中存在的 `(ue_id, drb_id, direction)`。
- `prbs`、capacity 和实际发送字节不得为负数。
- `layers` 不得超过 UE、gNB 和信道允许值。
- 未获得 allocation 的活跃 UE 保持排队，不能被标记为完成。

### 10.5 PHY、HARQ 与 RLC 重传守恒

```text
attempted_tb_bytes
= acknowledged_tb_bytes
 + harq_pending_bytes
 + final_failed_bytes
```

- HARQ pending 字节由 MAC/PHY executor 唯一持有，不能同时进入 RLC retransmission。
- HARQ 最终失败后，RLC AM 才接收失败 SDU/segment；RLC UM 将其计入永久丢弃。
- 无线首传失败不是最终丢包，成功重传后不得计入真实 loss。

在 HARQ executor 实现前，V1 mock 必须令 `harq_pending_bytes=0`，明确把失败交给 RLC 或 drop，不能生成无人持有的 HARQ 字节。

### 10.6 核心网守恒

```text
n3_input_bytes = n3_forwarded_bytes + n3_loss_bytes
n6_input_bytes = n6_delivered_bytes + n6_loss_bytes
```

N3/N6 loss 只能计入一次永久丢弃，不能继续出现在下游 delivered 中。

### 10.7 Metrics 守恒

- tick 吞吐只计算该 tick 成功交付的应用 payload。
- 真实 packet loss 使用最终丢弃 packet count / 已生成 packet count。
- retransmission rate、radio block error 和 permanent packet loss 分开统计。
- 全局指标等于所有 Service 指标按明确规则聚合，不能直接复用第一个 Agent 的指标。

## 11. 生命周期规则

```text
Intent:  PENDING -> ACTIVE -> COMPLETED | FAILED
Service: INITIALIZING -> ACTIVE -> WAITING_FOR_ALLOCATION
         -> ACTIVE -> COMPLETED | FAILED
Agent:   READY -> ACTIVE -> PAUSED | COMPLETED | FAILED
```

- Scheduler 暂时不给资源时，Service 进入或保持 `WAITING_FOR_ALLOCATION`。
- 只有 `delivered + permanently_dropped == requested` 且所有重传/在途为空时，Service 才结束。
- 一个 Service 完成不能结束其他 Agent 或整个场景。
- 场景只在全部 Service 进入终态时结束。

## 12. 合并门槛

成员模块合并前至少满足：

- 使用本文身份和命名，不通过成员本机路径或全局隐式状态通信。
- 输入输出中文接口文档完整。
- 多 Agent 实例之间没有共享可变状态。
- Scheduler JSON 可在 Python/Java 两侧按 list/record 还原。
- PRB、queue 和 payload 守恒可以通过测试核对。
- 对暂未实现的逻辑明确标记 mock，不用固定值伪装完整能力。
