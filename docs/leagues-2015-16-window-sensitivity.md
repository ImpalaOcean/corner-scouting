# League 2015/2016 outcome-window sensitivity

Completed and verified on 2026-11-12. The existing batch runner produced new 10-second, 20-second, and uncapped league runs using the same local input manifest as the preserved primary 15-second run. Extraction logic, original outputs, audit samples, and reviewer judgments were not changed. No commit or push was performed.

## Scope and settings

The population is fixed at 1,517 manifest matches and 15,482 unique corner summaries from Premier League, Ligue 1, La Liga, and Serie A in season 2015/2016. Ligue 1 contributes 377 listed matches; this exercise does not make that a complete 380-match season. All variants retain the same 15-native-coordinate-unit short-ground-delivery threshold. Only the outcome time window varies.

- Input: `data/ingested/leagues-2015-16/batch_manifest.json`.
- Primary: `outputs/leagues-2015-16-corners/` (existing 15-second run, not rerun).
- New outputs: `outputs/leagues-2015-16-window-10/`, `outputs/leagues-2015-16-window-20/`, and `outputs/leagues-2015-16-window-uncapped/`.
- Each run contains `corner_summary.csv`, `corner_summary.parquet`, and `run_manifest.json` under schema `corner_summary_batch_v1`.

Uncapped means `window_seconds=null` in JSON/Parquet and a blank CSV cell. It removes only the time cap. Possession changes, new restarts, explicit stoppages/non-advantage fouls, period changes, goals, explicit ball-out flags, and end of data still constrain the chain. Events exactly at a finite window limit are eligible.

## Verified attributed outcomes

| Window | Manifest matches | Corners | Attacking shots | Attacking goals | Shot-producing corners | Shot-producing corners / all corners |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 1,517 | 15,482 | 4,951 | 428 | 4,560 | 29.45% |
| 15 (primary) | 1,517 | 15,482 | 5,368 | 464 | 4,893 | 31.60% |
| 20 | 1,517 | 15,482 | 5,598 | 486 | 5,069 | 32.74% |
| uncapped | 1,517 | 15,482 | 6,033 | 517 | 5,401 | 34.89% |

Shots sum `shot_count`; goals sum `goal_count`; shot-producing corners count rows with `shot_count > 0`. The latter agrees with `led_to_shot` for every row. Multiple shots can arise from one corner. Percentages use the same 15,482-corner denominator and are rounded to two decimal places. Manifest shot and goal totals agree with the CSV totals in every setting.

These are outcomes attributed under the specified sequence rule. Changing a window changes attribution, not the underlying match. The higher counts do not measure a causal effect of corners or prove that a longer window is a more accurate definition.

## Adjacent-window changes

Each pair is matched by `(match_id, corner_event_id)`. Counts below refer to corners, not numbers of extra shots, and columns overlap.

| Transition | Any outcome changed | Shot count changed | Goal count changed | Shot-producing status changed | Shot-ID list changed | Provider xG sum changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 → 15 | 401 | 401 | 36 | 333 | 401 | 401 |
| 15 → 20 | 220 | 220 | 22 | 176 | 220 | 220 |
| 20 → uncapped | 403 | 403 | 31 | 332 | 403 | 403 |

`Any outcome changed` is the union of changes in shot count, goal count, shot-producing status, ordered shot-ID list, or provider xG sum. It excludes changes confined to chain membership or ending reason. In this corpus that union equals the corners whose shot count changes; goal-change counts are subsets, not additional corners to add.

| Transition | Stop reason changed | Ordered chain IDs changed | Shot-ID nesting violations |
| --- | ---: | ---: | ---: |
| 10 → 15 | 1,466 | 5,115 | 0 |
| 15 → 20 | 1,218 | 3,385 | 0 |
| 20 → uncapped | 6,001 | 2,654 | 0 |

Across 46,446 corner/pair comparisons, the earlier shot-ID set is always a subset of the later set. Earlier ordered shot-ID lists are also prefixes of later lists; there are zero prefix violations and no per-corner goal-count decreases. No nesting violation required source investigation.

A changed ending reason can occur without a changed chain or outcome: the first excluded event can exceed the smaller cap and satisfy a different boundary once the cap is enlarged or removed. The stop-reason change count should therefore not be read as an additional-shot count.

## Stop-reason distributions

| Stop reason | 10 seconds | 15 seconds | 20 seconds | Uncapped |
| --- | ---: | ---: | ---: | ---: |
| `time_limit` | 8,685 | 7,219 | 6,001 | 0 |
| `possession_change` | 2,849 | 3,490 | 3,946 | 5,017 |
| `ball_out` | 2,417 | 2,789 | 3,001 | 3,429 |
| `stoppage` | 1,051 | 1,273 | 1,412 | 1,768 |
| `goal` | 428 | 464 | 488 | 520 |
| `new_restart` | 52 | 247 | 634 | 4,748 |
| `period_end` | 0 | 0 | 0 | 0 |
| `end_of_data` | 0 | 0 | 0 | 0 |
| Total | 15,482 | 15,482 | 15,482 | 15,482 |

The code checks period, time, restart, possession, and explicit stoppage in that order before including an action. It then checks terminal goals and out flags. The recorded reason reflects this order. A shot without an explicit `out` flag can precede a `time_limit` label without proving the ball remained in play until the limit.

Goal-ending reasons and attacking-goal counts are distinct. For 20 seconds there are 488 goal-ending chains but 486 attributed attacking goals; uncapped has 520 versus 517. The code can stop on a goal by either team while counting only attacking-team Shot events. Those differing quantities are not a CSV/Parquet mismatch; the individual football interpretations have not been manually adjudicated here.

## Validation performed

All four settings passed the following artifact checks:

- Exactly 1,517 unique input/run manifest match IDs and 15,482 unique CSV corner keys, with identical key sets across windows and no extra/missing matches.
- Identical 35-column CSV schemas. Every per-match corner count agrees with its run manifest, and each manifest total and sum of per-match counts equals 15,482.
- No missing or whitespace-only values in `match_id`, `corner_event_id`, `team_id`, `possession_id`, `competition_id`, `competition_name`, `season_id`, `season`, `match_date`, `home_team`, `away_team`, `period`, or `timestamp`. CSV metadata agrees with the corresponding manifest metadata.
- Delivery classifications, kind, technique, height, foot, coordinates, and short threshold agree for every matched corner across windows. Comparison treats numeric `15` and `15.0` thresholds equivalently.
- Each manifest records its requested window and `short_limit=15`. Every CSV row agrees, including blank/null uncapped windows.
- Zero CSV/Parquet cell mismatches after parsing JSON-list strings, normalizing blank/null cells, and converting scalar values using the Parquet schema. All rows and columns were compared in saved order. List order and numeric zero values were preserved; floating-point comparisons used exact parsed values, not rounded display values.
- Shot-ID lists contain no duplicates, have lengths matching `shot_count`, and are subsets of their recorded chain IDs.
- All four manifests reference the same input-manifest hash, same per-match recorded event-file hashes, source revisions, and metadata. This verifies fixed recorded inputs; it is not an independent rehash of every raw event file.

The 15-second CSV/Parquet/run-manifest hashes match their pre-run values and the earlier primary validation record. Audit-sheet and reviewer-copy hashes are checked separately for preservation. No sampling or agreement calculation was performed for this task. There were no validation discrepancies.

An initial process was interrupted by the workspace transition before publishing a final run. Its incomplete staging directory was left untouched. The final destinations were confirmed absent before restarting. The successful runs were then validated as above; no existing final run was overwritten.

## Commands and revisions

Run from the corner-scouting repository root in PowerShell. All three final destinations were checked before starting; the loop stops on the first nonzero exit code.

```powershell
foreach ($window in @('10', '20', 'uncapped')) {
    $destination = "outputs/leagues-2015-16-window-$window"
    if (Test-Path -LiteralPath $destination) {
        throw "Refusing existing destination: $destination"
    }
}
foreach ($window in @('10', '20', 'uncapped')) {
    .\.venv\Scripts\python.exe -B src/run_corner_batch.py `
        --manifest data/ingested/leagues-2015-16/batch_manifest.json `
        --output "outputs/leagues-2015-16-window-$window" `
        --window $window --short-limit 15 --parquet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

These commands have now completed; repeating them against these existing destinations must refuse to overwrite them. The primary 15-second run was inspected rather than generated again.

- Recorded provider source revision, common to every match and window: `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.
- Checkout revision used for the new runs: `913e9e623ed7f2a4d8f1c89d4e246cbaa50363fd`. The older primary manifest does not independently record its original code revision.
- No extraction logic was modified. SHA-256 values for the inspected runner and modules:

```text
src/corners/extract.py  ef75162f75dd44daa70b25616a882ac9d7d26c27eb4578666888db252fa26794
src/corners/batch.py  094d18e961e34f8fed06ec7d319dbf333c838aae1bc4e47dd8d1add8e38d0885
src/run_corner_batch.py  d80341662f973a9fefdf59cff9f5095f8e0d0cd36c325525e63b1656721ca07a
```

## Input and output hashes

All values are SHA-256. Input manifest:

```text
data/ingested/leagues-2015-16/batch_manifest.json
ff5629a6d9f6524c41eb39590130b8a21ac7531f4f3fbe931a0ee5f9e357cec9
```

Run artifacts:

```text
10: outputs/leagues-2015-16-window-10/
corner_summary.csv  89d636eab7f2d101b8e02eb0427a065441d4a9a2065824c3c7925536f6072e1b
corner_summary.parquet  09d6f187e4c44d10ea6d6e147e97917beb93629739b406a324106cdd07bb124f
run_manifest.json  b794096457539d7ad1279f50c761dbd4d96dc0248006b0cd0f605d813c822f1d

15: outputs/leagues-2015-16-corners/
corner_summary.csv  425f08f3d659391ede373b77ea15da95c468b435b1a53f299f6064758bb627d8
corner_summary.parquet  891f2520d77918bfaaa37e6ebc0cb9623d67c8efe02e5c947a42d3e5c1bc42a6
run_manifest.json  510d56481fc2c57536cd0714391989c68ddbd43d714edcd38bb100afa7d4e2ae

20: outputs/leagues-2015-16-window-20/
corner_summary.csv  d93ff0e66985ae0bc02159acb28117390ac596a5c70623c752d3e79c61a0340e
corner_summary.parquet  96711517d91c7bf54d631c0b74c4c93407825090e9fcd8d6b9c2713dc7a027ed
run_manifest.json  5981117b9fd407671d9de5e47f5e61796ec58111c14e70c28eff888286282587

uncapped: outputs/leagues-2015-16-window-uncapped/
corner_summary.csv  3e036aed9bcf1037aa46dc13184abfad76c2e2a7ddb3dd22d58c4a9a8c71a356
corner_summary.parquet  5af0f3014ac04c5b3c4c0aa8d5b527454d273ce17152598e9b5741a6da001cbc
run_manifest.json  06f45be202515e4040681c1275057ad570d5ebfbd8391e9ef5cc54dca1e4b256

```

## What remains

This completes generation and artifact-level validation of the league outcome-window variants. It does not complete short-threshold sensitivity: the short threshold was held fixed at 15. Manual audit/adjudication remains separate, and existing audit samples and blank judgments were preserved.

Predictive sensitivity conclusions remain Asaad's evaluation task. He should use the fixed-input variants with the agreed prediction eligibility rules, chronological evaluation, uncertainty reporting, and team/competition breakdowns. These descriptive totals alone do not establish predictive improvement, causality, or the preferred outcome window.

