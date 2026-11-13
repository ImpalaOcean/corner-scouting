# Four-league 2015/2016 extraction validation

Verified on 2026-11-12 using the existing local CSV, Parquet, extraction run manifest, ingestion coverage manifest, and league configuration. The extraction code inspected was `src/corners/extract.py` and `src/corners/batch.py`. This is a read-only validation of Diego's completed extraction and descriptive delivery profile. No extraction or download was rerun; no source code, existing output, or private audit judgment was changed.

## Scope and provenance

The saved run contains **1,517 processed matches and 15,482 corner summaries**, all for season `2015/2016` (season ID 27). It covers Premier League, Ligue 1, La Liga, and Serie A. One summary represents a unique corner identified by a provider Corner-type pass or direct corner shot. The key is `(match_id, corner_event_id)`.

| League | Competition ID | Listed matches | Processed matches | Corner summaries |
| --- | ---: | ---: | ---: | ---: |
| Premier League | 2 | 380 | 380 | 4,108 |
| Ligue 1 | 7 | 377 | 377 | 3,591 |
| La Liga | 11 | 380 | 380 | 3,842 |
| Serie A | 12 | 380 | 380 | 3,941 |
| Total | — | 1,517 | 1,517 | 15,482 |

Ligue 1 has **377 listed matches, not a complete 380-match season**. Both `available_matches` and `selected_matches` are 377 in the coverage manifest. Its `status=ok` and the overall `complete=true` mean that the selected/listed inputs were processed; they do not establish full scheduled-season coverage. The inspected artifacts do not establish why three fixtures are absent from the pinned listing.

| Item | Recorded value or local reference |
| --- | --- |
| Source repository | `https://github.com/hudl/open-data` |
| Source revision | `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` |
| Coverage schema | `data_coverage_v1` |
| Extraction schema | `corner_summary_batch_v1` |
| Outcome window | `window_seconds=15` |
| Short-delivery threshold | `short_limit=15.0` native provider coordinate units |
| Loader configuration | `configs/data/leagues-2015-16.json` |
| Coverage manifest | `data/ingested/leagues-2015-16/coverage_manifest.json` |
| Extraction input manifest | `data/ingested/leagues-2015-16/batch_manifest.json` |
| Summary outputs | `outputs/leagues-2015-16-corners/corner_summary.csv` and `corner_summary.parquet` |
| Extraction run manifest | `outputs/leagues-2015-16-corners/run_manifest.json` |

The configuration and coverage settings agree on the four competition/season selections, pinned revision, and `download_360=false`. Every extraction manifest match records the same source revision. The input manifest references provider event files under `data/raw/<revision>/data/events/<match_id>.json`; relative paths resolve from the manifest's directory. The extraction manifest identifies inputs through its manifest hash and per-match event hashes, rather than storing the original CLI invocation or all input/output path strings.

The coverage manifest reports 5,321,459 events, 1,517 selected and usable matches, and 15,482 corners. Its match-ID set matches the extraction manifest exactly. All 1,517 extraction statuses are `ok`. Coverage and extraction per-match corner counts and recorded event-file hashes agree. The input manifest's actual SHA-256 matches the extraction manifest's recorded `manifest_sha256`. This inspection did not independently rehash all raw event files or contact upstream to authenticate the declared revision.

## CSV/Parquet and integrity checks

Both summary formats contain 15,482 rows and the same 35 named columns in the same order. Every row and every column was compared in saved order using the Parquet schema to normalize CSV values: blank CSV cells and Parquet nulls become `None`; JSON strings in `shot_event_ids` and `chain_event_ids` become native lists; integer, floating-point, and boolean strings become their corresponding typed values. List order was preserved, numeric zeros were not treated as null, and floating-point values were compared exactly after conversion, without a rounding tolerance. **Zero cell-value mismatches** were found.

The Parquet schema uses `int64` identifiers/counts, `double` numeric coordinates/settings/xG, a boolean `led_to_shot`, strings for dates and text, and `list<string>` for the two event-ID fields. Null normalization was implemented for all fields; the four coordinate columns and both list columns have zero blank CSV cells in this corpus.

| Check | Verified result |
| --- | ---: |
| Distinct CSV match IDs | 1,517 |
| Extraction manifest match entries | 1,517 |
| CSV summaries / Parquet rows / manifest total | 15,482 / 15,482 / 15,482 |
| Sum of per-match manifest corner counts | 15,482 |
| Per-match CSV corner-count discrepancies | 0 |
| CSV matches absent from run manifest | 0 |
| Duplicate `(match_id, corner_event_id)` key groups | 0 |
| CSV/Parquet cell mismatches | 0 |
| Rows with match metadata differing from run manifest | 0 |
| Rows with settings other than 15-second window and 15-unit short limit | 0 |
| `led_to_shot` inconsistent with `shot_count > 0` | 0 |

Required identifiers and metadata were checked explicitly for empty or whitespace-only cells: `match_id`, `corner_event_id`, `team_id`, `possession_id`, `competition_id`, `season_id`, `competition_name`, `season`, `match_date`, `home_team`, and `away_team`. All have **zero missing values**. The contextual fields `period` and `timestamp` also have zero missing values. All rows use season `2015/2016`; all exported metadata values match the run manifest. Completeness and manifest agreement do not independently prove that every raw provider label or metadata value is correct.

## Delivery profile

Counts below are computed from all exported `delivery_category` values, including direct corner shots and unknowns. Unknown percentages use the full league corner count as denominator and are rounded to two decimal places.

| Delivery category | Premier League | Ligue 1 | La Liga | Serie A | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `direct_shot` | 1 | 3 | 1 | 2 | 7 |
| `inswinging` | 1,625 | 1,773 | 1,347 | 1,346 | 6,091 |
| `outswinging` | 1,409 | 1,259 | 1,559 | 1,568 | 5,795 |
| `short` | 343 | 204 | 409 | 535 | 1,491 |
| `straight` | 403 | 114 | 193 | 171 | 881 |
| `unknown` | 327 | 238 | 333 | 319 | 1,217 |
| Total | 4,108 | 3,591 | 3,842 | 3,941 | 15,482 |
| Unknown percentage | 7.96% | 6.63% | 8.67% | 8.09% | 7.86% |

Under the inspected code, a short corner is a ground pass with finite start/end coordinates and Euclidean distance at most 15 native coordinate units. Short classification takes precedence over technique. Other passes use recognized Inswinging, Outswinging, or Straight techniques; unmatched passes remain unknown, and direct corner shots are `direct_shot`. Unknown records remain in the descriptive totals. Exported `technique="Unknown"` can be a fallback for missing nested data or a literal raw value; it alone does not establish raw-provider field absence. The tournament-specific findings about unknown ground-pass distances have not been assumed to hold for these league unknowns.

## Shots, goals, and shot-producing corners

| League | Attributed attacking shots | Attributed attacking goals | Corners producing at least one shot |
| --- | ---: | ---: | ---: |
| Premier League | 1,463 | 130 | 1,304 |
| Ligue 1 | 1,222 | 112 | 1,117 |
| La Liga | 1,358 | 115 | 1,245 |
| Serie A | 1,325 | 107 | 1,227 |
| Total | **5,368** | **464** | **4,893** |

Shots are the sum of `shot_count`; goals are the sum of `goal_count`; shot-producing corners count rows with `shot_count > 0`, independently checked against `led_to_shot`. A corner can produce multiple shots, so 5,368 shots must not be presented as 5,368 shot-producing corners. Manifest shot and goal totals also sum to 5,368 and 464. These are provider-event outcomes attributed by the current sequence rules, not manually adjudicated causal effects.

## Sequence ending reasons

| `stop_reason` | Corners |
| --- | ---: |
| `time_limit` | 7,219 |
| `possession_change` | 3,490 |
| `ball_out` | 2,789 |
| `stoppage` | 1,273 |
| `goal` | 464 |
| `new_restart` | 247 |
| `period_end` | 0 |
| `end_of_data` | 0 |
| Total | 15,482 |

Sequence membership uses provider possession IDs, event order, and the window alongside explicit restarts/stoppages. The batch runner orders each match by period, timestamp, and provider index. The extractor checks period, time limit, restart, possession, then stoppage; eligible terminal goal/ball-out actions are included before closing. Thus `stop_reason` describes the first implemented boundary condition encountered. An off-target shot without an explicit `out` flag does not prove that play continued until 15 seconds merely because the later recorded reason is `time_limit`. Goal-ending reasons and attacking-goal counts are separate concepts even though their totals coincide in this run; a goal by either team can close a sequence, while attributed shots/goals count only the attacking team.

## StatsBomb 360 interpretation

The configuration and coverage manifest both specify `download_360=false`. All 1,517 coverage entries have `frames_status="not_requested"`, and the coverage total is zero corners with matching 360 frames. This is the expected result when frame downloads are disabled, **not a measured 0% provider availability rate**. No conclusion about league-wide 360 availability or setup-classification eligibility can be drawn from this count.

## Reproduction commands

Commands are provided for reproducibility only; they were not run during this validation. Run from the repository root in PowerShell with the configured dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m src.data --config configs/data/leagues-2015-16.json --parquet
.\.venv\Scripts\python.exe src/run_corner_batch.py --manifest data/ingested/leagues-2015-16/batch_manifest.json --output outputs/leagues-2015-16-corners --window 15 --short-limit 15 --parquet
```

These paths and explicit settings reproduce the saved workflow, not a CLI command string embedded in the manifest. Existing output directories are protected by the runners. Do not delete or overwrite the saved run to repeat the commands: select fresh ingestion/extraction destinations and update the batch-manifest path accordingly. An extraction-only repeat from the existing pinned input manifest can use a new `--output` directory with the same 15/15 settings. The configured source revision, not current upstream master, is the relevant data reference.

## Artifact hashes

SHA-256 values computed from the existing local artifacts during this check:

```text
outputs/leagues-2015-16-corners/corner_summary.csv
425f08f3d659391ede373b77ea15da95c468b435b1a53f299f6064758bb627d8

outputs/leagues-2015-16-corners/corner_summary.parquet
891f2520d77918bfaaa37e6ebc0cb9623d67c8efe02e5c947a42d3e5c1bc42a6

outputs/leagues-2015-16-corners/run_manifest.json
510d56481fc2c57536cd0714391989c68ddbd43d714edcd38bb100afa7d4e2ae

data/ingested/leagues-2015-16/coverage_manifest.json
29d3072a74efbf775b69d85c7ebeab3db027a83ae9ca1e7d9132352bc6132fb6

configs/data/leagues-2015-16.json
5161fe9ebc30d8bcc2c68e586d2b98cf06b98f722156aaf2261ed931276fa132

data/ingested/leagues-2015-16/batch_manifest.json
ff5629a6d9f6524c41eb39590130b8a21ac7531f4f3fbe931a0ee5f9e357cec9
```

Inspected code hashes, recorded to distinguish the present implementation from any later revision; they are not proof that the run originally executed this exact code:

```text
src/corners/extract.py
ef75162f75dd44daa70b25616a882ac9d7d26c27eb4578666888db252fa26794

src/corners/batch.py
094d18e961e34f8fed06ec7d319dbf333c838aae1bc4e47dd8d1add8e38d0885
```

## Discrepancies, evidence limits, and pending validation

No discrepancy was found in the requested 1,517-match total, 15,482-corner total, four league corner counts, metadata completeness, key uniqueness, per-match corner counts, settings, or normalized CSV/Parquet agreement. The qualification is coverage: Ligue 1 has only 377 listed matches, so this is not four complete 380-match seasons. Missing scheduled-fixture explanations are not established by the inspected artifacts.

The **independent manual audit remains pending**; no audit judgments or accuracy estimates are supplied here. **Prediction eligibility and prediction results remain pending** and cannot be inferred from complete metadata or extracted counts. **League window and short-threshold sensitivity comparisons remain pending**; this document validates only the primary 15-second/15-unit run. Tournament sensitivity runs do not complete league sensitivity validation. The open physical-boundary interpretation should be agreed with Asaad before adjudication or any rule revision.

This corpus contains 15,482 corners. It must not be described as meeting a **“tens of thousands” corner requirement**; no such requirement is established as satisfied by this run. Event, match, shot, and corner counts are distinct quantities.

Only this new documentation file was created for this task. Existing extraction outputs and code, teammate modules, and private audit notes were preserved. No commit or push was performed.
