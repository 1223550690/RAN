from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CONTRACT_VERSION = "1.0"
Direction = Literal["UL", "DL"]


@dataclass(slots=True)
class Position:
    """地图中的二维全局坐标。"""

    x: float  # x: 地图全局 X 坐标。
    y: float  # y: 地图全局 Y 坐标。
