# gnb 接口文档

职责：按 gNB RU/DU/CU-UP/CU-CP 拆分 RAN 内部边界。

输入：
- `RlcQueue`
- `ChannelState`
- `MacAllocation`
- `TransmissionResult`
- `PduSession`

输出：
- `SchedulerRequest`
- `TransmissionResult`
- `N3ForwardingResult`

MVP 简化：
- DU 只构造 scheduler 输入。
- RU 只作为无线接收边界。
- CU-UP 只做 N3/GTP-U 结果封装。
- CU-CP 只保留控制面接口。
