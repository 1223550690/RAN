# ue 接口文档

职责：维护 UE 状态，并把 Agent 行为意图转换成 UE 网络请求。

输入：
- `AgentIntent`
- UE 当前地图坐标
- `selected_access`，可为 `5g`、`wifi`、`auto`

输出：
- `UEState`
- `UERequest`

MVP 简化：
- 默认 UE 使用 5G 接入。
- Wi-Fi 仅通过 `selected_access="wifi"` 和 `access_type="non_3gpp"` 预留字段，不执行 Wi-Fi 独立链路。
