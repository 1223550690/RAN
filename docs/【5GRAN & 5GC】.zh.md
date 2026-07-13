# 🌈序言

本文用于阐述项目用5GRAN基本框架以及相关协议。为了描述端到端数据路径，包含了必要的 5GC 用户面/控制面抽象。

---
# 💫正文

## 基础框架

- [Agent intent](#Agent%20intent)
- [UE request](#UE%20request)
- [IP packets](#IP%20packets)
- [QoS Flow / QFI](#QoS%20Flow%20/%20QFI)
- [SDAP: QFI -> DRB](#SDAP%20QFI%20->%20DRB)
- [PDCP](#PDCP)
- [RLC](#RLC)
- [MAC scheduler / UL grant](#MAC%20scheduler%20/%20UL%20grant)
- [PHY](#PHY)
- [Radio channel](#Radio%20channel)
- [gNB RU / DU / CU-UP](#gNB%20RU%20/%20DU%20/%20CU-UP)
- [N3 / GTP-U](#N3%20/%20GTP-U)
- [UPF](#UPF)
- [N6](#N6)
- [Data Network](#Data%20Network)
- [控制面准备](#控制面准备)

以上行链路为例，假设Agent a在B建筑的C房间中进行视频上传业务。
## Agent intent

Agent意图，表示Agent侧的应用业务需求，由Agent行为模拟接口返回。
Agent intent是原始输入，可以简单理解为“一个人想在油管上上传视频”。

```
Agent_Intent(
	agent_id="a",
	agent_pos = [x1,y1],
	action="upload",
	target="youtube_server",
	content={
		"type": "video",
        "size_bytes": 100 * 1024 * 1024,
	}
)
```

## UE request

UE请求，表示UE侧的终端网络请求，由Agent intent进一步得到。
UE request可以简单理解为“油管应用发出的上传视频的业务请求”

```
UE_Request(
	ue_id="a_phone",
	direction="UL",
	selected_access="5G",
	target="youtube_server",
	dnn="internet",
	pdu_session_type="IPv4",
	service_type="video_upload",
	size_bytes=100 * 1024 * 1024,
	qos_hint={
		"latency_budget_ms": 10000,
		"reliability": "normal",
		"throughput_preference": "high"
	}
)
```

- `dnn（Data Network Name）`：数据网络名。它用于指示UE 的 PDU Session 要接入哪个数据网络，在本项目中简化为决定UPF和N6出口。

## IP packets

IP包，应用业务数据被 UE 系统网络栈封装成的 IP 层数据单元。
这里作模拟只对一定量批次的IP包进行描述。

```
IP_TrafficBatch(
	src_ip="10.20.0.15",
	dst_ip="10.20.1.80",
	protocol="TCP",
	dst_port=443,
)
```

## QoS Flow / QFI

QFI, QoS Flow Identifier, 而QoS Flow 是 PDU Session 内的 QoS 区分单位。
这部分把 IP 业务流分类成 5G 系统内部可识别、可调度、可保障的 QoS 流。其中5QI表示5G QoS Identifier，决定 QoS Flow 的默认 QoS 特性。

QFI 是流 ID，5QI 是 QoS 模板。

```
	QoS_Flow(
	    pdu_session_id=10,
	    qfi=9,
	    five_qi=9,
	    direction="UL",
	    service_type="video_upload",
	    priority="normal",
	    packet_delay_budget_ms=300,
	    packet_error_rate=1e-6,
	    gbr_mbps=None,
	    mbr_mbps=None
	)
```

- `pdu_session_id`：PDU Session ID
- `packet_delay_budget_ms`：包时延预算
- `packet_error_rate`：目标错误率
- `gbr_mbps`：保证比特率，非 GBR 业务可为空
- `mbr_mbps`：最大比特率，可选

```
映射规则：

QoSRule(
    rule_id=1,
    match={
        "dst_ip": "youtube_server_ip",
        "protocol": "TCP",
        "dst_port": 443,
        "direction": "UL"
    },
    qfi=9
)
```

```
5QI表：

SERVICE_QOS_TABLE = {
    "video_upload": {
        "five_qi": 9,
        "priority": "normal",
        "packet_delay_budget_ms": 300,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr"
    },
    "game": {
        "five_qi": 80,
        "priority": "high",
        "packet_delay_budget_ms": 50,
        "packet_error_rate": 1e-3,
        "resource_type": "non_gbr"
    },
    "video_call": {
        "five_qi": 2,
        "priority": "high",
        "packet_delay_budget_ms": 150,
        "packet_error_rate": 1e-3,
        "resource_type": "gbr",
        "gbr_mbps": 2
    }
    ...
}
```


## SDAP: QFI -> DRB

Service Data Adaptation Protocol，服务数据适配协议。这部分把 5G Core / QoS Flow 层面的业务 QoS 分类，映射到 RAN 内部真正承载数据的无线承载 DRB。

```
SDAP_Mapping(
    pdu_session_id=10,
    qfi=9,
    drb_id=3,
    direction="UL",
    default_drb=True
)
```
`default_drb`: 是否为默认承载


```
DRB(
    drb_id=3,
    ue_id="alice_phone",
    pdu_session_id=10,
    qfi_list=[9],
    slice_id="embb",
    rlc_mode="AM",
    priority="normal",
    queue_bytes=104857600
)
```
- `qfi_list`：承载的QFI列表
- `slice_id`：网络切片ID
- `rlc_mode`：RLC 模式
- `priority`：调度优先级
- `queue_bytes`：当前待发送数据量
## PDCP

Packet Data Convergence Protocol，分组数据汇聚协议。这部分把上层业务数据整理成适合无线承载处理的 PDCP PDU，并提供安全、序号、重排序、去重等功能。
在发送端，PDCP添加SN（Sequence Number），头压缩，加密，完整性保护，最后生成生成 PDCP PDU。
在接收端，PDCP解密，完整性校验，按SN重排序，去重，去掉 PDCP header，最后交给 SDAP。

```
PDCP_Entity(
    drb_id=3,
    next_sn=0,
    header_overhead_bytes=2,
    ciphering_enabled=True,
    integrity_enabled=False,
    header_compression_enabled=False,
    reordering_buffer_bytes=0,
    delivered_bytes=0,
    dropped_bytes=0
)
```

- `next_sn`: 下一组序号起点
- `header_overhead_bytes`: 头字节数
- `ciphering_enabled`: 加密
- `integrity_enabled`: 完整性检查
- `header_compression_enabled`: 报头压缩
- `reordering_buffer_bytes`: 重排缓存字节数

同样地，我们每 tick 处理一批 bytes

```
PDCP_Batch(
    drb_id=3,
    sn_start=0,
    sn_end=399,
    payload_bytes=600000,
    overhead_bytes=800,
    output_bytes=600800
)
```

## RLC

Radio Link Control，无线链路控制层。
PDCP 交下来的数据大小不一定适合当前无线资源，MAC scheduler 每个 tick 只分配一部分无线资源，因此这部分把上层 PDCP 交来的数据整理成适合无线链路传输的形式，并根据模式决定是否重传、是否保证可靠性。

RLC存在三种模式：
- **TM**：Transparent Mode，透明模式。不加 RLC header，不分段/重传，用途较少，常用于某些控制信息。
- **UM**：Unacknowledged Mode，非确认模式。可以分段/重组，不做重传，低时延，允许少量丢失，适合语音、实时视频、游戏等。
- **AM**：Acknowledged Mode，确认模式。分段/重组，有确认和重传，可靠性高，时延可能增加，适合文件上传、网页、普通数据。

```
RLC_Queue(
    drb_id=3,
    mode="AM",
    queued_bytes=104857600,
    retransmission_bytes=0,
    delivered_bytes=0,
    dropped_bytes=0
)
```
- `queued_bytes`：等待首次发送的数据
- `retransmission_bytes`：等待重传的数据
- `delivered_bytes`：成功交给接收端的数据
- `dropped_bytes`：最终丢弃的数据

## MAC scheduler / UL grant

Medium Access Control，媒体接入控制层。
UL grant，gNB 给 UE 的上行发送许可和资源分配。

这部分决定在当前 tick，哪个 UE / 哪个 DRB 可以用多少无线资源、用什么 MCS、预计传多少数据。
这里不讨论调度算法实现，只考虑对外接口，下面只展示部分字段。
（此处将 SR(Scheduling Request)/BSR(Buffer Status Report) 简化为直接暴露 RLC queue size 给 MAC scheduler）

```
Scheduler_Input(
    tick=120,
    direction="UL",
    total_prbs=100,
    rlc_queues=[...],
    qos_flows=[...],
    drbs=[...],
    channel_states=[...],
    slice_policies=[...],
    harq_feedback=[...]
)
```

- `RLC queue`：RLC序列，表示谁有多少数据要发
- `ChannelState`: 信道状态，表示这个 UE 当前信道如何
- `Slice policy`: 切片策略，表示每个 slice 有多少资源预算
- `HARQ feedback`: Hybrid Automatic Repeat Request,  混合自动重传请求, 表示上一轮 PHY 传输是否成功。

```
MAC_Allocation(
    ue_id="alice_phone",
    drb_id=3,
    qfi=9,
    slice_id="embb",
    direction="UL",
    prbs=20,
    mcs=10,
    layers=1,
    scheduled_bytes=620000,
    expected_error_rate=0.03,
    is_retransmission=False
)
```

- `mcs`: Modulation and Coding Scheme，调制编码方案
- `layers`: MIMO 空间层数
- `scheduled_bytes`: 调度器预计本 tick 可发送的数据量
- `expected_error_rate`: 预计错误率
- `is_retransmission`: 这次调度是否主要用于重传

## PHY 

Physical Layer，物理层。
把 MAC 调度出来的数据真正变成无线信号发出去，或者把收到的无线信号解调还原成数据。
在我们项目中，可以简单理解实际传输。为统一视角理解，此部分顺带展开信道建模。
与MAC类似，这里我们不讨论内部实现，只考虑对外接口。
先看信道建模输入：

```
Channel_ModelInput(
    tick=120,
    ue_id="a_phone",
    ue_position=(520.0, 360.0),
    direction="UL",
    serving_gnb_id="gnb_001",
)
```

信道建模输出：
```
Channel_State(
    tick=120,
    ue_id="a_phone",
    gnb_id="gnb_001",
    direction="UL",
    distance_m=430.0,
    ue_area_id="student_union_entrance_lobby",
    ue_space_type="indoor",
    walls_crossed=["wall_01", "wall_02"],
    wall_loss_db=24.0,
    total_path_loss_db=144.5,
    received_power_dbm=-106.5,
    sinr_db=7.8,
    cqi=7,
    estimated_packet_error_rate=0.03
)
```
- `wall_loss_db`：墙体穿透损耗总和
- `total_path_loss_db`：总路径损耗
- `received_power_dbm`：接收端收到的信号功率
- `sinr_db`：信干噪比
- `cqi`：Channel Quality Indicator，调度器用来选 MCS

```
Phy_TransmissionInput(
    tick=120,
    allocation=MAC_Allocation(...),
    channel_state=ChannelState(...),

    harq_enabled=True,
    rlc_mode="AM",
    max_retx_attempts=4,
    random_seed=120
)
```
- `harq_enabled`:是否启用 HARQ 
- `rlc_mode`: RLC 模式，影响失败数据如何处理
- `max_retx_attempts`: 最大重传次数

```
TransmissionResult(
    tick=120,
    ue_id="alice_phone",
    gnb_id="gnb_001",
    drb_id=3,
    qfi=9,
    slice_id="embb",
    direction="UL",

    attempted_bytes=620000,
    successful_bytes=601400,
    failed_bytes=18600,

    effective_sinr_db=7.8,
    mcs=10,
    prbs=20,
    layers=1,

    harq_ack=False,
    harq_retx_bytes=18600,
    rlc_retx_bytes=0,
    dropped_bytes=0,

    transmission_delay_ms=1.0
)
```
- `layers`: MIMO 空间层数
- `harq_ack`: 是否传输成功到无需 HARQ 重传
- `harq_retx_bytes`: 进入 HARQ 快速重传的数据
- `rlc_retx_bytes`: 进入 RLC 重传队列的数据
- `dropped_bytes`: 最终丢弃的数据
- `transmission_delay_ms`: 本次 PHY/MAC 传输造成的基础时延

## Radio channel

见PHY中的信道建模部分。

## gNB RU / DU / CU-UP

gNB 即 5G 基站，在现代 5G 架构里，gNB 可以拆成多个部分：
gNB = RU + DU + CU，而其中CU又分为CU-CP和CU-UP。

### RU
Radio Unit，无线单元。
它最靠近天线，是真正“发射/接收无线信号”的硬件部分。

### DU
Distributed Unit，分布式单元。
它负责偏实时、低层的 RAN 功能，主要包括：RLC，MAC，部分 PHY，调度相关功能，HARQ。

### CU-UP
Central Unit - User Plane，集中单元用户面。
它负责较高层的用户面协议，主要包括：PDCP user plane，SDAP，GTP-U / N3 user-plane tunnel。

### CU-CP
Central Unit - Control Plane，集中单元控制面，主要包括：RRC，UE context，PDU Session Resource Setup，mobility control 和 AMF 的 N2/NGAP 信令。

要注意的是：
1. UE 侧也有 SDAP/PDCP/RLC/MAC/PHY 对等协议实体。gNB 侧 SDAP/PDCP 属于 CU-UP，RLC/MAC 属于 DU，PHY/RF 属于 RU/DU。
2. F1-U 是 DU 与 CU-UP 之间的用户面接口；F1-C 是 DU 与 CU-CP 之间的控制面接口。
3. gNB-CU-CP 通过 N2/NGAP 与 AMF 交互 PDU Session Resource Setup 等控制信令

## N3 / GTP-U

N3 是 5G 系统中RAN 和 UPF 之间的用户面接口，它只承载用户面数据，不负责控制面信令。控制面为N2: gNB-CU-CP <-> AMF。

GTP-U是GPRS Tunnelling Protocol - User Plane，在 N3 接口上用来封装用户数据的隧道协议。IP packet 本身不直接携带 5G 会话上下文，因此GTP-U 会给用户数据加一层隧道头TEID（Tunnel Endpoint Identifier），用于标识某条用户面隧道。

```
N3Tunnel(
    tunnel_id="n3_tunnel_1001",
    teid=1001,
    ue_id="a_phone",
    pdu_session_id=10,
    upf_id="internet_upf",
    qfi_list=[9],
    byte_count=0
)
```

```
N3ForwardingResult(
    tunnel_id="n3_tunnel_1001",
    forwarded_bytes=601400,
    n3_delay_ms=2,
    n3_loss_bytes=0
)
```

## UPF

User Plane Function，用户面功能。
它是 5G Core 里负责转发用户数据的核心节点，UE 数据从 RAN 进入核心网后，UPF 决定这批数据往哪里走、怎么转发、怎么统计、是否限速。

在UPF 收到 GTP-U 数据后：
1. 根据 TEID 找到 PDU Session
2. 解封装 GTP-U，取出内部 UE IP packet
3. 根据 PDR / FAR / QER 等规则处理
4. 根据 DNN 找到 N6 出口
5. 转发到 Data Network

## N6

N6 是UPF 和 Data Network 之间的接口。

## Data Network

Data Network 是 5G 系统外部或本地的数据网络，本例中需要上传到的数据网络为`internet`。

## 控制面准备

RM 表示注册状态（RM-DEREGISTERED / RM-REGISTERED），CM 表示 UE 与核心网控制面连接状态（CM-IDLE / CM-CONNECTED），RRC 表示 UE 与 gNB 的无线控制连接状态（RRC_IDLE / RRC_INACTIVE / RRC_CONNECTED）。

### 1. UE Registration

让 5GC 知道这个 UE 是谁、是否允许接入、当前在哪个注册区域。

```
RegistrationState(
    ue_id="a_phone",
    rm_state="REGISTERED",
    serving_amf="amf_001",
    allowed_slices=["embb", "urllc"],
    allowed_dnns=["internet", "campus"]
)
```

- `rm_state`：Registration Management 状态，表示 UE 是否已注册到 5GC
- `serving_amf`：当前服务该 UE 的 AMF

核心网认识 a_phone，知道它能用哪些 DNN / slice。
### 2. RRC Connection Establishment

建立 UE 与 gNB 之间的无线控制连接。

```
RrcConnection(
    ue_id="a_phone",
    serving_gnb="gnb_001",
    rrc_state="CONNECTED",
    srb_list=["SRB1", "SRB2"]
)
```

- `serving_gnb`: 当前服务 UE 的 gNB
- `rrc_state`: UE 与 gNB 之间的 RRC 状态
- `srb_list`: 已建立的信令无线承载列表

UE 和 gNB 之间存在控制面无线连接，可以配置承载和资源。
### 3. Service Request

如果 UE 已注册但处于空闲态，需要先恢复连接：让 CM-IDLE 的 UE 恢复到 CM-CONNECTED，以便发送业务或信令。

```
if ue.cm_state == "IDLE":
    service_request()
    ue.cm_state = "CONNECTED"
```

### 4. PDU Session Establishment

建立 UE 到某个 Data Network 的用户面会话。

```
PduSession(
    pdu_session_id=10,
    ue_id="a_phone",
    dnn="internet",
    s_nssai="embb",
    pdu_session_type="IPv4",
    ue_ip="10.20.0.15",
    smf_id="smf_001",
    upf_id="internet_upf",
    state="ACTIVE"
)
```
- `smf_id`：管理该会话的 SMF

UE 有了 PDU Session，知道自己接入 internet 这个 Data Network。UPF 已被选定，UE 获得 IP 地址


## 附页

这部分特别解释部分词汇。

### GBR/MBR
Guaranteed Bit Rate，保证比特率。
QoS Flow 需要网络尽量保证一个最低持续速率。

Maximum Bit Rate，最大允许速率。

### DRB/SRB
Data Radio Bearer，数据无线承载。
无线承载RB是基站为UE分配不同层协议实体及配置的总称。
相同的DRB负责为(用户)数据包提供相同的数据包转发处理。

与之对应的是SRB（Signaling Radio Bearer），信令无线承载。

### CQI
Channel Quality Indicator，信道质量指示。
它通常由 UE 根据信道测量得到，然后反馈给 gNB。范围一般是：1 ~ 15

### MCS
Modulation and Coding Scheme，调制编码方案。
它决定调制方式，编码率，每个 PRB 能承载多少 bit以及传输可靠性

### AMF
Access and Mobility Management Function，接入与移动性管理功能。
它是 5G Core 的控制面核心节点，主要负责：
- UE 注册
- UE 接入认证流程协调
- 连接管理 CM
- 移动性管理
- 选择 SMF
- 通过 N2/NGAP 和 gNB 交互控制信令

AMF 管“UE 能不能接入、当前连在哪里、移动时怎么管理”，但不转发用户数据。
### SMF
它是 5G Core 的控制面节点，主要负责：
- 建立/修改/释放 PDU Session
- 选择和控制 UPF（通过 N4/PFCP）
- 分配 UE IP 地址
- 配置用户面转发规则
- 管理 QoS 相关会话参数

SMF 管“这个 UE 的数据会话怎么建、走哪个 UPF、怎么转发”，但它本身不转发用户数据。

### NAS
Non-Access Stratum，非接入层信令。它是 UE 和 5G Core AMF 之间的控制面信令，被承载在 RRC 和 N2/NGAP 上，不属于无线接入层本身。
NAS 管 UE 和核心网之间的注册、会话、移动性等核心网控制逻辑。

### NGAP / N2
N2 是 gNB 和 AMF 之间的控制面接口。
NGAP 是NG Application Protocol，是运行在 N2 接口上的控制面协议。

他们的主要作用是：在 gNB 和 AMF 之间转发 NAS 消息；让 AMF 指挥 gNB 建立 RAN 资源。

### HARQ
Hybrid Automatic Repeat Request，混合自动重传请求。
它是 MAC/PHY 层的快速重传机制，用来处理无线传输失败。它比 RLC 重传更底层、更快。


---
# 🌙总览

最后完整走一次真实层次下的 a 上行完整路径，假设：
```
Agent a 在 B 建筑 C 房间
用 a_phone 上传 100MB 视频到 youtube_server
selected_access=5G
DNN=internet
PDU Session Type=IPv4
service_type=video_upload
```

前置状态：
```
UE 已注册到 5GC
UE 与 gNB 已建立 RRC connection
UE 已建立到 DNN=internet 的 PDU Session
核心网已选择 SMF/UPF
RAN 已为该 PDU Session 配置 QoS Flow、DRB、SDAP mapping
```

1. Agent / Intent：
	对应实体：人/agent + 应用行为
	`a 想上传一个 100MB 视频到 youtube_server`
	
2. Agent / Application / UE Request
	对应实体：应用 + OS 网络栈 + UE modem 控制逻辑
	`把“我要上传视频”整理成终端网络请求`
	
3. UE / IP Layer
	对应实体：UE 操作系统网络栈
	`应用数据被拆成 IP traffic`
	
4. UE / QoS Rule -> QoS Flow / QFI
	对应实体：UE 侧 QoS rule + 5G QoS framework
	`根据 service_type、DNN、目标地址、端口等匹配 QoS rule，随后给这批 IP traffic 标记 QFI`
	
5. UE / SDAP Transmitter
	对应实体：UE 侧 SDAP 实体
	`读取 QFI，根据 SDAP mapping 找到 DRB，把 对应的traffic 放入 DRB，必要时添加 SDAP header`

6. UE / PDCP Transmitter
	对应实体：UE 侧 PDCP 实体
	`给数据添加 PDCP SN，进行用户面加密，可选头压缩，生成 PDCP PDU后交给 RLC`

7. UE / RLC Transmitter
	对应实体：UE 侧 RLC 实体
	`把 PDCP PDU 排队，按 MAC grant 能力进行分段，在AM 模式下会维护重传队列，将可发送 RLC PDU 交给 MAC`

8. gNB / DU / MAC Scheduler and UL Grant
	对应实体：gNB-DU 的 MAC scheduler
	`选择 UE/DRB，分配 UL PRB，选择 MCS，生成 UL grant`

9. UE / MAC Transmitter
	对应实体：UE 侧 MAC 实体
	`接收 gNB 下发的 UL grant，从 RLC queue 取不超过 grant 允许的数据，组装 MAC PDU / Transport Block后交给 UE PHY`

10. UE / PHY Transmitter
	对应实体：UE baseband / PHY / RF
	`信道编码，调制，资源映射，MIMO layer mapping，射频发送`

11. Channel Modeling / Radio Environment（旁路状态输入，会同时影响MAC scheduler和PHY transmission）
	对应实体：真实无线传播环境
	`根据 a_phone 在 B 建筑 C 房间的位置，查询地图拓扑，得到室内/室外、距离、穿过墙体。结合 gNB 配置、频率、功率、噪声、干扰计算 SINR/CQI/PER`

12. gNB / RU Receiver
	对应实体：gNB RU
	`天线接收无线信号，射频下变频，做基础 PHY 前端处理，把数字基带数据交给 DU`
	
13. gNB / DU Receiver
	对应实体：gNB-DU
	`PHY 解调/解码结果进入 MAC，随后MAC 处理 HARQ ACK/NACK，RLC 重组 RLC PDU，在AM 模式下处理缺失和重传，把重组后的 PDCP PDU 通过 F1-U 交给 CU-UP`

14. gNB / CU-UP / PDCP Receiver
	对应实体：gNB-CU-UP 的 PDCP 实体
	`接收来自 DU/F1-U 的 PDCP PDU，解密，按 SN 重排序，去重，去 PDCP header，恢复上层数据`

15. gNB / CU-UP / SDAP Receiver
	对应实体：gNB-CU-UP 的 SDAP 实体
	`根据 DRB/QFI 关系恢复 QoS Flow，识别这批数据属于 PDU Session 10 / QFI 9，准备送入 N3 用户面隧道`

16. gNB / CU-UP -> N3 / GTP-U
	对应实体：gNB-CU-UP 与 UPF 之间的 N3 用户面接口
	`把 UE 的 IP packet 封装进 GTP-U，使用 TEID 标识 PDU Session 对应隧道，可携带 QFI 相关信息，随后通过 N3 发往 UPF`

17. UPF
	对应实体：5G Core User Plane Function
	`根据 TEID 找到 PDU Session，解封装 GTP-U，根据 PDR/FAR/QER 等用户面规则处理，按DNN=internet 选择 N6 出口，统计流量和 QoS`

18. N6
	对应实体：UPF 到 Data Network 的接口
	`把解封装后的 UE IP traffic 从 UPF 转发到 public internet`

19. Data Network / Target Service
	对应实体：public internet + youtube_server
	`internet 接收来自 N6 的 IP traffic，路由到 youtube_server，youtube_server 接收上传数据

下行路径从 Data Network -> UPF -> N3/GTP-U -> CU-UP -> DU -> RU/PHY -> UE，协议处理方向相反。要注意，下行不需要 UL grant，而是 gNB 直接调度 DL PRB。

---

# 🗓️ 时间

- **📅 创建**:  2026-07-05 21:07
- 🖌️
---
