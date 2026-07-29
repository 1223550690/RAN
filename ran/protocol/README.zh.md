# protocol 接口文档

职责：实现 UE 侧上行用户面协议的最小链路。

输入：

- `IPTrafficBatch`
- `QoSFlow`
- `Drb`
- `TransmissionResult`

输出：

- `PdcpBatch`
- `RlcQueue`
- 更新后的 `RlcQueue`

当前实现：

- SDAP 动态分配 DRB，区分 default/dedicated/shared bearer，并维护 `qfi_list`。
- GBR/低时延业务使用独立 DRB；兼容 non-GBR 业务可共享 DRB。
- 可靠业务映射 RLC AM，时延敏感业务映射 RLC UM。
- PDCP 只估算 SN 和 header overhead，不做真实加密、完整性保护或重排序。
- RLC 只维护队列字节和重传字节，不做真实 PDU 分段。

完整设计见 `docs/area_b_smf_ip_qos_sdap_zh.md`。
