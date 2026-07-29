# RAN

RAN 旨在为 Human Behavior Simulation 增加更真实的无线网络影响。项目从二维室内场景结构出发，加入单小区无线接入网仿真模块。系统会根据每个 Agent 的空间位置、信道条件、业务需求和基础资源调度策略，生成时延、吞吐、丢包率和拥塞状态等网络 QoS 反馈。

当前仓库保留已有的场景结构包，并为后续 Agent、simulation、RAN、service、experiment 和 validation 模块准备项目布局。

## 安装

```bash
pip install -e .
```

## 当前目录

- `structure/`：已有场景 schema、场景构建器、场景注册表和室内地图数据。
- `ran/`：无线接入网模型，例如基站、信道、调度器、业务流和 QoS 逻辑。
- `agents/`：为未来 Agent 侧集成预留；当前没有实现 Agent 运行时逻辑。
- `simulation/`：主仿真循环、时钟、事件和全局状态。
- `services/`：连接场景、RAN 和指标模块的应用层封装。
- `experiments/`：实验加载、执行、对比和报告。
- `configs/`：项目、场景、RAN、调度器和实验配置。
- `outputs/`：本地运行输出，例如日志、指标和报告。
- `docs/`：项目文档和团队协作说明。

当前还没有专用的 `tests/` 目录。等 RAN 模块和仿真契约足够稳定后，再补充自动化检查。

## 场景快速开始

```python
from structure import available_scene_names, build_scene

print(available_scene_names())
scene = build_scene("home")
print(scene.to_dict())
```

更多场景细节见 [`structure/README.md`](structure/README.md)。

## 仿真快速开始

运行最小 tick 仿真循环：

```bash
python -m simulation.main
```

运行仿真时打开实时预览：

```bash
python -m simulation.main -p
```

默认实时预览地址：

```text
http://127.0.0.1:8766/editor/live/
```

运行校园地图并打开实时预览：

```bash
python -m simulation.main -s bristol_topology -p
```

打开交互式地图查询控制台：

```bash
python -m simulation.main -s bristol_topology --console
```

常用选项：

```bash
python -m simulation.main -s potions_teacher_office --ticks 300 --tick-ms 300 -p
```

- `-s` / `--scene`：已注册场景名。
- `--ticks`：运行的 game tick 数。
- `--tick-ms`：每个 tick 的毫秒数。
- `-p` / `--preview`：打开浏览器实时预览。
- `--console`：打开交互式地图查询控制台，而不是 tick loop。

实时预览读取 `outputs/live_state.json`，该文件由仿真循环生成，并被 Git 忽略。预览还会显示最近的仿真控制台输出，并提供地图查询能力。

地图查询命令：

```text
area <x> <y>
pos <object_id>
walls <x1> <y1> <x2> <y2>
```

- `area`：返回某个全局地图坐标所在的 area 和 child area。
- `pos`：按 id 返回 area、child area、element、wall、portal、road segment 或 road intersection 的全局位置。
- `walls`：返回两点连线穿过的所有墙体片段。室内建筑边界会作为外墙纳入；逻辑 child-area 边界不会被视为墙，除非显式定义了 wall。

服务层接口细节见 [`services/README.md`](services/README.md)。

Agent 侧当前处于禁用状态。每个 tick 会写入空的 `ran_requests` 列表；未来 RAN 输入应通过专门的 UE request provider 接入，而不是旧的 Agent mock。

## Structure 冒烟测试

在项目根目录运行以下命令，检查现有 `structure` 包是否仍可导入并构建已注册场景。

安装当前项目的 editable 版本：

```bash
python -m pip install -e .
```

检查场景注册并构建 `home` 场景：

```bash
python -c "from structure import available_scene_names, build_scene; print(available_scene_names()); scene = build_scene('home'); print(scene.node_id, scene.name, len(scene.areas))"
```

该命令验证：

- `pyproject.toml` 中的项目打包配置
- `structure` 包导入
- 场景注册表
- `home` 场景构建器
- 基础场景对象字段

检查更复杂的 `potions_teacher_office` 场景：

```bash
python -c "from structure import build_scene; scene = build_scene('potions_teacher_office'); print(scene.node_id); print(scene.default_agent_start); print(len(scene.get_all_elements()))"
```

该命令验证更复杂场景能否加载其默认 Agent 起点和元素数据。

运行内置场景树 demo：

```bash
python -m structure.scene_tree
```

这会构建并打印 `home` 场景树。

这些命令只是最小冒烟测试，不验证 Agent 行为、RAN 仿真、调度、QoS 计算、寻路或完整坐标有效性。
