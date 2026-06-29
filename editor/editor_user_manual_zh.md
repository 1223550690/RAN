# 场景编辑器使用说明书

## 用途

场景编辑器用于编辑项目中的地图 JSON 文件，主要位置是：

```text
editor/data/scenes/
```

编辑器支持地图预览、属性编辑、对象移动、缩放、删除、道路、墙体、portal 连接，以及直接保存回对应 JSON 文件和自动生成的 Python structure 场景包。

## 启动编辑器

必须从项目根目录启动可写入的编辑器服务：

```powershell
cd D:\Code\RAN
python -m editor.server --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/editor/
```

不要使用普通的 `python -m http.server` 进行编辑。普通静态服务器可以显示页面，但不能把保存结果写回 JSON 文件。

## 页面结构

编辑器分为两个主要区域：

- `Property editor`：左侧属性栏，用于编辑 scene、area、element、road、wall、portal 的属性。
- `Scene preview`：右侧预览区，用二维平面图方式显示地图。

顶部工具栏包括：

- `Scene`：选择要加载的场景。
- `Save`：将当前修改写回对应 JSON 文件。
- `Fit`：将地图自动适配到预览区。
- `Indoor`：切换室内区域高亮显示。
- `Export JSON`：导出当前场景 JSON。

预览区上方工具包括：

- `Road`：添加道路段。
- `Junction`：添加道路交汇矩形。
- `Portal`：选择两个对象创建 portal。
- `Wall`：添加墙体。
- `x, y`：显示当前鼠标所在格子的坐标。

## 场景选择

场景列表来自：

```text
editor/data/scenes/index.json
```

每个场景条目都会指向一个 JSON 文件。点击 `Save` 后，会写回这个场景对应的 JSON 文件，并重新生成对应的 `structure/scenes/<scene_id>/` 目录。

示例：

```json
{
  "id": "bristol_topology",
  "name": "Bristol 2000x2000 topology",
  "path": "./data/scenes/bristol_topology.json"
}
```

## 对象编辑

### 选中对象

在右侧预览区点击对象即可选中。左侧属性栏会自动跳转到对应对象。

目前支持从预览区跳转到属性栏的对象包括：

- area
- element
- road segment
- road intersection
- wall
- portal

### 移动对象

大部分对象需要先点击一次选中，然后才能拖动。

选中后，在预览区拖拽对象即可修改位置。

### 缩放对象

选中对象后，拖拽四角控制点可以缩放对象。

支持缩放的对象包括：

- element
- area
- road
- junction
- wall
- portal

### 锁定对象

如果对象的 `locked` 属性开启，则不能在预览区移动或缩放。

## 左侧属性栏

主要母对象栏包括：

- `Scene`：场景级属性。
- `Areas`：地图区域、建筑、室外空地、绿地、室内房间等。
- `Roads`：道路段和道路交汇点。
- `Walls`：墙体几何与信号穿透损耗相关属性。
- `Portals`：对象之间的连接关系。

点击标题栏可以展开或折叠对应分组。

## Area 详细页面

area 属性栏中的 `...` 按钮用于打开该 area 的详细页面。

例如，点击建筑或绿地区域的 `...`，会生成一个临时详细场景，用于编辑该区域内部内容。

注意：

- 详细页面是临时页面。
- 在详细页面点击 `Save`，内容会写回父场景 JSON。
- 在详细页面点击 `...`，会返回父场景。
- 返回父场景后，临时详细页面会从场景列表中移除。
- 道路类 area 不允许打开详细页面。

## 添加、复制、删除

在预览区右键：

- 右击空白处：`Add element`
- 右击 element：`Duplicate` 或 `Delete`
- 右击 road、wall、portal、area、junction：`Delete`

左侧属性栏中 area 下的 `+` 按钮可以为该 area 添加新 element。

新 element 的默认尺寸是：

```json
"size": [50, 50]
```

## Roads、Walls、Portals

### Roads

道路段由上下两条水平边定义：

```json
"top": { "y": 100, "x1": 100, "x2": 300 },
"bottom": { "y": 180, "x1": 120, "x2": 320 }
```

这种结构可以表示平行四边形道路，也能支持简单斜向道路。

### Junctions

Junction 是矩形道路交汇区域，用于连接道路段。

### Walls

墙体包含：

- `start`
- `end`
- `material`
- `penetration_loss_db`
- `blocks_movement`

这些数据后续可用于 RAN 信道模型，例如墙体穿透损耗。

### Portals

Portal 用于记录两个对象之间的连接。

Portal 的角色包括：

- `passage`：可通行连接。
- `connection`：逻辑或几何连接，例如多个矩形拼接成同一个区域。

## 保存机制

点击 `Save` 或按：

```text
Ctrl+S
```

编辑器会直接写入 `editor/data/scenes` 下对应的 JSON 文件。

同时也会重新生成：

```text
structure/scenes/<scene_id>/
  __init__.py
  elements.py
  layout.py
  scene.py
  README.md
```

这些 structure 文件属于自动生成结果，不建议手动修改。下次编辑器保存时，它们可能会被覆盖。

未保存的修改只存在于当前浏览器页面状态中。

保存后可以用 Git 查看文件变化：

```powershell
git status
```

## Git 使用建议

编辑并保存后：

```powershell
git status
git add editor/data/scenes/bristol_topology.json structure/scenes/bristol_topology
git commit -m "Update Bristol scene"
git push
```

如果多个人同时编辑同一个 JSON 文件，容易产生 Git 冲突。因此在不拆分协作的情况下，需要提前约定谁负责哪一块区域，尽量避免同时修改同一个文件的同一部分。

## 常见问题

### 页面显示 Directory listing

请打开：

```text
http://127.0.0.1:8765/editor/
```

不要只打开：

```text
http://127.0.0.1:8765/
```

### 保存失败

确认你使用的是：

```powershell
python -m editor.server --port 8765
```

普通静态服务器不能保存文件。

### 刷新后没有看到最新修改

可以按 `Ctrl+F5` 强制刷新浏览器资源。

同时确认顶部 `Scene` 下拉框中选择的是正确场景。

### 对象无法移动或缩放

检查对象是否开启了 `locked`。

### Area 无法打开详细页面

道路类 area 不能打开详细页面。建筑、室内区域、绿地和普通区域可以打开详细页面。
