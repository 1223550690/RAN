# CKM 时空在线实验：多 Seed 结果与图表说明

实验范围：MSc Capstone controlled simulation evaluation。

配置：5 个 truth seeds（9042--9046），每个 seed 运行 120 ticks，前 60 ticks 用于 frozen-forecast model 的在线更新，后 60 ticks 冻结模型。所有 seed 使用相同 Agent 轨迹、observation budget、static CKM 和 estimator 配置，仅改变隐藏动态信道与 measurement noise 的随机实现。

## 1. 多 Seed 汇总结果

结果均为先计算每个 seed 的 RMSE，再报告 5 个 seed 的 mean ± sample standard deviation。

| Evaluation scope | Static CKM RMSE | Online/frozen RMSE | Relative improvement |
|---|---:|---:|---:|
| All tracking points | 5.04 ± 1.40 dB | 3.82 ± 0.71 dB | 22.74 ± 9.79% |
| Spatial hold-out | 5.03 ± 2.08 dB | 4.23 ± 1.24 dB | 12.69 ± 13.31% |
| Dynamic-event region | 7.72 ± 3.10 dB | 2.95 ± 0.62 dB | 58.58 ± 13.73% |
| Non-event points | 4.25 ± 0.97 dB | 3.97 ± 0.74 dB | 6.15 ± 4.30% |
| Probe Agent | 4.25 ± 0.89 dB | 4.44 ± 1.01 dB | -4.15 ± 5.44% |
| Frozen future forecast | 5.05 ± 1.48 dB | 4.21 ± 1.05 dB | 15.82 ± 7.49% |

Nominal 90% predictive interval 的 empirical coverage 为 `82.04 ± 4.56%`。

性能结果：

- prediction median latency：`0.129 ± 0.002 ms`；
- observation update median latency：`0.206 ± 0.001 ms`；
- estimator state：约 11.5 KB。

## 2. 如何理解“多画带线的图”

TA 的建议应理解为：不要只展示最终均值柱状图，而要展示模型如何随时间、动态事件和 forecast horizon 变化。线图提供过程证据，能回答以下问题：

1. 在线模型是否在收到历史 observation 后逐步适应；
2. 动态事件出现时误差是否上升、模型是否追踪、事件消失后是否恢复；
3. update 被冻结后，预测优势能保持多久；
4. prediction uncertainty 是否覆盖实际误差变化；
5. 不同 seed 的结果是否稳定。

图中的实线表示 5 个 seed 的均值，半透明区域表示 seed 间 ±1 standard deviation。它同时表达趋势与重复实验稳定性。

## 3. Figure 说明

### `fig_ckm_tracking_over_time`

展示 10-tick rolling RMSE 随时间的变化。Static CKM 在动态事件期间误差明显上升，而 online CKM 利用历史 observation 保持较低误差。这张图是整体性能的主结果图。

### `fig_ckm_event_adaptation`

上图比较 held-out event centre 的 hidden truth residual、online estimated correction 和 static zero correction；下图展示 support gating score。该点不提供 observation，因此曲线反映了空间泛化，而不是对训练点的直接拟合。

### `fig_ckm_forecast_horizon`

在 tick 60 后冻结 online model，不再更新。横轴为 forecast horizon，比较 frozen online model 与 static CKM 的 per-tick RMSE，用于证明模型保留了有限时间的预测能力。

### `fig_ckm_uncertainty_over_time`

比较 mean absolute prediction error 与 nominal 90% interval half-width。该图用于说明模型不仅输出 point estimate，也输出随时间变化的 uncertainty。

### `fig_ckm_scope_rmse_summary`

使用 mean ± SD 汇总六个 evaluation scopes。它适合作为结果章节的 overview，其他时间序列图用于解释 improvement 从何而来。

## 4. Report 可直接使用的结果描述

> Across five controlled dynamic-channel seeds, the online spatiotemporal CKM reduced overall tracking RMSE from 5.04 ± 1.40 dB to 3.82 ± 0.71 dB, corresponding to a mean relative improvement of 22.74%. The largest gain occurred in the controlled dynamic-event region, where RMSE decreased from 7.72 ± 3.10 dB to 2.95 ± 0.62 dB. Spatial hold-out RMSE improved by 12.69% on average, and the frozen 60-second forecast improved by 15.82%. The Probe Agent result was 4.15% worse on average, showing that the benefit did not generalise uniformly to every unobserved trajectory. The empirical coverage of the nominal 90% predictive interval was 82.04 ± 4.56%.

推荐在主文中使用：

- multi-seed summary table；
- tracking-over-time 主图；
- event-adaptation 或 forecast-horizon 中的一张。

其余图可放 appendix，避免结果章节过密。
