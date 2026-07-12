# traffic 接口文档

职责：把 UE 业务请求转换为 IP 层业务批次，并提供业务 QoS 模板。

输入：

- `UERequest`
- `PduSession`

输出：

- `IPTrafficBatch`
- service profile 字典

MVP 简化：

- 不逐包生成 IP packet，只按 `total_bytes` 和 `remaining_bytes` 推进。
- `youtube_server` 固定映射到模拟 IP。
