# scheduler 接口文档

职责：实现 gNB-DU MAC scheduler 的 PRB/MCS 分配边界。

输入：

- `SchedulerRequest`
- `RlcQueue`
- `QoSFlow`
- `Drb`
- `ChannelState`
- `SlicePolicy`

输出：

- `SchedulerResult`
- `MacAllocation`

MVP 简化：

- `JavaSchedulerAdapter` 保留 JSON 合同，但当前不调用 Java。
- 当前执行接到 `PythonBaselineScheduler`。
- Python fallback 使用队列大小、CQI 和切片优先级做粗略权重分配。
