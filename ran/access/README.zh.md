# access 接口文档

职责：根据 UE 请求和当前可用接入节点，选择 3GPP/5G 或预留的 non-3GPP 接入方式。

输入：

- `UERequest`
- `GnbSite`

输出：

- `AccessSelection`

MVP 简化：

- 默认使用单小区 5G gNB。
- Wi-Fi 只保留字段，不建立独立链路。
