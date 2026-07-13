# Scene Structure

该目录是场景定义边界。通过修改这里的空间数据，可以替换或扩展场景，而不需要修改 agent loop、interaction engine、physics engine 或 intent/action 代码。

当前地图都是单建筑室内场景。创建新地图时，可以参考 `scenes/` 下的文件夹：

- `scenes/home/`
- `scenes/office/`
- `scenes/potions_teacher_office/`

每个场景保持相同的基本形态：概念图、房间布局数据、元素数据、阻挡对象 id 和一个小型 builder 函数。添加新场景前，先让 AI 生成该地图的概念图，再把概念图转换为结构化 layout 和 element 文件。

当前文件：

- `scene_schema.py`：通用运行时对象，目前包括 `Home`、`Area` 和 `Element`。
- `scenes/home/`：home 场景布局、portal、element、blocking id 和 builder。
- `scenes/office/`：office 场景布局、portal、element、blocking id 和 builder。
- `scenes/potions_teacher_office/`：魔法学校魔药办公室场景数据与概念/spec 资源。
- `space_layout.py`：home layout 的兼容性 re-export。
- `area_elements.py`：home elements 的兼容性 re-export。
- `scene_tree.py`：通用场景 builder，以及当前 `build_home_tree()` 入口。
- `scene_registry.py`：场景名注册表，供 `main.py --scene` 等运行入口使用。

创建 hospital、classroom、shop 或其他室内 house-scale 地图时，需要提供：

- 概念图：先生成，再存入新场景文件夹。
- area definitions：`(area_id, area_name, bounds)`。
- portal definitions：可选，用于可视化和未来导航语义。
- area elements：`{area_id: [element, ...]}`。
- actor start position：位于有效 area 内、且不被阻挡的初始 `(x, y)`。

最小 element 字段：

- `node_id`
- `name`
- `center`
- `size`

可选 element 字段：

- `movable`，默认 `False`
- `blocks_movement`，默认 `False`，除非 scene builder 接收到匹配的 blocking id
- `status` 或 `physical_status`，默认 `regular`
- `evolution_status`，默认 `stable`
- `interaction_status`，默认 `idle`
- `state_details`，默认 `{}`

新场景数据使用 `build_scene_tree(...)`：

```python
from structure import build_scene_tree
from structure.scenes.hospital.layout import HOSPITAL_AREA_DEFINITIONS, HOSPITAL_PORTAL_DEFINITIONS
from structure.scenes.hospital.elements import HOSPITAL_AREA_ELEMENTS, HOSPITAL_BLOCKING_ELEMENT_IDS

scene = build_scene_tree(
    scene_id="hospital",
    scene_name="hospital_ward",
    area_definitions=HOSPITAL_AREA_DEFINITIONS,
    area_elements=HOSPITAL_AREA_ELEMENTS,
    blocking_element_ids=HOSPITAL_BLOCKING_ELEMENT_IDS,
    portal_definitions=HOSPITAL_PORTAL_DEFINITIONS,
    default_agent_start=(1.2, 1.0),
)
```

在 `scene_registry.py` 中注册场景：

```python
SCENE_BUILDERS = {
    "home": build_home_tree,
    "hospital": build_hospital_tree,
}
```

然后使用已注册场景：

```python
from structure import build_scene

scene = build_scene("hospital")
```

注册后，包会自动通过 `available_scene_names()` 暴露地图，并通过 `build_scene("hospital")` 加载。其他运行时代码不需要直接知道场景文件夹。

如果场景使用不同坐标布局，也需要配置初始 actor 位置。当前 `DEFAULT_AGENT_START` 只适合 home 场景。

`build_home_tree()` 仍然保留为当前 home 场景的兼容入口。
