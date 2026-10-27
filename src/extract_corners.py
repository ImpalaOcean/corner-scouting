import argparse
import json
import csv
from math import isfinite
from pathlib import Path
from urllib.request import urlopen
from corners.extract import (
    find_corners,
    find_corner_shots,
    extract_corner_sequence,
    describe_corner,
    build_corner_summaries,
)

parser = argparse.ArgumentParser(
    description="Extract corners and outcomes from a StatsBomb match."
)
parser.add_argument(
    "--match-id",
    type=int,
    default=3857276,
    help="StatsBomb match ID; defaults to Canada–Morocco.",
)
parser.add_argument(
    "--window",
    choices=["10", "15", "20", "uncapped"],
    default="15",
    help="Corner outcome window in seconds, or uncapped.",
)
parser.add_argument(
    "--short-limit",
    type=float,
    default=15,
    help="Maximum ground-delivery distance for a short corner.",
)
args = parser.parse_args()
if args.match_id <= 0:
    parser.error("--match-id must be positive")
if not isfinite(args.short_limit) or args.short_limit <= 0:
    parser.error("--short-limit must be positive and finite")
MAX_SECONDS = None if args.window == "uncapped" else int(args.window)
SHORT_LIMIT = args.short_limit
MATCH_ID = args.match_id
url = (
    "https://raw.githubusercontent.com/hudl/open-data/"
    f"master/data/events/{MATCH_ID}.json"
)

print("Downloading the sample match...")

with urlopen(url, timeout=30) as response:
    events = json.load(response)

corners = [
    event for event in find_corners(events)
    if event["type"]["name"] == "Pass"
]

print(f"Found {len(corners)} corner deliveries.")

for corner in corners:
    team = corner["team"]["name"]
    player = corner.get("player", {}).get("name", "Unknown")
    minute = corner["minute"]
    second = corner["second"]

    print(f"{minute}:{second:02d} | {team} | {player}")

project_folder = Path(__file__).resolve().parent.parent
output_folder = (
    project_folder
    / "outputs"
    / str(MATCH_ID)
    / f"window_{args.window}_short_{SHORT_LIMIT:g}"
)
output_folder.mkdir(parents=True, exist_ok=True)
output_file = output_folder / "sample_corners.csv"

with output_file.open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.writer(file)
    writer.writerow([
        "match_id",
        "event_id",
        "team",
        "taker",
        "minute",
        "second",
        "foot",
        "technique",
        "height",
    ])

    for corner in corners:
        delivery = corner["pass"]
        writer.writerow([
            MATCH_ID,
            corner.get("id", ""),
            corner.get("team", {}).get("name", "Unknown"),
            corner.get("player", {}).get("name", "Unknown"),
            corner.get("minute", ""),
            corner.get("second", ""),
            delivery.get("body_part", {}).get("name", "Unknown"),
            delivery.get("technique", {}).get("name", "Unknown"),
            delivery.get("height", {}).get("name", "Unknown"),
        ])

print(f"Saved {len(corners)} corners to {output_file}")

from collections import Counter

corners_by_team = Counter(
    corner["team"]["name"] for corner in corners
)

print("\nCorner deliveries by team:")
for team, count in sorted(corners_by_team.items()):
    print(f"{team}: {count}")

techniques_by_team = {}
for corner in corners:
    team = corner["team"]["name"]
    technique = (
        corner["pass"]
        .get("technique", {})
        .get("name", "Unknown")
    )
    if team not in techniques_by_team:
        techniques_by_team[team] = Counter()
    techniques_by_team[team][technique] += 1

print("\nDelivery techniques by team:")
for team, techniques in sorted(techniques_by_team.items()):
    total = corners_by_team[team]
    print(f"\n{team} — {total} corner deliveries")
    for technique, count in sorted(techniques.items()):
        percentage = count / total * 100
        print(f"  {technique}: {count} ({percentage:.1f}%)")

print("\nOutcomes for every corner:")
for corner in find_corners(events):
    shots = find_corner_shots(events, corner, max_seconds=MAX_SECONDS)
    goals = sum(
        shot["shot"].get("outcome", {}).get("name") == "Goal"
        for shot in shots
    )
    print(
        f"{corner['minute']}:{corner['second']:02d}"
        f" | {corner['team']['name']}"
        f" | shots: {len(shots)}"
        f" | goals: {goals}"
    )

summary_rows = build_corner_summaries(
    events,
    MATCH_ID,
    max_seconds=MAX_SECONDS,
    short_limit=SHORT_LIMIT,
)

summary_file = output_folder / "corner_summary.csv"
if summary_rows:
    with summary_file.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(summary_rows[0].keys()),
        )
        writer.writeheader()
        for row in summary_rows:
            csv_row = {
                key: json.dumps(value) if isinstance(value, list) else value
                for key, value in row.items()
            }
            writer.writerow(csv_row)
    print(f"Saved {len(summary_rows)} corner outcomes to {summary_file}")
