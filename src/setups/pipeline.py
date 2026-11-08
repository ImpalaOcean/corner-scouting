"""Corners + 360 frames -> setup_summary_v1 rows, clusters and a coverage report."""

from math import isfinite

from .cluster import kmeans, stability
from .features import ZONES, frame_features, polygon_points, vector
from .geometry import corner_side, polygon_area

ROW_FIELDS = (
    ["match_id", "corner_event_id", "team_id", "team", "status", "exclusion_reason",
     "corner_side", "visible_players", "visible_attackers", "visible_defenders",
     "visible_keepers", "box_coverage", "att_in_box", "def_in_box", "keeper_zone"]
    + [f"att_z{z}" for z in ZONES] + [f"def_z{z}" for z in ZONES] + ["cluster_id"]
)

REASONS = ("no_360_file", "no_360_frame", "invalid_frame", "no_corner_location",
           "invalid_corner_location", "low_visibility", "too_few_visible_players")

DEFAULTS = dict(k=4, min_box_coverage=0.5, min_visible_players=5,
                min_corners_confident=100, min_cluster_size=10,
                stability_threshold=0.6, seed=0)


def frame_problem(frame):
    """Why a frame cannot be used, or None if it is well formed."""
    players = frame.get("freeze_frame")
    area = frame.get("visible_area")
    ok_num = lambda v: type(v) in (int, float) and isfinite(v)
    if not isinstance(players, list) or not isinstance(area, list):
        return "freeze_frame/visible_area missing"
    if len(area) % 2 or not all(ok_num(v) for v in area):
        return "bad visible_area"
    outline = polygon_points(area)
    if len(outline) < 3 or polygon_area(outline) <= 1e-9:
        return "degenerate visible_area"
    for p in players:
        loc = p.get("location") if isinstance(p, dict) else None
        if not (isinstance(loc, list) and len(loc) >= 2 and all(ok_num(v) for v in loc[:2])):
            return "bad player location"
        if any(type(p.get(f)) is not bool for f in ("teammate", "actor", "keeper")):
            return "bad player flags"
    return None


def corner_location(row, frame):
    """(x, y) of the corner: from the corner table when both values are present,
    otherwise from the corner taker in the frame; None if neither exists."""
    if row["start_x"] is not None and row["start_y"] is not None:
        return row["start_x"], row["start_y"]
    for p in frame["freeze_frame"]:
        if p["actor"]:
            return p["location"][0], p["location"][1]
    return None


def build_setups(corners, frames_by_match, **options):
    """Return (rows, report). Every input corner yields exactly one row; corners
    that cannot be analysed are kept with status 'excluded' and a reason."""
    cfg = dict(DEFAULTS, **options)
    rows, usable = [], []
    for corner in corners:
        row = {f: "" for f in ROW_FIELDS}
        row.update(match_id=corner["match_id"], corner_event_id=corner["corner_event_id"],
                   team_id=corner.get("team_id", ""), team=corner.get("team", ""),
                   status="excluded")
        rows.append(row)
        frames = frames_by_match.get(corner["match_id"])
        if frames is None:
            row["exclusion_reason"] = "no_360_file"
            continue
        frame = frames.get(corner["corner_event_id"])
        if frame is None:
            row["exclusion_reason"] = "no_360_frame"
            continue
        if frame_problem(frame):
            row["exclusion_reason"] = "invalid_frame"
            continue
        location = corner_location(corner, frame)
        if location is None:
            row["exclusion_reason"] = "no_corner_location"
            continue
        if corner_side(location[1], location[0]) is None:
            row["exclusion_reason"] = "invalid_corner_location"
            continue
        feats = frame_features(frame, location[1], location[0])
        row.update({k: feats[k] for k in (
            "corner_side", "visible_players", "visible_attackers", "visible_defenders",
            "visible_keepers", "box_coverage", "att_in_box", "def_in_box")})
        row["keeper_zone"] = "" if feats["keeper_zone"] is None else feats["keeper_zone"]
        for z in ZONES:
            row[f"att_z{z}"], row[f"def_z{z}"] = feats["att_zone"][z], feats["def_zone"][z]
        if feats["visible_players"] < cfg["min_visible_players"]:
            row["exclusion_reason"] = "too_few_visible_players"
        elif feats["box_coverage"] < cfg["min_box_coverage"]:
            row["exclusion_reason"] = "low_visibility"
        else:
            row["status"] = "ok"
            usable.append((row, vector(feats)))

    # Cluster in a fixed order so results never depend on input order.
    usable.sort(key=lambda item: (item[0]["match_id"], item[0]["corner_event_id"]))
    labels, centers, stab, k_used = [], [], None, 0
    if usable:
        vectors = [v for _, v in usable]
        labels, centers = kmeans(vectors, cfg["k"])
        k_used = len(centers)
        stab = stability(vectors, labels, k_used, seed=cfg["seed"])
        for (row, _), label in zip(usable, labels):
            row["cluster_id"] = label

    reasons = {r: sum(row["exclusion_reason"] == r for row in rows) for r in REASONS}
    caveats = []
    if len(usable) < cfg["min_corners_confident"]:
        caveats.append(f"only {len(usable)} corners with usable 360 "
                       f"(< {cfg['min_corners_confident']})")
    if stab is None:
        if k_used >= 2:
            caveats.append("too few corners to test stability")
        elif usable:
            caveats.append("only one setup group found; stability cannot be estimated")
    elif stab < cfg["stability_threshold"]:
        caveats.append(f"stability {stab} below {cfg['stability_threshold']}")
    small = [c for c in range(k_used) if labels.count(c) < cfg["min_cluster_size"]]
    if small:
        caveats.append(f"clusters {small} have fewer than "
                       f"{cfg['min_cluster_size']} corners")
    if not usable:
        caveats.append("no usable 360 corners")
    clusters = []
    for c, centre in enumerate(centers):
        clusters.append(dict(
            cluster_id=c, size=labels.count(c),
            meets_min_size=labels.count(c) >= cfg["min_cluster_size"],
            mean_attackers_by_zone={z: round(centre[z - 1], 3) for z in ZONES},
            mean_defenders_by_zone={z: round(centre[9 + z - 1], 3) for z in ZONES}))
    report = dict(
        schema="setup_summary_v1", settings=cfg,
        corners_total=len(rows), corners_usable=len(usable),
        corners_excluded=len(rows) - len(usable), excluded_by_reason=reasons,
        usable_fraction=round(len(usable) / len(rows), 4) if rows else None,
        clusters_requested=cfg["k"], clusters_found=k_used, stability_ari=stab,
        exploratory=bool(caveats), caveats=caveats, clusters=clusters)
    return rows, report
