from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Direction = Literal["UL", "DL"]


@dataclass(slots=True)
class Position:
    """Project implementation detail."""

    x: float
    y: float
