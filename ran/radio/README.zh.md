# radio 接口文档

职责：把地图拓扑、基站参数、UE 位置转换为信道状态，并执行最小 PHY/OFDM 传输估算。

输入：
- `scene`
- `UERequest.position`
- `GnbSite`
- `MacAllocation`

输出：
- `GnbSite`
- `ChannelState`
- `TransmissionResult`

MVP 简化：
- 基站从地图 element `asset_type=gnb_base_station` 读取。
- 信道使用距离、墙体穿透损耗和简化 path loss。
- OFDM 只估算 PRB/MCS/layers 可承载字节，不做真实波形。
- MIMO 只用 `layers` 和 `antenna_elements` 影响容量/增益。
