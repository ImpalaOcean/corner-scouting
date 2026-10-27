import json
import csv
from pathlib import Path
from urllib.request import urlopen
from corners.extract import (
    find_corners,
    find_corner_shots,
    extract_corner_sequence,
    describe_corner,
)

MATCH_ID = 3857276
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
output_folder = project_folder / "outputs"
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
    shots = find_corner_shots(events, corner)
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

summary_rows = []
for corner in find_corners(events):
    sequence = extract_corner_sequence(events, corner)
    shots = sequence["shots"]
    corner_kind = corner["type"]["name"]
    delivery = corner[corner_kind.lower()]
    summary_rows.append({
        "match_id": MATCH_ID,
        "corner_event_id": corner["id"],
        "team_id": corner["team"]["id"],
        "team": corner["team"]["name"],
        "taker": corner.get("player", {}).get("name", "Unknown"),
        "period": corner["period"],
        "timestamp": corner["timestamp"],
        "possession_id": corner["possession"],
        "corner_kind": corner_kind,
        "technique": delivery.get("technique", {}).get("name", "Unknown"),
        "foot": delivery.get("body_part", {}).get("name", "Unknown"),
        "height": delivery.get("height", {}).get("name", "Unknown"),
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
        "shot_event_ids": json.dumps([shot["id"] for shot in shots]),
        "stop_reason": sequence["stop_reason"],
        "chain_event_ids": json.dumps(sequence["chain_event_ids"]),
        **describe_corner(corner),
    })

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
        writer.writerows(summary_rows)
    print(f"Saved {len(summary_rows)} corner outcomes to {summary_file}")
