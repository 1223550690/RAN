# 五成员分支合并计划(2026-08-06 审视版)

> 目标:除 `tr22068/scheduling-tests` 外,尽量合并 boyu / haoyu / xizhe / zhiqian
> 四个成员的分支到集成主线,修复衔接与逻辑 bug,使系统达成设计最终目标。
> 本文件是操作手册:按章节顺序逐步执行、每步检查,并记录各模块剩余工作。

---

## 0. 现状总览(审视结论)

所有成员分支均分叉自 `han/mvp`(= `05a67b3 "Versions tested"`,即 main 的合并基线)。
集成主线 = `backup/worktrees/final_version`(han/mvp + Agent 集成,未提交)。

| 分支 | 增量 | 改动模块 | 与主线的冲突程度 |
|---|---|---|---|
| `zhiqian/3gpp`(含 prop-geom 全部) | +8041 行 / 38 文件 | ran/radio 3GPP 信道(O2I 路径损耗/信道管道/坐标标定)+ 大量测试 | 🟢 低(纯新增,唯一同文件:channel.py 演进版) |
| `haoyu_amf` | +75 行 / 4 文件 | amf.py、access/selector.py(自动接入选择) | 🟢 低 |
| `xizhe_pdcp/rlc` | +1371 行 / 11 文件 | pdcp.py(+102)/rlc.py(+307) 实体化扩展、bearer.py +2 字段、tests | 🟡 中(scenario.py 改动弃用) |
| `boyu/area-b` | +3067 行 / 25 文件 | SMF/QoS/SDAP/IP 流量、contracts 校验收紧、configs、tests | 🟠 中高(contracts 校验 + establish_pdu_session 签名 + scenario.py) |
| `tr22068/scheduling-tests` | +444/-168 / 14 文件 | 多 UE scenario 重写、4 种调度算法、PHR 功率、dict 化状态 | 🔴 高(暂不合并,见 §6) |

**关键结论**:
1. 成员对 `ran/scenario.py` 的改动**一律弃用**(其单意图/硬编码多意图架构已被 `MultiAgentRanScenario` 取代),只取模块文件。
2. 除 `channel.py`(zhiqian 演进版)与 `scenario.py` 外,成员改动**均为向后兼容扩展**(保留旧接口 + 新增)。
3. 唯一必须让成员(boyu)改的:**`establish_pdu_session` 补 `ue_ip` 兼容参数**(否则合并后 Agent 意图管道 TypeError)。

---

## 1. 合并总策略

- **顺序**:风险从低到高 —— zhiqian → haoyu → xizhe → boyu。
- **方式**:在 final_version worktree 建集成分支 `integration/merge`;每合入一个成员分支后立即跑:
  1. `python -m py_compile`(语法)
  2. 该成员自带 tests(如 `tests/radio/`、`tests/test_pdcp.py`、`tests/test_area_b_modules.py`)
  3. Agent 闭环冒烟(30 tick, potions 小场景,模板模式)
- **贡献者体现**:合并提交保留成员作者(`git merge --no-ff` 或 cherry-pick 保留 author),由成员推 PR 的分支按 PR 合入;han 只做集成适配提交。
- **回退**:每步合并前打 tag(`merge-step-N`),失败可 `git reset --hard` 回退。

---

## 2. 逐分支合并计划

### 2.1 zhiqian/3gpp(第 1 步,低风险)

**合并内容**(全部新增/演进):
- `ran/radio/`:channel_pipeline.py、channel_policy.py、pathloss_3gpp.py、pathloss_3gpp_adapter.py、pathloss_3gpp_o2i.py、geometry.py、coordinate_calibration.py
- `ran/contracts/radio.py`(新增合同)
- `configs/ran/channel_model.json`、`coordinate_calibration.json`
- `tests/radio/`(约 12 个测试文件)
- `docs/3gpp_*`、`docs/channel_runtime_integration_zh.md`、`experiments/debug_3gpp_*`

**同名文件需人工比较**:`ran/radio/channel.py`(主线 60 行 vs 分支 130 行演进版)——保留分支版,并确认 `estimate_channel` 签名兼容(主线 `ran/scenario.py` 与 `ran/radio/__init__.py` 引用它)。

**衔接检查**:
- [ ] `ran/radio/__init__.py` 导出补全(zhiqian 是否新增导出项)
- [ ] `channel.py` 的 `estimate_channel` 是否仍被 `MultiAgentRanScenario` 调用且签名一致
- [ ] `python -m pytest tests/radio/ -x -q` 全绿
- [ ] Agent 闭环冒烟通过

**注意**:zhiqian 分支内 `prop-geom` 是 `3gpp` 的子集(文件完全包含),**只合并 3gpp 分支**。

### 2.2 haoyu_amf(第 2 步,低风险)

**合并内容**:
- `ran/core/amf.py`(+17:注册增强)
- `ran/access/selector.py`(+26:接入自动选择 5g/wifi/auto)

**弃用**:`ran/scenario.py` 的硬编码第二 Agent(intent2/ue_state2)改动。

**衔接检查**:
- [ ] `select_access(request, gnb)` 签名不变(主线调用方 `ran/scenario.py`、`ran/ue/request.py`)
- [ ] `register_ue` 流程与 amf.py 增强不重复
- [ ] Agent 闭环冒烟(注册 → 意图 → 完成)通过

### 2.3 xizhe_pdcp/rlc(第 3 步,中风险)

**合并内容**:
- `ran/protocol/pdcp.py`(+102:实体化扩展,保留 `build_pdcp_batch`)
- `ran/protocol/rlc.py`(+307:实体化扩展,保留 `build_rlc_queue`、`apply_transmission_to_rlc`)
- `ran/contracts/bearer.py`(+2:`RlcQueue.delivered_bytes/dropped_bytes`,默认值兼容)
- `ran/protocol/__init__.py`(导出扩展)
- `tests/test_pdcp.py`、`tests/test_rlc.py`、`tests/test_integration.py`、`tests/conftest.py`

**弃用**:`ran/scenario.py` 中把 `build_pdcp_batch/build_rlc_queue` 换成 `PdcpEntity/RlcEntity` 直接实例化的改动(主线的 `MultiAgentRanScenario` 保持函数式调用;实体类作为后续演进,由 xizhe 后续 PR 把管道切换到实体并自行验证)。

**衔接检查**:
- [ ] `build_pdcp_batch(traffic, drb)` / `build_rlc_queue(pdcp_batch, drb)` / `apply_transmission_to_rlc` 签名与主线一致
- [ ] `tests/test_pdcp.py`、`tests/test_rlc.py` 通过
- [ ] Agent 闭环冒烟(意图 → PDCP → RLC → 调度 → 完成)通过

### 2.4 boyu/area-b(第 4 步,中高风险,收尾)

**合并内容**:
- `ran/core/smf.py`(+261:SMF IP QoS)
- `ran/qos.py`(+330:QoS 流分类器)
- `ran/traffic/ip.py`(+302)、`ran/traffic/service_profile.py`(+192,读嵌套 profiles)
- `ran/protocol/sdap.py`(+436,保留 `map_qos_flow_to_drb`/`process_sdap` 旧接口)
- `ran/contracts/bearer.py`、`qos.py`、`traffic.py`(字段扩展 + **`__post_init__` 校验收紧**)
- `configs/ran/ip_endpoints.json`、`smf.json`、`service_profiles.json`(嵌套结构)
- `tests/test_area_b_modules.py`(+600)
- `docs/area_b_smf_ip_qos_sdap_zh.md`

**弃用**:`ran/scenario.py` 的 +18 行(RanUploadScenario 内,类已被 MultiAgentRanScenario 取代;其中 `build_qos_flow(..., traffic=...)` 参数在主线管道调用时**可选择性传入**)。

**⛔ 前置(必须让 boyu 更新,优先级:高)**:
> `ran/core/smf.py` 的 `establish_pdu_session(ue, request, *, slice_id, smf=None)`
> 补回可选参数 `ue_ip: str | None = None`(主线 `MultiAgentRanScenario` 用
> `ue_ip=_mock_ue_ip(index)` 做多 UE 地址隔离)。一行兼容改动,以 boyu 名义提交。

**衔接检查(重点,校验收紧的波及面)**:
- [ ] Agent 意图链路构造值全部合规:video_upload/message/video_call/file_transfer → qfi/five_qi/priority/delay/per 全部在新校验范围内(主线硬编码表 game qfi=80 已随 boyu 新表修正)
- [ ] `establish_pdu_session` 兼容参数生效(Agent 闭环不再 TypeError)
- [ ] `ran/scheduler/java_adapter.py:65` 反序列化 `QoSFlow(**item)/Drb(**item)` 在 Java transport 下满足校验(缺 ue_ip/qfi 违规会抛异常)——**需与 Java 侧确认或加容错**
- [ ] `service_profile_for` 返回结构与主线 `build_qos_flow` 读取方式一致(boyu 版读嵌套 profiles)
- [ ] `tests/test_area_b_modules.py` 通过
- [ ] Agent 闭环冒烟 + 全量回归通过

### 2.5 合并后整体回归(第 5 步)

- [ ] `python -m py_compile` 全仓
- [ ] 全部成员 tests + 既有 tests 通过
- [ ] potions Agent 闭环(模板模式)30-120 tick 通过
- [ ] Bristol 模板(bristol 同建筑内转移)端到端通过
- [ ] LLM 模式单学生冒烟(deepseek,可重放)
- [ ] 实时预览页面渲染正常(规划路线可视化)

---

## 3. 各模块剩余工作(合并后)

| 模块 | 负责人 | 已完成 | 剩余 |
|---|---|---|---|
| Agent/决策器 | han | LLM/模板双模式、同建筑限制、闭环验证 | LLM 全图(bristol 不限建筑)实测;preview 长期运行验证;Java round-trip 未验证 |
| SMF/IP QoS/SDAP | boyu | 模块实现 + 单测 | `establish_pdu_session` 兼容参数(**必要,尽快**);与 PDCP 的正式衔接(9bbe466 已做一半,合入后按 xizhe 实体类演进) |
| PDCP/RLC | xizhe | 实体化 + 分段 | 把 `MultiAgentRanScenario` 管道从函数式切换到实体类(不紧急,后续 PR);与 SDAP 输出衔接 |
| 3GPP 信道 | zhiqian | O2I 路径损耗、信道管道、坐标标定 | 信道管道接入 runtime 的正式开关(commit d7be862 已集成,合入后验证与既有 `estimate_channel` 的共存/切换策略) |
| AMF/接入 | haoyu | Module 1(UE 注册/接入选择) | Module 2+ 未开始;接入选择结果在 Agent 意图中的体现(暂用 5g 默认) |
| 场景数据 | — | — | Bristol:Football Ground 补门(必要);channel_id 编辑器分组(P2);显式墙盖门已由算法兜底 |
| 调度器 | tr22068 | 4 种算法 + PHR(未合并) | 见 §6 |

---

## 4. 执行清单(一步步操作)

```bash
cd /d/Code/RAN/backup/worktrees/final_version
git checkout -b integration/merge          # 1. 建集成分支(保留未提交的 agent 集成)
git tag merge-step-0                       # 2. 基线 tag

# —— Step 1: zhiqian/3gpp ——
git merge --no-ff origin/zhiqian/3gpp     # 3. 合并(注意:会带入 han/mvp 基线差异,先 cherry-pick 只取 zhiqian 的提交:96ee5dd..d7be862)
# 或按文件 cherry-pick:git cherry-pick 32f7021 c20d91d d7be862
python -m py_compile                      # 4. 语法
python -m pytest tests/radio/ -x -q       # 5. 信道测试
# 6. Agent 闭环冒烟(见 §5 命令)
git tag merge-step-1

# —— Step 2: haoyu_amf ——
git cherry-pick 7db3b81 94cd378           # 只取 amf.py / selector.py 相关提交(含 scenario.py 的丢弃)
# 检查 ran/core/amf.py、ran/access/selector.py
# 冲突时:保留主线 ran/scenario.py,取分支 amf.py/selector.py
git tag merge-step-2

# —— Step 3: xizhe_pdcp/rlc ——
git cherry-pick 3e8b54a 2d9afa6 6f5aafe
# 冲突时:保留主线 ran/scenario.py;bearer.py 取合并版
python -m pytest tests/test_pdcp.py tests/test_rlc.py -x -q
git tag merge-step-3

# —— Step 4: boyu/area-b(先等 boyu 补 establish_pdu_session 兼容参数)——
git cherry-pick 96ee5dd 9bbe466 cdbc48e
# 冲突时:ran/scenario.py 保留主线;contracts/qos.py 等取 boyu 版并全链路验证
python -m pytest tests/test_area_b_modules.py -x -q
git tag merge-step-4

# —— Step 5: 整体回归(§2.5 清单)——
```

## 5. 冒烟命令(每步后)

```bash
# Agent 闭环(potions,模板模式,30 tick)
python -m simulation.main -s potions_teacher_office --agent-sim --ticks 60 --tick-ms 10

# Bristol 同建筑内转移
python -m simulation.main -s bristol_topology --agent-sim \
  --agents-config configs/agents/deterministic_three_agents_bristol.json \
  --ticks 300 --tick-ms 50 --agent-speed 2.0
```

---

## 6. tr22068/scheduling-tests:合入评估

### 他的目标(为项目完整)
1. **多用户/多 UE 场景**:scenario 支持多个 UE 并行(他已在分支里硬编码实现)。
2. **可插拔调度算法**:4 种算法(roundRobinDL / maxThroughputDL / grantBasedUL / weightedUL)+ BSR/CQI 排序。
3. **功率余量报告(PHR)**:`transmit()` 用 `ue_state.cmax_transmit - (10log(PRB)+gnb.nominal_pusch+0.8·pathloss)` 计算。
4. **状态字典化**:scenario 的 users/snapshot 用 `dict[str, dict]`(按 agent_id/ue_id 索引)替代 dataclass 列表。

### 与主线的冲突(为什么不能直接合并)
- 他的 `ran/scenario.py` **整类重写**(多用户硬编码),与 `MultiAgentRanScenario`(动态 agent 集合)是两套架构——直接合并会破坏 Agent 子系统。
- `transmit()` 签名增加 `ue_state/gnb` 必选参数,破坏主线调用方。
- 状态 dict 化与 `AgentStateSnapshot` dataclass + `AgentStateProvider` 协议冲突。

### 他合入主线**最少需要做的工作**(按优先级)
1. **调度算法插件化**(必要):把 4 个算法函数改造成 `PythonBaselineScheduler` 的算法选择参数
   (`scheduler(algorithm="grant_based_ul")` 或注册表),**保持 `SchedulerRequest/SchedulerResult` 合同不变**。
   主线 `MultiAgentRanScenario` 默认调度器即可切到他的算法;他的 scenario 重写全部放弃。
2. **PHR 可选化**(必要):`transmit()` 的 `ue_state/gnb` 参数改为**可选**(默认 None 时跳过 PHR),
   或经合同扩展带默认值;主线调用点不动。
3. **agent_state 字典化诉求 → 适配方案**(必要,讨论后定):主线提供
   `get_agent_states()` 的 `dict[str, AgentStateSnapshot]` 视图(按 agent_id 索引)作为**附加接口**,
   不改变现有 Provider 协议;或在他的调度器内部需要时自行索引。
4. **测试重写**(必要):他的调度测试针对旧 scenario,改为针对 `PythonBaselineScheduler`
   的单元测试(输入固定 SchedulerRequest,断言分配结果)。
5. `UEState` 的 `cmax_transmit/ue_pusch` 字段:作为**可选字段带默认值**合入(boyu 的
   contracts 校验不涉及 UEState,无冲突)。

### 建议推进方式
- 以"调度器增强 PR"形式由 tr22068 提交(贡献者归他):算法 + PHR + UEState 字段,放弃 scenario 重写与 dict 化强制要求(提供 dict 视图接口)。
- 他若坚持 dict 化 agent_state,可以在 `AgentStateProvider` 上**增加** dict 访问器,但核心合同不动——这是最低成本达成双方目标的方式。

---

## 7. 待成员配合事项汇总

| 优先级 | 成员 | 事项 | 说明 |
|---|---|---|---|
| 🔴 必要 | boyu | `establish_pdu_session` 补 `ue_ip` 可选参数 | 不补则 Agent 意图管道合并后 TypeError |
| 🟡 建议 | boyu | `channel_id` 场景数据分组(编辑器 P2,可后置) | 已由几何合并兜底 |
| 🔴 必要 | 你/编辑器 | Bristol `Football Ground` 补入口门 | 区域图不连通(doors=0 直穿) |
| 🟡 建议 | xizhe | 后续 PR:管道切换到 PdcpEntity/RlcEntity | 不紧急,合入后自行演进 |
| 🟡 建议 | tr22068 | 按 §6 改造后以调度器 PR 合入 | 先对齐方案再动手 |
