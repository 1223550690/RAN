# RAN 项目五个开发板块会议评估

日期：2026-08-03  
用途：确认成员对负责模块、上下游接口和全局运行逻辑的理解程度。  
证据范围：截至 2026-08-01 的本地分支快照与静态审查，未重新拉取远程更新，未运行测试。

## 一、项目整体目标

项目需要实现多 Agent、多 UE 的 5G RAN 模拟：

```text
Agent Intent → UE/AMF → SMF/IP/QoS/SDAP
→ PDCP/RLC → Scheduler → MAC/PHY
→ Channel → gNB/Core Network/Data Network
```

完整版本不要求逐比特还原真实协议，但必须满足：

- Agent、Intent、Service、Packet/PDU、DRB 和传输结果可以追踪。
- 每个 tick 支持多个 UE 和多个业务竞争资源。
- Scheduler 只负责决策，Python 执行器负责执行分配结果。
- PRB、队列字节、在途字节、重传、丢弃和交付必须守恒。
- Java 调度接口保持稳定 JSON 合同，Python 可作为同合同 fallback。
- 一个业务完成不能导致其他 Agent 或整个场景提前结束。

## 二、当前总体进度

| 板块 | 分支快照 | 当前判断 | 集成建议 |
| --- | --- | --- | --- |
| Intent/UE/Access/AMF | `haoyu_amf@7db3b81` | 少量基础校验 | 小改后合并增量 |
| SMF/IP/QoS/SDAP | `boyu/area-b@96ee5dd` | 独立模块最完整 | 中改后按模块优先合并 |
| PDCP/RLC | `xizhe_pdcp/rlc@6f5aafe` | 有状态框架存在，核心语义未闭合 | 依据统一合同重构迁移 |
| Multi-UE/Scheduler/PHR | `tr22068/scheduling-tests@a7c3d29` | 多 UE 与算法实验草稿 | 不合场景代码，调度器返工 |
| Channel Model | `zhiqian/3gpp@c20d91d` | 大尺度路损库较完整，未接入运行链 | 公式库与运行接入分开合并 |

## 三、板块一：Intent / UE / Access / AMF

### 负责内容

接收 Agent 网络意图，建立 UE 身份和状态，执行注册，选择 5G 或预留的 non-3GPP 接入，并向 SMF 提供满足传输条件的 UE 请求。

### 目标要求

- 支持稳定的 `agent_id → intent_id → ue_id` 身份关系。
- 分开维护 RM 注册状态、CM 连接状态和 RRC 状态。
- 支持多 Agent、多轮 Intent，避免依赖固定单业务。
- Wi-Fi 当前只返回 reserved/not executable，不进入独立线路。
- 提供注册请求、注册结果、拒绝原因和 AMF UE Context 的最小结构。

### 实际进度

已修改 `register_ue()` 和 `select_access()`，增加空 ID 校验、重复注册返回以及 `5g/wifi/auto` 分支。但 Intent、UE Context 和状态机基本仍使用基线设计；`auto` 固定选择 5G；没有测试和中文接口文档。当前只能算注册 mock 的小幅增强。

### 核心逻辑问题

1. 为什么 `RM=REGISTERED` 不代表 UE 当前可以发送数据？合格回答应说明 CM/RRC 可能仍为 IDLE，需要连接恢复。
2. `register_ue()`、RRC 连接和 SMF 建立 PDU Session 的职责边界是什么？
3. 同一个 Agent 连续产生两个相同视频上传 Intent 时，如何保证身份不碰撞？
4. `auto` 接入未来应读取哪些数据？至少应涉及覆盖、ChannelState、负载、QoS 和接入可用性。
5. Wi-Fi 尚未实现时，接口如何避免让调用方误认为已经成功接入？

### 参考答案

1. `RM=REGISTERED` 只表示 UE 已完成核心网注册，UE 仍可能处于 `CM=IDLE` 和 `RRC=IDLE`。开始用户面传输前还需要连接恢复或最小化的 Service Request/RRC 建立过程，否则模拟会让未建立无线连接的 UE 直接发送数据。
2. `register_ue()` 负责 UE 的注册状态和 AMF 上下文；RRC 建立由 gNB 控制面或独立连接接口负责；SMF 在 UE 已注册且满足连接条件后建立和管理 PDU Session。三者不能通过一次状态赋值合并成同一步骤。
3. `agent_id` 和 `ue_id` 可以保持不变，但每次行为必须创建新的 `intent_id`，并由其派生唯一 `service_instance_id`。Agent Context 保存多个 Intent ID，UE Context 保存当前活跃 Service ID，不能用业务类型或目标地址充当唯一身份。
4. `auto` 至少应读取候选接入是否可执行、UE 能力、覆盖和 ChannelState、接入节点负载、业务 QoS/时延要求以及用户策略。当前只有 5G 可执行时可以固定返回 5G，但必须标记为 mock，而不是声称已经完成最优选择。
5. 接入结果应包含明确的 `availability/executable/status` 字段或等价状态。Wi-Fi 当前应返回 `RESERVED_NOT_EXECUTABLE`，不得继续创建无线业务；`reason` 中也应说明仅冻结 non-3GPP 字段，没有实际执行线路。

## 四、板块二：SMF / IP Packet / QoS / SDAP

### 负责内容

建立和释放 PDU Session，生成 IP Packet Batch，执行业务分类和 QFI 分配，再将 QoS Flow 映射到 DRB。

### 目标要求

- 每次模拟拥有独立的 SMF、QoS 和 SDAP 实例。
- 同类并发业务拥有唯一 `service_instance_id/flow_id`。
- 每 tick 根据业务模型生成新的 IP 包批次。
- 区分应用负载、IP 网络字节和协议开销。
- SDAP 不仅维护映射，还应输出可交给 PDCP 的批次结构。

### 实际进度

已实现有状态 SMF、IPv4 分配、五元组、包数和头部统计、QoS Profile、QFI/5QI、GBR/MBR 以及共享或专用 DRB 映射。配置、文档和测试较完整。主要缺口是一次性生成整项业务、缺少唯一业务实例身份、SDAP 没有正式 PDU 输出，以及模块级默认管理器可能跨模拟泄漏状态。

### 核心逻辑问题

1. QFI、5QI 和 DRB 分别表示什么，为什么不能互相替代？
2. 为什么一次生成完整 100 MiB 的 `IPTrafficBatch` 会让 RLC 队列和吞吐模型失真？
3. 两个相同 UE、目标和业务类型的并发 Intent 应通过哪些 ID 区分？
4. SDAP 的“QFI 到 DRB 映射”和“形成 SDAP PDU”有什么区别？
5. SMF 是否经过用户面数据？合格回答应说明 SMF 建立和管理会话，数据实际经过 UPF。

### 参考答案

1. QFI 标识一个 PDU Session 内的 QoS Flow；5QI 描述该 Flow 使用的标准化或预配置 QoS 特征，例如优先级和时延预算；DRB 是无线侧实际承载一个或多个 QoS Flow 的数据承载。一个 5QI 可被多个 QFI 使用，一个 DRB 也可承载多个 QFI，因此三者不能互换。
2. 一次把 100 MiB 全部写入下层会让 RLC 从首 tick 起始终处于满缓存状态，丢失真实的包到达速率、突发、排队时延和应用限速。每 tick 应只生成本 tick 到达的 Packet Batch，再逐层进入 SDAP、PDCP 和 RLC。
3. 至少使用 `intent_id → service_instance_id → flow_id → packet_batch_id` 区分。五元组可以描述网络流特征，但不能替代业务实例身份；同类并发业务还可使用不同源端口或 flow sequence，保证状态和指标不会合并。
4. 映射只维护“某个 QFI 应进入哪个 DRB”的控制状态；形成 SDAP PDU 还需要保留输入 Packet Batch 身份、QFI、DRB、包数量、负载和 SDAP header 开销，并输出 PDCP 可以消费的明确批次对象。
5. SMF 属于控制面，负责选择 UPF、分配地址以及建立、修改和释放 PDU Session。业务数据不穿过 SMF，而是由 UE 经 RAN、N3 和 UPF 转发；项目中只需要模拟该控制关系，不应把 SMF 写成数据转发函数。

## 五、板块三：PDCP / RLC

### 负责内容

PDCP 负责 SN、加密、完整性和重排序等协议能力；RLC 将 PDCP PDU 作为 SDU 排队，根据 MAC grant 分段，并维护 AM 重传状态。

### 目标要求

- 保持 `IP/SDAP PDU → PDCP PDU → RLC SDU` 边界。
- PDCP SN 按配置位宽回绕，而不是无限增长。
- 一个 PDCP PDU 对应一个 RLC SDU。
- 分段记录 RLC SN、Segment Offset、SDU ID 和首尾标记。
- PHY 失败能够映射回具体在途 Segment。
- 明确 HARQ 重传和 RLC AM 重传的边界。

### 实际进度

已实现 `PdcpEntity.process()`、`RlcEntity.enqueue()`、`on_grant()`、Segment 列表和重传队列。`actual_sent_bytes` 已经能够回写 PHY allocation。但整个 PDCP Batch 仍可能被当作一个 RLC SDU；同一 SDU 的不同 Segment 使用不同 SN；失败后重传元数据丢失；HARQ 没有执行主体；测试未覆盖真实 PDU 身份和跨层守恒。

### 核心逻辑问题

1. 一个 IP 包经过 SDAP、PDCP 和 RLC 后，各层 SDU/PDU 的关系是什么？
2. Grant 小于一个 RLC SDU 时应如何分段，剩余部分需要保存哪些信息？
3. 同一 RLC SDU 跨多个 grant 时，SN 和 Segment Offset 应如何保持关联？
4. HARQ 重传与 RLC AM 重传分别由谁触发，为什么不能重复记账？
5. `actual_sent_bytes`、RLC PDU bytes 和 MAC transport block bytes 为什么不一定相同？

### 参考答案

1. IP Packet Batch 经 QoS 分类后作为 SDAP 的输入 SDU；SDAP 添加可选 header 后形成 SDAP PDU，并作为 PDCP SDU；PDCP 添加 SN 等 header 后形成 PDCP PDU；每个 PDCP PDU作为一个 RLC SDU。RLC 可以对该 SDU 分段，但不能把多个不可区分的 PDCP PDU 合并成一个匿名字节块。
2. RLC 根据 grant 对 SDU 生成部分 Segment，并保存原 RLC SDU/PDU ID、RLC SN、Segment Offset、长度、首尾标记、剩余范围和重传次数。未发送部分继续留在队列中，不能记作已发送或失败。
3. 在当前项目的简化模型中，同一逻辑 RLC SDU 的所有 Segment 必须共享可追踪的分段身份和 SN，Segment Offset 表示各自覆盖的字节范围。后续 grant 从上次 offset 继续，接收侧才能重组和精确请求重传。
4. HARQ 由 MAC/PHY 根据 ACK/NACK 快速重传同一个 Transport Block；只有在 HARQ 尝试耗尽、上层确认数据未交付后，RLC AM 才把对应 Segment 放入 RLC 重传队列。处于 HARQ buffer 的字节不能同时计入 RLC retransmission，否则会重复发送和重复统计。
5. `actual_sent_bytes` 通常表示 RLC 从队列实际取出的数据预算；RLC PDU bytes 还包含 RLC header；MAC Transport Block 还可能包含 MAC header、控制元素、多个逻辑信道数据和 padding。因此执行器必须分别记录 payload、RLC PDU和TB占用，不能共用一个 `bytes` 字段。

## 六、板块四：Multi-UE / Scheduler / PHR

### 负责内容

汇总所有 UE/DRB 的队列、QoS、切片、信道、BSR、PHR 和 HARQ 输入，输出每个承载获得的 PRB、MCS、Layers 及传输预算。

### 目标要求

- UE 数量由场景配置决定，不能固定为三个。
- 每 tick 对所有活跃承载只调用一次 Scheduler。
- 跨 Java 边界的 `channel_states` 保持 JSON list。
- 所有算法满足 PRB 非负且总量不超过 `total_prbs`。
- 切片负责资源保障，QoS 负责业务优先级，PHR 限制上行可行分配。
- Scheduler 只决策，RLC/MAC/PHY 执行器负责真正发送。

### 实际进度

已实现固定三 UE 场景、PHR 上报通路和四个 Python 算法函数，但只有缓存比例 UL 算法实际调用。切片、QoS、PHR 和 HARQ 没有参与决策；`channel_states` 被改成 dict；默认路径绕过 Java adapter；Max Throughput 可能超额分配 PRB；没有自动化测试。当前不是可合并的调度模块。

### 核心逻辑问题

1. Scheduler 输出 allocation 后，哪些模块负责执行，为什么 Scheduler 不能直接扣减 RLC 队列？
2. 如何保证多次取整、最低一 PRB 和多 DRB 情况下仍满足 PRB 守恒？
3. 为什么跨语言合同要求 `channel_states` 是 list，而 Python 内部可以转换为 dict？
4. PHR 较低时，Scheduler 应如何调整 PRB、MCS 或 Layers？
5. 切片资源保障与 UE 公平性是什么关系？一个 UE 有多个 DRB 时如何避免天然多分资源？
6. 当前 Python 算法是否代表放弃 Java？正确答案应是没有，Java adapter 仍是正式边界。

### 参考答案

1. Scheduler 只输出 allocation。执行器先调用 RLC `on_grant()` 生成实际 Segment，再由 MAC 组装 TB、PHY 执行传输，最后根据 ACK/NACK 和传输结果回写 HARQ、RLC和Metrics。Scheduler 如果直接扣队列，会在实际容量不足、分段或失败时破坏状态和字节守恒。
2. 先计算可分配总量和各切片保底，再进行有上限的整数分配；向下取整后的余数按明确规则二次分发；当活跃承载数大于 PRB 数时允许部分承载获得 0，不能强制每个承载至少 1 PRB。返回前必须校验 `sum(prbs) <= total_prbs`、所有值非负且 allocation 指向有效 UE/DRB。
3. JSON list 可以稳定表达一组包含 `ue_id/gnb_id/direction` 的记录，Python 和 Java DTO 都能按同一 Schema 验证。Python Scheduler 收到后可以构建组合键 dict 加速查询，但不能把该运行期索引结构写回跨语言合同，尤其不能依赖复杂对象键或隐式键格式。
4. PHR 较低表示 UE 发射功率余量不足。Scheduler 应限制该 UE 同时占用的 PRB 数，必要时降低需要更高功率或可靠性的 MCS/Layers，并通过功率可行性检查避免产生 UE 无法执行的 allocation；具体关系应由统一功控模型提供，而不是任意阈值。
5. 先在切片层满足 `min/max PRB` 和优先级约束，再在切片内部按 QoS、队列、信道和公平状态分配给 UE/DRB。应对同一 UE 的多个 DRB 先聚合或设置 UE 级上限，避免仅因 DRB 数量更多就获得多份最低资源。
6. 没有放弃 Java。正式入口仍应是 `JavaSchedulerAdapter`，Java不可用时才由同合同的 Python Scheduler fallback。Python 算法还可作为参考实现和测试 Oracle；成员分支绕过 adapter 只是当前实现偏差，不代表架构决策。

## 七、板块五：Channel Model

### 负责内容

从地图和基站/UE 几何关系生成传播损耗、接收功率、噪声、干扰、SINR、CQI/PER，最终形成 Scheduler 和 PHY 使用的 `ChannelState`。

### 目标要求

- 将地图坐标转换为有证据的物理米制距离。
- 支持 UMi、InH 和 O2I 等场景选择。
- 区分 UL/DL 发射功率、天线增益和噪声参数。
- 生成可复现、空间相关的 Shadow Fading。
- 建立 `PathLoss → Link Budget → SINR → CQI/PER` 完整链路。
- 为每个 UE、方向和 tick 独立输出 ChannelState。

### 实际进度

已实现传播几何、坐标标定框架、3GPP UMi/InH 路损、O2I 穿透模型和 Geometry adapter。独立大尺度路损库完成度较高，但 Bristol 标定仍为 `provisional`；没有接入 `channel.py`；缺少接收功率、噪声、干扰、SINR、CQI 以及随机衰落。主模拟仍运行 baseline channel。

### 核心逻辑问题

1. 为什么 Path Loss 不能直接等同于 SINR、CQI 或完整 ChannelState？
2. 上行 Link Budget 为什么必须使用 UE 发射功率，而不是 gNB 发射功率？
3. Shadow Fading 如何保证相邻位置相关，同时在相同 seed 下可以复现？
4. O2I 外墙穿透损耗与地图墙体损耗为什么不能重复累加？
5. Bristol 标定为 provisional 时直接运行会产生什么后果？
6. ChannelState、Scheduler 建议的 MCS 和 PHY 实际错误率之间应如何分工？

### 参考答案

1. Path Loss 只描述传播造成的功率衰减。接收功率还取决于方向正确的发射功率、天线和波束增益；SINR 还需要噪声、干扰和随机衰落；CQI/PER 是根据 SINR 和链路映射得到的离散结果；ChannelState 则是提供给 Scheduler 的完整、带身份和有效期的链路快照。
2. 上行信号由 UE 发射、gNB 接收，因此必须使用 UE 发射功率、UE发送天线增益和gNB接收增益。gNB发射功率只适用于下行；方向错误会系统性高估上行覆盖、SINR和吞吐量。
3. 使用由 `simulation seed + carrier/model identity` 固定的空间随机场，并按相关距离建立协方差、滤波网格或等价的相关采样。相近位置共享相关残差，相同 seed 和位置得到相同结果；不能每 tick 独立抽样，否则静止 UE 的信道会无规律跳变。
4. 两项都可能描述同一次外墙穿透。如果3GPP O2I模型已经计算 external wall loss，地图几何只能用于判断建筑、材料类别和室内深度，不能再次累加同一堵墙的 penetration loss。必须指定唯一字节之外的“物理损耗所有者”，其他模块只提供输入。
5. 地图单位到米的比例不可信会直接导致传播距离错误，随后 Path Loss、接收功率、SINR、CQI和吞吐量全部失真。生产运行应拒绝 provisional calibration，或要求显式 opt-in 并在结果中保留警告，直到地图锚点和物理尺度得到确认。
6. Channel Model 根据物理链路输出 SINR、PER曲线或保守的MCS建议；Scheduler结合QoS、切片和资源状态选择最终MCS/Layers；PHY执行器根据实际PRB、MCS、Layers和ChannelState计算容量及传输成功/失败，并把反馈送入后续HARQ和调度。三者不能同时修改同一传输结果。

## 八、跨模块统一问题

1. 从 `agent_id` 到最终 `tb_id/harq_process_id`，完整身份链如何保持？
2. 100 MiB 应用负载经过协议头、重传和丢失后，哪些字节可以计入业务完成度？
3. 一个 UE 业务完成时，为什么不能直接结束 Agent、其他 UE 或整个场景？
4. RLC 失败、HARQ 失败、N3/N6 丢失分别由哪个指标账本记录？
5. 多 Agent 基底加入后，哪些对象应长期保留，哪些对象应在 Service 完成后释放？

### 参考答案

1. 每层创建新对象时都保留上游 ID：`agent_id → intent_id → service_instance_id → pdu_session_id → flow_id/packet_batch_id → qfi → drb_id → sdap_pdu_id → pdcp_pdu_id/pdcp_sn → rlc_sdu_id → rlc_sn/segment_offset → allocation_id → tb_id/harq_process_id`。接收结果必须引用发送对象的 ID，禁止靠列表下标或名字拼接反推身份。
2. 只有 Data Network 最终确认交付的应用 payload 可以增加业务完成度。IP、SDAP、PDCP、RLC、MAC header和padding属于协议开销；同一payload的HARQ/RLC重传只增加无线传输开销，不能再次增加已交付payload。
3. Agent、Intent、UE和Service拥有独立生命周期。一个Service终止只更新所属Intent和Agent状态；其他上下文继续运行。场景应根据所有配置任务、Agent行为序列或显式结束策略判断终止，而不是复用第一个完成标志。
4. RLC最终失败由所属RLC Entity和Service Counter记录具体Segment及payload归属；HARQ尝试和耗尽由MAC/PHY HARQ Process账本记录TB；N3和N6分别由核心网链路指标记录。全局指标只能从各Service分项聚合，不能让同一失败字节同时进入多个永久丢失类别。
5. Agent Context、UE/AMF Context以及仍有效的注册和PDU Session可以跨多个Intent保留。某个Service终止且队列、HARQ和在途状态清空后，可以释放其Flow、SDAP映射、PDCP/RLC Entity和临时传输对象，但应归档终态指标和身份关系，供日志、回放和Agent下一轮规划使用。

## 九、会议评估方式

| 分数 | 判断标准 |
| ---: | --- |
| 0 | 无法解释模块输入输出 |
| 1 | 能解释术语，但无法说明状态变化 |
| 2 | 能说明上下游合同和错误后果 |
| 3 | 能对应到代码、测试和守恒规则 |
| 4 | 能提出符合全局架构的修复方案 |

建议每位成员先用五分钟讲解自己的输入、核心状态、输出和完成条件，再从本模块问题中随机选择三个追问。不能解释错误情境和下游后果的实现，不应视为已完成。

## 十、审计依据

- `backup/global_review_reports/2026-08-01_01_five-part-integration-review.zh.md`
- `backup/haoyu_amf/review_reports/2026-08-01_02_recheck.zh.md`
- `backup/boyu_area-b/review_reports/2026-08-01_01_initial-review.zh.md`
- `backup/xizhe_pdcp_rlc/review_reports/2026-08-01_02_update-review.zh.md`
- `backup/tr22068_scheduling-tests/review_reports/2026-08-01_02_integration-assessment.zh.md`
- `backup/zhiqian_3gpp/review_reports/2026-08-01_02_update-review.zh.md`
