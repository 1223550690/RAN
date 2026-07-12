# 🌈 Preface

This document describes the basic 5G RAN framework and related protocols used in this project. To describe the end-to-end data path, it also includes the necessary 5GC user-plane and control-plane abstractions.

---
# 💫 Main Text

## Basic Framework

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
- [Control-plane preparation](#Control-plane%20preparation)

Take the uplink path as an example. Assume Agent `a` is in room `C` of building `B` and is performing a video upload service.

## Agent intent

Agent intent represents the application-level service demand on the Agent side. It is returned by the Agent behavior simulation interface.
Agent intent is the original input. It can be understood simply as "a person wants to upload a video to YouTube".

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

UE request represents the terminal-side network request derived from the Agent intent.
It can be understood simply as "the video upload service request issued by the YouTube application".

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

- `dnn` (Data Network Name): the data network name. It indicates which data network the UE's PDU Session should access. In this project, it is simplified as a factor that determines the UPF and the N6 exit.

## IP packets

IP packets are the IP-layer data units generated when application service data is encapsulated by the UE system network stack.
For simulation purposes, only a batch of IP packets is described here.

```
IP_TrafficBatch(
	src_ip="10.20.0.15",
	dst_ip="10.20.1.80",
	protocol="TCP",
	dst_port=443,
)
```

## QoS Flow / QFI

QFI means QoS Flow Identifier. A QoS Flow is the QoS differentiation unit inside a PDU Session.
This part classifies IP service flows into QoS flows that can be identified, scheduled, and guaranteed inside the 5G system. 5QI means 5G QoS Identifier and determines the default QoS characteristics of a QoS Flow.

QFI is the flow ID. 5QI is the QoS template.

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

- `pdu_session_id`: PDU Session ID.
- `packet_delay_budget_ms`: packet delay budget.
- `packet_error_rate`: target error rate.
- `gbr_mbps`: guaranteed bit rate. It can be empty for non-GBR services.
- `mbr_mbps`: maximum bit rate. Optional.

```
Mapping rule:

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
5QI table:

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

SDAP means Service Data Adaptation Protocol. This part maps service QoS classification at the 5G Core / QoS Flow level to the Data Radio Bearer (DRB), which is the radio bearer that actually carries data inside the RAN.

```
SDAP_Mapping(
    pdu_session_id=10,
    qfi=9,
    drb_id=3,
    direction="UL",
    default_drb=True
)
```

`default_drb`: whether this is the default bearer.

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

- `qfi_list`: the QFI list carried by this bearer.
- `slice_id`: network slice ID.
- `rlc_mode`: RLC mode.
- `priority`: scheduling priority.
- `queue_bytes`: current amount of data waiting to be sent.

## PDCP

PDCP means Packet Data Convergence Protocol. This part organizes upper-layer service data into PDCP PDUs suitable for radio bearer processing, and provides security, sequence numbering, reordering, duplicate removal, and related functions.
At the transmitter, PDCP adds an SN (Sequence Number), performs header compression, ciphering, and integrity protection, and finally generates PDCP PDUs.
At the receiver, PDCP performs deciphering, integrity verification, SN-based reordering, duplicate removal, and PDCP header removal, then passes the recovered data to SDAP.

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

- `next_sn`: starting point of the next sequence number range.
- `header_overhead_bytes`: header size in bytes.
- `ciphering_enabled`: ciphering.
- `integrity_enabled`: integrity protection.
- `header_compression_enabled`: header compression.
- `reordering_buffer_bytes`: reordering buffer size in bytes.

Similarly, one batch of bytes is processed per tick:

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

RLC means Radio Link Control.
The data passed down from PDCP may not fit the radio resources available at the current moment. The MAC scheduler only allocates part of the radio resources in each tick. Therefore, RLC organizes the PDCP data into a form suitable for radio-link transmission and decides, according to the RLC mode, whether retransmission and reliability guarantees are required.

RLC has three modes:
- **TM**: Transparent Mode. It does not add an RLC header and does not perform segmentation or retransmission. It is used less frequently and is often used for certain control information.
- **UM**: Unacknowledged Mode. It can perform segmentation and reassembly, but does not perform retransmission. It has low latency and allows a small amount of loss, making it suitable for voice, real-time video, games, and similar services.
- **AM**: Acknowledged Mode. It performs segmentation and reassembly, supports acknowledgements and retransmissions, provides higher reliability, and may introduce additional delay. It is suitable for file upload, web traffic, and ordinary data services.

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

- `queued_bytes`: data waiting for first transmission.
- `retransmission_bytes`: data waiting for retransmission.
- `delivered_bytes`: data successfully delivered to the receiver.
- `dropped_bytes`: data finally dropped.

## MAC scheduler / UL grant

MAC means Medium Access Control.
UL grant means the uplink transmission permission and resource allocation given by the gNB to the UE.

This part decides, in the current tick, which UE / DRB can use how many radio resources, which MCS should be used, and how much data is expected to be transmitted.
The scheduling algorithm itself is not discussed here. Only the external interface is considered, and only part of the fields are shown below.
Here, SR (Scheduling Request) / BSR (Buffer Status Report) is simplified as directly exposing RLC queue size to the MAC scheduler.

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

- `RLC queue`: the RLC queue sequence, indicating who has how much data to send.
- `ChannelState`: channel state, indicating the current channel condition of this UE.
- `Slice policy`: slice policy, indicating the resource budget of each slice.
- `HARQ feedback`: Hybrid Automatic Repeat Request feedback, indicating whether the previous PHY transmission succeeded.

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

- `mcs`: Modulation and Coding Scheme.
- `layers`: number of MIMO spatial layers.
- `scheduled_bytes`: the amount of data that the scheduler expects to send in this tick.
- `expected_error_rate`: expected error rate.
- `is_retransmission`: whether this scheduling decision is mainly for retransmission.

## PHY

PHY means Physical Layer.
It converts the data scheduled by MAC into radio signals for transmission, or demodulates received radio signals back into data.
In this project, it can be understood simply as the actual transmission step. For a unified view, this section also includes channel modeling.
Similar to the MAC section, internal implementation details are not discussed here. Only the external interface is considered.
First, consider the channel-modeling input:

```
Channel_ModelInput(
    tick=120,
    ue_id="a_phone",
    ue_position=(520.0, 360.0),
    direction="UL",
    serving_gnb_id="gnb_001",
)
```

Channel-modeling output:

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

- `wall_loss_db`: total wall penetration loss.
- `total_path_loss_db`: total path loss.
- `received_power_dbm`: received signal power at the receiver.
- `sinr_db`: Signal-to-Interference-plus-Noise Ratio.
- `cqi`: Channel Quality Indicator, used by the scheduler to select the MCS.

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

- `harq_enabled`: whether HARQ is enabled.
- `rlc_mode`: RLC mode, which affects how failed data is handled.
- `max_retx_attempts`: maximum number of retransmission attempts.

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

- `layers`: number of MIMO spatial layers.
- `harq_ack`: whether the transmission succeeded without requiring HARQ retransmission.
- `harq_retx_bytes`: data entering fast HARQ retransmission.
- `rlc_retx_bytes`: data entering the RLC retransmission queue.
- `dropped_bytes`: data finally dropped.
- `transmission_delay_ms`: base delay caused by this PHY/MAC transmission.

## Radio channel

See the channel-modeling part in the PHY section.

## gNB RU / DU / CU-UP

gNB means 5G base station. In modern 5G architecture, a gNB can be split into multiple parts:
gNB = RU + DU + CU. The CU can be further divided into CU-CP and CU-UP.

### RU

RU means Radio Unit.
It is the hardware part closest to the antenna and is responsible for actually transmitting and receiving radio signals.

### DU

DU means Distributed Unit.
It is responsible for latency-sensitive and lower-layer RAN functions, mainly including RLC, MAC, part of PHY, scheduling-related functions, and HARQ.

### CU-UP

CU-UP means Central Unit - User Plane.
It is responsible for higher-layer user-plane protocols, mainly including PDCP user plane, SDAP, and the GTP-U / N3 user-plane tunnel.

### CU-CP

CU-CP means Central Unit - Control Plane. It mainly includes RRC, UE context, PDU Session Resource Setup, mobility control, and N2/NGAP signaling with the AMF.

Important notes:
1. The UE side also has peer SDAP / PDCP / RLC / MAC / PHY protocol entities. On the gNB side, SDAP / PDCP belong to CU-UP, RLC / MAC belong to DU, and PHY / RF belong to RU / DU.
2. F1-U is the user-plane interface between DU and CU-UP. F1-C is the control-plane interface between DU and CU-CP.
3. gNB-CU-CP interacts with the AMF over N2/NGAP for control signaling such as PDU Session Resource Setup.

## N3 / GTP-U

N3 is the user-plane interface between the RAN and the UPF in the 5G system. It only carries user-plane data and does not carry control-plane signaling. The control-plane interface is N2: gNB-CU-CP <-> AMF.

GTP-U means GPRS Tunnelling Protocol - User Plane. It is the tunneling protocol used on the N3 interface to encapsulate user data. An IP packet itself does not directly carry 5G session context, so GTP-U adds a tunnel header with a TEID (Tunnel Endpoint Identifier) to identify a specific user-plane tunnel.

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

UPF means User Plane Function.
It is the core 5G Core node responsible for forwarding user data. After UE data enters the core network from the RAN, the UPF decides where the data should go, how it should be forwarded, how it should be counted, and whether rate limiting should be applied.

After the UPF receives GTP-U data:
1. It finds the PDU Session according to the TEID.
2. It decapsulates GTP-U and extracts the inner UE IP packet.
3. It processes the packet according to rules such as PDR / FAR / QER.
4. It finds the N6 exit according to the DNN.
5. It forwards the packet to the Data Network.

## N6

N6 is the interface between the UPF and the Data Network.

## Data Network

The Data Network is an external or local data network in the 5G system. In this example, the data network to which the upload is sent is `internet`.

## Control-plane preparation

RM indicates registration state (RM-DEREGISTERED / RM-REGISTERED). CM indicates the connection management state between the UE and the core network control plane (CM-IDLE / CM-CONNECTED). RRC indicates the radio control connection state between the UE and the gNB (RRC_IDLE / RRC_INACTIVE / RRC_CONNECTED).

### 1. UE Registration

Registration lets the 5GC know who this UE is, whether it is allowed to access the network, and which registration area it is currently in.

```
RegistrationState(
    ue_id="a_phone",
    rm_state="REGISTERED",
    serving_amf="amf_001",
    allowed_slices=["embb", "urllc"],
    allowed_dnns=["internet", "campus"]
)
```

- `rm_state`: Registration Management state, indicating whether the UE has registered with the 5GC.
- `serving_amf`: the AMF currently serving this UE.

The core network knows `a_phone` and knows which DNNs / slices it can use.

### 2. RRC Connection Establishment

Establish a radio control connection between the UE and the gNB.

```
RrcConnection(
    ue_id="a_phone",
    serving_gnb="gnb_001",
    rrc_state="CONNECTED",
    srb_list=["SRB1", "SRB2"]
)
```

- `serving_gnb`: the gNB currently serving the UE.
- `rrc_state`: the RRC state between the UE and the gNB.
- `srb_list`: the list of established Signaling Radio Bearers.

There is now a control-plane radio connection between the UE and the gNB, and bearers and resources can be configured.

### 3. Service Request

If the UE is already registered but idle, the connection must be resumed first: a CM-IDLE UE is moved back to CM-CONNECTED so that service data or signaling can be sent.

```
if ue.cm_state == "IDLE":
    service_request()
    ue.cm_state = "CONNECTED"
```

### 4. PDU Session Establishment

Establish a user-plane session from the UE to a specific Data Network.

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

- `smf_id`: the SMF that manages this session.

The UE now has a PDU Session and knows that it is connected to the `internet` Data Network. The UPF has been selected, and the UE has obtained an IP address.

## Appendix

This section explains several terms.

### GBR/MBR

GBR means Guaranteed Bit Rate.
A QoS Flow requires the network to try to guarantee a minimum sustained rate.

MBR means Maximum Bit Rate.
It is the maximum allowed bit rate.

### DRB/SRB

DRB means Data Radio Bearer.
A Radio Bearer (RB) is a set of layer protocol entities and configurations allocated by the base station to the UE.
The same DRB provides the same packet-forwarding treatment for user data packets.

The corresponding concept is SRB (Signaling Radio Bearer), which carries signaling.

### CQI

CQI means Channel Quality Indicator.
It is usually obtained by the UE from channel measurements and then fed back to the gNB. Its common range is 1 to 15.

### MCS

MCS means Modulation and Coding Scheme.
It determines the modulation scheme, coding rate, how many bits each PRB can carry, and the transmission reliability.

### AMF

AMF means Access and Mobility Management Function.
It is a control-plane core node in the 5G Core and is mainly responsible for:
- UE registration.
- UE access authentication coordination.
- CM connection management.
- Mobility management.
- SMF selection.
- Control signaling exchange with the gNB over N2/NGAP.

The AMF manages whether the UE can access the network and where it is currently connected, as well as how mobility is handled. It does not forward user data.

### SMF

SMF is a control-plane node in the 5G Core and is mainly responsible for:
- Establishing, modifying, and releasing PDU Sessions.
- Selecting and controlling the UPF through N4/PFCP.
- Allocating UE IP addresses.
- Configuring user-plane forwarding rules.
- Managing QoS-related session parameters.

The SMF manages how the UE's data session is established, which UPF it uses, and how it is forwarded. The SMF itself does not forward user data.

### NAS

NAS means Non-Access Stratum signaling. It is control-plane signaling between the UE and the 5G Core AMF, carried over RRC and N2/NGAP. It does not belong to the radio access layer itself.
NAS handles registration, session, mobility, and other core-network control logic between the UE and the core network.

### NGAP / N2

N2 is the control-plane interface between the gNB and the AMF.
NGAP means NG Application Protocol, the control-plane protocol running on the N2 interface.

Their main role is to forward NAS messages between the gNB and the AMF and to allow the AMF to instruct the gNB to establish RAN resources.

### HARQ

HARQ means Hybrid Automatic Repeat Request.
It is a fast retransmission mechanism at the MAC/PHY layer used to handle radio transmission failures. It is lower-layer and faster than RLC retransmission.

---
# 🌙 Overview

Finally, here is the complete uplink path of Agent `a` through the realistic protocol layers. Assume:

```
Agent a is in room C of building B.
It uses a_phone to upload a 100 MB video to youtube_server.
selected_access=5G
DNN=internet
PDU Session Type=IPv4
service_type=video_upload
```

Prerequisite state:

```
The UE has registered with the 5GC.
The UE has established an RRC connection with the gNB.
The UE has established a PDU Session to DNN=internet.
The core network has selected the SMF/UPF.
The RAN has configured the QoS Flow, DRB, and SDAP mapping for this PDU Session.
```

1. Agent / Intent:
	Corresponding entity: person / agent + application behavior.
	`a wants to upload a 100 MB video to youtube_server`.

2. Agent / Application / UE Request
	Corresponding entity: application + OS network stack + UE modem control logic.
	`Organize "I want to upload a video" into a terminal-side network request`.

3. UE / IP Layer
	Corresponding entity: UE operating system network stack.
	`Application data is split into IP traffic`.

4. UE / QoS Rule -> QoS Flow / QFI
	Corresponding entity: UE-side QoS rule + 5G QoS framework.
	`Match the QoS rule according to service_type, DNN, target address, port, and other fields, then mark this batch of IP traffic with a QFI`.

5. UE / SDAP Transmitter
	Corresponding entity: UE-side SDAP entity.
	`Read the QFI, find the DRB according to the SDAP mapping, place the corresponding traffic into the DRB, and add an SDAP header if needed`.

6. UE / PDCP Transmitter
	Corresponding entity: UE-side PDCP entity.
	`Add a PDCP SN to the data, perform user-plane ciphering and optional header compression, generate PDCP PDUs, and pass them to RLC`.

7. UE / RLC Transmitter
	Corresponding entity: UE-side RLC entity.
	`Queue the PDCP PDUs, segment them according to MAC grant capacity, maintain the retransmission queue in AM mode, and pass transmittable RLC PDUs to MAC`.

8. gNB / DU / MAC Scheduler and UL Grant
	Corresponding entity: MAC scheduler in the gNB-DU.
	`Select the UE/DRB, allocate UL PRBs, select the MCS, and generate the UL grant`.

9. UE / MAC Transmitter
	Corresponding entity: UE-side MAC entity.
	`Receive the UL grant issued by the gNB, take data from the RLC queue without exceeding the grant, assemble a MAC PDU / Transport Block, and pass it to UE PHY`.

10. UE / PHY Transmitter
	Corresponding entity: UE baseband / PHY / RF.
	`Perform channel coding, modulation, resource mapping, MIMO layer mapping, and RF transmission`.

11. Channel Modeling / Radio Environment (side-state input that affects both MAC scheduler and PHY transmission)
	Corresponding entity: real radio propagation environment.
	`According to the position of a_phone in room C of building B, query the map topology to obtain indoor/outdoor status, distance, and crossed walls. Combine this with gNB configuration, frequency, power, noise, and interference to calculate SINR/CQI/PER`.

12. gNB / RU Receiver
	Corresponding entity: gNB RU.
	`Receive the radio signal through the antenna, perform RF down-conversion and basic PHY front-end processing, and pass the digital baseband data to the DU`.

13. gNB / DU Receiver
	Corresponding entity: gNB-DU.
	`PHY demodulation/decoding results enter MAC. MAC then handles HARQ ACK/NACK. RLC reassembles RLC PDUs, handles missing data and retransmission in AM mode, and passes the reassembled PDCP PDUs to CU-UP through F1-U`.

14. gNB / CU-UP / PDCP Receiver
	Corresponding entity: PDCP entity in gNB-CU-UP.
	`Receive PDCP PDUs from DU/F1-U, decipher them, reorder by SN, remove duplicates, remove the PDCP header, and recover upper-layer data`.

15. gNB / CU-UP / SDAP Receiver
	Corresponding entity: SDAP entity in gNB-CU-UP.
	`Recover the QoS Flow according to the DRB/QFI relationship, identify that this batch of data belongs to PDU Session 10 / QFI 9, and prepare to send it into the N3 user-plane tunnel`.

16. gNB / CU-UP -> N3 / GTP-U
	Corresponding entity: N3 user-plane interface between gNB-CU-UP and UPF.
	`Encapsulate the UE IP packet into GTP-U, use the TEID to identify the tunnel corresponding to the PDU Session, optionally carry QFI-related information, and send it to the UPF through N3`.

17. UPF
	Corresponding entity: 5G Core User Plane Function.
	`Find the PDU Session according to the TEID, decapsulate GTP-U, process the packet according to user-plane rules such as PDR/FAR/QER, select the N6 exit according to DNN=internet, and collect traffic and QoS statistics`.

18. N6
	Corresponding entity: interface from UPF to Data Network.
	`Forward the decapsulated UE IP traffic from the UPF to the public internet`.

19. Data Network / Target Service
	Corresponding entity: public internet + youtube_server.
	`The internet receives IP traffic from N6, routes it to youtube_server, and youtube_server receives the uploaded data`.

The downlink path is Data Network -> UPF -> N3/GTP-U -> CU-UP -> DU -> RU/PHY -> UE, with protocol processing in the opposite direction. Note that downlink does not require a UL grant; the gNB directly schedules DL PRBs.

---

# 🗓️ Time

- **📅 Created**: 2026-07-05 21:07
- 🖌️
---
