# Services

`services/` contains application-level wrappers used by simulation code and the
live preview. These modules expose stable project-facing interfaces over lower
level scene data.

## MapService

`MapService` is defined in `services/map_service.py`. It provides read-only map
queries over a registered scene object.

### `get_area_at(scene, x, y)`

Returns the area information at a global map coordinate.

Input:

```python
scene
x: float
y: float
```

Output includes:

- `scene_id`
- `position`
- `local_position` when inside an area
- `area`
- `child_area`
- `space`
- `area_type`

If the coordinate is inside a building but not inside a defined child area, the
remaining space is returned as the building's auto open space.

Console command:

```text
area <x> <y>
```

### `get_object_position(scene, object_id)`

Returns global position information for a known object id.

Supported object types include:

- top-level area
- child area
- element
- wall
- portal
- road segment
- road intersection

Child-area and indoor element coordinates are converted from local building
coordinates into global map coordinates.

Console command:

```text
pos <object_id>
```

### `get_walls_between(scene, start, end)`

Returns all wall segments crossed by the line between two global map
coordinates.

Input:

```python
scene
start: tuple[float, float]
end: tuple[float, float]
```

Returned wall entries include:

- `wall_id`
- `name`
- `area_id`
- `area_name`
- `scope`
- `wall_type`
- `material`
- `thickness_m`
- `penetration_loss_db`
- `blocks_signal`
- `blocks_movement`
- `segment`
- `intersection`
- `distance_from_start`

Rules:

- Indoor top-level building boundaries are included as exterior walls.
- Explicit scene-level and building-level walls are included.
- Child-area logical bounds are not treated as walls unless an explicit wall is
  defined.
- Results are sorted by `distance_from_start`.

Console command:

```text
walls <x1> <y1> <x2> <y2>
```

This interface is intended for later wireless channel logic, where the channel
model needs to estimate wall penetration loss between a UE coordinate and a
base-station coordinate.
