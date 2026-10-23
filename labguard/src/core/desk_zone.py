"""
台面安全区（器皿靠近桌边判定）
src/core/desk_zone.py

现场在台面摄像头画面上框出台面多边形，并标出哪几条边是「危险边」（靠操作者、器皿会掉下去的那一侧）；
靠墙、画面边缘这类边标为「安全边」，器皿靠近它们不报警。
器皿底边中点：
  · 在安全区内，离任一危险边小于 edge_margin → 靠近桌边；
  · 在安全区外，且最近的边是危险边 → 已越过桌边；最近的是安全边 → 不判定（例如放在后方架子上）。
没框安全区时沿用旧的单条桌边线 desk.edge_line。

纯函数，不依赖 cv2 / Qt；坐标一律为归一化坐标（0–1，相对画面宽高）。
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
FAR = 9.0                       # 「离危险边很远」的占位距离（归一化坐标最大不超过 √2）
MIN_POINTS, MAX_POINTS = 3, 12
MIN_AREA = 0.02                 # 安全区至少占画面 2%，防止误点出一个极小的框
DEFAULT_LINE = [[0.0, 0.92], [1.0, 0.92]]


class ZoneError(ValueError):
    pass


def _area(pts: Sequence[Point]) -> float:
    s = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    d1, d2 = _cross(q1, q2, p1), _cross(q1, q2, p2)
    d3, d4 = _cross(p1, p2, q1), _cross(p1, p2, q2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and 0 not in (d1, d2, d3, d4)


def validate_zone(data: Any) -> Optional[Dict[str, Any]]:
    """校验网页提交的安全区；points 为空表示清除安全区（回到单条桌边线）。返回规范化后的 dict 或 None"""
    if not isinstance(data, dict):
        raise ZoneError("安全区格式错误")
    raw = data.get("points") or []
    if not raw:
        return None
    if not isinstance(raw, list) or not (MIN_POINTS <= len(raw) <= MAX_POINTS):
        raise ZoneError(f"安全区需要 {MIN_POINTS}–{MAX_POINTS} 个顶点")
    pts: List[Point] = []
    for p in raw:
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            raise ZoneError("顶点坐标格式错误")
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ZoneError("顶点必须在画面范围内")
        pts.append((round(x, 4), round(y, 4)))
    n = len(pts)
    for i in range(n):
        for j in range(i + 1, n):
            if (j - i) in (1, n - 1):
                continue                       # 相邻边共享顶点，不算相交
            if _segments_cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                raise ZoneError("安全区的边不能交叉")
    if _area(pts) < MIN_AREA:
        raise ZoneError("安全区面积过小")
    danger = data.get("danger")
    if danger is None:
        danger = [True] * n
    if not isinstance(danger, list) or len(danger) != n:
        raise ZoneError("危险边标记数量与边数不一致")
    danger = [bool(d) for d in danger]
    if not any(danger):
        raise ZoneError("至少需要一条危险边")
    return {"points": [list(p) for p in pts], "danger": danger}


def _inside(px: float, py: float, pts: Sequence[Sequence[float]]) -> bool:
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xc = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xc:
                inside = not inside
    return inside


def _seg_dist(px: float, py: float, a: Sequence[float], b: Sequence[float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / L2))
    cx, cy = a[0] + t * dx, a[1] + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def line_clearance(px: float, py: float, line=None) -> float:
    """点到单条桌边线的有向距离：正值在台面内侧（画面中心所在一侧），负值已越过桌边"""
    (x1, y1), (x2, y2) = line or DEFAULT_LINE
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    d = ((px - x1) * dy - (py - y1) * dx) / length
    d_center = ((0.5 - x1) * dy - (0.5 - y1) * dx) / length
    return d if d_center >= 0 else -d


def zone_clearance(px: float, py: float, zone: Dict[str, Any]) -> float:
    """点到危险边的有向距离：正值在安全区内，负值已越过危险边；不涉及危险边时返回 FAR"""
    pts, danger = zone["points"], zone["danger"]
    n = len(pts)
    dists = [_seg_dist(px, py, pts[i], pts[(i + 1) % n]) for i in range(n)]
    if _inside(px, py, pts):
        dd = [d for d, flag in zip(dists, danger) if flag]
        return min(dd) if dd else FAR
    nearest = min(range(n), key=lambda i: dists[i])
    return -dists[nearest] if danger[nearest] else FAR


def clearance(px: float, py: float, zone: Optional[Dict[str, Any]] = None, line=None) -> float:
    """有安全区用安全区，否则用单条桌边线"""
    if zone and zone.get("points"):
        return zone_clearance(px, py, zone)
    return line_clearance(px, py, line)
