"""房间-门连接图:跨房间路径的 BFS 通道序列规划。

通道(Channel)抽象:
- 编辑器里同一物理通道可能有多个 Portal(不同区域侧、不同名称,便于编辑);
  全局导航只认唯一通道边界。
- 通道合并来源:① Portal.channel_id(数据合同,编辑器未来写入);
  ② 几何合并兜底:开口段共线且区间重叠的多个门视为同一通道。
- 节点为全部区域(顶层 + 子区域),通道的 area_ids 经 open_space/outside 归一化。
- 通行以 Portal.open 为准;locked 是编辑器锁定字段,不视为物理门锁。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .geometry import Point, segments_collinear_overlap
from .semantic_index import IndexedArea, IndexedPortal, SceneSemanticIndex


@dataclass(slots=True)
class ChannelGroup:
    """同一物理通道的 Portal 集合;对外表现为唯一的通道边界。"""

    channel_id: str  # channel_id: 通道标识(优先取成员 channel_id,否则派生)。
    members: list[IndexedPortal] = field(default_factory=list)  # members: 构成通道的门。
    area_ids: set[str] = field(default_factory=set)  # area_ids: 通道两侧区域(已归一化,含 OUTSIDE)。

    @property
    def center(self) -> Point:
        """通道几何中心:所有成员开口段合并区间的中心。"""

        xs = [point[0] for portal in self.members for point in portal.segment]
        ys = [point[1] for portal in self.members for point in portal.segment]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    @property
    def representative(self) -> IndexedPortal:
        """代表门:第一个成员(open 优先),用于对外展示。"""

        for member in self.members:
            if member.open:
                return member
        return self.members[0]

    def as_portal(self) -> IndexedPortal:
        """以合并后的通道边界构造一个虚拟 Portal(segment 为并集开口段)。"""

        representative = self.representative
        xs = [point[0] for portal in self.members for point in portal.segment]
        ys = [point[1] for portal in self.members for point in portal.segment]
        segment = ((min(xs), min(ys)), (max(xs), max(ys)))
        return IndexedPortal(
            portal_id=self.channel_id,
            name=f"channel:{self.channel_id}",
            segment=segment,
            center=self.center,
            area_ids=(),
            open=True,
            channel_id=self.channel_id,
        )


class RoomGraph:
    OUTSIDE = "__outside__"
    """虚拟户外枢纽:场景数据中门连接 outside 表示建筑对外出口。"""

    def __init__(
        self,
        semantic_index: SceneSemanticIndex,
        *,
        merge_eps: float = 0.1,
    ) -> None:
        self.index = semantic_index
        self.area_ids = set(semantic_index.areas.keys())
        self.merge_eps = merge_eps
        self.channels: dict[str, ChannelGroup] = {}
        self.portals_by_area: dict[str, list[ChannelGroup]] = {}
        self._build()

    def _build(self) -> None:
        for channel in self._group_channels():
            if not channel.members:
                continue
            self.channels[channel.channel_id] = channel
            for area_id in channel.area_ids:
                self.portals_by_area.setdefault(area_id, []).append(channel)

    # ------------------------------------------------------------------ 通道构建

    def _group_channels(self) -> list[ChannelGroup]:
        """把全部门归并为通道组(channel_id 优先,几何共线重叠兜底)。"""

        open_portals = [portal for portal in self.index.portals.values() if portal.open]
        groups: list[ChannelGroup] = []
        used: set[str] = set()
        for portal in open_portals:
            if portal.portal_id in used:
                continue
            members: list[IndexedPortal] = [portal]
            used.add(portal.portal_id)
            # 贪心传播:组内成员与未使用门比较,避免链式合并漏项。
            changed = True
            while changed:
                changed = False
                for candidate in open_portals:
                    if candidate.portal_id in used:
                        continue
                    if any(self._same_channel(member, candidate) for member in members):
                        members.append(candidate)
                        used.add(candidate.portal_id)
                        changed = True
            groups.append(self._make_channel(members))
        return groups

    def _same_channel(self, a: IndexedPortal, b: IndexedPortal) -> bool:
        """两个门是否属于同一物理通道。"""

        if a.channel_id is not None and a.channel_id == b.channel_id:
            return True
        return segments_collinear_overlap(
            a.segment[0],
            a.segment[1],
            b.segment[0],
            b.segment[1],
            eps=self.merge_eps,
        )

    def _make_channel(self, members: list[IndexedPortal]) -> ChannelGroup:
        channel_id = next(
            (member.channel_id for member in members if member.channel_id),
            f"ch_{members[0].portal_id}",
        )
        area_ids: set[str] = set()
        for member in members:
            for area_id in member.area_ids:
                normalized = self._normalize_area_id(area_id, fallback_point=member.center)
                if normalized is not None:
                    area_ids.add(normalized)
        return ChannelGroup(channel_id=channel_id, members=members, area_ids=area_ids)

    def _normalize_area_id(
        self,
        area_id: str | None,
        *,
        fallback_point: Point | None = None,
    ) -> str | None:
        """把虚拟区域引用归一到真实区域或户外枢纽。

        场景数据中的门可能连接 `{area}_open_space`(父区域内部开放空间)
        或 `outside`(户外)。open_space 优先按 ID 前缀匹配父区域;匹配失败时
        用门中心的空间包含关系推断归属(门一定位于其父区域内)。
        """

        if not area_id:
            return None
        if area_id in self.area_ids:
            return area_id
        if area_id == "outside":
            return self.OUTSIDE
        if area_id.endswith("_open_space"):
            parent_id = area_id[: -len("_open_space")]
            if parent_id in self.area_ids:
                return parent_id
            if fallback_point is not None:
                area = self.index.find_area_at(fallback_point)
                if area is not None:
                    # 归一到顶层区域(建筑级):保证 BFS 从顶层节点出发可达,
                    # 子区域内部的门统一挂在建筑节点下。
                    while area.parent_id is not None:
                        parent = self.index.get_area(area.parent_id)
                        if parent is None:
                            break
                        area = parent
                    return area.area_id
        return None

    def is_same_room(self, area_a: IndexedArea | None, area_b: IndexedArea | None) -> bool:
        """两个区域是否同房间(相同、或互为祖先/后代)。

        户外(None)与户外同房间;户外与任何室内区域不同房间。
        """

        if area_a is None and area_b is None:
            return True
        if area_a is None or area_b is None:
            return False
        if area_a.area_id == area_b.area_id:
            return True
        path_a, path_b = area_a.path, area_b.path
        return path_a.startswith(path_b + " / ") or path_b.startswith(path_a + " / ")

    # ------------------------------------------------------------------ 通道序列

    def find_door_sequence(
        self,
        start_area_id: str | None,
        goal_area_id: str | None,
    ) -> list[IndexedPortal] | None:
        """BFS 求跨房间通道序列;同房间或无解返回 None 或空列表。

        返回:按顺序穿过的通道(以合并后的虚拟 Portal 表示)。无法到达时返回 None。
        """

        if start_area_id == goal_area_id:
            return []
        start_area = self.index.get_area(start_area_id or "")
        goal_area = self.index.get_area(goal_area_id or "")
        if self.is_same_room(start_area, goal_area):
            return []

        queue = deque([start_area_id])
        visited = {start_area_id}
        came_from_channel: dict[str, ChannelGroup] = {}
        came_from_area: dict[str, str] = {}
        while queue:
            current = queue.popleft()
            current_area = self.index.get_area(current)
            if current_area is not None and self.is_same_room(current_area, goal_area):
                # 从实际到达的节点回溯(goal 可能通过其子区域到达,不在回溯链上)。
                return self._reconstruct_channels(current, came_from_channel, came_from_area)
            for channel in self.portals_by_area.get(current, []):
                for neighbor in channel.area_ids:
                    if neighbor == current or neighbor in visited:
                        continue
                    visited.add(neighbor)
                    came_from_channel[neighbor] = channel
                    came_from_area[neighbor] = current
                    queue.append(neighbor)
        return None

    @staticmethod
    def _reconstruct_channels(
        goal_area_id: str,
        came_from_channel: dict[str, ChannelGroup],
        came_from_area: dict[str, str],
    ) -> list[IndexedPortal]:
        channels: list[ChannelGroup] = []
        current = goal_area_id
        while current in came_from_channel:
            channel = came_from_channel[current]
            channels.append(channel)
            current = came_from_area[current]
        channels.reverse()
        return [channel.as_portal() for channel in channels]
