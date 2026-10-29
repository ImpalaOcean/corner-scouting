# src/analysis/

Owner: Asaad Faris Husein (Member 3: team distributions and evaluation)

## What this module does

Takes the corner table from the batch extractor (`corner_summary.csv` or
`.parquet`, schema `corner_summary_batch_v1`, one row per corner) and produces:

* `team_summary_v1.csv`: one row per team per competition season with corner
  counts, delivery category counts and frequencies, shot rate, goals, provider
  xG, first/last match dates and a `small_sample` flag.
* `match_splits.csv`: every match assigned to `train` (earliest 60%),
  `validation` (next 20%) or `test` (last 20%) by date within its competition
  season. Matches with no date are `excluded`. Competition seasons with fewer
  than 5 dated matches are `too_few_matches`.
* `analysis_manifest.json`: what was run, on which input, with which
  extraction settings.

Standard library only for CSV input. Parquet input needs `pyarrow`.

## Run

From the repository root:

```
python -m unittest discover -s tests -p "test_analysis.py" -v
python -m src.analysis --input tests/fixtures/corners_v1.csv --output outputs/analysis_fixture
python -m src.analysis --input outputs/sample_corners/corner_summary.csv --output outputs/analysis_sample
```

The output folder must be new for each run (same rule as the batch runner).

## Definitions

* Delivery frequencies use all corners as the denominator, including
  `direct_shot` and `unknown`, so each team's frequencies add up to 1.
* `shot_rate` = corners whose chain contained at least one shot / corners.
* `goal_rate` = goals / corners. `xg_sum` adds provider xG; it is not our model.
* `small_sample` is True below 10 matches or 30 corners (proposal rule). Those
  teams are shown descriptively and are not used for prediction.
* Splits sort matches by `match_date`, then `match_id`, so same day matches
  always land in the same order.
* The input must come from a single batch run: mixed window or short limit
  settings, duplicate `(match_id, corner_event_id)` keys and unknown delivery
  categories are rejected.

## Not done yet (Nov 2 to 15)

Shrinkage toward competition averages, pooled and unsmoothed baselines,
log loss and Brier score on held out matches, match bootstrap intervals,
and sensitivity comparisons across the 10/15/20/uncapped runs.
