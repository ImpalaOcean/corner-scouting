"""Per-corner static features from one 360 freeze frame."""

from .geometry import (
    BOX_X0, BOX_X1, BOX_Y0, BOX_Y1, corner_side, coverage, mirror_y, zone_of,
    zone_rect,
)

ZONES = range(1, 10)


def polygon_points(flat):
    """[x0, y0, x1, y1, ...] -> [(x0, y0), ...]."""
    return [(float(flat[i]), float(flat[i + 1])) for i in range(0, len(flat) - 1, 2)]


def frame_features(frame, start_y, start_x=120.0):
    """Features for one corner. Returns None if the corner side is unknown.

    Attackers are the actor's teammates (teammate=True). The actor (corner
    taker) and keepers are excluded from the attacker/defender counts and from
    the outfield zone counts; keepers are reported separately. Bottom corners
    (y<40) are mirrored so every corner is analysed as if taken from the top
    touchline (y=80).
    """
    side = corner_side(start_y, start_x)
    if side is None:
        return None
    flip = side == "bottom"

    def norm(point):
        x, y = point
        return (x, mirror_y(y)) if flip else (x, y)

    att = {z: 0 for z in ZONES}
    dfn = {z: 0 for z in ZONES}
    visible = attackers = defenders = 0
    keeper_zone = None
    keepers = 0
    for p in frame["freeze_frame"]:
        visible += 1
        if p["actor"]:
            continue
        x, y = norm(p["location"][:2])
        zone = zone_of(x, y)
        if p["keeper"]:
            keepers += 1
            if not p["teammate"]:
                keeper_zone = zone if zone is not None else 0
            continue
        if p["teammate"]:
            attackers += 1
        else:
            defenders += 1
        if zone is not None:
            (att if p["teammate"] else dfn)[zone] += 1

    polygon = [norm(pt) for pt in polygon_points(frame["visible_area"])]
    box = (BOX_X0, BOX_Y0, BOX_X1, BOX_Y1)
    return {
        "corner_side": side,
        "visible_players": visible,
        "visible_attackers": attackers,
        "visible_defenders": defenders,
        "visible_keepers": keepers,
        "box_coverage": round(coverage(polygon, box), 4),
        "zone_coverage": {z: round(coverage(polygon, zone_rect(z)), 4) for z in ZONES},
        "att_zone": att,
        "def_zone": dfn,
        "att_in_box": sum(att.values()),
        "def_in_box": sum(dfn.values()),
        "keeper_zone": keeper_zone,
    }


def vector(features):
    """18-number setup vector: attackers per zone then defenders per zone."""
    return [features["att_zone"][z] for z in ZONES] + [features["def_zone"][z] for z in ZONES]
