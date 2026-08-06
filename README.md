# RAN 5G Simulation System (Integrated)

> Built on the merged branches of five members (haoyu / boyu / xizhe / tr22068 / zhiqian), with system-level capabilities filled in at the integration layer.

---

## 1. Project Overview

This project extends the Human Behavior Simulation platform (2D scene + human behavior agents) with a **single-cell 5G RAN simulation module**: agents generate communication intents (messaging / video / web / gaming etc.), and the system completes end-to-end network processing — registration → access → session → scheduling → transmission → delivery — driven by spatial position, indoor/outdoor area, channel conditions, resource availability and scheduling policy, while exporting real-time metrics.

### 1.1 Merged Foundation (Member Contributions)

| Member | Module | Content |
|---|---|---|
| haoyu | UE registration & access selection | RM/CM registration state machine, 3GPP/Wi-Fi access selection |
| boyu | SMF IP QoS + SDAP | PDU session management (IP/slice/validation), QoS flow→DRB mapping, IP traffic factory |
| xizhe | PDCP/RLC entity pipeline | PDCP sequence numbers/overhead, RLC segmentation/ARQ retransmission/SN management entities |
| tr22068 | MAC scheduler | 4 algorithms (round-robin / max-throughput / BSR grant / weighted), PHR, Java adapter |
| zhiqian | Radio channel | coordinate calibration, propagation geometry, 3GPP 38.901 path loss (UMi/InH/O2I), beamforming |
| Integration layer | System completeness | see 1.2 |

### 1.2 New Capabilities at the Integration Layer

- **Control plane**: AMF CM/RRC state machine (TS 24.501 / 38.331; suspends to RRC_INACTIVE between services)
- **User plane entities**: UPF entity + N3 GTP-U tunnels (UL/DL; GTP overhead accounting; optional N3 rate limiting)
- **Downlink path**: DN → N6 → UPF buffer → N3 → gNB → radio → UE, complete chain
- **Hybrid CKM + beamforming**: physical priors + sparse-reference calibration + GP residual + 8-beam codebook; pre-generated at simulation start with version-keyed caching; hybrid mode on by default, can be disabled for comparison
- **Standard CQI/MCS/BLER tables** (TS 38.214) replacing linear mapping; noise `-174+10lg(BW)+NF`
- **Congestion & service-failure detection**: PRB utilisation / queue backlog / waiting-ticks metrics; long starvation → FAILED
- **Multi-UE tunnel isolation**: UPF tunnel/buffer keys include `ue_id` (fixes multi-UE PDU session ID collisions)
- **Entity pipeline in the runtime**: MultiAgentRanScenario fully switched to xizhe's PDCP/RLC entities (functional API kept for compatibility)
- **Agent subsystem**: template/LLM dual-mode planning, navigation (pathfinding/semantic targets), intent gateway, stationary templates (`stay`)
- **Runtime engineering**: single-instance lock, true pause (file control channel), guarded preview server, one-shot launcher, auto browser open
- **Frontend preview**: MD3 light-blue bilingual UI, live map (top-level agents as authoritative source), heatmap overlay (adaptive colour scale, toggleable), task panel (template mode), 8 chart types in a single chart with dropdown switcher (multi-UE multi-line + hover values)

## 2. Quick Start

### 2.1 Environment

```bash
# Zero third-party dependencies (Python 3.10+); pytest/playwright optional for tests
python -m simulation.main --help
```

### 2.2 One-shot demo (default template)

```bash
python start_demo.py --ticks 800 --tick-ms 200
```

Starts the simulation plus the preview server (8766) and opens the browser when ready.

### 2.3 Manual run

```bash
# Custom template + preview
python -m simulation.main -s bristol_topology --agent-sim --agents-config configs/agents/template_different_buildings_video_download.json --ticks 800 --tick-ms 200 --preview

# Simulation only (no preview)
python -m simulation.main -s bristol_topology --agent-sim --agents-config configs/agents/deterministic_three_agents_bristol.json --ticks 800 --tick-ms 200
```

### 2.4 Key parameters

| Parameter | Description | Default |
|---|---|---|
| `-s / --scene` | Scene (Bristol for now) | bristol_topology |
| `--ticks` | Number of simulation ticks | 3000 |
| `--tick-ms` | Duration per tick (1 tick = one radio slot semantic) | 200 |
| `--agents-config` | Template config file (JSON) | deterministic template |
| `--agent-speed` | Movement speed (m/tick) | 2.0 |
| `--preview` | Start preview server and open browser | off |
| `--n3-bandwidth-mbps` | N3 backhaul rate limit (None = instantaneous) | None |
| `--max-waiting-ticks` | Service-failure threshold (0 = disabled) | 600 |
| `--llm-*` | LLM mode (endpoint/model/key, provided at runtime, never committed) | off |

### 2.5 Channel mode switching (for comparison experiments)

`configs/ran/channel_model.json` → the `mode` of bristol:

- `hybrid` (default): hybrid CKM (physics + calibration + GP residual + beam)
- `shadow` / `legacy`: comparison modes with CKM disabled
- `RAN_DISABLE_CKM=1` env var: skip CKM construction (debug acceleration)

## 3. Custom Simulation Templates

A template is a single JSON file (`configs/agents/*.json`):

```json
{
  "simulation_id": "my_template",
  "seed": 42,
  "loop_policy": "stop",
  "llm_mode": false,
  "agents": [
    { "agent_id": "student_001", "role": "student",
      "spawn_position": [520.0, 300.0], "ue_id": "student_001_phone" }
  ],
  "plans": {
    "student_001": [
      { "destination_ref": "Block 09 / Student Union / Food Service South",
        "intent_type": "video_upload",
        "intent_parameters": { "size_profile": "medium" },
        "stay": true }
    ]
  }
}
```

### Field reference

| Field | Description |
|---|---|
| `spawn_position` | Spawn point (map coordinates); with `stay: true` this is also where the service starts |
| `destination_ref` | Semantic destination (scene path, e.g. `Block 09 / Student Union / Food Service South`); display-only with `stay` |
| `intent_type` | Traffic type (see below) |
| `intent_parameters` | `size_profile` (small/medium/large) or `duration_seconds`/`bitrate_kbps` (video_call) |
| `stay` | `true` = stationary, submits the service immediately (used by channel-comparison templates) |

### Supported intent types

| Type | Direction | Description |
|---|---|---|
| `message` | UL | Short message (fixed 4KB) |
| `video_upload` | UL | Video upload (size_profile) |
| `video_download` | DL | Video download (size_profile) |
| `video_call` | UL | Video call (duration_seconds + bitrate_kbps) |
| `web_browse` | DL | Web browsing (small packets, low-latency preference) |
| `gaming` | DL | Online gaming (low-latency, high-reliability preference) |
| `file_transfer` | UL | File transfer (size_profile) |

### Example templates

- `deterministic_three_agents_bristol.json`: three agents moving + multiple services (default)
- `template_same_building_three_services.json`: 3 services in the same building (upload/download/message×3, stationary) — compares different services under similar channels
- `template_different_buildings_video_download.json`: 3× video download in different buildings (near indoor / deep indoor tower / outdoor) — compares the same service under different channels

## 4. System Architecture

```
Agent subsystem (movement/planning/intent)      RAN scene (ran/)
┌──────────────────────────┐   ┌─────────────────────────────────┐
│ runtime/state_machine    │   │ Registration(AMF)→ Access(selector)│
│ navigation(astar/room)   │   │ → Session(SMF)→ SDAP → PDCP → RLC  │
│ planning(template/LLM)   │   │ → Scheduling(4 algos)→ PHY → N3/UPF │
│ intent_gateway           │   │ Channel: geometry → 3GPP → CKM     │
└──────────┬───────────────┘   └──────────────┬──────────────────┘
           └──── intent/state ────────────────┘
                     ↓
        Preview server (live_state.json) → Frontend (map/charts/task panel)
```

## 5. Tests

```bash
python -m unittest discover -s tests -t .        # full unit test suite
python -m pytest tests/ -k "not aggregate"       # pytest (optional)
```
