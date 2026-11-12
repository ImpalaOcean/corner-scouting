# Tournament 360 coverage by delivery category

Measured on 2026-11-12 from the primary 15-second/short-limit-15 tournament corner table and the existing pinned cache. This profile uses every corner, including unknown deliveries and direct corner shots. No downloads, extraction reruns, setup-rule changes, or audit judgments were made.

## Three distinct checks

`src/profile_tournament_360.py` uses `src.setups.loader.read_corner_table()` for identifiers, duplicate rejection, and coordinate conversion. For each match it resolves the coverage manifest's frame path (or the conventional cache path when absent), records file status and SHA-256, verifies the recorded hash when present, and applies `src.data.validation.validate_frames()` to the whole file. It then uses `src.setups.loader.read_frames()` for the match-local event UUID join. A corrupt JSON file, invalid provider structure, read error, or hash mismatch is a file-level failure, never an ordinary unmatched frame.

Each corner retains `file_loaded`, `file_status`, `frame_matched`, `setup_eligible`, a coverage status, and both setup and profiling exclusion reasons. File-unavailable corners have null matching/eligibility assessments, rather than false assertions that a loaded file lacked the frame. Empty but valid files are loaded with zero matches. Matched frames are passed to the unchanged `build_setups()` pipeline, preserving its frame validation, corner-location fallback, eligibility priority, visibility and player thresholds. Setup clustering is an internal consequence of reusing that pipeline; this profile makes no cluster/routine claims.

The eligibility thresholds actually used are minimum box coverage **0.5** and minimum visible players **5**. Corner-location and geometry rules are reused directly, including the current three-unit corner-flag tolerance; the actor fallback applies when the table cannot supply both coordinates. The pipeline's rounded four-decimal `box_coverage` is the value tested. Full setup defaults, module hashes and the checkout revision are recorded in provenance. Cluster size/confidence defaults do not determine eligibility.

## Reconciliation and denominators

All **115 match files** loaded successfully (64 World Cup, 51 Euro), with their recorded hashes verified. All 1,083 corners are therefore in matches with available files. The exact join yields **592 matched frames**, agreeing with the ingestion coverage total and every per-match count. There are **491 unmatched corners in loaded files**, no unavailable/corrupt files, and **one matched but ineligible frame**. All 1,083 records remain in `per_corner.csv`.

Overall matching is 592/1,083 = **54.66%**, while usable coverage is 591/1,083 = **54.57%**. Eligibility among matched frames is 591/592 = **99.83%**. World Cup totals are 302 matched and usable out of 571 corners (52.89%); Euro totals are 290 matched out of 512 (56.64%) and 289 usable out of 512 (56.45%). No count discrepancy was forced into agreement.

Output percentage denominators are explicit:

- `matching_pct_all`: matched / all corners in the competition-category or comparison group.
- `usable_pct_all`: usable / all corners in that group.
- `matching_pct_loaded`: matched / corners in that group whose match file loaded successfully.
- `usable_pct_matched`: usable / matched corners in that group.

Zero denominators produce null/blank percentages, not zero. Unavailable-file corners stay in the all-corner denominator; they are excluded only from the explicitly conditional loaded-file denominator. In this run, every file loaded, so matching rates conditional on loaded files equal the all-corner matching rates in every row below. All six categories are emitted per tournament, even if a future group has no corners. Non-short means all five other categories combined, including unknown and direct_shot.

## Measured category coverage

The denominator N is every corner of that category within that tournament. Matching and usable percentages both divide by N. For this run N also equals `corners_in_loaded_matches`; thus the matching column is also the matching rate among corners in loaded matches.

| Tournament | Delivery | N | Matched | Usable | Matched / N | Usable / N |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| World Cup 2022 | short | 65 | 19 | 19 | 29.23% | 29.23% |
| World Cup 2022 | inswinging | 234 | 132 | 132 | 56.41% | 56.41% |
| World Cup 2022 | outswinging | 206 | 120 | 120 | 58.25% | 58.25% |
| World Cup 2022 | straight | 20 | 14 | 14 | 70.00% | 70.00% |
| World Cup 2022 | unknown | 44 | 15 | 15 | 34.09% | 34.09% |
| World Cup 2022 | direct_shot | 2 | 2 | 2 | 100.00% | 100.00% |
| Euro 2024 | short | 62 | 20 | 20 | 32.26% | 32.26% |
| Euro 2024 | inswinging | 221 | 143 | 143 | 64.71% | 64.71% |
| Euro 2024 | outswinging | 161 | 98 | 98 | 60.87% | 60.87% |
| Euro 2024 | straight | 16 | 10 | 10 | 62.50% | 62.50% |
| Euro 2024 | unknown | 48 | 17 | 16 | 35.42% | 33.33% |
| Euro 2024 | direct_shot | 4 | 2 | 2 | 50.00% | 50.00% |

## Short versus non-short

| Tournament | Group | N | Matched | Usable | Matched / N | Usable / N |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| World Cup 2022 | short | 65 | 19 | 19 | 29.23% | 29.23% |
| World Cup 2022 | non_short | 506 | 283 | 283 | 55.93% | 55.93% |
| Euro 2024 | short | 62 | 20 | 20 | 32.26% | 32.26% |
| Euro 2024 | non_short | 450 | 270 | 269 | 60.00% | 59.78% |

Short matching is 26.70 percentage points below non-short matching in World Cup 2022, and 27.74 points below it in Euro 2024. These are descriptive differences, not causal effects or a test of random missingness. Unknown deliveries also have relatively low matching rates (34.09% and 35.42%).

## Exclusions

| Setup reason | World Cup | Euro | Total |
| --- | ---: | ---: | ---: |
| no_360_frame | 269 | 222 | 491 |
| low_visibility | 0 | 1 | 1 |
| no_360_file | 0 | 0 | 0 |
| invalid_frame | 0 | 0 | 0 |
| no_corner_location | 0 | 0 | 0 |
| invalid_corner_location | 0 | 0 | 0 |
| too_few_visible_players | 0 | 0 | 0 |
| Total excluded | 269 | 223 | 492 |

The single ineligible matched frame is match `3930168`, corner `6580d401-661a-426a-bbe0-824678c256b6` (Euro, unknown delivery). It has 19 visible players but box coverage 0.2649, so the current pipeline excludes it as `low_visibility`. It remains a matching frame for coverage purposes. `exclusions.csv` stores observed nonzero exclusion counts; zeros are shown here for completeness. Hypothetical file-level failures have their own reasons in the profiler and are covered by tests.

## Interpretation and limitations

World Cup direct shots number only two and Euro direct shots only four. Their apparent 100% and 50% matching rates are unstable descriptions of very small groups; straight-delivery groups are also small (20 and 16). Corners are clustered within matches and teams, so these rows cannot be treated as independent Bernoulli observations for naive uncertainty tests. A formal comparison should account for match-level clustering and competition composition. No significance test or confidence interval is claimed here.

Similar rates between some categories cannot prove availability is random, and the lower short-corner rates do not identify the cause. Camera/provider selection, event recording and match context may be related to delivery type. Usable-frame conclusions apply only to the observed subset. This task profiles matching and eligibility; it does not perform predictive evaluation, revise corner classification, or supply football ground truth.

## Reproduction, outputs and provenance

Run from the repository root with a new destination. The output directory is refused if it already exists; output files are staged and published together only after profiling succeeds.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_360_delivery_coverage.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_setups.py -v
.\.venv\Scripts\python.exe -B -m src.profile_tournament_360 `
    --corners outputs/wc2022-euro2024-corners/corner_summary.csv `
    --coverage-manifest data/ingested/wc2022-euro2024/coverage_manifest.json `
    --frames-dir data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/three-sixty `
    --output outputs/tournament-360-delivery-coverage
```

Eight focused tests passed, covering cross-match isolation, missing versus unmatched files, corrupt JSON, duplicate UUIDs, hash mismatches, setup exclusion reasons, zero denominators/all-six-category output, reconciliation differences, duplicate corners, and existing-destination refusal. All 30 existing setup tests also passed. Invented fixtures do not replace the independent manual audit.

New local outputs in `outputs/tournament-360-delivery-coverage/`:

- `per_corner.csv`: all original corner fields plus matching/eligibility/file-status diagnostics.
- `by_delivery.csv`: 12 competition-category groups with counts and named percentage denominators.
- `short_comparison.csv`: short and non-short within each tournament.
- `match_files.csv`: all 115 observed file statuses, hashes, paths, and errors if any.
- `exclusions.csv`: exclusion counts by tournament and reason.
- `provenance.json`: input hashes, pinned source revision, checkout/code hashes, actual setup settings, file hashes, output hashes and per-match reconciliation.

Reconciliation failures are explicitly recorded in provenance rather than forcing totals. The supplied manifest reports 1,083 corners and 592 matches; the measured run agrees with both and has no per-match discrepancy. Source revision is `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. The checkout base is `1bc19f56b828faf50df637f5a1b8b0a77647211d`; the new uncommitted profiler is identified by its actual source hash, not claimed to be part of that commit.

```text
corner_summary.csv input SHA-256
343938466196c8ad377d05eeafd0f9726ac70d269329f4fb853e9b5ac6bec0b7
coverage_manifest.json input SHA-256
295c84ddc368f205f5ee91eb938bc088802b9d9afdd35d2b997dc260921d7720
```

Provenance includes the full defaults: k=4, min_box_coverage=0.5, min_visible_players=5, min_corners_confident=100, min_cluster_size=10, stability_threshold=0.6, seed=0. Only the existing visibility/player/geometry validation rules govern eligibility; clustering-confidence settings are not additional frame filters. Raw files remain in their pinned cache locations and must be available there (or at rebased manifest paths) to reproduce this profile.

