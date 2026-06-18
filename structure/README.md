# Scene Structure

This directory is the scene definition boundary. A scene can be replaced or
extended by changing the spatial data here without changing the agent loop,
interaction engine, physics engine, or intent/action code.

The current maps are all single-building indoor scenes. Use the folders under
`scenes/` as references when creating a new map:

- `scenes/home/`
- `scenes/office/`
- `scenes/potions_teacher_office/`

Each scene keeps the same basic shape: a concept image, room layout data,
element data, blocking object ids, and a small builder function. Before adding a
new scene, first ask AI to generate the concept image for that map, then turn
that concept into structured layout and element files.

Current files:

- `scene_schema.py`: generic runtime objects, currently `Home`, `Area`, and `Element`.
- `scenes/home/`: home scene layout, portals, elements, blocking ids, and builder.
- `scenes/office/`: office scene layout, portals, elements, blocking ids, and builder.
- `scenes/potions_teacher_office/`: magic-school potions office scene data and concept/spec assets.
- `space_layout.py`: compatibility re-export for the home layout.
- `area_elements.py`: compatibility re-export for the home elements.
- `scene_tree.py`: generic scene builder plus the current `build_home_tree()` entry.
- `scene_registry.py`: scene name registry used by runtime entries such as `main.py --scene`.

To create another scene, such as a hospital, classroom, shop, or another indoor
house-scale map, provide:

- concept image: generated first, then stored in the new scene folder
- area definitions: `(area_id, area_name, bounds)`
- portal definitions: optional for visualization and future navigation semantics
- area elements: `{area_id: [element, ...]}`
- actor start position: an initial `(x, y)` that lies inside a valid area and is not blocked

Minimum element fields:

- `node_id`
- `name`
- `center`
- `size`

Optional element fields:

- `movable`, default `False`
- `blocks_movement`, default `False` unless the scene builder receives a matching blocking id
- `status` or `physical_status`, default `regular`
- `evolution_status`, default `stable`
- `interaction_status`, default `idle`
- `state_details`, default `{}`

Use `build_scene_tree(...)` for new scene data:

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

Register the scene in `scene_registry.py`:

```python
SCENE_BUILDERS = {
    "home": build_home_tree,
    "hospital": build_hospital_tree,
}
```

Then use the registered scene:

```python
from structure import build_scene

scene = build_scene("hospital")
```

After registration, the package automatically exposes the map through
`available_scene_names()` and loads it through `build_scene("hospital")`. No
other runtime code needs to know the scene folder directly.

If the scene uses a different coordinate layout, also configure the initial
actor position. The current `DEFAULT_AGENT_START` is only suitable for the home
scene.

`build_home_tree()` remains the compatibility entry for the current home scene.
