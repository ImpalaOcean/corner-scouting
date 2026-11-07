"""Read Diego's corner table and StatsBomb 360 files. Read-only; nothing is
downloaded here (Ebtesam's loader in src/data provides the 360 files)."""

import csv
from math import isfinite
import json
from pathlib import Path

REQUIRED_COLUMNS = ("match_id", "corner_event_id", "start_x", "start_y")


def number(value):
    """Blank -> None (missing). Text that is not a finite number -> nan
    (invalid, so it is never mistaken for a blank). Otherwise a float."""
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except ValueError:
        return float("nan")
    return result if isfinite(result) else float("nan")


def read_corner_table(path):
    """Rows of a corner_summary.csv (any extra columns are kept as text)."""
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Corner table lacks columns: {missing}")
        rows = list(reader)
    seen = set()
    for row in rows:
        key = (str(row["match_id"]).strip(), row["corner_event_id"].strip())
        if not key[0] or not key[1]:
            raise ValueError("Corner table has a blank match_id or corner_event_id")
        if key in seen:
            raise ValueError(f"Duplicate corner in table: {key}")
        seen.add(key)
        row["match_id"], row["corner_event_id"] = key
        row["start_x"], row["start_y"] = number(row["start_x"]), number(row["start_y"])
    return rows


def read_frames(directory, match_ids):
    """{match_id: {event_uuid: frame}} for each match. A match whose 360 file
    does not exist maps to None (that is normal: not every match has 360)."""
    result = {}
    for match_id in sorted(set(match_ids)):
        path = Path(directory) / f"{match_id}.json"
        if not path.is_file():
            result[match_id] = None
            continue
        with path.open(encoding="utf-8-sig") as stream:
            frames = json.load(stream)
        if not isinstance(frames, list):
            raise ValueError(f"{path.name}: expected a JSON array of frames")
        indexed = {}
        for frame in frames:
            uuid = frame.get("event_uuid") if isinstance(frame, dict) else None
            if isinstance(uuid, str) and uuid and uuid not in indexed:
                indexed[uuid] = frame
        result[match_id] = indexed
    return result
