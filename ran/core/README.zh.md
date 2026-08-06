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

当前实现：

- AMF 只更新注册状态。
- SMF 校验注册/slice/DNN，动态分配 UE IP 和 PDU Session ID，按 DNN/slice 选择 UPF。
- SMF 维护活动会话注册表，并支持幂等建立、查询、列举和释放。
- UPF 不实现 PDR/FAR/QER，只做固定时延转发。

默认 SMF/UPF/IP 池配置位于 `configs/ran/smf.json`。
完整设计见 `docs/area_b_smf_ip_qos_sdap_zh.md`。
