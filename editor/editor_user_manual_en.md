# Scene Editor User Manual

## Purpose

The scene editor is used to edit the project map JSON files under:

```text
editor/data/scenes/
```

It supports map preview, property editing, object movement, resizing, deletion, portals, roads, walls, and direct saving back to the corresponding JSON file and generated Python structure package.

## Start The Editor

Run the writable editor server from the project root:

```powershell
cd D:\Code\RAN
python -m editor.server --port 8765
```

Open:

```text
http://127.0.0.1:8765/editor/
```

Do not use plain `python -m http.server` for editing. A plain static server can display the page, but it cannot write changes back to JSON files.

## Page Layout

The editor has two main panels:

- `Property editor`: left panel. It shows editable scene, area, element, road, wall, and portal properties.
- `Scene preview`: right panel. It shows the map as a 2D floor-plan style canvas.

The top toolbar includes:

- `Scene`: choose which scene JSON to load.
- `Save`: write current changes to the corresponding JSON file.
- `Fit`: fit the current map into the preview area.
- `Indoor`: toggle indoor-area highlight.
- `Export JSON`: download the current scene JSON.

The preview toolbar includes:

- `Road`: add a road segment.
- `Junction`: add a road intersection.
- `Portal`: select two objects to create a portal.
- `Wall`: add a wall.
- `x, y`: current mouse grid coordinate.

## Scene Selection

Scenes are loaded from:

```text
editor/data/scenes/index.json
```

Each scene entry points to a JSON file. Saving writes back to that same file and regenerates the matching `structure/scenes/<scene_id>/` package.

Example:

```json
{
  "id": "bristol_topology",
  "name": "Bristol 2000x2000 topology",
  "path": "./data/scenes/bristol_topology.json"
}
```

## Editing Objects

### Select

Click an object in the preview to select it. The property editor will jump to the matching item.

Supported preview-to-property jump:

- area
- element
- road segment
- road intersection
- wall
- portal

### Move

Most map objects must be clicked once before they can be moved.

After selection, drag the object in the preview.

### Resize

After selection, drag a corner handle to resize the object.

Supported resizable objects include:

- elements
- areas
- roads
- junctions
- walls
- portals

### Lock

Objects with `locked` enabled cannot be moved or resized from the preview.

## Property Editor

Main sections include:

- `Scene`: scene-level fields.
- `Areas`: map regions, buildings, outdoor lots, green spaces, and indoor rooms.
- `Roads`: road segments and junctions.
- `Walls`: wall geometry and radio attenuation properties.
- `Portals`: logical or physical links between objects.

Object sections can be collapsed and expanded by clicking the section header.

## Area Detail Pages

The `...` button on an area opens its detail page.

For example, opening a building or green area creates a temporary detail scene for editing that area internally.

Important behavior:

- Detail pages are temporary.
- Saving a detail page writes its contents back into the parent scene JSON.
- In a detail page, the `...` button returns to the parent scene.
- Temporary detail pages are removed from the scene selector after returning.
- Road areas cannot open detail pages.

## Add, Duplicate, Delete

Right-click the preview:

- empty space: `Add element`
- existing element: `Duplicate` or `Delete`
- road, wall, portal, area, junction: `Delete`

The `+` button in the property editor adds a new element under the relevant area.

New elements default to:

```json
"size": [50, 50]
```

## Roads, Walls, And Portals

### Roads

Road segments are represented by top and bottom horizontal edges:

```json
"top": { "y": 100, "x1": 100, "x2": 300 },
"bottom": { "y": 180, "x1": 120, "x2": 320 }
```

This allows slanted road shapes as parallelograms.

### Junctions

Junctions are rectangular road intersections. They are used to connect road segments.

### Walls

Walls have:

- `start`
- `end`
- `material`
- `penetration_loss_db`
- `blocks_movement`

Wall data is useful for later RAN channel modeling.

### Portals

A portal records a connection between two objects.

Portal roles:

- `passage`: a traversable connection.
- `connection`: a geometry-only connection, useful when multiple shapes represent the same logical area.

## Save Behavior

Click `Save` or press:

```text
Ctrl+S
```

The editor writes directly to the scene JSON file under `editor/data/scenes`.
It also regenerates:

```text
structure/scenes/<scene_id>/
  __init__.py
  elements.py
  layout.py
  scene.py
  README.md
```

These structure files are generated outputs. Do not edit them manually because the next editor save may overwrite them.

Unsaved changes only exist in the current browser session.

After saving, use Git to check the file changes:

```powershell
git status
```

## Git Workflow

After editing and saving:

```powershell
git status
git add editor/data/scenes/bristol_topology.json structure/scenes/bristol_topology
git commit -m "Update Bristol scene"
git push
```

If a team member edits the same JSON file at the same time, Git conflicts may occur. Coordinate before editing the same scene.

## Common Problems

### Page shows directory listing

Open:

```text
http://127.0.0.1:8765/editor/
```

Do not open only:

```text
http://127.0.0.1:8765/
```

### Save fails

Make sure the editor is started with:

```powershell
python -m editor.server --port 8765
```

Plain static servers cannot save files.

### Changes do not appear after refresh

Use `Ctrl+F5` to force-refresh browser assets.

Also make sure you are loading the correct scene from the scene selector.

### Object cannot move or resize

Check whether `locked` is enabled.

### Area cannot open detail page

Road areas cannot open detail pages. Buildings, indoor areas, green spaces, and normal areas can.
