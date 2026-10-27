# Corner extraction — Diego

Owner: Diego Fuentes. This is the first extraction handoff for review.

## Requirements and input

Python 3.11+; the extractor uses only the standard library.
Run the commands below from the repository root.

Input is a StatsBomb event JSON array in provider chronological order.
With a local file, supply the correct match ID explicitly: the event array
itself cannot verify that ID. Preserve provider event IDs, timestamps, periods,
team IDs, possession IDs, and nested pass/shot attributes.

## Run

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_corners.py -v
.\.venv\Scripts\python.exe src/extract_corners.py --match-id 3857276
.\.venv\Scripts\python.exe src/extract_corners.py --events data/manual_test/3857276.json --match-id 3857276
```

If no event file is supplied, the runner downloads the selected match from
StatsBomb's current master branch. Default match is 3857276. Downloads are not
yet pinned or cached by this runner; use revision-controlled local inputs from
the data workstream for reproducible research runs.

Sensitivity options:

```powershell
.\.venv\Scripts\python.exe src/extract_corners.py --events data/manual_test/3857276.json --match-id 3857276 --window 10
.\.venv\Scripts\python.exe src/extract_corners.py --events data/manual_test/3857276.json --match-id 3857276 --window uncapped --short-limit 20
```

Allowed windows: 10, 15 (default), 20, uncapped. The default short limit is
15 native coordinate units. Uncapped removes only the time cap.

## Output and schema

Files go to outputs/<match_id>/window_<window>_short_<short_limit>/.
Repeating the same match/settings replaces the generated files in that folder.

- corner_summary.csv: one row per unique corner, including direct corner shots.
- sample_corners.csv: legacy delivery-only table. It excludes direct corner shots.
- The printed delivery counts also exclude direct corner shots; the outcome
  summaries include them. Use corner_summary.csv for the new handoff.

Proposed summary join key: (match_id, corner_event_id).

| Group | Columns |
| --- | --- |
| Identity | match_id, corner_event_id, team_id, team, taker, period, timestamp, minute, second, possession_id, corner_kind |
| Delivery | technique, foot, height, delivery_category, start_x, start_y, end_x, end_y |
| Outcomes | shot_count, goal_count, led_to_shot, provider_xg_sum |
| Audit | shot_event_ids, chain_event_ids, stop_reason |
| Settings | window_seconds, short_limit |

The Python API returns dictionaries with native lists for event IDs.
CSV list fields contain JSON arrays; decode with json.loads(). Booleans are
True/False and missing values are blank. An uncapped window is represented by
None in Python and a blank window_seconds cell in CSV, with uncapped in the
folder name. Coordinates follow the provider 120 x 80 pitch convention;
missing coordinates remain null. provider_xg_sum adds provider shot estimates:
it is not a fitted model or the probability of at least one goal.

delivery_category values: short, inswinging, outswinging, straight, unknown,
direct_shot. A short delivery must be a ground pass with start-to-end distance
at or below the configured limit; otherwise the known technique is used.
Missing technique never implies short.

stop_reason values: time_limit, possession_change, new_restart, period_end,
stoppage, ball_out, goal, end_of_data. Restart/possession/stoppage boundary events
are excluded from chain_event_ids; terminal shots and ball-out actions are
included. For simultaneous boundaries, the implementation's check order
determines the recorded reason. This is an extraction convention to audit.

A zero-corner run currently writes an empty legacy delivery table but does not
write/clear corner_summary.csv. Avoid reusing a settings folder for empty runs
until empty-summary output is hardened.

## Python API

With src on the Python import path:

```python
from corners.extract import build_corner_summaries

rows = build_corner_summaries(
    events,
    match_id=3857276,
    max_seconds=15,  # None means uncapped.
    short_limit=15,
)
```

The reusable module performs no downloading or file writing. Import this module,
not src/extract_corners.py: the latter is a command-line runner.

## Validation and integration review

Current unit suite: 15 tests covering corners/direct shots, duplicates, time and
period boundaries, possession, restarts/stoppages, advantage, terminal goals,
delivery categories, coordinates and summary fields.

Two-match checks reported by Diego at the default settings:
- 3857276: eight summaries, three shots, zero goals.
- 3857271: eight summaries, two shots, one goal.

Four window settings were also exercised on 3857276 with matching totals;
that is a sample smoke check, not a corpus-wide sensitivity result.

Review with Asaad and Mohamed before freezing the interface: this summary is
additional to the repository's current event-grain corner_events fixture.
It is not a drop-in replacement. In particular, team versus team_name and
corner_event_id versus event_id need an agreed mapping. Do not change shared
fixtures or teammates' consumers silently.

Remaining integration/research work: match metadata, batch/corpus execution,
Parquet, source-revision/hash provenance, the independent 100-sequence audit,
corpus sensitivity results, and extraction methods/results for the paper.

Data source: https://github.com/hudl/open-data. Follow StatsBomb attribution and
usage terms for published outputs. Raw files and generated outputs stay out of Git.
