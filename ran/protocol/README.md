# protocol 接口文档

职责：实现 UE 侧上行用户面协议的最小链路。

输入：
- `IPTrafficBatch`
- `QoSFlow`
- `UERequest`

输出：
- `Drb`
- `PdcpBatch`
- `RlcQueue`

MVP 简化：
- SDAP 使用固定 QFI -> DRB 映射。
- PDCP 只估算 SN 和 header overhead，不做真实加密/完整性/重排序。
- RLC 只维护队列字节和重传字节，不做真实 PDU 分段。
