# src/analysis/

Owner: Asaad Faris Husein (Member 3: team distributions and evaluation)

## What this module does

Takes the corner table from the batch extractor (`corner_summary.csv` or
`.parquet`, one row per corner) and answers proposal question 1: does a
team's corner history predict its later corners better than the competition
average? Full method and first results: `docs/evaluation.md`.

## Files

* `summary.py`: loading and checks, team summaries with bootstrap intervals,
  period breakdown, prematch cutoff, chronological splits.
* `evaluation.py`: pooled, unsmoothed and shrunk predictions, alpha and beta
  selection on validation, log loss and Brier score on test, bootstrap
  intervals, reliability and stability tables.
* `compare.py`: sensitivity comparison across extraction settings.
* `audit.py`: the 100 corner audit (sample, show raw events, agreement).
  Protocol: `docs/audit-protocol.md`.
* `__main__.py`: the command that runs everything.

## Outputs

Column by column reference for the dossier: `docs/analysis-outputs.md`.

* `team_summary_v1.csv`: per team per competition season counts,
  frequencies and shot rate with 95% intervals, goals, xG, `small_sample`.
  This is the dossier's input.
* `period_summary.csv`, `match_splits.csv`, `analysis_manifest.json`.
* `evaluation/`: `alpha_selection`, `evaluation_summary`,
  `evaluation_differences`, `team_evaluation`, `reliability` (+ png if
  matplotlib is installed), `profile_stability`, `team_predictions`.

Standard library only for CSV input. Parquet input needs `pyarrow`.

## Run

From the repository root:

```
python -m unittest discover -s tests -v
python -m src.analysis --input outputs/sample_corners/corner_summary.csv --output outputs/analysis_sample
python -m src.analysis --input outputs/sample_corners/corner_summary.csv --output outputs/prematch --cutoff 2022-12-01
python -m src.analysis.compare --runs outputs/analysis_w10 outputs/analysis_w15 --output outputs/sensitivity
```

Every output folder must be new.

## Definitions

* Delivery frequencies use all corners as the denominator, including
  `direct_shot` and `unknown`, so they add up to 1.
* `shot_rate` = corners whose chain contained at least one shot / corners.
* `small_sample` is True below 10 matches or 30 corners (proposal rule).
* The input must come from a single batch run: mixed window or short limit
  settings, duplicate `(match_id, corner_event_id)` keys and unknown delivery
  categories are rejected.
