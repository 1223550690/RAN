# RAN MVP 模块接口文档

本包实现从 Agent 意图到 Data Network 的最小 5G RAN/5GC 仿真链路。

## 总输入

- `AgentIntent`：Agent 在地图上的业务意图。
- `scene`：当前地图拓扑，包含区域、墙体、道路和基站 element。

## 总输出

- `EndToEndResult`：端到端交付字节、失败字节、吞吐、时延和丢包率。
- 每层调试对象：`UERequest`、`QoSFlow`、`DRB`、`RLCQueue`、`ChannelState`、`SchedulerRequest`、`SchedulerResult`、`TransmissionResult`、`N3/N6` 结果。

## MVP 边界

- Python 拥有仿真状态、协议队列、地图/信道、PHY、核心网转发和 QoS 统计。
- Java scheduler 只保留 JSON 接口，当前接 Python fallback。
- Wi-Fi 仅保留 `selected_access` 和 `access_type` 字段，不实现独立 Wi-Fi 路径。
- 基站为单个 `gnb_001`，位置与参数来自地图编辑器 element，不允许新增第二基站。
