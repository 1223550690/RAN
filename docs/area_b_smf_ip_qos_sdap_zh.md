# Area B：SMF、IP Packet、QoS、SDAP 实现说明

本文说明 `boyu/area-b` 中四个模块的实现边界、状态模型、配置入口和集成方式。
实现保留了 MVP 原有兼容入口，并在 Area B 边界提供可单独调用的正式 SDAP 输出链路：

```text
establish_pdu_session()
-> build_ip_traffic()
-> build_qos_flow()
-> process_sdap()
```

现有主场景仍通过 `map_qos_flow_to_drb()` 兼容入口把 DRB 交给 PDCP。
`SdapOutput` 已经作为明确的下游交接契约，但 PDCP 内部接入由对应模块负责人完成。

同时，每个模块都提供独立的状态管理类，便于多 UE、多会话、单元测试和后续依赖注入。

## 1. SMF / PDU Session

主要文件：

- `ran/core/smf.py`
- `configs/ran/smf.json`
- `ran/contracts/qos.py`

`SessionManagementFunction` 实现：

- 校验 UE 已注册、UE ID/Agent ID 一致、slice 已授权；
- 按 DNN 和 slice 选择 UPF；
- 为每个 UE 动态分配 `PDU Session ID`（1-15）；
- 从 DNN 对应地址池分配唯一 IPv4 地址；
- 维护活动会话、逻辑会话键和 IP 占用表；
- 相同请求重复建立时返回同一个活动会话；
- 支持查询、列举、释放和测试重置。

当前 IPv4 地址池：

| DNN | UPF | 地址池 |
|---|---|---|
| `internet` | `internet_upf` | `10.20.0.0/24` |
| `campus` | `campus_upf` | `10.30.0.0/24` |
| `ims` | `ims_upf` | `10.40.0.0/24` |

当前 MVP 明确拒绝 IPv6 PDU Session，而不是返回一个看似成功但不可转发的会话。

## 2. IP Packet / Traffic Batch

主要文件：

- `ran/traffic/ip.py`
- `ran/contracts/traffic.py`
- `configs/ran/ip_endpoints.json`

`IPPacketFactory` 根据 target、DNN、service type 和方向生成流：

- UL：UE IP/临时端口 -> 服务端 IP/服务端口；
- DL：服务端 IP/服务端口 -> UE IP/临时端口；
- TCP 和 UDP 由端点配置确定；
- 未配置的符号目标会明确报错；IP 字面量可以作为受控回退；
- `service_id` 包含 UE、业务、PDU Session、方向和目标，保持可读且可区分。
- 同一 PDU Session 内的不同连接动态分配不同 UE 临时端口，避免五元组冲突；
- UL/DL 同一连接保持相同 UE 侧端口，并支持会话释放后回收端口。

`IPTrafficBatch` 不逐个创建上万个 Python packet 对象，但保留：

- 应用 payload 总字节和剩余字节；
- IP/传输层 header 大小；
- MTU、单包 payload 容量；
- 总 packet 数、剩余 packet 数；
- 包含 IP/TCP/UDP overhead 的网络总字节；
- 会话、slice、SMF、UPF、接入方式等 metadata。

这样可以满足指标侧的包/字节统计，同时避免 100MB 场景产生大量对象。

## 3. QoS Flow / QFI

主要文件：

- `ran/qos.py`
- `ran/traffic/service_profile.py`
- `configs/ran/service_profiles.json`
- `ran/contracts/qos.py`

关键修正：

- QFI 与 5QI 分开建模；
- QFI 必须是 1-63；
- `game` 使用 `QFI=7, 5QI=80`，不再把 80 当成 QFI；
- `QoSFlow.slice_id` 取自已经建立的 PDU Session，而不是在 QoS 表里二次决定；
- GBR / MBR、PDB、PER、priority 和 resource type 均进行一致性校验。

`QoSFlowClassifier` 支持：

- 按 `QoSRule` 的 service type、target、协议、端口和方向匹配 profile；
- 同一 PDU Session 内的 QFI 冲突检测与重新分配；
- 相同 flow 的幂等分类；
- 识别 PDU Session ID 复用和上下文变化，清除旧 slice/QFI 缓存；
- `qos_hint.latency_budget_ms` 只允许收紧 profile，不能放宽网络策略；
- 活动会话、DNN、UE、方向和 traffic/session identity 校验。

配置覆盖默认、视频上传/流媒体、网页、文件、游戏、语音/视频通话、消息、遥测和控制业务。

## 4. SDAP / QFI -> DRB

主要文件：

- `ran/protocol/sdap.py`
- `ran/contracts/bearer.py`

`SdapMapper` 实现：

- 为每个 UE 动态分配 `DRB ID`（1-32）；
- 每个 PDU Session 和方向的首个 DRB 标记为 default DRB；
- GBR、delay-critical 和低时延业务使用独立 DRB；
- 兼容的可靠 non-GBR 业务允许共享 DRB；
- DRB 保留 `qfi_list`，而当前 flow 的 `qfi` 仍可被 PDCP/RLC 使用；
- 文件/网页/上传等可靠业务使用 RLC AM；
- 游戏、通话、实时视频、控制等时延敏感业务使用 RLC UM；
- 多 QFI 共享后启用 SDAP header，避免接收端丢失 QFI 区分；
- `process_sdap()` 正式输出 `SdapOutput`，包含业务标识、QFI、DRB、PDU 数、应用字节、IP/传输层 header 字节、SDAP header 字节和输出字节；
- 识别会话编号、slice 或 QFI 复用后的旧 DRB 映射，重建当前上下文；
- `SdapOutput` 是供下游 PDCP 负责人接入的交接契约，本分支不修改 PDCP 实现；
- 支持映射查询、列举、会话释放和测试重置。

## 5. 配置与兼容性

三个 JSON 文件是项目默认配置：

```text
configs/ran/smf.json
configs/ran/ip_endpoints.json
configs/ran/service_profiles.json
```

如果以不包含仓库级 `configs/` 的方式安装 package，代码会使用经过相同校验的内置默认值。

兼容入口均接受可选的管理器参数，例如：

```python
session = establish_pdu_session(ue, request, slice_id="embb", smf=my_smf)
traffic = build_ip_traffic(request, session, factory=my_packet_factory)
qos = build_qos_flow(request, session, traffic=traffic, classifier=my_classifier)
sdap_output = process_sdap(traffic, qos, request, mapper=my_sdap_mapper)
```

不传管理器参数时使用默认实例。原有场景仍可使用
`map_qos_flow_to_drb()`，因此无需改写 PDCP 或 Scenario。

## 6. 验证

运行 Area B 自动测试：

```bash
python -m unittest discover -s tests -v
```

覆盖：

- 多 UE IP 唯一性和 PDU Session ID 作用域；
- 会话幂等、释放、DNN/UPF 选择、注册/slice 拒绝路径；
- UL/DL 五元组、TCP/UDP、packet/byte 统计和错误目标；
- QFI/5QI 区分、GBR/MBR、规则、hint、QFI 冲突；
- AM/UM 选择、default/dedicated/shared DRB、`qfi_list` 和映射查询；
- `SdapOutput` 正式输出、IP/传输层字节与 SDAP header 字节统计；
- 会话、slice 和 QFI 复用后不返回旧 QoS/DRB 状态；
- 数据契约的非法值拒绝。

端到端 smoke test：

```bash
python -m ran.demo --mode aggregate --max-ticks 5000
```

当前实现仍保持 MVP 的抽象边界：不模拟完整 PFCP、真实 IP 分片、完整 NAS QoS rule
下发或逐比特 SDAP 编解码；但 SDAP 已有正式、可观测、可供 PDCP
后续接入的批量输出契约。
