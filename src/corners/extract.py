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


def find_corner_shots(events, corner, max_seconds=15):
    """Find attacking shots until a sequence boundary or optional time limit."""
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
    # A direct shot from a corner counts as a shot itself.
    shots = [corner] if corner["type"]["name"] == "Shot" else []
    seen_shots = {shot["id"] for shot in shots}
    restart_types = {"Corner", "Free Kick", "Goal Kick", "Kick Off", "Throw-in", "Penalty"}
    if (
        corner.get("out")
        or corner.get("shot", {}).get("outcome", {}).get("name") == "Goal"
    ):
        return shots

    for action in events[corner_index + 1:]:
        # A repeated starter record is not a new corner restart.
        if action["id"] == corner["id"]:
            continue
        if action["period"] != corner["period"]:
            break
        if action.get("possession") != possession:
            break
        elapsed = timestamp_seconds(action["timestamp"]) - start_time
        if max_seconds is not None and elapsed > max_seconds:
            break
        action_type = action["type"]["name"]
        details = action.get(action_type.lower().replace(" ", "_"), {})
        if (
            action_type in {"Pass", "Shot"}
            and details.get("type", {}).get("name") in restart_types
        ):
            break
        if action_type in {
            "Half End", "Injury Stoppage", "Offside", "Referee Ball-Drop"
        }:
            break
        if (
            action_type in {"Foul Committed", "Foul Won"}
            and not details.get("advantage", False)
        ):
            break
        if (
            action_type == "Shot"
            and action["team"]["id"] == team_id
            and action["id"] not in seen_shots
        ):
            shots.append(action)
            seen_shots.add(action["id"])
        if (
            action.get("out")
            or action.get("shot", {}).get("outcome", {}).get("name") == "Goal"
        ):
            break

    return shots
