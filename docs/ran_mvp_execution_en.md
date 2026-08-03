# RAN MVP Execution Logic

This document explains how the current RAN MVP runs from the fixed test scenario to the Data Network, and maps each stage to the relevant code files. The goal is to provide a minimal runnable chain with live preview support and a replaceable scheduler boundary. Internal algorithms remain MVP-level implementations that can be replaced module by module.

## 1. Test Scenario

- Scene: `bristol_topology`
- Agent: `student_a`
- Agent position: near the Student Union area at map coordinate `(520, 430)`
- UE: `student_a_phone`
- Access: `selected_access="5g"`, `access_type="3gpp"`
- Service: upload a 100 MB video to `youtube_server` over 5G
- DNN: `internet`
- Single gNB: `gnb_001`
- Initial gNB position: upper-left area of the map, approximately `(90, 90)`

Relevant code:

- Fixed scenario parameters: `ran/scenario.py`
- Scene loading: `services/scene_service.py`
- gNB loading from map data: `ran/radio/topology_adapter.py`
- Map data: `editor/data/scenes/bristol_topology.json`

## 2. Entry Points

Tick mode with live preview:

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode tick --ticks 5000 --tick-ms 50 -p
```

Execution path:

```text
simulation/main.py
-> parse_args()
-> SceneService.load_scene()
-> start_preview_server()
-> run_ran_mvp_tick()
-> RanEngine.build_upload_scenario()
-> SimulationLoop.run()
-> RanUploadScenario.step()
```

Aggregate mode:

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode aggregate --ticks 5000
```

Execution path:

```text
simulation/main.py
-> run_ran_mvp_aggregate()
-> RanEngine.run_agent_upload_demo()
-> RanUploadScenario.step() repeatedly
-> print final summary
```

Aggregate mode does not open the preview page. It prints a final summary. `tick_throughput_mbps` is the instantaneous throughput of the last tick, not cumulative average throughput.

## 3. Overall Chain

```text
AgentIntent
-> UERequest
-> AccessSelection
-> UE registration
-> PDU Session
-> IPTrafficBatch
-> QoSFlow / QFI
-> SlicePolicy
-> SDAP: QFI -> DRB -> SdapOutput
-> PDCPBatch
-> RLCQueue
-> ChannelState
-> SchedulerRequest JSON
-> JavaSchedulerAdapter
-> PythonBaselineScheduler fallback
-> SchedulerResult / MACAllocation
-> PHY TransmissionResult
-> gNB RU
-> gNB CU-UP / N3 GTP-U
-> UPF
-> N6
-> DataNetwork
-> QosMetrics / EndToEndResult
```

Core orchestration files:

- `ran/engine.py`: high-level RAN MVP entry point.
- `ran/scenario.py`: tick-based state machine for the fixed 100 MB upload scenario.
- `simulation/simulation_loop.py`: generic simulation tick loop, pause handling, logging, and preview state writing.

## 4. Stage-to-Code Mapping

| Stage | Role | Main input | Main output | Code files |
|---|---|---|---|---|
| Agent intent | Fixed student upload demand | agent, position, target, 100 MB | `AgentIntent` | `ran/scenario.py`, `ran/contracts/agent.py` |
| UE state | Create and register the phone UE | `AgentIntent` | `UEState` | `ran/ue/state.py`, `ran/core/amf.py`, `ran/contracts/ue.py` |
| UE request | Convert intent into a UE service request | `AgentIntent`, `ue_id` | `UERequest` | `ran/ue/request.py`, `ran/contracts/ue.py` |
| Access selection | Currently fixed to 5G/3GPP | `UERequest`, `GnbSite` | `AccessSelection` | `ran/access/selector.py` |
| PDU Session | Establish the minimal PDU session | `UEState`, `UERequest`, `slice_id` | `PduSession` | `ran/core/smf.py`, `ran/contracts/traffic.py` |
| IP traffic | Build the upload traffic batch | `UERequest`, `PduSession` | `IPTrafficBatch` | `ran/traffic/ip.py`, `ran/traffic/service_profile.py` |
| QoS Flow | Select QFI, 5QI, and delay budget | `UERequest`, service profile | `QoSFlow` | `ran/qos.py`, `configs/ran/service_profiles.json` |
| Network slice | Classify the service into a slice | service type | `slice_id`, `SlicePolicy` | `ran/slicing/classifier.py`, `ran/slicing/controller.py`, `configs/ran/slice_policies.json` |
| SDAP | Map QFI to DRB and emit a formal SDAP batch | `IPTrafficBatch`, `QoSFlow`, `UERequest` | `SdapOutput` (including `Drb`) | `ran/protocol/sdap.py`, `ran/contracts/bearer.py` |
| PDCP | Consume SDAP output and build a minimal PDCP batch | `SdapOutput` | `PdcpBatch` | `ran/protocol/pdcp.py` |
| RLC | Maintain queue and retransmission bytes | `PdcpBatch`, `Drb` | `RlcQueue` | `ran/protocol/rlc.py`, `ran/contracts/bearer.py` |
| Map channel | Calculate distance, wall loss, SINR, CQI | UE position, gNB position, map walls | `ChannelState` | `ran/radio/channel.py`, `ran/radio/topology_adapter.py`, `services/map_service.py` |
| Scheduler request | Aggregate MAC scheduling inputs | RLC, QoS, DRB, Channel, Slice | `SchedulerRequest` | `ran/gnb/du.py`, `ran/contracts/scheduler.py` |
| Java boundary | Keep the Java scheduler JSON interface | `SchedulerRequest` | `SchedulerResult` | `ran/scheduler/java_adapter.py` |
| Python fallback | Temporary Java replacement | `SchedulerRequest` | `MacAllocation` | `ran/scheduler/python_baseline.py` |
| OFDM/MIMO abstraction | Estimate capacity from PRB/MCS/layers | PRB, MCS, layers | scheduled bytes | `ran/radio/ofdm.py`, `ran/scheduler/python_baseline.py` |
| PHY | Convert error rate into success/failure/retransmission | `MacAllocation`, `ChannelState` | `TransmissionResult` | `ran/radio/phy.py`, `ran/contracts/radio.py` |
| RLC update | Remove transmitted bytes and add retransmissions | `RlcQueue`, `TransmissionResult` | updated `RlcQueue` | `ran/protocol/rlc.py` |
| gNB RU | Receive radio transmission result | `TransmissionResult` | `TransmissionResult` | `ran/gnb/ru.py` |
| CU-UP/N3 | Encapsulate and forward to N3 | `TransmissionResult`, `PduSession` | `N3ForwardingResult` | `ran/gnb/cu_up.py`, `ran/transport/n3_gtpu.py` |
| Backhaul | Minimal backhaul capacity boundary | `N3ForwardingResult` | `N3ForwardingResult` | `ran/transport/backhaul.py` |
| UPF | Forward to N6 | `N3ForwardingResult`, `PduSession` | `N6DeliveryResult` | `ran/core/upf.py` |
| Data Network | Receive target traffic | `N6DeliveryResult` | `N6DeliveryResult` | `ran/core/data_network.py`, `ran/transport/n6.py` |
| Metrics | Build tick metrics and end-to-end result | transmission, N3, N6, progress | `QosMetrics`, `EndToEndResult` | `ran/metrics/qos.py`, `ran/metrics/records.py` |

## 5. Java Scheduler Boundary

The Java scheduler is not connected yet. Python keeps the complete interface:

- Boundary file: `ran/scheduler/java_adapter.py`
- Current fallback: `ran/scheduler/python_baseline.py`
- Scheduler base class: `ran/scheduler/base.py`
- Input/output contracts: `ran/contracts/scheduler.py`

`SchedulerRequest` contains `tick`, `direction`, `total_prbs`, `rlc_queues`, `qos_flows`, `drbs`, `channel_states`, `slice_policies`, and reserved `harq_feedback`.

`SchedulerResult` returns `allocations` with PRB, MCS, layers, and scheduled bytes for each UE/DRB, plus `debug` metadata for logs and later debugging.

When replacing Java, prefer changing only `JavaSchedulerAdapter._send_to_java()` and keep the Python data contracts stable.

## 6. Slice, OFDM/MIMO, Preview, and Metrics

The MVP carries `slice_id` through UE request, PDU Session, QoS Flow, DRB, RLC queue, scheduler policy, and allocation. The current slice logic is a policy label and scheduler weight input, not a full isolated slice implementation.

OFDM/MIMO is a minimal system-level abstraction. `total_prbs` is the available PRB pool, `mcs` is the modulation and coding level, `layers` is the MIMO layer count, and `scheduled_bytes` is estimated from PRB, MCS, and layers.

The preview writes `outputs/live_state.json` through `LivePreviewService` and displays RAN tick status, UE/gNB information, CQI/SINR, PRB/MCS, transmission bytes, queue state, throughput, latency, completion ratio, remaining ratio, and loss rate.

Current metrics are MVP indicators only. They are useful for verifying the simulation chain but do not represent complete 3GPP KPI coverage.

## 7. Extension Order

1. Connect the real Java scheduler through `ran/scheduler/java_adapter.py`.
2. Extend `ran/slicing/controller.py` for AI/RIC-like slicing while keeping `SlicePolicy` as its output.
3. Improve `ran/radio/channel.py` and `ran/radio/ofdm.py` for more realistic channel, PRB, MCS, and MIMO behavior.
4. Add Wi-Fi/non-3GPP access later, without forcing it into the 5G MAC scheduler prematurely.
