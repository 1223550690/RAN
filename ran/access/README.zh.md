# access 接口文档

职责：决定 UERequest 走 5G 还是预留的 non-3GPP 接入。

输入：
- `UERequest.selected_access`
- 当前可用 `GnbSite`

输出：
- `AccessSelection`

MVP 简化：
- `5g` 和 `auto` 都映射到单个 `gnb_001`。
- `wifi` 仅返回预留结果，不创建 Wi-Fi 线路。
