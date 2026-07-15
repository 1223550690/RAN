# Simulation Entrypoint Parameters

The main entry point is:

```bash
python -m simulation.main
```

## Common Parameters

```text
-s, --scene
  Scene name. `bristol_topology` is recommended for the RAN MVP.

--ticks
  Number of simulation ticks.

--tick-ms
  Real wait time per tick, in milliseconds.

-p, --preview
  Start the live preview page.

--preview-port
  Live preview port. Default: 8766.

--console
  Start the map query console and do not run the tick loop.
```

## Map Query Mode

```bash
python -m simulation.main -s bristol_topology --console
```

Use this mode to query the area at a coordinate, the position of an object, or walls crossed by a line segment.

## Normal Simulation Mode

```bash
python -m simulation.main -s bristol_topology --ticks 200 --tick-ms 500 -p
```

This runs the existing tick loop. Agent input is currently disabled. The live preview displays the map, console, and map query tools.

## RAN MVP Aggregate Mode

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode aggregate --ticks 5000
```

Aggregate is the default RAN MVP mode. It advances up to `max(5000, --ticks)` RAN ticks internally, prints one aggregate result line, and does not start live preview.

Equivalent short form:

```bash
python -m simulation.main -s bristol_topology --ran-mvp
```

Example output:

```text
ran_mvp=service_id=student_a_phone_video_upload_001 delivered=... undelivered=... tick_throughput_mbps=... latency_ms=... remaining_ratio=... loss_rate=...
```

## RAN MVP Tick Mode

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode tick --ticks 5000 --tick-ms 50 -p
```

Each simulation tick calls `RanUploadScenario.step()`, writes `outputs/live_state.json`, and can show RAN state in live preview with `-p`.

The preview displays RAN status, UE, gNB, target service, CQI, SINR, wall count, PRB, MCS, scheduled bytes, successful/failed bytes, remaining queue, delivered/requested bytes, completion ratio, throughput, packet path latency, remaining ratio, and loss rate.

## RAN Demo Entrypoints

Aggregate JSON:

```bash
python -m ran.demo -s bristol_topology --mode aggregate --max-ticks 5000
```

Tick JSON lines:

```bash
python -m ran.demo -s bristol_topology --mode tick --max-ticks 20
```

## Parameter Recommendations

Quick result:

```bash
python -m simulation.main -s bristol_topology --ran-mvp
```

Observe the process:

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode tick --ticks 5000 --tick-ms 50 -p
```

Debug the first few ticks:

```bash
python -m ran.demo -s bristol_topology --mode tick --max-ticks 5
```
