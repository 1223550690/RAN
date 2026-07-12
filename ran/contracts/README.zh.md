# contracts 接口文档

`ran/contracts/` 是 RAN MVP 的稳定数据契约层。

输入：
- Agent/UE/traffic/protocol/radio/scheduler/transport 各阶段的 Python dataclass。

输出：
- 可在 Python 内部直接传递，也可在 `scheduler/java_adapter.py` 序列化成 JSON。

约定：
- 字段名尽量稳定。
- 内部算法可以替换，但模块之间只通过这些结构传递核心数据。
- Wi-Fi 仅通过 `selected_access` 和 `access_type` 预留，不在 MVP 中实现独立链路。
