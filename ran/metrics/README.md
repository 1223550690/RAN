# metrics 接口文档

职责：计算业务级 QoS、切片资源使用和端到端记录。

输入：
- `TransmissionResult`
- `N3ForwardingResult`
- `N6DeliveryResult`
- `MacAllocation`

输出：
- `QosMetrics`
- `EndToEndResult`
- slice PRB 使用字典

MVP 简化：
- 吞吐按 delivered bytes / delay 粗略估算。
- 拥塞用 PRB 占用和未交付字节粗略判断。
