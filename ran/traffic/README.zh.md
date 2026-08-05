# traffic 接口文档

职责：把 UE 业务请求转换为 IP 层业务批次，并提供业务 QoS 模板。

输入：

- `UERequest`
- `PduSession`

输出：

- `IPTrafficBatch`
- service profile 字典

当前实现：

- 使用批次模型避免为大流量逐包创建对象，但保留 packet 数、header、MTU 和网络总字节。
- 正确建模 UL/DL 地址和端口方向，并支持 TCP/UDP。
- 端点和服务 profile 分别由 `configs/ran/ip_endpoints.json` 与
  `configs/ran/service_profiles.json` 驱动。
- 未配置的符号目标、DNN 不一致和非活动会话会明确报错。

完整设计见 `docs/area_b_smf_ip_qos_sdap_zh.md`。
