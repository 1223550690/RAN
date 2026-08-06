from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CONTRACT_VERSION = "1.0"
Direction = Literal["UL", "DL"]


@dataclass(slots=True)
class Position:
    """Two-dimensional global coordinates on the map."""

    x: float  # x: global X coordinate on the map.
    y: float  # y: global Y coordinate on the map.
