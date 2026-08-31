# CKM Report Review 与写作交接

用途：供其他 Agent 或组员更新最终报告的 CKM 部分。

更新状态：已纳入 2026-08-31 完成的 5-seed 重复实验、逐时间/预测时域折线图、mean ± SD 结果表与新增测试。

Review 结论：**CKM 的实现和实验验证已足以支撑 MSc Capstone 的一个主要技术贡献；现有 Overleaf 小节仍需要扩写后再作为最终稿使用。** 应保留静态 Hybrid CKM 作为已接入 runtime 的基础，再加入已完成的时空在线 residual 实验。两层必须明确区分，不能把受控实验写成真实路测、active runtime 接入或 scheduler/QoS 改进。

---

## 1. 当前实现应分成两层描述

### 1.1 已接入 runtime 的 Static Hybrid CKM

当前生产路径中的 CKM 是二维、单场景/单 gNB 上下文的静态位置查询模型。它在仿真启动时构建或读取缓存，并挂载到 scene；运行时根据 UE 的 map coordinates 查询 CKM cell。

模型组成应写成：

\[
PL_{\mathrm{hybrid}}(x,y)
=PL_{\mathrm{physical}}(x,y)
+\Delta PL_{\mathrm{cal}}(x,y)
+\mu_{\mathrm{spatial}}(x,y).
\]

其中：

- \(PL_{\mathrm{physical}}\)：由坐标标定、传播几何和 3GPP-inspired UMi/InH/O2I 路损路径产生的物理先验；
- \(\Delta PL_{\mathrm{cal}}\)：基于材料穿越次数、外墙数、室内距离和 NLOS indicator 的低维 ridge calibration；
- \(\mu_{\mathrm{spatial}}\)：由 GP（默认）或 IDW 得到的空间 residual correction；
- prediction uncertainty 结合物理模型 shadow standard deviation 与 residual prediction standard deviation；
- CKM cell 还可保存 beam selection、predicted RSRP 和 geometry provenance。

Static Hybrid CKM 已经具备：

- 10 m 基础网格与 5 m 室内细化配置；
- Bristol build 的 71,903 cells；
- 20 个当前 synthetic reference observations；
- version-keyed JSON cache；
- 启动时构建/加载；
- 坐标查询与 heatmap 输出；
- CKM 不可用或构建失败时回退到现有 channel path；
- `RAN_DISABLE_CKM=1` 禁用路径。

报告可以声称这是一个“可查询、可缓存、保留物理先验并叠加数据校正的 Hybrid CKM framework”。不能声称它已经通过真实 Bristol 无线测量验证。

### 1.2 尚未接入 runtime 的 Online Spatiotemporal CKM

新增工作是独立的 physics-informed online spatiotemporal residual estimator：

\[
PL_{\mathrm{online}}(x,y,t)
=PL_{\mathrm{static\ CKM}}(x,y)
+\hat r(x,y,t).
\]

这里的 \(\hat r(x,y,t)\) 使用：

- 固定低秩 RBF spatial basis；
- Gauss--Markov 时间状态演化；
- Kalman/RLS-style online observation update；
- prediction mean 和 uncertainty；
- spatial-temporal support gating；
- residual clipping 和安全 fallback。

它是真正带有 \((x,y,t)\) 输入、时间衰减、在线更新和未来预测的时空模型。但当前只在独立实验中使用，未导入 `channel.py`，未修改 `ChannelState`，也未改变 scheduler 或 PHY 数值。

---

## 2. 对现有 Overleaf CKM 小节的 Review

当前文件：

```text
exports/RAN_3GPP_Final_Report_Overleaf_2026-08-24/sections/sec4_7_ckm.tex
```

### 已经写对的内容

- 保留 3GPP/map-aware mean path loss 作为可审计 physical prior；
- learned correction 没有被描述为替代物理模型；
- 给出了 71,903 cells、10 m/5 m 网格和 20 个 synthetic references；
- 明确指出 4.84 dB calibration RMSE 不等于 field-validated accuracy；
- Figure `fig_4_7_ckm_layers` 适合作为静态 CKM 架构与结果图。

### 需要补充或调整的内容

1. 当前正文只有一段，缺少 CKM motivation、数学组成、构建/查询流程、runtime fallback 和验证方法。
2. “learns only a spatial residual”过于简化；实现还包含低维 ridge calibration、GP/IDW residual、uncertainty 和 beam output。
3. 必须增加独立的 online spatiotemporal extension，但明确标注为 experiment-only。
4. 必须解释 truth/estimator 隔离和 `predict -> score -> observe`，否则在线结果容易被质疑存在数据泄漏。
5. 必须加入 baseline comparison、hold-out、forecast、latency 和 limitations。
6. 不应将时空实验结果加入 end-to-end scheduler 或 QoS performance claim。
7. 结果应从原先的 single-seed 数值更新为当前 5-seed mean ± sample standard deviation。
8. 主文应至少加入一张时间序列图，展示动态事件期间的 adaptation，而不应只放 summary table 或柱状图。

### 更新后实验的 Review 判断

更新后的实验已经补上原 review 中最关键的证据缺口：

- 从单一 seed 扩展为 5 个独立 truth/noise realizations；
- 使用 seed-level mean ± sample standard deviation，而不是合并全部 ticks 后计算一个伪重复统计量；
- 保留 physical、static CKM 和 online/frozen model 对比；
- 同时覆盖 online tracking、spatial hold-out、dynamic event、non-event、probe Agent 和 frozen forecast；
- 生成时间序列、事件适应、预测时域、uncertainty 和 scope summary 五类图；
- 新增 multi-seed aggregation/reporting tests，目标 CKM 测试共 34 个通过。

从 MSc Capstone 的实验完整性看，当前 evidence chain 已经充分。报告不需要继续扩大算法或系统范围，重点应转为清晰呈现研究问题、方法、动态过程和多 seed 结果。

---

## 3. 推荐的报告结构

建议把 Section 4.7 扩展为以下六部分。

### 4.7.1 Motivation and scope

说明传统 path-loss model 提供场景级平均行为，但不会保存特定地图位置上的可复用知识。CKM 的目标是把 geometry/3GPP prior、稀疏参考数据、空间校正和 uncertainty 组织为可重复查询的位置知识层。

同时声明范围：当前系统是 single-cell、2D prototype；reference measurements 为 synthetic；coordinate calibration 为 provisional。

### 4.7.2 Static physics-informed Hybrid CKM

给出静态公式：

\[
PL_{\mathrm{hybrid}}
=PL_{\mathrm{physical}}
+\boldsymbol{x}_{\mathrm{geom}}^{T}\boldsymbol{\beta}
+\mu_{\mathrm{GP}}(x,y).
\]

其中 geometry feature vector 包含 intercept、brick/glass/drywall crossing、exterior crossing、indoor distance 和 NLOS indicator。说明 calibration 使用 ridge regression，空间 residual 默认使用 Matérn-3/2 GP，也保留 IDW 路径。

### 4.7.3 Construction, cache and runtime query

描述流程：

```text
scene + gNB + channel policy
    -> coordinate/geometry and physical path loss over grid
    -> synthetic sparse references
    -> ridge calibration and spatial residual model
    -> HybridCKMCell collection
    -> versioned cache
    -> UE coordinate query at runtime
    -> link-budget output
```

强调 CKM 构建失败不会阻断 MVP，而是回退到现有 shadow/3GPP-compatible channel path。

### 4.7.4 Online spatiotemporal residual extension

把新增模型描述为静态 CKM 上的附加 residual，而不是重建整个 channel model：

\[
\hat r(x,y,t)=s(x,y,t)\,\boldsymbol{\phi}(x,y)^T\boldsymbol{\theta}(t),
\]

其中 \(\boldsymbol{\phi}\) 为低秩 RBF basis，\(\boldsymbol{\theta}(t)\) 按 Gauss--Markov 模型演化并通过 Kalman/RLS update 学习。support gating 为：

\[
s(x,y,t)=\max_i
\exp\left[-\frac{d_i^2}{2R^2}\right]
\exp\left[-\frac{t-t_i}{\tau_s}\right].
\]

该 gating 限制局部 observation 对远距离或长时间未观测区域的传播；当没有可靠支持时 correction 退化为零，即返回 static CKM。

### 4.7.5 Controlled validation protocol and results

验证使用受控动态 truth：

\[
PL_{\mathrm{truth}}
=PL_{\mathrm{static\ CKM}}
+S_{\mathrm{static}}(x,y)
+S_{\mathrm{temporal}}(x,y,t)
+B_{\mathrm{event}}(x,y,t).
\]

必须写明：

- truth 使用隐藏 Fourier features，estimator 使用不同的 RBF representation；
- estimator 不读取 truth seed、hidden features、coherence parameters 或 event parameters；
- 120 ticks，1 second/tick；
- student 和 teacher 为 measurement Agents；
- staff 为无 observation 的 probe Agent；
- 另有三个固定 spatial hold-out points；
- 每个 tick 严格执行 `predict -> score -> observe`；
- frozen forecast 在前 60 ticks 学习，后 60 ticks 停止 observation update。
- 共运行 seeds 9042--9046；不同 seed 只改变隐藏动态场与 measurement noise realization；
- 每个 seed 独立计算 RMSE，最终报告 seed-level mean ± sample standard deviation。
- 为控制独立实验成本，实验 static CKM 使用 100 m base grid、50 m indoor refinement，共 842 cells；这与 production/report static CKM 的 10 m/5 m、71,903 cells 必须分开表述。

推荐使用下表：

| Evaluation scope | Static CKM RMSE | Online/frozen RMSE | Relative change |
|---|---:|---:|---:|
| All tracking points | 5.04 ± 1.40 dB | 3.82 ± 0.71 dB | 22.74 ± 9.79% improvement |
| Spatial hold-out | 5.03 ± 2.08 dB | 4.23 ± 1.24 dB | 12.69 ± 13.31% improvement |
| Dynamic-event region | 7.72 ± 3.10 dB | 2.95 ± 0.62 dB | 58.58 ± 13.73% improvement |
| Non-event points | 4.25 ± 0.97 dB | 3.97 ± 0.74 dB | 6.15 ± 4.30% improvement |
| Probe Agent | 4.25 ± 0.89 dB | 4.44 ± 1.01 dB | 4.15 ± 5.44% degradation |
| Frozen future forecast | 5.05 ± 1.48 dB | 4.21 ± 1.05 dB | 15.82 ± 7.49% improvement |

补充结果：

- 90% predictive interval empirical coverage：82.04 ± 4.56%；
- prediction median latency：0.129 ± 0.002 ms；
- observation update median latency：0.206 ± 0.001 ms；
- estimator state：约 11.5 KB；
- targeted static + online + reporting CKM tests：34 passed。

Probe Agent 的 4.15% mean degradation 必须保留，不能只报告改善结果。

### 4.7.6 Limitations and integration boundary

必须明确：

- 数据来自 controlled simulation，不是真实 Bristol measurements；
- static CKM 的 references 是 synthetic；
- 多 seed 实验使用粗化的 842-cell static CKM baseline，而非 production-resolution CKM；
- 当前已完成 5 seeds；更广泛的 event/location sensitivity 可作为 future work；
- probe trajectory 并未改善，说明空间泛化不是处处成立；
- online estimator 尚未接入 main runtime；
- `ChannelState`、`estimate_channel()`、scheduler 和 PHY 没有改变；
- 尚未区分 scheduler 使用的 predicted channel 与 PHY execution 使用的 oracle channel；
- 因此不能声称 throughput、QoS、fairness 或 real-network accuracy 改善。

---

## 4. 可直接使用的英文正文草稿

### Static Hybrid CKM

> The implemented Channel Knowledge Map is a physics-informed spatial knowledge layer rather than a replacement for the propagation model. For each map location, the system first evaluates a map-aware physical path-loss prior using calibrated geometry and the available 3GPP-inspired UMi, InH and O2I paths. A low-dimensional ridge model then applies geometry-dependent calibration using material crossings, exterior-wall count, indoor distance and the LOS/NLOS state. Finally, a Gaussian-process spatial residual, or an IDW alternative, provides a location-dependent correction and predictive uncertainty. The resulting hybrid path loss is therefore expressed as the sum of the physical prior, a calibration term and a spatial residual.

> The Bristol CKM contains 71,903 cells on a 10 m base grid with 5 m indoor refinement. It supports version-keyed caching and repeated coordinate queries during simulation. If construction is disabled or fails, the existing channel path remains available as a fallback, preserving the runnable RAN pipeline. The present 20 reference observations are synthetic, and the coordinate calibration is provisional; consequently, the CKM demonstrates framework construction, querying and integration rather than field-validated radio accuracy.

### Online spatiotemporal extension

> To investigate channel dynamics without modifying the operational RAN interfaces, an online spatiotemporal residual estimator was implemented as an isolated CKM module. The existing static Hybrid CKM remains the baseline, while a low-rank RBF representation estimates an additional residual as a function of map position and elapsed time. The coefficient state follows a Gauss--Markov evolution and is updated from sparse path-loss observations using a Kalman/RLS-style update. A bounded spatiotemporal support function attenuates corrections away from recent observations, causing unsupported predictions to revert safely to the static CKM.

### Validation

> Validation used a controlled dynamic-channel generator that was separated from the estimator in both module dependency and spatial representation. Hidden Fourier features produced static and temporally evolving residual fields, while a local event introduced a transient excess-loss region. Two moving Agents supplied sparse measurements, whereas a third probe Agent and three fixed spatial hold-out points never supplied training observations. At every simulation tick, predictions were generated and scored before the current observations were assimilated. This prequential order prevents same-sample information leakage. A separate frozen-forecast protocol stopped online updates after 60 of the 120 one-second ticks.

> To keep the repeated experiment computationally bounded, its static CKM baseline used a 100 m base grid with 50 m indoor refinement, producing 842 cells. This experimental baseline should be distinguished from the 71,903-cell, 10 m/5 m production-resolution Bristol CKM described above.

> Across five controlled dynamic-channel seeds, the online model reduced overall tracking RMSE from 5.04 ± 1.40 dB to 3.82 ± 0.71 dB. During the controlled dynamic event, RMSE decreased from 7.72 ± 3.10 dB to 2.95 ± 0.62 dB. Spatial hold-out RMSE improved by 12.69% on average, while frozen future-forecast RMSE improved by 15.82%. The empirical coverage of the nominal 90% predictive interval was 82.04 ± 4.56%. Median prediction and update latencies were 0.129 ms and 0.206 ms, respectively. However, probe-Agent RMSE increased by 4.15% on average, indicating that spatial generalisation was not uniformly beneficial.

### Boundary statement

> These results establish algorithmic behaviour in a controlled simulation only. They do not constitute Bristol field validation, active runtime integration, or evidence of scheduler, throughput or QoS improvement. The online estimator does not currently modify ChannelState, scheduler inputs or PHY execution. A future runtime study should first use a shadow-only adapter and should separately represent the predicted channel available to the scheduler and the oracle channel used for PHY execution.

---

## 5. Claims 检查表

| Claim | 是否允许 | Review 说明 |
|---|---|---|
| CKM 保留 geometry/3GPP physical prior | 是 | 与实现一致 |
| 静态 CKM 已接入 runtime 并支持 fallback | 是 | 与 scenario/channel 路径一致 |
| Online CKM 具有空间和时间状态 | 是 | RBF + Gauss--Markov + online update |
| 在线模型在受控实验中改善总体 RMSE | 是 | 必须附具体 scope 和数值 |
| 在线模型在所有 Agent 上都更好 | 否 | Probe Agent 平均恶化 4.15% |
| 使用真实 Bristol measurement 训练 | 否 | 当前 references/truth 均为 synthetic/controlled |
| 时空 CKM 已接入 ChannelState | 否 | 当前 experiment-only |
| 已证明 scheduler/QoS/throughput 改善 | 否 | 没有闭环验证 |
| 实现是完整 3GPP CKM | 否 | 物理先验为 3GPP-inspired，CKM 增强属于项目实现 |
| 结果可代表真实网络部署精度 | 否 | 已有 multi-seed controlled evaluation，但无 field calibration/measurement validation |

---

## 6. 写作时应引用的实现证据

| 内容 | 代码/结果位置 |
|---|---|
| Static CKM builder | `ran/ckm/builder.py` |
| CKM cell 与 query | `ran/ckm/ckm.py` |
| Ridge calibration | `ran/ckm/calibration.py` |
| GP/IDW residual | `ran/ckm/residual.py` |
| Runtime CKM query | `ran/radio/channel.py` |
| Startup build/fallback | `ran/scenario.py` |
| Online spatiotemporal estimator | `ran/ckm/online_spatiotemporal.py` |
| Controlled hidden truth | `experiments/controlled_dynamic_channel.py` |
| Validation harness | `experiments/ckm_spatiotemporal_ablation.py` |
| Multi-seed runner | `experiments/ckm_spatiotemporal_multiseed.py` |
| Report figure generator | `experiments/plot_ckm_spatiotemporal_multiseed.py` |
| Single-seed machine-readable result | `outputs/ckm_spatiotemporal_ablation.json` |
| Multi-seed machine-readable result | `outputs/ckm_spatiotemporal_multiseed.json` |
| Multi-seed summary table | `outputs/report/ckm_spatiotemporal/table_ckm_multiseed_summary.csv` |
| Unit tests | `tests/test_ckm_hybrid.py`, `tests/test_ckm_online_spatiotemporal.py`, `tests/test_ckm_multiseed_reporting.py` |

---

## 7. Figure 与表格建议

保留现有 `fig_4_7_ckm_layers`，用于说明 static physical prior、spatial correction、hybrid output 和 uncertainty。更新后的实验已经生成以下 report-ready PNG/PDF：

| Figure | 表达内容 | 推荐位置 |
|---|---|---|
| `fig_ckm_tracking_over_time` | 5 seeds 的 10-tick rolling RMSE；Static 与 Online CKM 随时间变化；动态事件区间着色 | 主文，核心结果图 |
| `fig_ckm_event_adaptation` | held-out event centre 的 hidden truth residual、online correction、static zero correction 和 support score | 主文或 appendix |
| `fig_ckm_forecast_horizon` | tick 60 冻结更新后，RMSE 随 forecast horizon 的变化 | 主文或 appendix |
| `fig_ckm_uncertainty_over_time` | prediction error 与 nominal 90% interval half-width 随时间变化 | Appendix |
| `fig_ckm_scope_rmse_summary` | 六个 evaluation scopes 的 seed-level RMSE mean ± SD | 主文 overview |

所有图位于：

```text
outputs/report/ckm_spatiotemporal/
```

线图的统一读法必须在正文或 caption 中说明：

- 实线为 5 个 seeds 的均值；
- 主文折线图只显示 seed mean，以保持图形简洁；seed 间 ±1 sample standard deviation 在结果表中报告；
- 黄色背景为 controlled dynamic event 区间；
- 所有 online scores 均在 assimilating current observation 之前计算。

建议主文使用以下最小组合：

1. `fig_4_7_ckm_layers`：解释 static CKM 的四层结构；
2. multi-seed RMSE summary table：给出最终量化结果；
3. `fig_ckm_tracking_over_time`：证明动态事件期间的在线适应；
4. `fig_ckm_event_adaptation` 或 `fig_ckm_forecast_horizon` 二选一：分别突出空间泛化或未来预测。

其余图放 appendix。这样既响应“多画带线的图”的建议，也不会让主结果章节过密。

推荐的 tracking figure caption：

> Ten-tick rolling path-loss RMSE over five controlled dynamic-channel seeds. Lines show the seed mean, while vertical dotted lines delimit the controlled dynamic event. Seed-level dispersion is reported in the result table. Predictions are scored before current observations are assimilated.

推荐的 event-adaptation figure caption：

> Spatiotemporal adaptation at a held-out event-centre location that never supplies training observations. The upper panel compares the hidden residual with the online correction and the zero-correction static CKM baseline; the lower panel shows the spatiotemporal support score. Lines show the five-seed mean, with seed-level dispersion reported in the result table.

建议新增一张简洁流程图：

```text
Static Hybrid CKM ───────────────┐
                                ├─> Online residual prediction ─> score
Past sparse Agent observations ─┘              ↑
                                               │ after scoring
Controlled hidden truth ─> current observation ┘
```

图注必须包含：`Predictions are scored before current observations are assimilated.`

该流程图是可选项；若篇幅有限，优先保留实际结果折线图。结果部分应同时使用第 3 节的 RMSE 表和至少一张时间线图，因为实验包含 event、non-event、probe 和 forecast 等不同 scope。

---

## 8. 最终 Review 决议

建议接受 CKM 部分作为报告的项目创新内容。最终写作应满足以下条件：

1. 静态 CKM 与时空在线 CKM 分节书写；
2. 保留 physical prior、fallback 和接口边界；
3. 将在线部分明确标注为 controlled experiment；
4. 说明 truth/estimator 隔离以及 predict-before-update；
5. 同时报告改善结果、Probe Agent 恶化和 uncertainty coverage；
6. 不宣称真实测量精度或 scheduler/QoS 改善；
7. 使用 5-seed mean ± SD 和更新后的折线图，不再引用原 single-seed 主结果；
8. future work 写为 event/location sensitivity、measurement ingestion 和 shadow-only runtime adapter，而不是重复已完成的 multi-seed validation 或直接承诺 active integration。

### MSc Capstone 范围下的最终判断

当前 CKM 工作已经形成完整闭环：

```text
research question
    -> static physics-informed baseline
    -> online spatiotemporal method
    -> leakage-controlled validation
    -> multiple baselines and hold-outs
    -> five-seed repeated evaluation
    -> time-series/result figures
    -> reproducible code and tests
```

因此不需要为了补足 CKM report 再扩展 multi-gNB、3D CKM、深度学习模型、真实数据管理平台或 scheduler/PHY active integration。剩余任务是把本交接中的结构、最终数值、caption 和边界准确写入正式报告。
