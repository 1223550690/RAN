# 3GPP Path-Loss 分阶段实现方案

## 1. 方案目的

本文档把 `docs/3gpp_pathloss_design_zh.md` 转换成可执行、可测试、可单独
review 的实施阶段。

总原则：

```text
公式核心先独立实现
纯数值验证先于地图接入
Geometry adapter 先于 runtime integration
O2I、shadow fading、CKM 分开实施
保留当前 channel baseline
不修改共享 contract
```

当前工作位置：

```text
worktree: D:\AI_RAN_SANBOX\RAN_3GPP
branch:   zhiqian/3gpp
baseline: d21a43d
```

本方案不会自动 push。每一阶段先在本地完成、测试和 review，再决定是否
commit 或 push。

---

## 2. 总体阶段

| 阶段 | 名称 | 主要产物 | 是否接 runtime |
| --- | --- | --- | --- |
| 0 | 设计冻结与基线确认 | 设计、实施方案、测试基线 | 否 |
| 1A | 内部接口与输入验证 | dataclass、错误类型、validation | 否 |
| 1B | UMi 公式核心 | UMi LOS/NLOS、breakpoint | 否 |
| 1C | InH 公式核心 | InH LOS/NLOS | 否 |
| 2 | 纯数值 debug 与对比 | CLI、JSON report、FSPL 对比 | 否 |
| 3 | Geometry/Calibration adapter | read-only adapter、Bristol dry run | 否 |
| 4A | O2I 决策与数据准备 | outdoor LOS、材料 profile、随机策略 | 否 |
| 4B | O2I 实现 | building penetration 组合模型 | 否 |
| 5 | Shadow fading 与 CKM | spatial prior / residual | 否 |
| 6 | 可选 runtime integration | model selector、baseline fallback | 可选 |

必须按顺序完成 Gate。阶段 4、5、6 需要新的团队确认，不属于第一轮实现。

---

## 3. 阶段 0：设计冻结与基线确认

### 3.1 目标

在写公式代码前固定：

- 标准版本和条款。
- 第一阶段场景。
- 输入/输出字段。
- 单位和适用范围。
- 不做项。
- 回归基线。

### 3.2 文件

```text
docs/3gpp_pathloss_design_zh.md
docs/3gpp_pathloss_implementation_plan_zh.md
```

### 3.3 执行步骤

1. Review 公式、单位和固定测试值。
2. 确认第一阶段只做 UMi/InH deterministic mean path loss。
3. 确认 `carrier_frequency_mhz` 是 API 输入单位。
4. 确认不修改 Geometry、Calibration 和 `ChannelState`。
5. 记录未决问题，不在实现中自行猜测。
6. 运行现有基线。

### 3.4 验证命令

```powershell
python -m unittest discover -s tests
python -m ran.demo -s bristol_topology --mode tick --max-ticks 10
git status --short
```

### 3.5 Gate 0

- `36/36` 现有测试通过。
- MVP 正常到 tick 10。
- 设计文档和实施方案完成 review。
- 没有修改代码或共享接口。

建议提交：

```text
Document staged 3GPP path-loss implementation
```

---

## 4. 阶段 1A：内部接口与输入验证

### 4.1 目标

只建立新模块的内部 contract 和防误用机制，不实现 UMi/InH 公式。

### 4.2 新增文件

```text
ran/radio/pathloss_3gpp.py
tests/radio/test_pathloss_3gpp.py
```

### 4.3 `pathloss_3gpp.py` 初始内容

新增：

```text
PathLossRequest
PathLossResult
PathLossInputError
PathLossApplicabilityError
scenario constants
LOS/NLOS constants
standard/version constants
input validation helpers
frequency conversion helpers
2D/3D consistency helper
```

暂不新增到 `ran/radio/__init__.py`，避免过早把内部 API 变成公共入口。

### 4.4 实现顺序

1. 定义字符串常量和标准版本常量。
2. 定义 frozen/slots dataclass。
3. 验证所有数值是 finite。
4. 验证频率、距离和高度为合法正值。
5. 验证 `d3D >= d2D`。
6. 验证：

   ```text
   d3D ≈ sqrt(d2D^2 + (hBS-hUT)^2)
   ```

7. 建立 applicability warning/error 收集机制。
8. 建立 `allow_extrapolation=False` 默认行为。

### 4.5 第一批测试

```text
合法 UMi request 通过 validation
合法 InH request 通过 validation
未知 scenario 拒绝
未知 los_state 拒绝
NaN/infinity 拒绝
零/负频率拒绝
负 d2D 拒绝
零/负 d3D 拒绝
d3D < d2D 拒绝
高度非正拒绝
2D/3D/高度不一致拒绝
UMi effective height 非正拒绝
```

### 4.6 明确不改

- `channel.py`
- `geometry.py`
- `coordinate_calibration.py`
- `contracts/`
- `ran/radio/__init__.py`
- scheduler、PHY、metrics

### 4.7 Gate 1A

- 所有 validation 测试通过。
- 原 36 项测试继续通过。
- 模块不能 import Geometry、MapService 或 ChannelState。
- `git diff` 只包含两个新增文件和已批准文档。

建议提交：

```text
Add validated 3GPP path-loss request contract
```

---

## 5. 阶段 1B：UMi Street Canyon 公式核心

### 5.1 目标

实现并独立验证：

```text
UMi effective breakpoint
UMi LOS PL1
UMi LOS PL2
UMi NLOS candidate
UMi NLOS max guard
UMi shadow-fading std metadata
```

### 5.2 实现步骤

1. 实现 MHz → GHz 和 MHz → Hz 转换。
2. 实现 UMi `hE=1 m` effective height。
3. 实现：

   ```text
   dBP' = 4 hBS' hUT' fc_Hz / c
   ```

4. 实现 UMi LOS PL1。
5. 实现 UMi LOS PL2。
6. 在 breakpoint 上固定分支规则：

   ```text
   d2D <= dBP' → PL1
   d2D >  dBP' → PL2
   ```

7. 实现 UMi NLOS candidate。
8. 实现：

   ```text
   PL_NLOS = max(PL_LOS, PL_NLOS_candidate)
   ```

9. 返回：

   ```text
   formula_id
   breakpoint_distance_m
   los_reference_path_loss_db
   nlos_candidate_path_loss_db
   shadow_fading_std_db
   ```

### 5.3 测试顺序

1. `3500 MHz, 10 m, 1.5 m` 的 breakpoint 为 `210 m`。
2. `d2D=10 m` 使用 PL1，结果约 `66.761033 dB`。
3. `d2D=100 m` 使用 PL1，结果约 `85.314189 dB`。
4. `d2D=210 m` 两条公式连续，结果约 `92.055431 dB`。
5. `d2D=300 m` 使用 PL2，结果约 `98.244261 dB`。
6. UMi NLOS `d2D=100 m` 结果约 `104.643832 dB`。
7. LOS 的 SF 为 `4 dB`。
8. NLOS 的 SF 为 `7.82 dB`。
9. `d2D < 10 m` 默认拒绝。
10. `allow_extrapolation=True` 时允许 debug 结果并标记 warning。

### 5.4 Gate 1B

- breakpoint 前后连续。
- 公式固定值误差在 `1e-6 dB` 级别。
- NLOS 不能低于同输入的 LOS。
- 结果明确说明 PL1/PL2/NLOS 公式 ID。
- 原测试和 MVP 不变。

建议提交：

```text
Implement 3GPP UMi path-loss formulas
```

---

## 6. 阶段 1C：InH Office 公式核心

### 6.1 目标

实现并独立验证：

```text
InH LOS
InH NLOS candidate
InH NLOS max guard
InH shadow-fading std metadata
```

### 6.2 实现步骤

1. 实现 InH LOS。
2. 实现 InH NLOS candidate。
3. 实现：

   ```text
   PL_NLOS = max(PL_LOS, PL_NLOS_candidate)
   ```

4. 实现 `1 m <= d3D <= 150 m` applicability。
5. 对非参考 `hBS=3 m / hUT=1 m` 返回 warning。
6. 不实现 optional InH-NLOS 公式。

### 6.3 测试顺序

1. `d3D=10 m` LOS 结果约 `60.581361 dB`。
2. `d3D=10 m` NLOS 结果约 `69.147294 dB`。
3. `d2D=0 m, d3D=2 m` 的 NLOS 结果由 LOS max guard 决定，
   约 `48.489180 dB`。
4. LOS 的 SF 为 `3 dB`。
5. NLOS 的 SF 为 `8.03 dB`。
6. `d3D > 150 m` 默认拒绝。
7. 非参考高度产生 `non_reference_height` warning。

### 6.4 Gate 1C

- UMi 和 InH 通过同一个 dispatcher 调用。
- 场景之间不共享错误的距离规则。
- 所有公式测试和 validation 测试通过。
- 原 36 项测试与 MVP 继续通过。

建议提交：

```text
Implement 3GPP InH path-loss formulas
```

---

## 7. 阶段 1 总体验收

阶段 1A、1B、1C 全部完成后，运行：

```powershell
python -m unittest tests.radio.test_pathloss_3gpp -v
python -m unittest discover -s tests
python -m ran.demo -s bristol_topology --mode tick --max-ticks 10
git diff --check
```

验收报告应包含：

```text
新增测试数量
全部固定测试值
breakpoint 连续性
输入错误案例
公式 applicability 案例
原 MVP 无变化
共享接口无变化
```

这时模块仍然只是纯公式库。

---

## 8. 阶段 2：纯数值 debug 与 baseline 对比

### 8.1 目标

在不读取地图的情况下，让团队可以从命令行输入物理参数并查看：

- 3GPP mean path loss。
- formula ID。
- SF 标准差。
- breakpoint。
- applicability warning。
- 当前 FSPL 形式 baseline 的对比值。

### 8.2 新增文件

```text
experiments/debug_3gpp_pathloss.py
```

可选新增纯内部 report helper，但不修改 `ChannelState`。

### 8.3 CLI 示例

```powershell
python -m experiments.debug_3gpp_pathloss `
  --scenario umi_street_canyon `
  --los-state los `
  --frequency-mhz 3500 `
  --distance-2d-m 100 `
  --bs-height-m 10 `
  --ut-height-m 1.5 `
  --pretty
```

如果没有显式给出 `d3D`，CLI 可以根据 2D 距离和高度计算；公式核心 API
本身仍要求完整、一致的 request。

### 8.4 输出结构

```text
input
normalized_units
standard_reference
formula_id
mean_path_loss_db
shadow_fading_std_db
breakpoint_distance_m
baseline_fspl_db
difference_from_baseline_db
is_extrapolated
warnings
```

### 8.5 Gate 2

- CLI 输出 JSON，可复现。
- 同样输入重复运行得到同样结果。
- CLI 不 import scene、Geometry 或 ChannelState。
- 没有随机项。
- 所有阶段 1 测试继续通过。

建议提交：

```text
Add standalone 3GPP path-loss debug report
```

---

## 9. 阶段 3：Geometry/Calibration adapter

### 9.1 前置条件

- 阶段 1 和阶段 2 已通过 review。
- 坐标标定能够显式提供米制距离。
- debug 调用明确提供 gNB/UE 高度。
- 团队接受 Bristol 室外暂用 UMi Street Canyon。

### 9.2 目标

新增 read-only adapter，把已有 Geometry 结果转换成
`PathLossRequest`，但仍不接入 `channel.py`。

### 9.3 建议新增文件

```text
ran/radio/pathloss_3gpp_adapter.py
tests/radio/test_pathloss_3gpp_adapter.py
experiments/debug_bristol_3gpp_pathloss.py
```

不要把 adapter 塞进 `geometry.py`，避免 Geometry 反向依赖 path loss。

### 9.4 adapter 责任

adapter 只做：

1. 检查 `distance_2d_m` 和 `distance_3d_m` 非 `None`。
2. 读取 Geometry `link_type` 和 `los_state`。
3. 按批准的映射选择 UMi 或 InH。
4. 传入 gNB/UE 高度和 `carrier_freq_mhz`。
5. 对不支持的 link type 明确抛出：

   ```text
   UnsupportedGeometryLinkError
   ```

adapter 不做：

- 坐标拟合。
- 修改 Geometry。
- 从 map units 推断米。
- O2I 公式拼接。
- 材料损耗。
- `ChannelState` 构造。

### 9.5 第一批允许的 Bristol 案例

| 案例 | Geometry | 3GPP |
| --- | --- | --- |
| `outdoor_green` | `outdoor_los` | UMi LOS |
| `outdoor_east_of_student_union` | `outdoor_nlos` | UMi NLOS |

以下案例在阶段 3 必须返回 unsupported，而不是偷偷使用 UMi NLOS：

```text
student_union_center
gym_center
```

因为它们是 `outdoor_to_indoor`。

### 9.6 adapter 测试

1. outdoor LOS 正确映射 UMi LOS。
2. outdoor NLOS 正确映射 UMi NLOS。
3. indoor same-building LOS/NLOS 正确映射 InH。
4. meter 字段为 `None` 时失败。
5. O2I/I2O/different-building 明确失败。
6. 频率从 `GnbSite.carrier_freq_mhz` 原样进入 request。
7. UL/DL 不交换 BS/UT 高度。
8. adapter 不修改传入 Geometry。

### 9.7 Gate 3

- Bristol dry-run report 可生成。
- 报告显示 calibration status。
- provisional calibration 明确标注，不伪装成 confirmed。
- 不支持的 link 不产生 path-loss 数值。
- 原 `channel.py` 和 MVP 输出不变。

建议提交：

```text
Add read-only Geometry adapter for 3GPP path loss
```

---

## 10. 阶段 4A：O2I 决策 Gate

这一阶段先产出设计和数据，不写 O2I 公式代码。

必须确认：

1. outdoor segment 是 LOS 还是 NLOS。
2. 是否需要扩展 Geometry debug output 来提供 outdoor-segment 状态。
3. Bristol 建筑采用 low-loss、high-loss 或 map-material profile。
4. 外墙材料比例如何获得。
5. 入射角是否进入第一版。
6. `PLin` 使用 Geometry `indoor_distance_m` 还是标准随机 indoor depth。
7. penetration random term 是否暂设为 0、固定 seed 或后续实现。
8. 当前 raw `penetration_loss_db` 如何避免重复计算。

### Gate 4A

只有这些规则被团队书面确认，才能开始阶段 4B。

---

## 11. 阶段 4B：O2I 实现

### 11.1 建议新增文件

```text
ran/radio/pathloss_3gpp_o2i.py
tests/radio/test_pathloss_3gpp_o2i.py
```

### 11.2 实现结构

```text
outdoor basic path loss
+ external wall penetration PLtw
+ indoor-depth loss PLin
+ explicit penetration residual
```

每个分量必须单独出现在结果/report 中，禁止只返回一个无法解释的总值。

### 11.3 Gate 4B

- Student Union 和 Gym 案例有可解释的 O2I components。
- 没有与 raw wall loss 双重计数。
- 关闭某个 component 时结果可做 baseline comparison。
- O2I 测试独立于 scheduler/PHY。
- 仍不接入 runtime。

---

## 12. 阶段 5：Shadow fading 与 CKM

这部分必须与 CKM 目标一起设计，不能简单地每 tick 独立
`random.gauss(0, SF)`。

需要确定：

```text
随机 seed
UE 移动时的 spatial correlation
同一位置重复查询的稳定性
CKM mean/prior
measurement residual
离线预计算与 runtime cache
```

建议接口：

```text
mean path loss
+ spatial shadow term
+ optional CKM correction
→ large-scale channel state
```

Gate 5 需要单独方案和团队 review。

---

## 13. 阶段 6：可选 runtime integration

### 13.1 前置条件

- 阶段 1-3 稳定。
- O2I 所需场景已经覆盖，或者 runtime 明确支持 fallback。
- 团队批准修改 `channel.py`。
- scheduler/PHY 所有者知道 path-loss 行为将影响 SINR、CQI 和 error rate。

### 13.2 集成原则

建议给 `estimate_channel()` 增加可选、带默认值的 model selector：

```text
baseline
3gpp
```

默认仍为现有 baseline，或者由团队明确决定切换时间。

必须：

- 保留现有函数调用方式。
- 保留现有 `ChannelState` 字段。
- 不删除 raw wall-loss 路径。
- unsupported/out-of-range 时按批准策略 fallback 或明确失败。
- debug 输出说明实际使用哪个 model。

### 13.3 回归范围

```text
ChannelState
SchedulerRequest
MCS/PRB allocation
TransmissionResult
HARQ/RLC retransmission
QoS metrics
10-tick 和 aggregate MVP
```

### Gate 6

这是跨组接口行为变化，必须经过团队 code review 后才能 merge。

---

## 14. 每阶段统一工作流程

每个阶段都按以下顺序执行：

1. 更新本阶段 checklist。
2. 只编辑列出的 ownership 文件。
3. 先写最小失败测试。
4. 实现最小公式或 adapter。
5. 运行本阶段 focused tests。
6. 运行完整 unittest。
7. 运行 10-tick MVP。
8. 执行 `git diff --check`。
9. Review `git diff`，确认没有共享接口变化。
10. 更新工作日志与 handoff。
11. 使用 `Zhiqian He <xa25139@bristol.ac.uk>` commit。
12. 未收到明确指示前不 push。

---

## 15. 阶段报告模板

每阶段完成后记录：

```text
Stage:
Objective:
Files added:
Files modified:
Standard clauses:
Formula IDs:
Focused tests:
Full tests:
MVP regression:
Shared interface changed: yes/no
Runtime behavior changed: yes/no
Fallback retained: yes/no
Known limitations:
Open decisions:
Commit:
Push status:
```

---

## 16. 风险与控制

| 风险 | 控制 |
| --- | --- |
| MHz/GHz/Hz 混用 | API 固定 MHz，内部集中转换 |
| map units 被当成 meter | adapter 对 meter `None` 明确失败 |
| d2D/d3D 不一致 | 高度一致性 validation |
| UMi breakpoint 分支错误 | 210 m 固定值与连续性测试 |
| NLOS 小于 LOS | 强制 `max(LOS, candidate)` 测试 |
| 超范围静默外推 | 默认抛 applicability error |
| Geometry LOS 被误称标准随机 LOS | report 标注 `geometry_determined` |
| O2I 重复墙损耗 | components 分离，禁止直接叠加 raw wall loss |
| provisional calibration 被当真值 | dry-run report 显示 calibration status |
| 新模型破坏 scheduler | runtime 最后接入，保留 baseline |
| 文档标准版本漂移 | formula ID 固定 `v19_4_0` |

---

## 17. 当前推荐执行点

现在只进入：

```text
Stage 0 review
→ Stage 1A internal contract and validation
→ Stage 1B UMi
→ Stage 1C InH
```

阶段 1 完成后暂停，进行一次 code review 和公式结果汇报，再决定是否进入
阶段 2 和阶段 3。

当前不应开始：

```text
O2I
shadow fading
CKM
channel.py integration
ChannelState extension
scheduler linkage
```
