# gNB 接口文档

职责：表示 gNB 内部 RU、DU、CU-CP、CU-UP 的最小边界。

输入：

- `TransmissionResult`
- `RlcQueue`
- `QoSFlow`
- `Drb`
- `ChannelState`
- `SlicePolicy`

输出：

- `SchedulerRequest`
- N3 转发输入

MVP 简化：

- DU 只组装 scheduler 输入。
- RU 只接收 PHY 结果。
- CU-UP 只把无线结果转为 N3 转发。
- CU-CP 只保留控制面边界。
