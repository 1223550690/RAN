from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# direction: 业务方向，UL 表示 UE 上行到网络，DL 表示网络下行到 UE。
Direction = Literal["UL", "DL"]


@dataclass(slots=True)
class Position:
    """地图坐标。

    输入字段:
    - x/y: 现有 2D 地图中的全局坐标。

    输出用途:
    - 提供给地图查询、信道建模、基站/UE 距离计算。
    """

    x: float  # x: 地图全局横坐标。
    y: float  # y: 地图全局纵坐标。
