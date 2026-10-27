"""Identify corner kicks in StatsBomb match events."""


def find_corners(events):
    """Return corner deliveries and direct shots taken from corners."""
    corners = []
    seen_ids = set()
    for event in events:
        event_type = event.get("type", {}).get("name")
        if event_type not in {"Pass", "Shot"}:
            continue
        details = event.get(event_type.lower(), {})
        is_corner = details.get("type", {}).get("name") == "Corner"
        if is_corner and event["id"] not in seen_ids:
            corners.append(event)
            seen_ids.add(event["id"])
    return corners


def timestamp_seconds(timestamp):
    hours, minutes, seconds = timestamp.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_corner_sequence(events, corner, max_seconds=15):
    """Return the included event IDs, attacking shots, and ending reason."""
    possession = corner.get("possession")
    if possession is None:
        raise ValueError("Corner has no possession identifier.")
    start_time = timestamp_seconds(corner["timestamp"])
    team_id = corner["team"]["id"]
    corner_index = next(
        index
        for index, event in enumerate(events)
        if event["id"] == corner["id"]
    )
    result = {
        "chain_event_ids": [corner["id"]],
        "shots": [corner] if corner["type"]["name"] == "Shot" else [],
        "stop_reason": "end_of_data",
    }
    seen_ids = {corner["id"]}
    corner_details = corner.get(corner["type"]["name"].lower(), {})
    if corner_details.get("outcome", {}).get("name") == "Goal":
        result["stop_reason"] = "goal"
        return result
    if corner.get("out"):
        result["stop_reason"] = "ball_out"
        return result

    restart_types = {
        "Corner", "Free Kick", "Goal Kick",
        "Kick Off", "Throw-in", "Penalty",
    }

    for action in events[corner_index + 1:]:
        if action["id"] in seen_ids:
            continue
        if action["period"] != corner["period"]:
            result["stop_reason"] = "period_end"
            break
        elapsed = timestamp_seconds(action["timestamp"]) - start_time
        if max_seconds is not None and elapsed > max_seconds:
            result["stop_reason"] = "time_limit"
            break
        action_type = action["type"]["name"]
        details = action.get(action_type.lower().replace(" ", "_"), {})
        if (
            action_type in {"Pass", "Shot"}
            and details.get("type", {}).get("name") in restart_types
        ):
            result["stop_reason"] = "new_restart"
            break
        if action.get("possession") != possession:
            result["stop_reason"] = "possession_change"
            break
        if action_type in {
            "Half End", "Injury Stoppage", "Offside", "Referee Ball-Drop"
        }:
            result["stop_reason"] = "stoppage"
            break
        if (
            action_type in {"Foul Committed", "Foul Won"}
            and not details.get("advantage", False)
        ):
            result["stop_reason"] = "stoppage"
            break
        result["chain_event_ids"].append(action["id"])
        seen_ids.add(action["id"])
        if (
            action_type == "Shot"
            and action["team"]["id"] == team_id
        ):
            result["shots"].append(action)
        if action.get("shot", {}).get("outcome", {}).get("name") == "Goal":
            result["stop_reason"] = "goal"
            break
        if action.get("out"):
            result["stop_reason"] = "ball_out"
            break

    return result


def find_corner_shots(events, corner, max_seconds=15):
    """Keep the existing interface for callers that only need shots."""
    return extract_corner_sequence(events, corner, max_seconds)["shots"]


def describe_corner(corner, short_limit=15):
    """Describe the delivery using the proposal's short-corner rule."""
    from math import hypot, isfinite

    if not isfinite(short_limit) or short_limit <= 0:
        raise ValueError("Short-corner limit must be positive and finite.")
    kind = corner["type"]["name"]
    details = corner.get(kind.lower(), {})
    start = corner.get("location") or []
    end = details.get("end_location") or []
    start_x = start[0] if len(start) >= 2 else None
    start_y = start[1] if len(start) >= 2 else None
    end_x = end[0] if len(end) >= 2 else None
    end_y = end[1] if len(end) >= 2 else None
    category = "unknown"
    if kind == "Shot":
        category = "direct_shot"
    elif kind == "Pass":
        coordinates = (start_x, start_y, end_x, end_y)
        if (
            details.get("height", {}).get("name") == "Ground Pass"
            and all(value is not None and isfinite(value) for value in coordinates)
            and hypot(end_x - start_x, end_y - start_y) <= short_limit
        ):
            category = "short"
        else:
            technique = details.get("technique", {}).get("name")
            if technique in {"Inswinging", "Outswinging", "Straight"}:
                category = technique.lower()

    return {
        "delivery_category": category,
        "start_x": start_x,
        "start_y": start_y,
        "end_x": end_x,
        "end_y": end_y,
    }


def build_corner_summaries(events, match_id, max_seconds=15, short_limit=15):
    """Build corner summary dictionaries without downloading or writing data."""
    rows = []
    for corner in find_corners(events):
        sequence = extract_corner_sequence(
            events, corner, max_seconds=max_seconds
        )
        shots = sequence["shots"]
        corner_kind = corner["type"]["name"]
        delivery = corner[corner_kind.lower()]
        rows.append({
            "match_id": match_id,
            "corner_event_id": corner["id"],
            "team_id": corner["team"]["id"],
            "team": corner["team"].get("name", "Unknown"),
            "taker": corner.get("player", {}).get("name", "Unknown"),
            "period": corner["period"],
            "timestamp": corner["timestamp"],
            "minute": corner.get("minute"),
            "second": corner.get("second"),
            "possession_id": corner["possession"],
            "corner_kind": corner_kind,
            "technique": delivery.get("technique", {}).get("name", "Unknown"),
            "foot": delivery.get("body_part", {}).get("name", "Unknown"),
            "height": delivery.get("height", {}).get("name", "Unknown"),
            **describe_corner(corner, short_limit=short_limit),
            "shot_count": len(shots),
            "goal_count": sum(
                shot["shot"].get("outcome", {}).get("name") == "Goal"
                for shot in shots
            ),
            "led_to_shot": bool(shots),
            "provider_xg_sum": sum(
                shot["shot"].get("statsbomb_xg", 0) or 0
                for shot in shots
            ),
            "shot_event_ids": [shot["id"] for shot in shots],
            "chain_event_ids": sequence["chain_event_ids"],
            "stop_reason": sequence["stop_reason"],
            "window_seconds": max_seconds,
            "short_limit": short_limit,
        })
    return rows
