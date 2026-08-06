"""Room-door connection graph: BFS channel-sequence planning for cross-room paths.

Channel abstraction:
- A single physical channel may have multiple Portals in the editor (different area sides, different names, for editing convenience);
  global navigation only recognizes the unique channel boundary.
- Channel merging sources: 1) Portal.channel_id (data contract, written by the editor in the future);
  2) geometric merge fallback: multiple doors whose opening segments are collinear and overlapping are treated as one channel.
- Nodes are all areas (top-level + child areas); channel area_ids are normalized through open_space/outside.
- Passability follows Portal.open; locked is an editor lock field, not a physical door lock.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .geometry import Point, segments_collinear_overlap
from .semantic_index import IndexedArea, IndexedPortal, SceneSemanticIndex


@dataclass(slots=True)
class ChannelGroup:
    """Set of Portals of the same physical channel; exposed externally as a unique channel boundary."""

    channel_id: str  # channel_id: channel identifier (prefers a member's channel_id, otherwise derived).
    members: list[IndexedPortal] = field(default_factory=list)  # members: doors forming the channel.
    area_ids: set[str] = field(default_factory=set)  # area_ids: areas on both sides of the channel (normalized, including OUTSIDE).

    @property
    def center(self) -> Point:
        """Channel geometric center: center of the merged interval of all members' opening segments."""

        xs = [point[0] for portal in self.members for point in portal.segment]
        ys = [point[1] for portal in self.members for point in portal.segment]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    @property
    def representative(self) -> IndexedPortal:
        """Representative door: the first member (open preferred), used for external display."""

        for member in self.members:
            if member.open:
                return member
        return self.members[0]

    def as_portal(self) -> IndexedPortal:
        """Build a virtual Portal from the merged channel boundary (segment is the union opening)."""

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
    """Virtual outdoor hub: in scene data, a door connecting to outside marks a building exit."""

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

    # ------------------------------------------------------------------ channel construction

    def _group_channels(self) -> list[ChannelGroup]:
        """Group all doors into channel groups (channel_id first, geometric collinear-overlap fallback)."""

        open_portals = [portal for portal in self.index.portals.values() if portal.open]
        groups: list[ChannelGroup] = []
        used: set[str] = set()
        for portal in open_portals:
            if portal.portal_id in used:
                continue
            members: list[IndexedPortal] = [portal]
            used.add(portal.portal_id)
            # Greedy propagation: compare group members against unused doors to avoid missing chained merges.
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
        """Whether two doors belong to the same physical channel."""

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
        """Normalize a virtual area reference to a real area or the outdoor hub.

        Doors in scene data may connect to `{area}_open_space` (open space inside the parent area)
        or `outside` (outdoors). open_space matches the parent area by ID prefix first; when that
        fails, the door center's spatial containment is used to infer the parent (a door always lies inside it).
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
                    # Normalize to the top-level area (building level): ensures BFS from the top-level
                    # node reaches it; doors inside child areas are uniformly attached to the building node.
                    while area.parent_id is not None:
                        parent = self.index.get_area(area.parent_id)
                        if parent is None:
                            break
                        area = parent
                    return area.area_id
        return None

    def is_same_room(self, area_a: IndexedArea | None, area_b: IndexedArea | None) -> bool:
        """Whether two areas are in the same room (identical, or ancestor/descendant of each other).

        Outdoors (None) and outdoors are the same room; outdoors differs from every indoor area.
        """

        if area_a is None and area_b is None:
            return True
        if area_a is None or area_b is None:
            return False
        if area_a.area_id == area_b.area_id:
            return True
        path_a, path_b = area_a.path, area_b.path
        return path_a.startswith(path_b + " / ") or path_b.startswith(path_a + " / ")

    # ------------------------------------------------------------------ channel sequence

    def find_door_sequence(
        self,
        start_area_id: str | None,
        goal_area_id: str | None,
    ) -> list[IndexedPortal] | None:
        """BFS for the cross-room channel sequence; returns None or an empty list for the same room or no solution.

        Returns: channels to traverse in order (as merged virtual Portals). None when unreachable.
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
                # Backtrack from the actually-reached node (the goal may be reached via a child area not on the backtrack chain).
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
