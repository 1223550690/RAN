# 多 Agent RAN 基线执行逻辑说明

本文说明当前 RAN 基线如何从固定规模的多 Agent 测试场景执行到 Data Network，并标明每一步对应的代码文件。合同、身份和守恒规则以 `docs/integration/frozen_contracts_v1_zh.md` 为准。以下协议链对每个 `ServiceContext` 分别执行，各模块内部算法仍保持最小实现。

## 1. 测试背景

- 地图：`bristol_topology`
- 场景建立时固定三个 Agent，运行期间不可隐式增删。
- `student_a/student_a_phone`：上传 100 MiB 视频到 `youtube_server`。
- `student_b/student_b_phone`：发送 4 KiB 即时消息到 `chat_server`。
- `student_c/student_c_phone`：上传 1 MiB 语音片段到 `voice_server`。
- 接入方式：`selected_access="5g"`，`access_type="3gpp"`
- DNN：`internet`
- 单基站：`gnb_001`
- 基站初始位置：大地图左上角，地图坐标约 `(90, 90)`

对应代码：

- 默认场景参数：`ran/orchestration/definitions.py`
- Agent 状态 mock：`ran/orchestration/agent_state.py`
- 多 Agent 编排：`ran/scenario.py`
- 地图加载：`services/scene_service.py`
- 基站从地图读取：`ran/radio/topology_adapter.py`
- 地图数据：`editor/data/scenes/bristol_topology.json`

## 2. 启动方式

### 2.1 带预览的逐 tick 模式

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode tick --ticks 5000 --tick-ms 50 -p
```

执行路径：

```text
simulation/main.py
-> parse_args()
-> SceneService.load_scene()
-> start_preview_server()
-> run_ran_mvp_tick()
-> RanEngine.build_scenario()
-> SimulationLoop.run()
-> MultiAgentRanScenario.step()
```

说明：

- `--ran-mvp` 进入 RAN MVP。
- `--ran-mvp-mode tick` 表示每个 simulation tick 推进一步 RAN 场景。
- `--tick-ms` 是预览/循环等待时间，不等同于真实 5G slot 长度。
- `-p` 会打开 `editor/live/` 预览页面。

### 2.2 聚合模式

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode aggregate --ticks 5000
```

执行路径：

```text
simulation/main.py
-> run_ran_mvp_aggregate()
-> RanEngine.run_scenario()
-> MultiAgentRanScenario.step() 多次
-> 打印最终摘要
```

聚合模式不打开预览页，只输出最终摘要。当前摘要中的 `tick_throughput_mbps` 是最后一个 tick 的实时吞吐，不是累计平均吞吐。

## 3. 总体链路

对每个活跃 Service 执行的协议/模块链路如下；SchedulerRequest 会在同一 tick 汇总所有活跃 Service，并只调用一次 Scheduler：

```text
AgentIntent
-> UERequest
-> AccessSelection
-> UE registration
-> PDU Session
-> IPTrafficBatch
-> QoSFlow / QFI
-> SlicePolicy
-> SDAP: QFI -> DRB
-> PDCPBatch
-> RLCQueue
-> ChannelState
-> SchedulerRequest JSON
-> JavaSchedulerAdapter
-> PythonBaselineScheduler fallback
-> SchedulerResult / MACAllocation
-> PHY TransmissionResult
-> gNB RU
-> gNB CU-UP / N3 GTP-U
-> UPF
-> N6
-> DataNetwork
-> QosMetrics / EndToEndResult
```

核心编排文件：

- `ran/engine.py`：RAN MVP 高层编排入口。
- `ran/scenario.py`：固定 100MB 上传场景的逐 tick 状态机。
- `simulation/simulation_loop.py`：通用 simulation tick loop，负责暂停、日志、预览写入。

## 4. 逐步执行与代码映射

| 阶段 | 作用 | 主要输入 | 主要输出 | 代码文件 |
|---|---|---|---|---|
| Agent 意图 | 固定生成学生上传视频需求 | agent、位置、目标、100MB | `AgentIntent` | `ran/scenario.py`, `ran/contracts/agent.py` |
| UE 状态 | 创建手机 UE 并注册 | `AgentIntent` | `UeState` | `ran/ue/state.py`, `ran/core/amf.py`, `ran/contracts/ue.py` |
| UE 请求 | 把意图转成 UE 业务请求 | `AgentIntent`, `ue_id` | `UERequest` | `ran/ue/request.py`, `ran/contracts/ue.py` |
| 接入选择 | 当前固定选择 5G/3GPP | `UERequest`, `GnbSite` | `AccessSelection` | `ran/access/selector.py` |
| PDU Session | 建立最小 PDU 会话 | `UeState`, `UERequest`, `slice_id` | `PduSession` | `ran/core/smf.py`, `ran/contracts/traffic.py` |
| IP 业务 | 生成上传业务批次 | `UERequest`, `PduSession` | `IPTrafficBatch` | `ran/traffic/ip.py`, `ran/traffic/service_profile.py` |
| QoS Flow | 选择 QFI、5QI、时延预算 | `UERequest`, service profile | `QoSFlow` | `ran/qos.py`, `configs/ran/service_profiles.json` |
| 网络切片 | 按业务类型分类切片 | service type | `slice_id`, `SlicePolicy` | `ran/slicing/classifier.py`, `ran/slicing/controller.py`, `configs/ran/slice_policies.json` |
| SDAP | QFI 映射到 DRB | `QoSFlow`, `UERequest` | `Drb` | `ran/protocol/sdap.py`, `ran/contracts/bearer.py` |
| PDCP | 最小 PDCP 批处理 | `IPTrafficBatch`, `Drb` | `PdcpBatch` | `ran/protocol/pdcp.py` |
| RLC | 维护队列和重传字节 | `PdcpBatch`, `Drb` | `RlcQueue` | `ran/protocol/rlc.py`, `ran/contracts/bearer.py` |
| 地图信道 | 计算距离、墙损耗、SINR、CQI | UE 位置、gNB 位置、地图墙体 | `ChannelState` | `ran/radio/channel.py`, `ran/radio/topology_adapter.py`, `services/map_service.py` |
| Scheduler 请求 | 汇总 MAC 调度输入 | RLC、QoS、DRB、Channel、Slice | `SchedulerRequest` | `ran/gnb/du.py`, `ran/contracts/scheduler.py` |
| Java 边界 | 保留 Java scheduler JSON 接口 | `SchedulerRequest` | `SchedulerResult` | `ran/scheduler/java_adapter.py` |
| Python fallback | 当前临时代替 Java | `SchedulerRequest` | `MacAllocation` | `ran/scheduler/python_baseline.py` |
| OFDM/MIMO 抽象 | 用 PRB/MCS/layers 估算容量 | PRB、MCS、layers | scheduled bytes | `ran/radio/ofdm.py`, `ran/scheduler/python_baseline.py` |
| PHY | 按错误率折算成功/失败/重传 | `MacAllocation`, `ChannelState` | `TransmissionResult` | `ran/radio/phy.py`, `ran/contracts/radio.py` |
| RLC 更新 | 扣减队列、加入重传 | `RlcQueue`, `TransmissionResult` | updated `RlcQueue` | `ran/protocol/rlc.py` |
| gNB RU | 接收无线传输结果 | `TransmissionResult` | `TransmissionResult` | `ran/gnb/ru.py` |
| CU-UP/N3 | 封装并转发到 N3 | `TransmissionResult`, `PduSession` | `N3ForwardingResult` | `ran/gnb/cu_up.py`, `ran/transport/n3_gtpu.py` |
| Backhaul | 最小回传容量接口 | `N3ForwardingResult` | `N3ForwardingResult` | `ran/transport/backhaul.py` |
| UPF | 转发到 N6 | `N3ForwardingResult`, `PduSession` | `N6DeliveryResult` | `ran/core/upf.py` |
| Data Network | 目标网络接收 | `N6DeliveryResult` | `N6DeliveryResult` | `ran/core/data_network.py`, `ran/transport/n6.py` |
| 指标 | 生成 tick 指标和端到端结果 | transmission、N3、N6、progress | `QosMetrics`, `EndToEndResult` | `ran/metrics/qos.py`, `ran/metrics/records.py` |

## 5. Java Scheduler 边界

当前 Java scheduler 还没有真正接入。Python 侧保留了完整接口：

- 边界文件：`ran/scheduler/java_adapter.py`
- 当前 fallback：`ran/scheduler/python_baseline.py`
- scheduler 抽象基类：`ran/scheduler/base.py`
- 输入输出契约：`ran/contracts/scheduler.py`

Java scheduler 的输入是 `SchedulerRequest`，主要字段包括：

- `tick`：当前 tick。
- `direction`：UL/DL。
- `total_prbs`：当前 gNB 可用 PRB 总数。
- `rlc_queues`：各 DRB 的排队字节和重传字节。
- `qos_flows`：QFI、5QI、GBR/MBR、时延预算。
- `drbs`：DRB 与 QFI、slice 的绑定。
- `channel_states`：CQI、SINR、距离、墙损耗。
- `slice_policies`：切片优先级、最小/最大 PRB 比例。
- `harq_feedback`：预留 HARQ 反馈字段。

Java scheduler 的输出是 `SchedulerResult`：

- `allocations`：每个 UE/DRB 获得的 PRB、MCS、layers、scheduled bytes。
- `debug`：调度器内部解释信息，供日志和后续调试使用。

替换 Java 时，优先只改 `JavaSchedulerAdapter._send_to_java()`，不要改 Python 侧数据契约。这样其他模块仍然只依赖 `SchedulerRequest -> SchedulerResult`。

## 6. 网络切片在 MVP 中的位置

当前切片不是独立链路，而是贯穿业务和调度：

```text
UERequest.service_type
-> classify_slice()
-> PduSession.slice_id
-> QoSFlow.slice_id
-> Drb.slice_id
-> RlcQueue.slice_id
-> SchedulerRequest.slice_policies
-> MacAllocation.slice_id
```

对应代码：

- 切片分类：`ran/slicing/classifier.py`
- 切片策略：`ran/slicing/policy.py`
- 策略更新入口：`ran/slicing/controller.py`
- 配置文件：`configs/ran/slice_policies.json`
- scheduler 使用切片策略：`ran/scheduler/python_baseline.py`

后续如果引入 AI-powered slicing，建议替换或扩展 `ran/slicing/controller.py`，让它根据队列、CQI、业务 SLA 和历史指标动态生成 `SlicePolicy`。MAC scheduler 仍然只消费 `slice_policies`，不直接依赖 AI 模型。

## 7. OFDM、MIMO、天线和基站参数

当前 OFDM/MIMO 是最小抽象，不做真实资源网格：

- `total_prbs` 表示 gNB 可用 PRB 总量。
- `mcs` 表示调制编码等级。
- `layers` 表示 MIMO 层数。
- `scheduled_bytes` 根据 PRB、MCS、layers 粗略估算。

对应代码：

- gNB 参数读取：`ran/radio/topology_adapter.py`
- gNB 数据结构：`ran/contracts/radio.py`
- OFDM 容量估算：`ran/radio/ofdm.py`
- scheduler 分配 PRB/MCS/layers：`ran/scheduler/python_baseline.py`
- PHY 传输：`ran/radio/phy.py`

基站参数来自地图元素 `gnb_001`：

- `center`：基站位置。
- `carrier_freq_mhz`：载波频率。
- `bandwidth_mhz`：带宽。
- `tx_power_dbm`：发射功率。
- `total_prbs`：可用 PRB 总数。
- `antenna_elements`：天线阵元数。
- `mimo_layers`：最大 MIMO 层数。

约束：当前 MVP 只允许一个基站。需要移动或修改参数时，应更新 `gnb_001`，不要新增第二个 gNB。

## 8. 预览、暂停和日志导出

预览链路：

```text
SimulationLoop.write_preview_state()
-> LivePreviewService.write_state()
-> outputs/live_state.json
-> editor/live/livePreview.js
-> editor/live/index.html
```

对应代码：

- tick loop 和暂停逻辑：`simulation/simulation_loop.py`
- 暂停/继续/导出控制：`simulation/control.py`
- 预览状态写入：`services/preview_service.py`
- HTTP 控制接口：`simulation/main.py`
- 页面结构：`editor/live/index.html`
- 页面逻辑：`editor/live/livePreview.js`
- 页面样式：`editor/live/livePreview.css`

预览页当前包含：

- 地图 canvas。
- 右侧 `Current RAN Tick`：一行一个字段，支持滚动查看。
- 底部 `Runtime Log`：滚动历史日志。
- `Pause/Resume`：在当前 tick 暂停或继续。
- `Export Logs`：导出当前累计日志到 `log/ran_simulation_YYYYMMDD_HHMMSS.log`。

暂停后，如果 tick 状态和日志没有变化，前端不会重复重绘信息窗口，便于选择和复制文本。

## 9. 当前指标含义

当前 tick 状态和日志中的主要指标：

- `tick`：当前 simulation tick。
- `cqi`：简化 CQI，来自信道模型。
- `sinr`：简化 SINR，单位 dB。
- `prbs`：当前 tick 分配给该 UE/DRB 的 PRB 数。
- `mcs`：当前 tick 使用的 MCS。
- `tx`：当前 tick 成功送达无线接收端并进入后续链路的字节。
- `fail`：当前 tick 无线失败字节，可能进入 HARQ/RLC 重传，不等于最终丢包。
- `total`：累计 delivered bytes / requested bytes。
- `remaining`：当前 RLC 队列和重传队列剩余字节。
- `completion_ratio`：累计完成比例。
- `remaining_ratio`：仍在队列或等待重传的未完成比例。
- `tick_throughput_mbps`：当前 tick 的实时吞吐，不是累计平均吞吐。
- `loss_rate`：真实丢包率，只统计 `dropped_bytes + n3_loss_bytes + n6_loss_bytes`。
- `dropped`：累计不可恢复丢弃字节。
- `latency_ms`：单批 packet path delay，当前为无线路径 + N3 + N6 的最小估计，不表示整个 100MB 文件完成时间。

指标计算代码：

- QoS 计算：`ran/metrics/qos.py`
- 端到端结果汇总：`ran/metrics/records.py`
- 切片资源统计：`ran/metrics/slice_metrics.py`
- tick 日志格式：`simulation/simulation_loop.py`
- 前端字段格式化：`editor/live/livePreview.js`

## 10. Wi-Fi / non-3GPP 预留

MVP 不单独设计 Wi-Fi 文件夹，也不建立第二条 Wi-Fi 链路。当前只保留接口字段：

- `UERequest.selected_access`
- `UERequest.access_type`
- `AccessSelection.selected_access`
- `AccessSelection.access_type`
- `EndToEndResult.access_type`

对应代码：

- 接入选择：`ran/access/selector.py`
- UE 请求：`ran/ue/request.py`
- 端到端结果：`ran/contracts/metrics.py`

未来接入 Wi-Fi/non-3GPP 时，应优先扩展这些字段和 `ran/access/selector.py`，而不是把 Wi-Fi 强行塞进 5G MAC scheduler。共享频谱、干扰和 backhaul 耦合可以作为后续信道/传输层扩展。

## 11. 当前最小实现边界

- AMF：只更新 UE 注册状态，见 `ran/core/amf.py`。
- SMF：只创建固定 PDU Session，见 `ran/core/smf.py`。
- QoS：使用固定 service profile，见 `ran/qos.py` 和 `configs/ran/service_profiles.json`。
- SDAP：固定 QFI 到 DRB 映射，见 `ran/protocol/sdap.py`。
- PDCP：只估算 header 和 SN，见 `ran/protocol/pdcp.py`。
- RLC：只维护字节队列和重传字节，见 `ran/protocol/rlc.py`。
- Channel：距离、墙损耗、简化 path loss，见 `ran/radio/channel.py`。
- Scheduler：Python fallback 分配 PRB/MCS/layers，见 `ran/scheduler/python_baseline.py`。
- PHY：按错误率折算成功、失败、重传，见 `ran/radio/phy.py`。
- N3/UPF/N6：固定时延转发，见 `ran/gnb/cu_up.py`、`ran/core/upf.py`、`ran/transport/n6.py`。
- Metrics：当前只提供 MVP 指标，不代表完整 3GPP KPI。

## 12. 建议后续扩展顺序

1. 先完善 `ran/scheduler/java_adapter.py`，让 Java scheduler 真正接入。
2. 再扩展 `ran/slicing/controller.py`，引入 AI slicing，但保持输出仍是 `SlicePolicy`。
3. 然后增强 `ran/radio/channel.py` 和 `ran/radio/ofdm.py`，把信道、PRB、MCS、MIMO 关系做得更真实。
4. 最后再考虑 Wi-Fi/non-3GPP 接入，不要过早拆出第二条完整链路。
