# 时空 CKM 独立实验结果

状态：实验阶段完成，未接入主 runtime
日期：2026-08-24
数据性质：受控仿真，不是真实 Bristol 路测

## 1. 实验范围

本实验验证：

```text
Static Hybrid CKM
+ Agent 稀疏 path-loss observation
+ 低秩空间 RBF residual
+ Gauss-Markov 时间演化
+ Kalman/RLS 在线更新
+ 时空 support gating
```

实验没有修改或调用主 RAN scheduler/PHY 闭环，不用于证明实际 QoS 提升。

运行命令：

```bash
python -m experiments.ckm_spatiotemporal_ablation \
  --ticks 120 \
  --forecast-train-ticks 60 \
  --grid 100 \
  --indoor-grid 50 \
  --agent-speed 15 \
  --output outputs/ckm_spatiotemporal_ablation.json
```

实验配置：

- Bristol 场景。
- 120 ticks，`tick_ms=1000`。
- 当前 Agent 定义和语义目的地生成的三条确定性轨迹。
- student、teacher 作为 measurement Agents。
- staff 作为全程不提供 observation 的 probe Agent。
- 3 个固定空间 hold-out 点。
- 25 个 estimator RBF features。
- 240 个 online observation updates。
- 静态 CKM 使用实验用粗网格，共 842 cells。
- truth 使用与 estimator 不同的隐藏 Fourier features。
- 所有评分遵循 `predict -> score -> observe`。

## 2. 主要结果

| 范围 | Static CKM RMSE | Online RMSE | 相对变化 |
|---|---:|---:|---:|
| 全部 tracking points | 4.16 dB | 3.18 dB | 改善 23.48% |
| Spatial hold-out | 4.42 dB | 3.38 dB | 改善 23.39% |
| Dynamic event active | 6.97 dB | 2.87 dB | 改善 58.89% |
| Non-event points | 3.32 dB | 3.24 dB | 改善 2.31% |
| Probe Agent | 3.83 dB | 3.99 dB | 恶化 4.28% |
| Frozen future forecast | 4.41 dB | 3.34 dB | 改善 24.23% |

90% predictive interval 的总体 empirical coverage 为：

```text
86.13%
```

落在设计 Gate 的 `80%～98%` 范围内。

## 3. 性能

| 项目 | Median | P95 | Max |
|---|---:|---:|---:|
| 单次 prediction | 0.215 ms | 0.371 ms | 0.680 ms |
| 单次 observation update | 0.335 ms | 0.596 ms | 1.044 ms |

Estimator 状态估算：

```text
11,544 bytes
```

没有构造 cell-count covariance，也没有保存完整 `(cell, tick)` 数组。

## 4. Gate 判断

### Gate A：算法正确性

- [x] Truth 和 estimator 位于不同模块，无 import 依赖。
- [x] Truth 和 estimator 使用不同空间表示。
- [x] Predict-before-update。
- [x] 时间使用 seconds。
- [x] 无 observation 时严格返回 static baseline。
- [x] Prediction 不推进内部时间。
- [x] 非法、重复和时间回退 observation 不修改状态。
- [x] 无稠密 GP 或三维数组。

### Gate B：时空效果

- [x] Spatial hold-out 优于 static CKM。
- [x] Dynamic event 区域明显优于 static CKM。
- [x] Non-event 区域没有被明显破坏。
- [x] Frozen forecasting 优于 static baseline。
- [x] 总体 uncertainty coverage 在目标范围内。
- [ ] Probe Agent RMSE 仍有 4.28% 恶化，需要作为限制保留。

### Gate C：稳定性

- [x] 只新增独立 CKM、experiment、test 和 docs 文件。
- [x] 未修改 `ChannelState`。
- [x] 未修改 `estimate_channel()`。
- [x] 未修改 scheduler/PHY/geometry/path-loss/editor。
- [x] 主 runtime 数值不变。
- [x] 性能低于预算。

## 5. Support gating 的必要性

初始实现只使用低秩 Kalman 状态，局部 observation 会被过度传播到未观测区域。120-tick 初始实验中 online RMSE 高于 static CKM。

修正方法不是更改 truth，而是增加有界的时空 support：

```text
support(x, y, t)
= max_i exp(-0.5 * (distance_i / radius)^2)
        * exp(-age_i / time_constant)

selected residual
= support * estimated residual
```

模型只保留有限数量的 `(x, y, time)` support summary。远离近期 observation 的区域自动退回 static CKM，解决了局部证据全图传播的问题。

## 6. 限制

- Ground truth 是 controlled simulation，不代表真实 Bristol 信道。
- 静态 CKM 使用粗实验网格，不是生产默认精度。
- Truth 和 estimator 的参数仍由同一个实验作者配置，需要后续 peer 复核。
- Probe Agent 有 4.28% RMSE 恶化，说明空间泛化并非所有轨迹都改善。
- Event-region 的预测区间 coverage 低于总体 coverage，动态突变期 uncertainty 仍可继续校准。
- 尚未进行多 seed 重复实验，当前结果只对应 seed `9042`。
- 尚未区分 predicted channel 和 PHY oracle channel，因此不能评价闭环 scheduler/QoS。

## 7. 下一步建议

在不影响主 runtime 的前提下，建议下一步只做：

1. 使用至少 5 个 truth seeds 重复消融，报告均值和标准差。
2. 增加 event location、coherence time 和 observation budget sensitivity。
3. 对 Probe Agent 恶化进行独立分析，保持 support gating 安全回退。
4. 由 peers 复核 truth 参数和 Gate。

在以上完成之前，不建议接入 `channel.py`。即使后续接入，也应先采用 shadow-only adapter，不改变 `ChannelState` 运行值。
