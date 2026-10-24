import json
import csv
from pathlib import Path
from urllib.request import urlopen

MATCH_ID = 3857276
url = (
    "https://raw.githubusercontent.com/hudl/open-data/"
    f"master/data/events/{MATCH_ID}.json"
)

print("Downloading the sample match...")

with urlopen(url, timeout=30) as response:
    events = json.load(response)

corners = [
    event
    for event in events
    if (
        event.get("type", {}).get("name") == "Pass"
        and event.get("pass", {}).get("type", {}).get("name") == "Corner"
    )
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
