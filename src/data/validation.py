"""Validate provider structures and normalize event rows."""

from datetime import date
import json
from math import isfinite
import re

from .source import DataError


def require(condition, message):
    if not condition:
        raise DataError("invalid_schema", message)


def integer(value, label):
    require(
        type(value) is int and value > 0,
        f"{label} must be a positive integer",
    )
    return value


def named(value, label):
    require(
        isinstance(value, dict),
        f"{label} must be an object",
    )
    integer(value.get("id"), label + ".id")
    require(
        isinstance(value.get("name"), str)
        and bool(value["name"]),
        label + ".name is required",
    )


def objects(value, label):
    require(
        isinstance(value, list)
        and all(isinstance(x, dict) for x in value),
        f"{label} must be an array of objects",
    )
    return value


def competitions(value):
    rows = objects(value, "competitions")
    seen = set()

    for row in rows:
        key = (
            integer(row.get("competition_id"), "competition_id"),
            integer(row.get("season_id"), "season_id"),
        )

        require(
            key not in seen,
            "Duplicate competition-season",
        )
        seen.add(key)

        for field in ("competition_name", "season_name"):
            require(
                isinstance(row.get(field), str)
                and bool(row[field]),
                f"Missing {field}",
            )

    return rows


def matches(value, competition):
    rows = objects(value, "matches")
    seen = set()

    for row in rows:
        mid = integer(row.get("match_id"), "match_id")
        require(mid not in seen, "Duplicate match_id")
        seen.add(mid)

        for section, id_key in (
            ("competition", "competition_id"),
            ("season", "season_id"),
        ):
            obj = row.get(section)
            require(
                isinstance(obj, dict)
                and obj.get(id_key) == competition[id_key],
                f"Match {mid}: inconsistent {section}",
            )

        try:
            require(
                date.fromisoformat(
                    row["match_date"]
                ).isoformat() == row["match_date"],
                "match_date must be YYYY-MM-DD",
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError(
                "invalid_schema",
                f"Match {mid}: invalid match_date",
            ) from exc

        for side in ("home_team", "away_team"):
            obj = row.get(side)

            require(
                isinstance(obj, dict),
                f"Missing {side}",
            )
            integer(
                obj.get(side + "_id"),
                side + "_id",
            )
            require(
                isinstance(obj.get(side + "_name"), str)
                and bool(obj[side + "_name"]),
                f"Missing {side} name",
            )

    return sorted(
        rows,
        key=lambda row: (
            row["match_date"],
            row["match_id"],
        ),
    )


def timestamp_seconds(value):
    require(
        isinstance(value, str)
        and re.fullmatch(
            r"\d{2}:\d{2}:\d{2}(?:\.\d+)?",
            value,
        ),
        "Invalid event timestamp",
    )

    hours, minutes, seconds = value.split(":")

    require(
        int(minutes) < 60 and float(seconds) < 60,
        "Invalid event timestamp",
    )

    return (
        int(hours) * 3600
        + int(minutes) * 60
        + float(seconds)
    )


def location(value):
    if not isinstance(value, list) or len(value) < 2:
        return None, None

    x, y = value[:2]

    if not all(
        type(n) in (int, float) and isfinite(n)
        for n in (x, y)
    ):
        return None, None

    return float(x), float(y)


def on_pitch(value):
    x, y = location(value)

    return (
        x is not None
        and 0 <= x <= 120
        and 0 <= y <= 80
    )


def is_corner(event):
    kind = event["type"]["name"]

    return (
        kind in ("Pass", "Shot")
        and event.get(kind.lower(), {})
        .get("type", {})
        .get("name") == "Corner"
    )


def validate_events(value):
    raw = objects(value, "events")
    seen = {}
    result = []

    for event in raw:
        eid = event.get("id")

        require(
            isinstance(eid, str) and bool(eid),
            "Event id is required",
        )
        integer(event.get("index"), "event index")
        require(
            type(event.get("period")) is int
            and 1 <= event["period"] <= 5,
            "Invalid event period",
        )

        timestamp_seconds(event.get("timestamp"))
        named(event.get("type"), "event type")

        for key in ("minute", "second"):
            if key in event:
                require(
                    type(event[key]) is int
                    and event[key] >= 0,
                    f"Invalid {key}",
                )

        if "second" in event:
            require(event["second"] < 60, "Invalid second")

        if "possession" in event:
            integer(event["possession"], "possession")

        for key in ("pass", "shot"):
            if key in event:
                require(
                    isinstance(event[key], dict),
                    f"{key} must be an object",
                )

                for optional in (
                    "type",
                    "outcome",
                    "body_part",
                    "height",
                    "technique",
                    "recipient",
                ):
                    if optional in event[key]:
                        require(
                            isinstance(
                                event[key][optional],
                                dict,
                            ),
                            f"{key}.{optional} must be an object",
                        )

        xg = event.get("shot", {}).get("statsbomb_xg")

        if xg is not None:
            require(
                type(xg) in (int, float)
                and isfinite(xg)
                and 0 <= xg <= 1,
                "Invalid shot xG",
            )

        if (
            is_corner(event)
            or event["type"]["name"] == "Shot"
        ):
            named(
                event.get("team"),
                "corner/shot team",
            )

        if is_corner(event):
            integer(
                event.get("possession"),
                "corner possession",
            )

        for optional in ("player", "team"):
            if optional in event:
                named(event[optional], optional)

        if eid in seen:
            require(
                seen[eid] == event,
                f"Conflicting duplicate event ID: {eid}",
            )
        else:
            seen[eid] = event
            result.append(event)

    result.sort(
        key=lambda e: (
            e["period"],
            timestamp_seconds(e["timestamp"]),
            e["index"],
            e["id"],
        )
    )

    return result, len(raw) - len(result)


def validate_frames(value):
    rows = objects(value, "360 frames")
    seen = set()

    for row in rows:
        eid = row.get("event_uuid")

        require(
            isinstance(eid, str)
            and bool(eid)
            and eid not in seen,
            "Missing/duplicate 360 event_uuid",
        )
        seen.add(eid)

        area = row.get("visible_area")

        require(
            isinstance(area, list)
            and (not area or len(area) >= 6)
            and len(area) % 2 == 0
            and all(
                type(x) in (int, float) and isfinite(x)
                for x in area
            ),
            "Invalid visible_area",
        )

        players = objects(
            row.get("freeze_frame"),
            "freeze_frame",
        )

        for player in players:
            require(
                location(player.get("location"))[0]
                is not None,
                "Invalid 360 player location",
            )

            for flag in ("teammate", "actor", "keeper"):
                require(
                    type(player.get(flag)) is bool,
                    f"Invalid 360 {flag}",
                )

    return rows


EVENT_FIELDS = [
    "match_id",
    "competition_id",
    "competition_name",
    "season_id",
    "season",
    "match_date",
    "home_team",
    "away_team",
    "event_id",
    "index",
    "period",
    "timestamp",
    "minute",
    "second",
    "possession_id",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    "event_type",
    "start_x",
    "start_y",
    "end_x",
    "end_y",
    "body_part",
    "technique",
    "height",
    "delivery_type",
    "outcome",
    "recipient_id",
    "recipient_name",
    "provider_xg",
    "source_revision",
    "source_event_json",
]


def event_row(event, metadata, revision):
    kind = event["type"]["name"]
    details = event.get(
        kind.lower().replace(" ", "_"),
        {},
    )
    details = (
        details if isinstance(details, dict) else {}
    )

    row = dict(metadata)
    row.update(
        event_id=event["id"],
        index=event["index"],
        period=event["period"],
        timestamp=event["timestamp"],
        minute=event.get("minute"),
        second=event.get("second"),
        possession_id=event.get("possession"),
        event_type=kind,
        source_revision=revision,
        source_event_json=json.dumps(
            event,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ),
    )

    for obj, prefix in (
        (event.get("team", {}), "team"),
        (event.get("player", {}), "player"),
        (details.get("recipient", {}), "recipient"),
    ):
        for field in ("id", "name"):
            row[prefix + "_" + field] = obj.get(field)

    row["start_x"], row["start_y"] = location(
        event.get("location")
    )
    row["end_x"], row["end_y"] = location(
        details.get("end_location")
    )

    for key in (
        "body_part",
        "technique",
        "height",
        "outcome",
    ):
        obj = details.get(key, {})
        row[key] = (
            obj.get("name")
            if isinstance(obj, dict)
            else None
        )

    row["delivery_type"] = (
        details.get("type", {}).get("name")
    )
    row["provider_xg"] = details.get("statsbomb_xg")

    return {
        key: row.get(key)
        for key in EVENT_FIELDS
    }


def completeness(events):
    corners = [
        event for event in events
        if is_corner(event)
    ]
    passes = [
        event for event in corners
        if event["type"]["name"] == "Pass"
    ]

    def report(rows, predicate):
        total = len(rows)
        present = sum(
            bool(predicate(event))
            for event in rows
        )

        return {
            "present": present,
            "missing": total - present,
            "total": total,
            "fraction_present": (
                present / total if total else None
            ),
        }

    def detail(event, key):
        return (
            event.get(
                event["type"]["name"].lower(),
                {},
            )
            .get(key, {})
            .get("name")
        )

    return {
        "event_location": report(
            events,
            lambda e: location(
                e.get("location")
            )[0] is not None,
        ),
        "event_location_in_pitch": report(
            events,
            lambda e: on_pitch(e.get("location")),
        ),
        "event_team": report(
            events,
            lambda e: e.get("team", {}).get("id"),
        ),
        "event_player": report(
            events,
            lambda e: e.get("player", {}).get("id"),
        ),
        "corner_location": report(
            corners,
            lambda e: location(
                e.get("location")
            )[0] is not None,
        ),
        "corner_body_part": report(
            corners,
            lambda e: detail(e, "body_part"),
        ),
        "corner_pass_technique": report(
            passes,
            lambda e: detail(e, "technique"),
        ),
        "corner_pass_height": report(
            passes,
            lambda e: detail(e, "height"),
        ),
        "corner_end_location": report(
            corners,
            lambda e: location(
                e[e["type"]["name"].lower()].get(
                    "end_location"
                )
            )[0] is not None,
        ),
    }