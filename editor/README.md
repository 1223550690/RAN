# Scene Editor

This folder contains a standalone scene editor for the project.

The first version is a dependency-free browser app. Start a static server from
this folder and open the local URL in a browser. The scene preview module is
kept separate from the editor shell so it can later be reused by the main
simulation program.

```powershell
cd D:\Code\RAN\editor
python -m http.server 8765 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8765/`.

## Modules

- `src/app/`: editor bootstrap, state store, and property editor binding.
- `src/scene_model/`: scene data shape, sample scene, and adapters.
- `src/scene_preview/`: reusable canvas scene preview module.
- `src/styles/`: Fluent Design inspired editor styling.
- `data/scenes/`: exported JSON scene data loaded by the editor.

## Editing

- Use the scene selector to load a scene from `structure/scenes`.
- `community_outdoor` is a community-level map with outdoor road areas arranged
  like the Chinese character `艹`, three outdoor lots above, and the existing
  `home`, `office`, and `potions_teacher_office` indoor regions below.
- Left panel edits update the preview immediately.
- Area and element property groups are collapsible.
- Area metadata includes `space` (`indoor` / `outdoor`) and `area_type`.
- Hovering an element in the property panel highlights the same object in the
  preview.
- Drag objects in the preview to update their coordinates.
- Use the mouse wheel to zoom the preview. Hold `Alt` and drag, or use the
  middle mouse button, to pan.
- Use the Indoor / Outdoor highlight buttons to color indoor areas light green
  and outdoor areas light red.
- Right-click empty space to add an element.
- Right-click an element to copy or delete it.
- `Ctrl+Z` undoes the previous operation.
- `Ctrl+S` saves the current scene to browser `localStorage`.

Unsaved edits only affect the current browser session. Click Save or press
`Ctrl+S` to make the edited scene persist in this editor. Export JSON when you
need a file copy of the current edited scene.

## Reusable Preview

The preview can be reused without the full editor:

```js
import { ScenePreview } from "./src/scene_preview/ScenePreview.js";

const preview = new ScenePreview(canvasElement, {
  onElementMoved: ({ elementId, center }) => {},
  onContextMenu: ({ type, target, world }) => {},
});

preview.setScene(scene);
preview.setAgents(agentStates);
preview.setSignalMap(signalMap);
preview.setQosResults(qosResults);
preview.render();
```

The current overlay hooks are intentionally light. They reserve space for later
Agent position, RAN signal, and QoS visualization layers.
