# 合同 V1 与多 Agent 基底更新报告

日期：2026-08-02  
分支：`final_version`  
基线：`fadb403`  
测试状态：未运行（遵守项目约定）

## 1. 本次目标

- 冻结后续成员模块共同使用的合同、命名和守恒规则。
- 将单 UE、单业务场景改造成固定规模的集合式多 Agent 编排。
- 提供可替换的 Agent 状态接口和当前静态 mock。
- 默认建立视频上传、即时消息和语音上传三个 Agent。

## 2. 新增文件与功能

| 文件 | 功能 |
| --- | --- |
| `docs/integration/frozen_contracts_v1_zh.md` | 合同 V1、身份作用域、Scheduler JSON 和守恒规则 |
| `docs/integration/change_log_zh.md` | `final_version` 长期集成变更索引 |
| `ran/orchestration/definitions.py` | 不可变场景和 Agent 定义、默认三 Agent 配置 |
| `ran/orchestration/agent_state.py` | `AgentStateProvider` 接口与静态 mock |
| `ran/orchestration/contexts.py` | Agent、Intent、UE、Service 四类运行上下文及业务账本 |
| `ran/orchestration/README.zh.md` | 模块中文接口文档 |

## 3. 修改文件与功能

### 公共合同

- `ran/contracts/common.py`：增加 `CONTRACT_VERSION=1.0`。
- `ran/contracts/agent.py`：增加全局 `intent_id`、稳定 `service_type`、应用 payload 字段和 `AgentStateSnapshot`。
- `ran/contracts/ue.py`：UERequest 增加 Intent/Service 身份。
- `ran/contracts/qos.py`：QoSFlow 增加 UE 和 Service 来源。
- `ran/contracts/scheduler.py`：增加合同、仿真、request 和 gNB envelope。
- `ran/contracts/radio.py`：MacAllocation 增加 `allocation_id`。

### 编排与入口

- `ran/scenario.py`：新增 `MultiAgentRanScenario`，每 tick 汇总全部活跃 Service，只调用一次 Scheduler，再逐 Service 执行。
- `ran/engine.py`：新增 `build_scenario()` 和 `run_scenario()`；旧 upload 方法作为兼容入口。
- `simulation/main.py`：aggregate 模式逐 Agent 输出结果，并输出全局聚合结果。
- `simulation/simulation_loop.py`：tick 日志逐 Service 输出完整信息，并增加全局汇总行。
- `editor/live/livePreview.js`：右侧当前 tick 区域逐 Service 显示，避免混用首个业务字段和全局 progress。

### 最小守恒修复

- `ran/scheduler/python_baseline.py`：使用最大余数法分配整数 PRB，保证总量不超过基站资源。
- `ran/radio/phy.py`、`ran/protocol/rlc.py`：真实 HARQ executor 建立前禁用无人持有的 HARQ pending；AM 失败进入 RLC，UM 失败进入 drop。
- `ran/core/smf.py`：允许场景为多个 UE 注入互不冲突的 mock IP。
- `ServiceCounters`：分别累计 protocol delivered/drop，再按原始 payload 与协议总字节比例映射，避免把 PDCP header 计为业务交付。

### 默认业务

- 视频上传：100 MiB，`video_upload -> embb`。
- 即时消息：4 KiB，`message -> mmtc`。
- 语音片段上传：1 MiB，`voice_upload -> urllc`。
- `configs/ran/service_profiles.json` 和代码表增加 `voice_upload` 的临时 QoS profile。

## 4. 新状态输出

```text
agent_count
agent_states[]
service_states[]
results[]
progress              # 全局聚合
scheduler_request
scheduler_result
```

为避免立即破坏旧预览，顶层仍临时映射第一个 Service 的 `result`、`ue_request`、`channel`、`transmission` 等字段。新模块必须读取列表结构。

## 5. 当前验证与保护

场景运行时会检查：

- AgentStateProvider 每 tick 返回的 Agent 集合与场景建立时一致。
- SchedulerResult 对应当前合同版本、simulation、request 和 tick。
- allocation 指向有效 UE/DRB、没有重复、字节非负且不超过队列。
- allocation PRB 总量不超过 `total_prbs`。
- 没有获得 allocation 的业务保持等待，不会被误判完成。

## 6. 已知限制

以下逻辑明确仍为最小实现，留给后续成员模块合并：

1. IP traffic 仍是一次性字节批次，不是逐 tick `IpPacketBatch`。
2. PDCP/RLC 仍未形成完整 PDU、SDU 和 segment 身份；当前 RLC grant 仅按队列字节截断。
3. Java adapter 当前仍调用 Python fallback，没有外部 Java transport。
4. HARQ 状态机未实现，因此当前 mock 将失败直接交给 RLC AM 或 UM drop。
5. 信道仍使用 baseline，3GPP path-loss 尚未接入 runtime。
6. Live Preview 地图上的 Agent 图标仍未接入新的 AgentStateSnapshot；右侧 RAN 状态和 tick 日志已包含全部 Service。
7. 当前 orchestrator 的执行映射假设一个 `(ue_id, drb_id)` 对应一个独立 Service queue；共享 DRB 需要在正式 RLC entity 接入时改为 segment 归属账本。
8. 本次没有运行单元测试、集成测试或模拟命令，不能声明运行验证通过。

## 7. 后续建议顺序

1. 审核并确认合同 V1。
2. 小改后合并 Access/AMF 增量。
3. 按合同迁移 SMF、IpPacketBatch、QoS 和 SDAP。
4. 重构迁移 PDCP/RLC PDU 与 segment 实体。
5. 接入 channel runtime、MAC/PHY executor、HARQ 和 metrics。
6. 在稳定合同上接入 Python/Java Scheduler 和后续 AI slicing。

## 8. 工作树隔离

本次修改位于 `backup/worktrees/final_version` 的独立 `final_version` worktree。原 `han/mvp` 工作树中的用户未提交 `.gitignore` 和协议文档修改未被带入或覆盖。
