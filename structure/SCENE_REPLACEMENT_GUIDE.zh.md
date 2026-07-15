# Scene Replacement Guide

This guide describes the recommended workflow for replacing the current home
scene with another 2D scene, such as a hospital, office, school, or shop.

## 1. Start With A 2D Concept Image

First create a simple top-down concept image, usually named `concept.png`.

The image should make these decisions visible:

- overall scene boundary
- major areas or rooms
- doors, openings, and corridors
- large blocking objects
- important interactive objects
- likely starting positions for actors

The concept image does not need to be beautiful. It should be clear enough that
someone can translate it into coordinates.

## 2. Decide The Coordinate System

Use a simple 2D meter-like coordinate system.

Recommended convention:

- top-left or lower-left can be chosen freely, but stay consistent
- all coordinates use the same unit
- every area is represented by bounds: `(x_min, y_min, x_max, y_max)`
- every element is represented by center and size: `(center_x, center_y)`,
  `(width, height)`

Before writing files, decide the total approximate scene size. For example:

```python
scene bounds: x = 0.0 .. 12.0, y = 0.0 .. 8.0
```

## 3. Design Areas

Areas are the main spatial regions the agent can reason about.

Examples:

- hospital: nurse station, ward, corridor, treatment room
- office: entrance, open office, meeting room, pantry
- school: classroom, corridor, office, library

Each area needs:

- stable id
- human-readable name
- rectangular bounds

Follow the current format in `space_layout.py`:

```python
AREA_DEFINITIONS = [
    ("nurse_station", "护士站", (0.0, 0.0, 3.0, 2.0)),
    ("ward_01", "病房", (3.0, 0.0, 8.0, 4.0)),
]
```

Area ids should be lowercase English identifiers. Area names can be Chinese or
natural language.

## 4. Design Portals

Portals describe doors, openings, or major connections between areas.

The current runtime mostly uses area bounds and pathfinding, while portals are
mainly useful for visualization and future navigation semantics. Still, define
them when they exist.

Follow the current format:

```python
PORTAL_DEFINITIONS = [
    {
        "id": "nurse_station_ward_opening",
        "name": "护士站到病房通道",
        "kind": "opening",
        "areas": ("nurse_station", "ward_01"),
        "segment": ((3.0, 0.8), (3.0, 1.4)),
    },
]
```

Recommended `kind` values:

- `door`
- `opening`
- `glass_door`
- `corridor`

## 5. Design Elements

Elements are the objects that occupy the scene.

Each element must belong to one area. Start with important objects only. Do not
model every tiny item.

Minimum fields:

```python
{
    "node_id": "hospital_bed_01",
    "name": "病床",
    "center": (4.2, 2.0),
    "size": (1.9, 0.9),
    "status": "regular",
    "movable": False,
}
```

Optional fields:

```python
{
    "blocks_movement": True,
    "evolution_status": "stable",
    "interaction_status": "idle",
    "state_details": {
        "bed_state": "empty",
        "sheet_state": "neat",
    },
}
```

Use `state_details` for element-specific facts. Keep them short and concrete.

## 6. Decide Blocking Rules

Blocking is currently inferred from element properties by the physics rules.

When designing a scene:

- large furniture and fixed equipment should usually be `movable=False`
- handheld or small objects can be `movable=True`
- objects that block walking should set `blocks_movement=True`
- flat or decorative objects that can be walked over should set `blocks_movement=False`
- avoid placing blocking elements so tightly that no perimeter point is reachable
- leave enough walking space around major interactive objects

After creating the scene, run a simple path or visualizer test to check whether
the actor can reach important areas and elements.

## 7. Build The Scene

For the current home scene, files are:

- `scenes/home/layout.py`
- `scenes/home/elements.py`
- `scenes/home/scene.py`

The root `space_layout.py` and `area_elements.py` files are compatibility
re-exports for the home scene.

For a new scene, either replace those data files during experiment, or create
new data files and call `build_scene_tree(...)`:

```python
from structure import build_scene_tree
from .layout import HOSPITAL_AREA_DEFINITIONS, HOSPITAL_PORTAL_DEFINITIONS
from .elements import HOSPITAL_AREA_ELEMENTS, HOSPITAL_BLOCKING_ELEMENT_IDS


def build_hospital_tree():
    return build_scene_tree(
        scene_id="hospital",
        scene_name="hospital_ward",
        area_definitions=HOSPITAL_AREA_DEFINITIONS,
        area_elements=HOSPITAL_AREA_ELEMENTS,
        blocking_element_ids=HOSPITAL_BLOCKING_ELEMENT_IDS,
        portal_definitions=HOSPITAL_PORTAL_DEFINITIONS,
        default_agent_start=HOSPITAL_AGENT_START,
    )
```

Register the scene in `scene_registry.py`:

```python
SCENE_BUILDERS = {
    "home": build_home_tree,
    "hospital": build_hospital_tree,
}
```

Then choose it at runtime:

```bash
python main.py --scene hospital
```

## 8. Set Actor Start Position

The actor start position is part of the scene setup.

The current `DEFAULT_AGENT_START` is designed for the home scene only. If a new
scene has a different coordinate system or room layout, choose a new start
position before running agents.

The start position should:

- lie inside an existing area
- not overlap a blocking element
- be close enough to the first expected area of activity
- match the actor's initial belief and persona context

For example:

```python
HOSPITAL_AGENT_START = (1.2, 1.0)  # nurse_station
```

## 9. Check The Scene

Before running agents, check:

- every area id is unique
- every element id is unique
- every element belongs to an existing area
- every element center lies inside its area bounds
- every element size is positive
- blocking elements use `blocks_movement=True`
- actor start position lies inside an area and does not overlap blocking elements
- important elements are reachable
- names are descriptive enough for LLM grounding

The most common failure is not semantic. It is usually spatial: the actor cannot
stand near the object, or the object is outside the intended area.

## 10. Then Adjust Persona, Desire, And Belief

Scene replacement only changes what exists in the world.

To make behavior match the new scene, also adjust:

- Persona: who the actor is
- Desire: what the actor wants
- Belief: what the actor knows or remembers

For example, a hospital map alone does not make Alice behave like a nurse. A
nurse persona and work goals are needed for that.
