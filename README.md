# RAN

Reusable indoor map and scene-structure definitions extracted from the world
simulation project.

This repository contains the standalone `structure` Python package. It defines
scene schemas, scene builders, registry helpers, and example single-house indoor
scenes with layout data, element data, and concept images.

The goal is to make it easy to extend the map set. Start by studying the three
existing scenes in [`structure/scenes`](structure/scenes): `home`, `office`, and
`potions_teacher_office`. They are all single-building indoor scenes and can be
used as references for room layout, portals, blocking objects, element metadata,
and scene builders.

When creating a new scene, first ask AI to produce a concept image, following
the same pattern as the existing scenes. After that, add the scene folder with
its `layout.py`, `elements.py`, `scene.py`, `__init__.py`, and image asset. Once
the scene builder is registered, the package can load the new map through
`build_scene(...)`.

## Install

```bash
pip install -e .
```

## Quick Start

```python
from structure import available_scene_names, build_scene

print(available_scene_names())
scene = build_scene("home")
print(scene.to_dict())
```

More details are in [`structure/README.md`](structure/README.md).
