# Data contract

This document defines the shared schema and exchange formats used across the project so that teammates can work independently without waiting on each other's code.

## Canonical table: `corner_events`

All downstream analysis should consume a single normalized table with the following columns.

| Column | Type | Description |
| --- | --- | --- |
| `match_id` | string | Unique StatsBomb match identifier. |
| `competition_id` | int | Competition identifier from StatsBomb metadata. |
| `competition_name` | string | Competition name, e.g. `FA Women's Super League`. |
| `season_id` | int | Season identifier. |
| `match_date` | string | Date in ISO format (`YYYY-MM-DD`). |
| `home_team` | string | Home team name. |
| `away_team` | string | Away team name. |
| `team_name` | string | Team that executed or received the corner event. |
| `team_id` | int | StatsBomb team identifier. |
| `minute` | int | Minute of the event, 0-90+ (or match-specific range). |
| `second` | int | Second within the minute. |
| `event_id` | string | Unique event identifier. |
| `event_type` | string | Event type such as `pass`, `cross`, `shot`, `goal`, `clearance`. |
| `set_piece_type` | string | Always `corner` for canonical corner records. |
| `starter_event_id` | string | Event ID for the event that initiated the corner sequence. |
| `corner_sequence_id` | string | Identifier that groups all events belonging to the same corner sequence. |
| `origin_x` | float | X coordinate of origin event in StatsBomb 360 frame. |
| `origin_y` | float | Y coordinate of origin event in StatsBomb 360 frame. |
| `end_x` | float | End X coordinate of the relevant pass/cross/shot. |
| `end_y` | float | End Y coordinate of the relevant pass/cross/shot. |
| `is_goal` | bool | Whether the sequence resulted in a goal. |
| `is_shot` | bool | Whether a shot occurred. |
| `is_successful` | bool | Whether the corner routine achieved its immediate objective. |
| `body_part` | string | Body part used for a shot or touch, e.g. `left_foot`, `right_foot`, `head`. |
| `player_name` | string | Subject player name. |
| `player_id` | int | StatsBomb player identifier. |
| `recipient_name` | string | Recipient player name, if applicable. |
| `recipient_id` | int | Recipient player ID, if applicable. |
| `notes` | string | Free-text annotation or edge-case note. |

## Coordinate conventions

- Coordinates should follow the StatsBomb 360 coordinate system.
- X values range from 0 to 120 and Y values from 0 to 80 unless explicitly stated otherwise.
- Columns should be stored as numeric types in CSV/Parquet outputs rather than as strings.
- Use ISO-8601 strings for dates and booleans as `True`/`False` when writing CSV.

## Data exchange expectations

The team should exchange the following artifacts:

1. `corner_events.csv` or `corner_events.parquet` from the extraction step.
2. `setup_summary.csv` from the setups module with routine categories and counts.
3. `analysis_summary.csv` from the analysis module with key metrics.
4. `team_dossier.md` or a notebook-based output from the dossier module.

## Acceptance criteria

- Every module must read or write the same columns and types.
- No component should depend on a teammate's unfinished code to produce its first version.
- Sample fixtures in `tests/fixtures/` must validate the schema before full data ingestion is available.
