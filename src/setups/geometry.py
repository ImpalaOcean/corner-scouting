"""Pitch geometry helpers. StatsBomb pitch: x 0-120, y 0-80, attack toward x=120.

360 frames use the same orientation as events: the team in possession attacks
toward x=120, so corners are always taken at x=120 from y near 0 or y near 80.
"""

from math import isfinite

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0

# A corner must be taken within this many yards of a corner flag.
CORNER_TOLERANCE = 3.0

# Penalty box (attacking end): 18-yard line to goal line, 18 to 62 across.
BOX_X0, BOX_X1 = 102.0, 120.0
BOX_Y0, BOX_Y1 = 18.0, 62.0

# Nine zones: 3 depth bands (x) by 3 width bands (y).
X_EDGES = (102.0, 108.0, 114.0, 120.0)
Y_EDGES = (18.0, 18.0 + 44.0 / 3, 18.0 + 88.0 / 3, 62.0)


def corner_side(start_y, start_x=PITCH_LENGTH):
    """'top' if the corner is at the y=80 flag, 'bottom' if at the y=0 flag.

    Returns None for anything that is not a real corner position: a missing or
    non-finite coordinate, or a point more than CORNER_TOLERANCE yards from a
    corner flag on the goal line (x=120)."""
    for value in (start_x, start_y):
        if type(value) not in (int, float) or not isfinite(value):
            return None
    if not PITCH_LENGTH - CORNER_TOLERANCE <= start_x <= PITCH_LENGTH:
        return None
    if 0 <= start_y <= CORNER_TOLERANCE:
        return "bottom"
    if PITCH_WIDTH - CORNER_TOLERANCE <= start_y <= PITCH_WIDTH:
        return "top"
    return None


def mirror_y(y):
    return PITCH_WIDTH - y


def zone_rect(zone):
    """Rectangle (x0, y0, x1, y1) of zone 1-9. Zones run row by row:
    1-3 = y band nearest y=18, 4-6 = middle, 7-9 = y band nearest y=62;
    within a row, x increases from the 18-yard line to the goal line."""
    row, col = divmod(zone - 1, 3)
    return X_EDGES[col], Y_EDGES[row], X_EDGES[col + 1], Y_EDGES[row + 1]


def zone_of(x, y):
    """Zone 1-9 for a point inside the penalty box (edges inclusive), else None."""
    if not (BOX_X0 <= x <= BOX_X1 and BOX_Y0 <= y <= BOX_Y1):
        return None
    col = 0 if x < X_EDGES[1] else 1 if x < X_EDGES[2] else 2
    row = 0 if y < Y_EDGES[1] else 1 if y < Y_EDGES[2] else 2
    return row * 3 + col + 1


def polygon_area(points):
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def clip_to_rect(points, x0, y0, x1, y1):
    """Sutherland-Hodgman clip of a polygon against an axis-aligned rectangle."""
    def clip(pts, inside, cross):
        out = []
        for i, cur in enumerate(pts):
            prev = pts[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
        return out

    def at_x(xv):
        return lambda a, b: (xv, a[1] + (b[1] - a[1]) * (xv - a[0]) / (b[0] - a[0]))

    def at_y(yv):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (yv - a[1]) / (b[1] - a[1]), yv)

    pts = list(points)
    for inside, cross in (
        (lambda p: p[0] >= x0, at_x(x0)),
        (lambda p: p[0] <= x1, at_x(x1)),
        (lambda p: p[1] >= y0, at_y(y0)),
        (lambda p: p[1] <= y1, at_y(y1)),
    ):
        if not pts:
            return []
        pts = clip(pts, inside, cross)
    return pts


def coverage(polygon, rect):
    """Fraction (0-1) of a rectangle that lies inside a visible-area polygon."""
    x0, y0, x1, y1 = rect
    if len(polygon) < 3:
        return 0.0
    clipped = clip_to_rect(polygon, x0, y0, x1, y1)
    if len(clipped) < 3:
        return 0.0
    return min(1.0, polygon_area(clipped) / ((x1 - x0) * (y1 - y0)))
