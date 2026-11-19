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
  10s, 15s, 20s and uncapped corner tables. This is a window-only comparison:
  corner keys, immutable delivery/location attributes, team and competition-season
  metadata, short threshold, cutoff, seed, bootstrap controls and recorded analysis
  code must agree. It rejects missing result files and incompatible populations.

## Unavailable targets and publication

Delivery and shot availability are handled separately. If validation has no
eligible known delivery labels, alpha remains null: no delivery parameter is
invented, delivery scores/probabilities remain unavailable for all three methods,
and beta selection plus shot evaluation continue on all eligible corners. This
target-level unavailable policy keeps the three delivery methods on the same
scoring population. If test delivery labels are all unknown, delivery metrics are
unavailable, while valid shot scores remain available. Empty CSV cells represent
unavailable values, never zero; status/reason fields and eligible/known/unknown
counts explain them. Eligibility thresholds, grids, baseline formulas,
chronological splits and validation-only parameter selection are unchanged.

New analysis outputs are written to a temporary sibling directory and published
only after writing, plotting, formatting and final input-hash checks succeed.
Existing destinations are refused. New manifests record input/artifact/code
SHA-256 hashes and a normalized `input_contract.json`. That contract fingerprints
all corner keys and invariant attributes independently of outcomes and window.
Comparison checks source bytes and recorded hashes when available, or a
hash-verified saved contract if the original input cannot be accessed; it records
that limitation in `comparison_manifest.json`. A legacy analysis can be compared
only when its original input is accessible and compatible; absent recorded hashes
and code evidence are disclosed as unverified, not silently treated as verified.
Relative legacy input paths are resolved from the invocation's repository root.
Historical association between an unhashed legacy result and today's source file
cannot be established. New extraction or sensitivity tables are not needed to
use these fixes; existing tables can be passed to a future analysis run.

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

## Final results (2015/16 Premier League, La Liga, Serie A, Ligue 1)

Reviewed and independently reproduced by Asaad on 2026-11-15. Input: the
primary 15 second, 15 unit short limit corner table, 1,517 matches and
15,482 corners. Its SHA-256 (`425f08f3...627d8`) equals Diego's primary run
recorded in `docs/leagues-2015-16-window-sensitivity.md`, so both runs used
byte identical input. Tables and figures come from
`python -m src.analysis.report` (commands below), which rebuilds every test
score from the saved alpha and beta and refuses to report if any overall score
differs from the saved run.

### Eligibility

All 80 teams pass the training threshold (10 matches, 30 corners in the
training split). Every competition season splits into 226 to 228 train, 75 to
76 validation and 76 test matches. Ligue 1 has 377 listed matches (provider
gap, see the data coverage docs). Per team counts: `eligibility_teams.csv`.

| Competition | Matches | Train / val / test | Corners | Eligible teams |
| --- | ---: | --- | ---: | ---: |
| Premier League | 380 | 228 / 76 / 76 | 4,108 | 20 of 20 |
| Ligue 1 | 377 | 226 / 75 / 76 | 3,591 | 20 of 20 |
| La Liga | 380 | 228 / 76 / 76 | 3,842 | 20 of 20 |
| Serie A | 380 | 228 / 76 / 76 | 3,941 | 20 of 20 |

### Main result

Chosen on validation: alpha = 50 (delivery), beta = 200 (shot); neither is at
the edge of the grid. 3,154 test corners in 304 test matches; 2,916 have a
known delivery and are scored for log loss. Differences are shrunk minus
baseline on the same corners (paired), with 95% match bootstrap intervals.

| Target | Pooled | Unsmoothed | Shrunk | Shrunk minus pooled | Shrunk minus unsmoothed |
| --- | ---: | ---: | ---: | --- | --- |
| Delivery (log loss) | 1.1294 | 1.1187 | 1.0960 | -0.0334 [-0.0466, -0.0201] | -0.0226 [-0.0424, -0.0070] |
| Shot (Brier) | 0.2204 | 0.2214 | 0.2203 | -0.0002 [-0.0009, 0.0006] | -0.0011 [-0.0020, -0.0002] |

* **Deliveries:** team history, shrunk toward the league average, predicts
  later delivery types better than the league average alone. The interval is
  entirely below zero. By league the gain is clear in the Premier League
  (-0.057), La Liga (-0.030) and Serie A (-0.029); in Ligue 1 it points the
  same way (-0.015) but the interval includes zero.
* **Shot creation:** no measurable gain over the league average in any
  league. The large chosen beta (200) itself says the data prefers the league
  average. Shrinkage does beat raw team shot rates, which means raw team shot
  rates are worse than the league average at predicting later shot creation.
* **Per team:** 20 of 80 teams have a delivery interval below zero and 2 above,
  where about 2 per side would be expected by chance alone; individual teams
  should not be singled out as proof. For shots, 9 below and 4 above, against
  the overall null result.
* **Windows:** delivery results are identical for 10s, 15s, 20s and uncapped
  (windows change outcomes, not deliveries). The shot result is null under all
  four (10s chose beta = 500, the others 200).

Interpretation for the paper: teams have repeatable corner delivery habits that
are worth scouting, but a team's past rate of shots from corners does not
predict its later rate better than the league average in this corpus.

### Review notes (methodological concerns, nothing rerun or changed)

1. **Shrunk versus unsmoothed delivery depends on the floor probability.** The
   unsmoothed baseline gives a never seen category probability 1e-6. Seven test
   corners (0.24%) fall in such a category and each costs about 13.8 in log
   loss. They account for -0.0195 of the -0.0226 gap; without them the gap is
   -0.0032. Report this comparison with that caveat. The main comparison
   (shrunk versus pooled) is unaffected because pooled uses add one smoothing.
2. **Wording in the console printout.** The runner labels any negative interval
   "team history helps", including shrunk minus unsmoothed, where it actually
   means "smoothing helps". The report uses neutral wording ("shrunk better").
3. **Per team intervals are 80 separate comparisons;** about 4 would exclude
   zero by chance. Use them descriptively, not as team level claims.
4. **The test split is the last 20% of each season,** so it covers the run
   in; end of season effects are not separated from habit stability.
5. **One alpha and one beta for all four leagues.** League specific smoothing
   was not tried, by design; the per league table shows the shared choice
   still helps in three of four.

## Running

### Report evidence safeguards

The report verifies the recorded input and artifact hashes before reading saved
scores, paired differences, intervals, team results or parameter-selection tables.
It refuses evaluation artifacts without recorded hashes. `--input` can relocate
the source table but cannot bypass its recorded hash or population contract.
Any permitted legacy provenance limitations are written into the report checks
and Markdown. Alternative-window reports use the same population, invariant
attributes, settings, code and analysis-control checks as `src.analysis.compare`.
The report does not alter or regenerate saved experiments.

Reproduce the final tables and figures (after the league extraction runs in
`docs/league-2015-16-runs.md`):

    python -m src.analysis --input outputs/leagues-2015-16-corners/corner_summary.csv --output outputs/analysis_leagues_w15
    python -m src.analysis --input outputs/leagues-2015-16-window-10/corner_summary.csv --output outputs/analysis_leagues_w10
    python -m src.analysis --input outputs/leagues-2015-16-window-20/corner_summary.csv --output outputs/analysis_leagues_w20
    python -m src.analysis --input outputs/leagues-2015-16-window-uncapped/corner_summary.csv --output outputs/analysis_leagues_wuncapped
    python -m src.analysis.report --run outputs/analysis_leagues_w15 --windows outputs/analysis_leagues_w10 outputs/analysis_leagues_w20 outputs/analysis_leagues_wuncapped --output outputs/report_leagues

General usage:

    python -m src.analysis --input outputs/<run>/corner_summary.csv --output outputs/analysis_<run>
    python -m src.analysis.compare --runs outputs/analysis_w10 outputs/analysis_w15 --output outputs/sensitivity

Options: `--bootstrap N` (0 turns intervals off), `--seed`, and `--cutoff
YYYY-MM-DD` for a prematch view (summaries only, evaluation skipped).
