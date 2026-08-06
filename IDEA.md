# RAN `final_version` 项目交接

更新时间：2026-08-04  
目标读者：接手当前集成工作的下一位 Agent  
当前工作树：`D:\Code\RAN\backup\worktrees\final_version`  
当前分支：`final_version`，跟踪 `origin/final_version`  
基线提交：`fadb40369bc23aa505ccc1c4fa5ad7eaa012f8c2`  
验证状态：当前集成改动没有运行单元测试、集成测试、Java round-trip 或端到端模拟，不能描述为已验证完成。

## 0. 接手后首先遵守的规则

1. 默认使用中文与用户沟通。
2. 用户未明确使用“执行”关键词前，只允许分析和提出方案，不修改项目。
3. 用户明确要求：代码修改后不要主动运行测试，只有得到明确测试授权后才能运行。
4. 所有集成工作必须继续在本文件所处的 `final_version` 隔离 worktree 中进行。
5. 不要在主工作树 `D:\Code\RAN` 上继续集成；该工作树仍位于 `han/mvp`，并有用户自己的 `.gitignore` 和 `docs/【5GRAN & 5GC】.zh.md` 未提交修改。
6. 不要清理、重置、覆盖或格式化现有未提交改动。当前 `final_version` 工作树本身也有大量未提交文件。
7. 公共合同、`scenario.py`、Scheduler JSON、共享数据结构和跨组接口属于跨模块修改，必须提醒用户并交由人工审核。
8. 每次集成在 `docs/integration/change_log_zh.md` 追加记录；详细集成工作应新增带日期的报告，不覆盖旧报告。

## 1. 项目背景与最终目标

这是一个 Python-first 的 5G RAN/5GC 仿真项目。地图拓扑、地图编辑器、单基站位置配置、RAN MVP、多 tick 预览和日志界面已经存在。项目当前从单 UE、字节级 MVP 向多 Agent、多 UE、协议批次、真实信道和可替换调度器演进。

主要目标：

- Agent 在地图中移动，并在静止时产生网络意图。
- 多个 UE 同时运行视频上传、即时消息、语音、视频通话和文件传输等业务。
- RAN 各层保持可追踪的 Packet/PDU/Segment 身份和字节守恒。
- Java 只承担 MAC Scheduler 决策；Python 持有状态并执行 RLC、MAC/PHY、HARQ、核心网转发和指标统计。
- 最终支持 AI 网络切片：AI优先决定切片预算、权重或策略，Scheduler再在策略约束下分配 UE/DRB 的 PRB。
- Wi-Fi 目前只冻结 non-3GPP 接入字段，不实现独立 Wi-Fi 执行线路。

当前地图只有一个可编辑 gNB，不允许增加第二个基站。当前历史配置将其放在大地图左上角，位置约为 `(90, 90)`；后续允许在地图编辑器中修改该 gNB 的位置和参数。

## 2. 冻结的端到端逻辑

### 2.1 控制与业务入口

```text
Agent plan / network intent
-> UE request
-> registration and connection readiness
-> PDU session
```

AMF负责接入和注册状态，RRC负责UE与gNB的无线连接，SMF负责PDU Session、UE IP、DNN和UPF选择。SMF不转发用户面数据。

### 2.2 用户面主链

```text
Agent Intent
-> UE / AMF / Access
-> SMF / IP Packet Batch
-> QoS Flow / QFI
-> SDAP: QFI -> DRB
-> PDCP PDU
-> RLC SDU / Segment
-> MAC Scheduler / UL grant
-> MAC/PHY executor + ChannelState
-> gNB RU / DU / CU-UP
-> N3 / GTP-U
-> UPF
-> N6
-> Data Network
```

Channel Model不是第二条串行协议链。它根据地图、UE、gNB和无线参数生成 `ChannelState`，供 Scheduler 和 PHY 使用。

### 2.3 Java Scheduler 边界

```text
Python SchedulerRequest
  - RLC queues
  - QoS flows / DRBs
  - slice policies
  - ChannelState list
  - PHR / BSR / HARQ feedback
  - total PRBs
        ↓ JSON
Java Scheduler decision
        ↓ JSON
SchedulerResult / MacAllocation
  - ue_id / drb_id / direction
  - prbs / mcs / layers
  - scheduled_bytes
        ↓
Python executor
  - RLC on_grant
  - MAC TB / PHY transmit
  - HARQ/RLC feedback
  - N3/UPF/N6 delivery
  - metrics
```

正式入口必须保留 `JavaSchedulerAdapter`。当前 Java 外部 transport 尚未实现，Python Scheduler只是同合同 fallback 和参考实现。不要因为成员分支已有 Python 算法就删除 Java 边界。

## 3. 合同和守恒原则

正式依据是 `docs/integration/frozen_contracts_v1_zh.md`。关键规则如下。

### 3.1 身份链

```text
simulation_id
-> agent_id
-> intent_id
-> service_instance_id
-> ue_id / pdu_session_id
-> flow_id / packet_batch_id
-> qfi
-> drb_id
-> sdap_pdu_id
-> pdcp_pdu_id / pdcp_sn
-> rlc_sdu_id
-> rlc_sn + segment_offset
-> allocation_id
-> tb_id / harq_process_id
```

禁止用列表下标、Agent名字拼接、业务类型或成员本机路径充当隐式身份。

### 3.2 字节域

以下数据不能共用一个含义模糊的 `bytes` 字段：

- `app_payload_bytes`
- `ip_payload_bytes`
- `ip_network_bytes`
- `sdap_pdu_bytes`
- `pdcp_pdu_bytes`
- `rlc_pdu_bytes`
- `mac_tb_bytes`
- `delivered_payload_bytes`

只有最终交付的应用 payload 可以增加业务完成度。协议头、padding和同一payload的重传只能增加开销，不能重复增加交付量。

### 3.3 资源和状态所有权

- Scheduler只决策，不扣减RLC队列。
- RLC `on_grant()`生成实际Segment并报告真实可发送量。
- MAC/PHY执行TB传输并维护HARQ。
- RLC AM只处理HARQ最终未解决、需要上层重传的数据。
- 所有allocation的PRB总和不得超过gNB可用PRB。
- 一个Service完成不能结束其他Agent、UE或整个场景。
- `channel_states`跨Python/Java边界必须保持record list；Python内部可以建立dict索引。
- `get_agent_states()`必须是无副作用快照，不能因为预览或重复读取而触发LLM、移动或创建Intent。

## 4. `final_version` 当前实际状态

### 4.1 Git和工作树状态

- `final_version`与`origin/final_version`当前基线仍为`fadb403`。
- 当前改动没有commit、stage或push。
- 26个已跟踪文件有未提交修改，静态统计约为增加913行、删除237行。
- `docs/integration/`和`ran/orchestration/`当前整体仍为untracked。
- 不要通过reset、checkout或整分支merge覆盖这些工作。

### 4.2 已写入但未验证的多Agent脚手架

新增或扩展的主要能力：

- `RanScenarioDefinition`：在场景构造时冻结Agent集合。
- `AgentStateProvider`与`MockAgentStateProvider`：提供固定Agent集合的状态快照。
- `AgentContext`、`IntentContext`、`UeContext`、`ServiceContext`：分离四类运行状态。
- `MultiAgentRanScenario`：每tick汇总全部活跃Service，只调用一次Scheduler，再逐Service执行。
- Scheduler结果验证：检查合同版本、request identity、UE/DRB、非负字节和PRB总量。
- Python baseline使用整数余数分配，避免明显PRB超额。
- HARQ executor尚未存在，因此当前mock不产生无人持有的HARQ pending字节；失败临时交给RLC AM或UM drop。
- 预览和日志开始使用`agent_states[]`、`service_states[]`和全局progress，同时保留首个Service的旧顶层兼容字段。

默认测试配置冻结三个Agent：

| Agent | 业务 | 数据量 | 临时切片映射 |
| --- | --- | ---: | --- |
| `student_a` | 视频上传 | 100 MiB | `embb` |
| `student_b` | 即时消息 | 4 KiB | `mmtc` |
| `student_c` | 语音片段上传 | 1 MiB | `urllc` |

### 4.3 当前脚手架的已知限制

- Agent状态仍是静态mock，位置不移动。
- 每个Agent只有启动时的一个固定Intent。
- 所有初始Service完成后，`MultiAgentRanScenario`会结束；尚不支持运行中动态提交下一轮Intent。
- IP traffic仍是一项业务的整体批次，不是每tick到达的`IpPacketBatch`。
- SDAP没有正式`SdapPduBatch`输出。
- PDCP/RLC没有完整PDU、SDU、Segment身份；RLC grant当前主要按字节截断。
- 共享DRB的多Service归属账本未实现。
- HARQ process和ACK/NACK状态机未实现。
- 3GPP信道库尚未接入runtime，主循环仍使用baseline channel。
- 外部Java Scheduler transport未实现。
- 这些改动没有运行import、unit、integration、Java round-trip或端到端模拟。

## 5. 五个成员板块审查结论

完整问题和参考答案位于 `docs/integration/project_meeting_five_part_review_zh.md`。审查基于2026-08-01左右的本地/远端快照，接手时如需确认最新代码，应先获得用户“执行”授权再fetch；不要把以下状态自动视为远端最新状态。

### 5.1 Intent / UE / Access / AMF

来源：`haoyu_amf@7db3b81`  
备份：`D:\Code\RAN\backup\haoyu_amf`

当前只有：

- `register_ue()`的空ID和RM状态校验。
- `5g/wifi/auto`显式接入分支。
- 注册时直接设置RM/CM/RRC为CONNECTED。

缺口：

- `RM=REGISTERED`时直接返回，可能让`CM/RRC=IDLE`的UE绕过连接恢复后直接传输。
- 没有`RegistrationRequest/Result`、`AmfUeContext`、拒绝原因、注销和连接恢复。
- Intent和UE仍是固定基线，没有多Intent身份和生命周期。
- `auto`固定选择5G；Wi-Fi返回结果容易被误认为可执行。
- 没有测试和中文接口文档。

决策：已有小增量在修复连接语义、Wi-Fi reserved状态、测试和文档后可以合并，但不能称为模块完成。LLM规划和导航不属于该成员；该模块应消费上层已经生成的网络Intent。

### 5.2 SMF / IP Packet / QoS / SDAP

来源：`boyu/area-b@96ee5dd`  
备份：`D:\Code\RAN\backup\boyu_area-b`

已完成度相对最高：

- 有状态SMF、PDU Session、IP地址、DNN和UPF选择。
- `IPTrafficBatch`描述五元组、方向、应用payload、MTU、IP/TCP/UDP头、包数和network bytes。
- QoS分类、QFI/5QI、GBR/MBR、PDB/PER。
- QFI到共享、专用或默认DRB的SDAP映射。
- 配置、中文文档和较多测试代码。

缺口：

- `IPTrafficBatch`描述整项Flow，不是每tick`IpPacketBatch`。
- 缺`intent_id/service_instance_id/flow_id/packet_batch_id`，同类并发业务可能碰撞。
- SDAP只有`QFI -> DRB`映射，没有供PDCP消费的`SdapPduBatch`。
- 模块级默认manager可能在多Scenario之间泄漏状态。
- 共享DRB副本可能与canonical bearer状态分叉。

决策：中等修改后按SMF、IP、QoS、SDAP、配置和测试逐模块迁移；不要整合该分支的`scenario.py`和非必要地图输出。

### 5.3 PDCP / RLC

来源：`xizhe_pdcp/rlc@6f5aafe`  
备份：`D:\Code\RAN\backup\xizhe_pdcp_rlc`

已有：

- `PdcpEntity`、SN推进、批次开销和处理钩子。
- `RlcEntity`、SDU队列、`on_grant()`、Segment列表和重传队列。
- `actual_sent_bytes`回写PHY allocation。
- 分段、grant和部分集成测试代码。

阻断问题：

- 整个`PdcpBatch`可能被视为一个RLC SDU；应保持一个PDCP PDU对应一个RLC SDU。
- 同一SDU跨grant的不同Segment被分配不同SN；当前项目要求共享SDU/SN身份，以不同offset表示范围。
- PHY失败没有按具体inflight Segment回写，重传元数据丢失。
- HARQ没有执行主体。
- RLC header、payload和MAC TB字节没有分开。

正确简化示例：

```text
1000-byte RLC SDU
Segment 1: SN=25, offset=0,   length=400
Segment 2: SN=25, offset=400, length=600
```

决策：不整分支合并。保留entity、grant result、Segment和测试组织思路，在统一PDU合同上重构迁移。

### 5.4 Multi-UE / Scheduler / PHR

来源：`tr22068/scheduling-tests@a7c3d29`  
备份：`D:\Code\RAN\backup\tr22068_scheduling-tests`

已有：

- 硬编码三个UE并发上传的场景实验。
- PHR从PHY结果到下一tick SchedulerRequest的初步通路。
- Python equal split、max throughput、grant-based UL和weighted UL函数。

阻断问题：

- 三个UE和业务参数硬编码，不能自然配置任意N个UE。
- `channel_states`实际改成dict，破坏跨Java的list合同。
- Engine默认绕过Java adapter。
- Max Throughput和最低1 PRB逻辑可能使分配总量超过`total_prbs`。
- QoS、切片、PHR和HARQ输入没有真正参与决策。
- 分支名包含tests，但没有自动化测试文件。

决策：不合并成员的`scenario.py`。集成方在主线维护通用多UE容器和编排；调度成员只在冻结SchedulerRequest/Result合同内重写算法和测试。Python实现不代表放弃Java。

### 5.5 Channel Model

来源审查：`zhiqian/3gpp@c20d91d`  
备份/报告：`D:\Code\RAN\backup\zhiqian_3gpp`

已有：

- 地图传播几何和坐标标定框架。
- 3GPP TR 38.901 UMi/InH LOS/NLOS mean path loss。
- `PropagationGeometry -> PathLossRequest` adapter。
- O2I low/high-loss穿透和室内深度损耗。

缺口：

- Bristol地图物理尺度仍为`provisional`，不能当作confirmed ground truth。
- 未接入`ran/radio/channel.py`和主循环。
- 尚缺UL/DL link budget、方向正确的发射功率、天线增益、noise、interference、SINR、CQI/PER。
- shadow fading只有标准差或残差入口，没有可复现、空间相关的realization。
- small-scale fading、Doppler、delay、beam/MIMO和PRB级信道尚未实现。

决策：独立Geometry/Calibration/3GPP/O2I公式库可在小改和授权测试后dormant merge；runtime integration必须另开跨地图、信道、Scheduler和PHY的PR。

## 6. 当前暂停中的Agent / LLM / 导航工作

用户在合并前新增了一项重要设计：使用LLM引导场景角色移动并产生网络Intent。此部分当前只有架构设计，没有代码实现。

### 6.1 用户要求

- Agent总数在场景开始前确定，运行期间集合固定。
- Agent从地图固定出生点刷新。
- 仿真开始时，以及每个网络Intent完成或失败后，为对应Agent生成下一项计划。
- 角色初步限制为学生、教师和工作人员。
- Intent初步包括视频通话、视频上传和文件传输等。
- 为简化无线行为，Agent只在静止时进行网络活动。
- 必须支持不调用LLM的确定性模板，可固定Agent数量、位置、角色和Intent序列，以便复现。

### 6.2 推荐架构

```text
SimulationOrchestrator
├── AgentPlanProvider
│   ├── LlmAgentPlanProvider
│   └── TemplateAgentPlanProvider
├── SceneSemanticIndex
├── NavigationPlanner
├── AgentRuntime / state machine
├── RanIntentGateway
└── AgentStateProvider (read-only snapshot)
```

职责：

- LLM只决定“去哪个语义目标、做什么网络业务”。
- SceneSemanticIndex通过完整层级路径、ID、名字和别名解析目标。
- NavigationPlanner验证坐标并生成路径，不能信任LLM直接给出的坐标。
- AgentRuntime按tick移动角色并维护状态机。
- RanIntentGateway将到达且静止的角色计划转换为RAN `AgentIntent`。
- 上层SimulationOrchestrator接收RAN的`IntentCompleted/Failed`事件，再触发下一次规划。
- `ran/scenario.py`不能内置LLM循环。

建议状态机：

```text
READY
-> PLANNING
-> WALKING
-> NETWORK_PENDING
-> NETWORK_ACTIVE
-> PLANNING
```

约束：

- `WALKING`时不得生成网络流量。
- `NETWORK_ACTIVE`时位置和速度保持不变。
- 初期每个Agent最多一个活跃网络Intent。
- 规划只由start或Intent终态事件触发，不能每tick调用LLM。
- 规划调用应发生在tick边界；LLM墙钟延迟不应自动变成仿真时间。

### 6.3 导航设计

现有地图已经提供：

- `Area`层级和室内/室外元数据。
- `Portal`及其连接区域。
- `WallSegment`。
- `Element.blocks_movement`。
- `MapService.get_area_at()`、`get_object_position()`和`get_walls_between()`。
- 一个`Home.default_agent_start`。

尚缺稳定合同：

- 多个命名出生点和容量。
- 目标别名和完整递归语义索引。
- 交互区域、物体正面、可站立区域和朝向。
- 为导航切开Portal的可通行墙体几何。

推荐路径算法：

1. 将房间、Portal、Wall和Element递归转换到统一全局坐标。
2. 根据Portal连接建立房间图，跨房间使用BFS得到门序列。
3. 起点位于障碍中时搜索附近安全起点。
4. 在目标区域、物体侧面或交互区域采样最多48个候选终点。
5. 对候选运行八方向A*，禁止斜向穿过相邻障碍夹角。
6. A*代价使用行走距离加障碍净空惩罚。
7. 对简化后的连续线段再次碰撞检测，防止穿墙。
8. 按路线长度、平均/最小净空、靠墙比例和终点可站立空间评分。
9. P1再加入物体正面、手臂触达、最终移动方向和注视方向。
10. 使用视线简化和最小间距过滤Waypoints。

地图数据中常见`locked=true`同时`open=true`。`locked`主要是编辑器/资产锁定语义；导航通行应读取`open`或正式门状态，不能把`locked`直接当作物理门锁。

### 6.4 推荐的Agent状态输出

```text
AgentStateFrame
- simulation_id
- tick
- agents[]
  - agent_id
  - role
  - lifecycle_status
  - activity_state
  - position
  - current_room_id
  - destination_id
  - current_intent
  - active_service_id
  - waypoint_index / waypoint_count
  - last_transition_tick
  - error
```

### 6.5 尚未由用户确认的方向问题

1. LLM是否只返回语义目标，由导航器生成合法坐标？推荐答案：是。
2. 视频通话是否使用“持续时间 + 目标码率”而不是固定payload？推荐答案：是；上传和文件传输仍使用有限字节。
3. 出生点是否作为地图编辑器中的可编辑对象保存？推荐答案：是；Scenario只引用`spawn_point_id`并冻结分配。
4. 仿真开始时多个Agent的首次计划是否允许一次批量LLM请求？推荐支持`plan_many()`，但语义上仍为每Agent独立Plan。

## 7. 最近已经澄清的协议问题

### 7.1 IP包描述

Area B的`IPTrafficBatch`可以准确描述一个理想化Flow的共同标签、包数和总字节，但它不是逐个IP包，也不是每tick新到达的Packet Batch。

推荐两层结构：

```text
IPTrafficFlow        # 整个业务持久状态和五元组
  -> per tick
IpPacketBatch        # 本tick新到达的包数、payload、header和network bytes
```

### 7.2 SDAP正式输出

只有`QFI -> DRB`映射不代表完成SDAP数据处理。应形成：

```text
SdapPduBatch
- source_packet_batch_id
- qfi / drb_id
- packet_count
- payload_bytes
- sdap_header_bytes
- total_bytes
```

即使SDAP header配置为不存在、开销为0，也应存在逻辑输出合同供PDCP消费。

### 7.3 PDCP和RLC关系

- SDAP PDU作为PDCP SDU。
- PDCP增加SN和header后形成PDCP PDU。
- 一个PDCP PDU对应一个RLC SDU。
- RLC可分段，但Segment必须保留SDU ID、RLC SN、offset、length、边界标记和重传次数。

### 7.4 HARQ和RLC AM

- HARQ由MAC/PHY维护同一个TB的快速重传。
- HARQ尚未耗尽时，字节仍属于HARQ buffer，不能同时进入RLC重传队列。
- HARQ最终失败后，RLC AM才对对应Segment进行上层重传。

## 8. 推荐集成顺序

### P0：保护和验证当前基底

1. 不修改前先阅读本文件、冻结合同、多Agent报告和会议文档。
2. 检查当前diff，区分已有未提交改动和新任务改动。
3. 在用户明确授权测试后，先运行import、合同构造、Scheduler adapter round-trip、PRB/字节守恒和最小多Agent端到端模拟。
4. 根据验证结果修复当前`final_version`脚手架，再考虑成员模块迁移。

### P0：合并核心模块

1. Access/AMF：原成员小修后迁移小增量。
2. Area B：先统一身份和每tick Packet Batch，再按SMF、IP、QoS、SDAP迁移。
3. PDCP/RLC：冻结PDU和Segment合同后重构迁移，不整支merge。
4. 通用多UE orchestration继续由集成方维护，不使用Scheduler分支硬编码Scenario。
5. Channel公式库可dormant merge；runtime adapter另行审核。
6. Scheduler成员在稳定合同上返工Python/Java算法和单元测试。

### P1：闭合执行链

- 动态Intent提交和完成事件。
- Agent Runtime和确定性模板。
- MAC allocation executor和真实RLC Segment。
- HARQ Process、ACK/NACK和失败上交。
- Path Loss到Link Budget、SINR、CQI/PER的ChannelState。
- payload、协议开销、无线失败、HARQ、RLC和N3/N6分项指标。

### P2：真实性和研究能力

- LLM Agent规划和完整导航评分。
- AI切片预算和SLA反馈。
- small-scale fading、Doppler、delay spread、beam/MIMO和更细OFDM模型。
- 多cell、mobility和handover。
- 真实Wi-Fi non-3GPP线路；当前不要提前建立独立Wi-Fi目录和执行链。

## 9. 下一位Agent的建议起点

用户在本轮最后要求导出交接文档，之前的“逐模块merge”流程已为项目会议和Agent状态设计暂停。不要自行假设应立即继续某个成员分支。

建议首次回复先向用户报告：

1. 已读取`IDEA.md`并识别当前`final_version`未提交、未验证状态。
2. 当前有两条可恢复线路：
   - 实现Agent状态/LLM/导航基底；
   - 回到五成员模块的逐步合并。
3. 请用户指定优先线路；在没有“执行”前只给方案。

若用户选择Agent线路，第一阶段应只做：

- 冻结Agent Plan、State Frame、IntentCreated和IntentCompleted合同。
- 把现有`AgentStateProvider`保持为纯快照。
- 建立`TemplateAgentPlanProvider`，先不接真实LLM。
- 建立Agent状态机和移动runtime。
- 建立RanIntentGateway，使RAN可动态接收Intent并返回终态事件。
- 在此之后再实现地图语义索引和导航算法。

若用户选择合并线路，先处理Access/AMF的小增量或Area B的身份/Packet Batch合同；不要直接merge任何成员的`scenario.py`。

## 10. 关键文件索引

### 当前集成工作树

- `IDEA.md`：本交接文件。
- `docs/integration/frozen_contracts_v1_zh.md`：合同和守恒规则。
- `docs/integration/change_log_zh.md`：变更索引。
- `docs/integration/reports/2026-08-02_01_multi_agent_foundation_zh.md`：当前多Agent脚手架报告。
- `docs/integration/project_meeting_five_part_review_zh.md`：五板块进度、问题和参考答案。
- `ran/orchestration/definitions.py`：场景和默认三Agent定义。
- `ran/orchestration/agent_state.py`：状态Provider和静态mock。
- `ran/orchestration/contexts.py`：Agent/Intent/UE/Service Context。
- `ran/scenario.py`：当前多Service tick编排，最大跨模块冲突点。
- `ran/scheduler/java_adapter.py`：Java/Python调度边界。
- `ran/scheduler/python_baseline.py`：当前fallback调度器。

### 成员审查资料

- `D:\Code\RAN\backup\global_review_reports\2026-08-01_01_five-part-integration-review.zh.md`
- `D:\Code\RAN\backup\haoyu_amf\review_reports\2026-08-01_02_recheck.zh.md`
- `D:\Code\RAN\backup\boyu_area-b\review_reports\2026-08-01_01_initial-review.zh.md`
- `D:\Code\RAN\backup\xizhe_pdcp_rlc\review_reports\2026-08-01_02_update-review.zh.md`
- `D:\Code\RAN\backup\tr22068_scheduling-tests\review_reports\2026-08-01_02_integration-assessment.zh.md`
- `D:\Code\RAN\backup\zhiqian_3gpp\review_reports\2026-08-01_02_update-review.zh.md`

### 项目背景

- `docs/【5GRAN & 5GC】.zh.md`
- `docs/ran_mvp_execution_zh.md`
- `docs/simulation_entrypoints_zh.md`
- `structure/scene_schema.py`
- `services/map_service.py`
- `editor/data/scenes/bristol_topology.json`

## 11. 可用运行入口（仅在用户授权测试后）

逐tick、多Agent预览入口：

```powershell
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode tick --ticks 5000 --tick-ms 50 -p
```

聚合入口：

```powershell
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode aggregate --ticks 5000
```

注意：`--tick-ms`是预览/循环的墙钟等待时间，不等于真实5G slot长度。当前文档列出命令不代表这些命令已在`final_version`改动后通过。

## 12. 禁止误判的事项

- “代码存在”不等于“已接入主循环”。
- “存在测试文件”不等于“测试通过”。
- `git diff --check`只能检查空白问题，不代表功能验证。
- Channel公式正确不代表Bristol物理标定正确。
- Python Scheduler代码存在不代表Java已经被放弃。
- 三个硬编码UE能循环不代表支持任意N个Agent。
- `IPTrafficBatch.packet_count`存在不代表已有每tick Packet Batch。
- `QFI -> DRB`存在不代表已有SDAP PDU。
- RLC有`on_grant()`不代表SN、offset、HARQ和重传身份闭环。
- 当前`final_version`所有新增能力仍是未提交、未运行验证的集成脚手架。

## 13. 一句话交接结论

项目已经从单UE MVP推进到具有冻结合同和集合式多Agent编排的未验证脚手架；五成员分支的价值与阻断点已经审查清楚，但正式协议批次、动态Agent意图、RLC/HARQ执行闭环、完整ChannelState和可验证Scheduler仍未完成。下一步必须继续以统一身份、字节守恒和Python状态所有权为中心，按模块迁移，禁止用整分支覆盖方式“快速合并”。
