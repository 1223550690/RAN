# core 接口文档

职责：提供最小 5GC 控制面/用户面抽象。

输入：

- `UEState`
- `UERequest`
- `PduSession`
- `N3ForwardingResult`

输出：

- 已注册/连接的 `UEState`
- `PduSession`
- UPF/N6 转发结果

MVP 简化：

- AMF 只更新注册状态。
- SMF 固定分配 UE IP、PDU Session ID 和 UPF。
- UPF 不实现 PDR/FAR/QER，只做固定时延转发。
