# Evaluation (Member 3: team distributions and evaluation)

Owner: Asaad Faris Husein. Code: `src/analysis/`. Tests: `tests/test_analysis.py`,
`tests/test_evaluation.py`.

## Question

Proposal question 1: does a team's historical corner profile predict its later
deliveries and shot creation better than the competition average?

## Input

The batch runner's corner table (`corner_summary_batch_v1`, one row per
corner, CSV or Parquet). One run per extraction setting; mixed settings are
rejected.

## Chronological splits

Within each competition season, matches are sorted by `match_date`, then
`match_id`. The earliest 60% are train, the next 20% validation, the last 20%
test. Whole matches stay in one split. Matches without a date are excluded.
Competition seasons with fewer than 5 dated matches are not split
(`too_few_matches`).

## Eligibility

A team is evaluated only with at least 10 matches and 30 corners in the train
split (proposal rule). Other teams stay in the descriptive tables with
`small_sample = True`. Tournaments never reach this bar (at most 7 matches per
team), so predictive results come from full league seasons.

## Methods

For delivery category d, team t, competition season c:

* pooled: competition average over history corners, with add one smoothing
  so no category has probability zero.
* unsmoothed: the team's own history frequencies (zeros raised to 1e-6 and
  renormalised).
* shrunk: p = (n_td + alpha * p_cd) / (N_t + alpha), the proposal's formula.

Shot rate uses the same three methods with its own smoothing weight, beta.

## Two stages, test used once

1. Selection: fit on train, score validation for every alpha and beta in
   {0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000}. Pick the lowest validation
   log loss (alpha) and Brier score (beta); ties go to more smoothing.
2. Final: refit on train plus validation (everything before the test
   matches), score the test matches once with the chosen alpha and beta.

The test split never influences a choice. `tests/test_evaluation.py` checks
this by changing every test corner and confirming alpha, beta and the fitted
profiles do not change.

## Metrics

* Deliveries: multiclass log loss over short, inswinging, outswinging,
  straight and direct_shot. Corners labelled `unknown` are missing data, not a
  team choice, so they are left out of delivery scoring and counted
  separately (`test_corners_unknown`).
* Shot creation: Brier score on `led_to_shot`, every corner.
* Lower is better for both. A difference `shrunk_minus_pooled` below zero
  means team history helped.
* Goals are reported descriptively only; they are too rare to score.

## Uncertainty

95% intervals come from a match bootstrap (1000 draws, seed 5118): whole
matches are resampled, keeping every corner of a match (both teams) together.
Used for team frequencies and shot rates, aggregate scores, the differences
between methods, and per team differences.

## Diagnostics

* `reliability.csv` / `reliability.png`: predicted shot probability against
  observed shot rate in ten bins.
* `profile_stability.csv`: total variation distance between each team's
  history profile and its profile in the later test matches, next to the
  same distance for the competition average.
* `period_summary.csv`: corners and shot rate by first half, second half and
  extra time. Descriptive; no causal claims.
* Sensitivity: `python -m src.analysis.compare` lines up runs made from the
  10s, 15s, 20s and uncapped corner tables.

Not available from the current corner table: score state and opponent
strength. Opponent strata would hold one or two matches each, so they are not
reported.

## Dataset requirement

Predictive evaluation needs teams with at least 10 training matches. Tournaments
cannot provide that: in the agreed first run (World Cup 2022 + Euro 2024, 115
matches, 1,083 corners, 56 team rows) no team plays more than 7 matches, so
every team is `small_sample` and nothing can be scored. The splits themselves
work (68 train, 23 validation, 24 test matches).

To answer question 1, the corpus needs full league seasons. In the pinned
source, the 2015/16 Premier League (2/27), La Liga (11/27), Serie A (12/27) and
Ligue 1 (7/27) are complete (377 to 380 matches each, about 1,500 matches,
roughly 15,000 corners). Women's league seasons (FA WSL, NWSL, Liga F,
Frauen Bundesliga) also reach the bar. The full open corpus (80 competition
seasons, 3,961 matches) would meet the proposal's "tens of thousands of
corners" target. Tournaments remain useful for descriptive dossiers and the
360 setups, since league seasons have no 360 data.

## First results (Premier League 2015/16 + FA WSL 2020/21, 511 matches)

Local test run, not yet the full corpus. 30 eligible teams, 1,067 test
corners in 102 test matches. Chosen alpha = 20, beta = 200.

* Deliveries: team history beats the competition average. Log loss 1.152
  (shrunk) vs 1.200 (pooled); difference -0.048, 95% interval [-0.081,
  -0.017]. Shrunk and unsmoothed are close (difference -0.003, interval
  includes zero).
* Shot creation: no clear gain. Brier 0.2296 (shrunk) vs 0.2298 (pooled),
  difference interval includes zero. The large chosen beta says the data
  prefers the competition average.
* Per team: the gain varies. 7 of 30 teams show a clear delivery
  improvement; a few show none or a loss.
* Sensitivity: the delivery result is identical for every window (windows
  only change outcomes). The overall shot rate rises with the window (30.7%
  at 10s, 33.0% at 15s, 34.2% at 20s, 36.7% uncapped), but the shot finding
  (no clear team effect) holds for all four.

Interpretation for the paper: teams have stable delivery habits worth scouting,
but in this sample their past shot creation rate from corners does not
predict future shot creation better than the league average.

## Running

    python -m src.analysis --input outputs/<run>/corner_summary.csv --output outputs/analysis_<run>
    python -m src.analysis.compare --runs outputs/analysis_w10 outputs/analysis_w15 --output outputs/sensitivity

Options: `--bootstrap N` (0 turns intervals off), `--seed`, and `--cutoff
YYYY-MM-DD` for a prematch view (summaries only, evaluation skipped).
