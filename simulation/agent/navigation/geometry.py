"""二维几何基础工具(自包含,不依赖 services/map_service,避免反向依赖)。

与 MapService 中的几何逻辑保持同一套约定:坐标均为全局地图坐标。
"""

from __future__ import annotations

Point = tuple[float, float]
Segment = tuple[Point, Point]
Rect = tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)

_EPS = 1e-9


def distance(a: Point, b: Point) -> float:
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5


def cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def point_on_segment(p: Point, start: Point, end: Point) -> bool:
    return (
        min(start[0], end[0]) - _EPS <= p[0] <= max(start[0], end[0]) + _EPS
        and min(start[1], end[1]) - _EPS <= p[1] <= max(start[1], end[1]) + _EPS
        and abs(cross((end[0] - start[0], end[1] - start[1]), (p[0] - start[0], p[1] - start[1]))) <= _EPS
    )


def segment_intersection(a: Point, b: Point, c: Point, d: Point) -> Point | None:
    """返回线段 ab 与 cd 的交点;平行/共线时返回共线重叠起点,不相交返回 None。"""

    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    denominator = cross(r, s)
    q_minus_p = (c[0] - a[0], c[1] - a[1])

    if abs(denominator) < _EPS:
        if abs(cross(q_minus_p, r)) >= _EPS:
            return None
        return _collinear_overlap_point(a, b, c, d)
    t = cross(q_minus_p, s) / denominator
    u = cross(q_minus_p, r) / denominator
    if -_EPS <= t <= 1 + _EPS and -_EPS <= u <= 1 + _EPS:
        return (a[0] + t * r[0], a[1] + t * r[1])
    return None


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    return segment_intersection(a, b, c, d) is not None


def _collinear_overlap_point(a: Point, b: Point, c: Point, d: Point) -> Point | None:
    ab = (b[0] - a[0], b[1] - a[1])
    length_sq = ab[0] * ab[0] + ab[1] * ab[1]
    if length_sq < _EPS:
        return a if point_on_segment(a, c, d) else None
    t1 = ((c[0] - a[0]) * ab[0] + (c[1] - a[1]) * ab[1]) / length_sq
    t2 = ((d[0] - a[0]) * ab[0] + (d[1] - a[1]) * ab[1]) / length_sq
    start_t = max(0.0, min(t1, t2))
    end_t = min(1.0, max(t1, t2))
    if start_t <= end_t + _EPS:
        return (a[0] + start_t * ab[0], a[1] + start_t * ab[1])
    return None


def point_to_segment_distance(p: Point, start: Point, end: Point) -> float:
    """点到线段的最短距离。"""

    closest = closest_point_on_segment(p, start, end)
    return distance(p, closest)


def closest_point_on_segment(p: Point, start: Point, end: Point) -> Point:
    """p 在线段 start-end 上的最近点(含端点)。"""

    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq < _EPS:
        return start
    t = max(0.0, min(1.0, ((p[0] - sx) * dx + (p[1] - sy) * dy) / length_sq))
    return (sx + t * dx, sy + t * dy)


def point_in_rect(p: Point, rect: Rect, padding: float = 0.0) -> bool:
    min_x, min_y, max_x, max_y = rect
    return (
        min_x - padding <= p[0] <= max_x + padding
        and min_y - padding <= p[1] <= max_y + padding
    )


def rects_overlap(a: Rect, b: Rect) -> bool:
    return not (
        a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
    )


def rect_intersection(a: Rect, b: Rect) -> Rect | None:
    min_x = max(a[0], b[0])
    min_y = max(a[1], b[1])
    max_x = min(a[2], b[2])
    max_y = min(a[3], b[3])
    if min_x >= max_x or min_y >= max_y:
        return None
    return (min_x, min_y, max_x, max_y)


def segment_crosses_rect(a: Point, b: Point, rect: Rect) -> bool:
    """线段 ab 是否穿过矩形(含边界接触)。"""

    min_x, min_y, max_x, max_y = rect
    corners = [
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    ]
    for i in range(4):
        c = corners[i]
        d = corners[(i + 1) % 4]
        if segments_intersect(a, b, c, d):
            return True
    return point_in_rect(a, rect) or point_in_rect(b, rect)


def segments_collinear_overlap(a: Point, b: Point, c: Point, d: Point, eps: float = 0.1) -> bool:
    """两线段是否共线且区间重叠(同一通道开口段的判定)。

    用于把同一物理通道的多个门(编辑器多视角)合并为唯一通道边界。
    """

    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (d[0] - c[0], d[1] - c[1])
    len1 = (v1[0] * v1[0] + v1[1] * v1[1]) ** 0.5
    len2 = (v2[0] * v2[0] + v2[1] * v2[1]) ** 0.5
    if len1 < 1e-9 or len2 < 1e-9:
        return False
    # 平行(叉积 ≈ 0)。
    if abs(v1[0] * v2[1] - v1[1] * v2[0]) > eps * len1 * len2:
        return False
    # 共线:线段 2 至少一个端点落在线段 1 上(含端点附近)。
    if point_to_segment_distance(c, a, b) > eps and point_to_segment_distance(d, a, b) > eps:
        return False
    # 区间重叠:任一线段端点落在另一线段上。
    return (
        point_to_segment_distance(c, a, b) <= eps
        or point_to_segment_distance(d, a, b) <= eps
        or point_to_segment_distance(a, c, d) <= eps
        or point_to_segment_distance(b, c, d) <= eps
    )


def _segment_aabb(segment: Segment) -> Rect:
    """线段的轴对齐包围盒 (min_x, min_y, max_x, max_y)。"""

    a, b = segment
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def _projection_interval(segment: Segment, other: Segment) -> tuple[float, float]:
    """把线段 other 投影到 segment 的参数区间 [0,1] 上(共线线段用)。"""

    (ax, ay), (bx, by) = segment
    vx, vy = bx - ax, by - ay
    length_sq = vx * vx + vy * vy
    if length_sq < 1e-9:
        return (0.0, 1.0)
    ts = []
    for px, py in (other[0], other[1]):
        t = ((px - ax) * vx + (py - ay) * vy) / length_sq
        ts.append(max(0.0, min(1.0, t)))
    return (min(ts), max(ts))


def _subtract_intervals(
    keep: list[tuple[float, float]],
    removed: tuple[float, float],
) -> list[tuple[float, float]]:
    """从区间列表中扣除一个区间(参数化区间减法)。"""

    result: list[tuple[float, float]] = []
    r_start, r_end = removed
    for start, end in keep:
        if r_start <= start and r_end >= end:
            continue
        if r_end <= start or r_start >= end:
            result.append((start, end))
            continue
        if r_start > start:
            result.append((start, min(end, r_start)))
        if r_end < end:
            result.append((max(start, r_end), end))
    return result


def _expand_interval(interval: tuple[float, float], length_m: float, segment: Segment | None = None) -> tuple[float, float]:
    """按长度(米)扩张参数化区间两端;无 segment 时按比例 0.01 保底。"""

    start, end = interval
    if segment is not None:
        (ax, ay), (bx, by) = segment
        seg_length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        if seg_length > 1e-9:
            delta = length_m / seg_length
            return (max(0.0, start - delta), min(1.0, end + delta))
    return (max(0.0, start - 0.01), min(1.0, end + 0.01))


def _interpolate_segment(segment: Segment, t_start: float, t_end: float) -> Segment:
    """按参数区间截取线段子段。"""

    (ax, ay), (bx, by) = segment
    start = (ax + (bx - ax) * t_start, ay + (by - ay) * t_start)
    end = (ax + (bx - ax) * t_end, ay + (by - ay) * t_end)
    return (start, end)


def _aabbs_overlap(a: Rect, b: Rect) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _point_in_expanded_aabb(point: Point, aabb: Rect, padding: float) -> bool:
    return (
        aabb[0] - padding <= point[0] <= aabb[2] + padding
        and aabb[1] - padding <= point[1] <= aabb[3] + padding
    )
