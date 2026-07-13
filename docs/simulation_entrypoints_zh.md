# 仿真入口参数说明

当前主要入口是：

```bash
python -m simulation.main
```

## 通用参数

```text
-s, --scene
  场景名称。RAN MVP 建议使用 bristol_topology。

--ticks
  仿真 tick 数。

--tick-ms
  每个 tick 的真实等待时间，单位毫秒。

-p, --preview
  启动 live preview 页面。

--preview-port
  live preview 端口，默认 8766。

--console
  启动地图查询 console，不运行 tick loop。
```

## 地图查询模式

```bash
python -m simulation.main -s bristol_topology --console
```

用途：
- 查询坐标所在 area。
- 查询对象位置。
- 查询两点之间穿过的墙体。

## 普通仿真模式

```bash
python -m simulation.main -s bristol_topology --ticks 200 --tick-ms 500 -p
```

用途：
- 运行原有 tick loop。
- 当前 Agent 输入仍是 disabled。
- live preview 显示地图、console 和地图查询功能。

## RAN MVP 聚合模式

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode aggregate --ticks 5000
```

说明：
- 默认模式就是 `aggregate`。
- 内部会连续推进最多 `max(5000, --ticks)` 个 RAN tick。
- 最后只打印一行聚合结果。
- 不启动 live preview。

等价简写：

```bash
python -m simulation.main -s bristol_topology --ran-mvp
```

输出示例：

```text
ran_mvp=service_id=student_a_phone_video_upload_001 delivered=... undelivered=... tick_throughput_mbps=... latency_ms=... remaining_ratio=... loss_rate=...
```

## RAN MVP 逐 tick 模式

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode tick --ticks 5000 --tick-ms 50 -p
```

说明：
- 每个 simulation tick 调用一次 RAN scenario `step()`。
- 每 tick 写入 `outputs/live_state.json`。
- 配合 `-p` 可以在 live preview 中看到 RAN 状态。
- 到上传完成后，scenario 状态会变为 `completed`，但 simulation loop 会继续跑到 `--ticks` 结束。

live preview 会显示：
- RAN running/completed 状态。
- UE、gNB、目标业务。
- CQI、SINR、穿墙数量。
- PRB、MCS、本 tick 调度字节。
- 成功/失败字节、剩余队列。
- 累计 delivered/requested/完成比例。
- tick_throughput_mbps、packet path latency、completion_ratio、remaining_ratio、loss_rate。
- tick_throughput_mbps 表示当前 tick 的实时吞吐，不再提供累计平均吞吐。
- remaining_ratio 表示仍在队列中或等待重传的未完成比例；loss_rate 表示真实丢包率，只统计 dropped/N3/N6 等不可恢复丢弃。

## RAN demo 入口

也可以直接运行 RAN 包：

聚合 JSON：

```bash
python -m ran.demo -s bristol_topology --mode aggregate --max-ticks 5000
```

逐 tick JSON lines：

```bash
python -m ran.demo -s bristol_topology --mode tick --max-ticks 20
```

## 参数选择建议

快速看结果：

```bash
python -m simulation.main -s bristol_topology --ran-mvp
```

观察过程：

```bash
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode tick --ticks 5000 --tick-ms 50 -p
```

调试前几个 tick：

```bash
python -m ran.demo -s bristol_topology --mode tick --max-ticks 5
```
