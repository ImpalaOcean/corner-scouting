# Analysis outputs (for the dossier)

Owner: Asaad. Producer: `python -m src.analysis`. Method details: `docs/evaluation.md`.

Every run writes into one new folder:

```
outputs/analysis_<name>/
  team_summary_v1.csv        main dossier input, one row per team per competition season
  period_summary.csv         corners and shot rate by half
  match_splits.csv           train / validation / test label for every match
  analysis_manifest.json     what was run: input, settings, cutoff, evaluation results
  evaluation/                only when evaluation ran (no --cutoff)
    team_predictions.csv     expected delivery mix and shot chance for eligible teams
    team_evaluation.csv      per team test scores
    evaluation_summary.csv, evaluation_differences.csv, alpha_selection.csv,
    reliability.csv, reliability.png, profile_stability.csv
```

Join keys: a team is `(competition_id, season_id, team_id)`. A corner is
`(match_id, corner_event_id)`, the same key the setups module uses.
Empty cells mean "not available" (for example no interval when bootstrap is off).

## team_summary_v1.csv

| Column | Type | Meaning |
|---|---|---|
| competition_id, season_id, team_id | int | Keys |
| competition_name, season, team | text | Labels for display |
| window_seconds, short_limit | number | Extraction settings the corners came from (blank window = uncapped) |
| date_cutoff | date or blank | Only matches strictly before this date were used (prematch view) |
| first_match_date, last_match_date | date | Range of matches behind the numbers |
| matches, corners | int | Sample size; show these next to every number |
| n_short, n_inswinging, n_outswinging, n_straight, n_unknown, n_direct_shot | int | Corner counts per delivery type |
| freq_short ... freq_direct_shot | 0 to 1 | Share of the team's corners; the six add up to 1 |
| freq_<type>_ci_low, freq_<type>_ci_high | 0 to 1 | 95% match bootstrap interval for that share |
| corners_with_shot | int | Corners whose chain had at least one shot |
| shot_rate, shot_rate_ci_low, shot_rate_ci_high | 0 to 1 | corners_with_shot / corners, with 95% interval |
| shots, goals | int | Totals inside the chains |
| goal_rate | 0 to 1 | goals / corners (descriptive only) |
| xg_sum, xg_per_corner | number | StatsBomb provider xG, not our model |
| small_sample | True/False | True below 10 matches or 30 corners: show with a caveat |

## evaluation/team_predictions.csv

Only teams eligible for prediction (10+ training matches and 30+ training
corners). Three rows per team, one per `method`: `pooled` (competition
average), `unsmoothed` (team raw history), `shrunk` (recommended for display).

| Column | Meaning |
|---|---|
| competition_id ... team | Same keys and labels as above |
| method | pooled, unsmoothed or shrunk |
| p_short, p_inswinging, p_outswinging, p_straight, p_direct_shot | Expected share of the next corners (unknown excluded, so these add up to 1) |
| p_shot | Expected chance a corner leads to a shot |

## period_summary.csv

| Column | Meaning |
|---|---|
| competition_id ... team | Keys and labels |
| period_group | half_1, half_2, extra_time |
| corners, corners_with_shot, shot_rate, goals | As above, within that period group |

## match_splits.csv

| Column | Meaning |
|---|---|
| match_id, match_date, competition_id, season_id (+ labels) | Match identity |
| order | Position by date within its competition season |
| split | train, validation, test, excluded (no date) or too_few_matches (season under 5 matches) |

## Prematch views

The dossier must only use matches before the game it prepares for:

```
python -m src.analysis --input outputs/<run>/corner_summary.csv --output outputs/prematch_2024-07-01 --cutoff 2024-07-01
```

This writes `team_summary_v1.csv` and `period_summary.csv` from matches
strictly before the date, fills `date_cutoff`, and skips evaluation.

From Python (run from the repository root):

```python
from src.analysis.summary import load_corners, team_summaries, period_breakdown

rows = load_corners('outputs/wce_corners/corner_summary.csv')
teams = team_summaries(rows, bootstrap_draws=1000, seed=5118, cutoff='2024-07-01')
spain = [t for t in teams if t['team'] == 'Spain']
```

`team_summaries` returns a list of dicts with exactly the columns above.

## Suggested dossier wording rules

* Always print `matches` and `corners` beside percentages.
* When `small_sample` is True, label the section "descriptive, small sample".
* Show intervals as a range ("between 38% and 61%") rather than only the point value.
* Goals and goal_rate are descriptive; do not present them as a prediction.
