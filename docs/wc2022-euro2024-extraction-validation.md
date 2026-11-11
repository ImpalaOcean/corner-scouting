# World Cup 2022 + Euro 2024 extraction and delivery validation

Verified on 2026-11-09 by inspecting the saved local CSV and run manifest, with the extraction code as the classification reference. This documents Diego's completed extraction and descriptive delivery profiling. It does not constitute a completed manual audit or predictive evaluation. No extraction, download, or output replacement was performed for this verification.

## Purpose and dataset scope

The run covers 115 international tournament matches: all 64 World Cup 2022 matches and 51 Euro 2024 matches represented in the manifest. It contains 1,083 corner summaries, including direct shots taken from corners. The unit of analysis is one unique corner, keyed by `(match_id, corner_event_id)`, rather than one row for every subsequent action. The batch input contains provider-format event JSON and per-match metadata. This scope does not include league expansion.

## Provenance, settings, and references

| Item | Saved value or local reference |
| --- | --- |
| Source revision, common to all 115 manifest entries | `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` |
| Run schema label | `corner_summary_batch_v1` |
| Outcome window | `window_seconds: 15` |
| Short-corner distance threshold | `short_limit: 15` native provider coordinate units |
| Loader configuration | `configs/data/wc2022-euro2024.json` |
| Input manifest resolved for this run | `data/ingested/wc2022-euro2024/batch_manifest.json` |
| Input-manifest SHA-256 recorded in run manifest | `291858343eb806d3cae667660bd5d65165266ff1e073b6055ca2b324d3df7e0c` |
| Provider event files referenced by input manifest | `data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/events/<match_id>.json` |
| Summary CSV inspected | `outputs/wc2022-euro2024-corners/corner_summary.csv` |
| Run manifest inspected | `outputs/wc2022-euro2024-corners/run_manifest.json` |
| Companion output | `outputs/wc2022-euro2024-corners/corner_summary.parquet` |

The run manifest records the input-manifest hash, source revision and event-file hash for each match, normalized metadata and its hash, per-match event/corner/shot/goal counts, status, and the extraction settings. It does not store input/output path strings or the original CLI invocation. Paths above are established from the local input manifest, loader configuration, output directory, and batch-runner documentation, not invented manifest fields. Relative event paths resolve from the input manifest's directory. The source revision is a recorded provenance declaration; this check did not redownload upstream files to independently authenticate it. The local input-manifest SHA-256 matches the saved value.

Every one of the 1,083 CSV rows records `window_seconds=15` and `short_limit=15`, agreeing with the run settings. All 115 manifest match statuses are `ok`, and per-match CSV corner totals agree with the manifest. The manifest's total and the sum of its per-match corner counts both equal 1,083.

The inspected CSV has these 35 fields, consistent with `src/corners/batch.py`:

| Group | Fields |
| --- | --- |
| Identity and timing | `match_id`, `corner_event_id`, `team_id`, `team`, `taker`, `period`, `timestamp`, `minute`, `second`, `possession_id`, `corner_kind` |
| Delivery | `technique`, `foot`, `height`, `delivery_category`, `start_x`, `start_y`, `end_x`, `end_y` |
| Outcomes | `shot_count`, `goal_count`, `led_to_shot`, `provider_xg_sum` |
| Traceability | `shot_event_ids`, `chain_event_ids`, `stop_reason` |
| Settings | `window_seconds`, `short_limit` |
| Match metadata | `competition_id`, `competition_name`, `season_id`, `season`, `match_date`, `home_team`, `away_team` |

CSV event-ID lists are JSON arrays and missing values are blank. The batch code defines typed Parquet output with native lists; this document's numerical verification uses the CSV and JSON manifest, not a row-by-row Parquet comparison. This corner-summary schema is distinct from the separate event-grain `corner_events` data contract.

## Reproduction commands

The following commands, run from the repository root in PowerShell, reproduce the loader-to-extractor workflow and settings used for this run. They are recorded here, not executed during verification. The original directories already exist: do not delete or overwrite them. The batch runner intentionally rejects an existing output directory; use new loader and extraction directories for a future repeat.

```powershell
.\.venv\Scripts\python.exe -m src.data --config configs/data/wc2022-euro2024.json --parquet
.\.venv\Scripts\python.exe src/run_corner_batch.py --manifest data/ingested/wc2022-euro2024/batch_manifest.json --output outputs/wc2022-euro2024-corners --window 15 --short-limit 15 --parquet
```

The explicit window and threshold equal the defaults used by the recorded workflow. A later extraction-only repeat from the same existing input manifest must use a new destination, for example `--output outputs/wc2022-euro2024-corners-reproduction-01`, after confirming that destination does not exist. The loader configuration pins the revision and selects competition/season IDs `43/106` and `55/282`.

## Verified totals and data integrity

| Check | Independently observed result |
| --- | ---: |
| Distinct matches in CSV | 115 |
| Match entries in run manifest | 115 |
| CSV corner summaries | 1,083 |
| Manifest corner total | 1,083 |
| Missing or whitespace-only `match_date` | 0 |
| Missing or whitespace-only `competition_name` | 0 |
| Missing or whitespace-only `season` | 0 |
| Duplicate `(match_id, corner_event_id)` groups | 0 |

| Competition and season | Matches | Corner summaries |
| --- | ---: | ---: |
| FIFA World Cup 2022 | 64 | 571 |
| UEFA Euro 2024 | 51 | 512 |
| Total | 115 | 1,083 |

Completeness is not proof that every metadata value is correct. These checks establish the reported totals, field population, and key uniqueness in the saved artifacts; they do not replace independent source or sequence review.

## Verified delivery profile

Counts were grouped directly from the CSV's `delivery_category`, retaining all categories and all corner summaries, including direct corner shots.

| Delivery category | World Cup 2022 | Euro 2024 | Total |
| --- | ---: | ---: | ---: |
| `direct_shot` | 2 | 4 | 6 |
| `inswinging` | 234 | 221 | 455 |
| `outswinging` | 206 | 161 | 367 |
| `short` | 65 | 62 | 127 |
| `straight` | 20 | 16 | 36 |
| `unknown` | 44 | 48 | 92 |
| Total | 571 | 512 | 1,083 |

## Unknown-delivery findings and classification

| Scope | Unknown / all corners | Percentage | Minimum distance | Maximum distance |
| --- | ---: | ---: | ---: | ---: |
| World Cup 2022 | 44 / 571 | 7.71% | 15.08 | 37.57 |
| Euro 2024 | 48 / 512 | 9.38% | 15.01 | 40.42 |
| Combined | 92 / 1,083 | 8.49% | — | — |

Percentages use the complete competition or combined corner denominator and are rounded to two decimal places. All 92 unknown rows are passes, have exported `technique="Unknown"` and `height="Ground Pass"`, and contain all four finite start/end coordinates. None has missing coordinates. Distances were recomputed from the exported coordinates as `sqrt((end_x-start_x)^2 + (end_y-start_y)^2)` in native provider coordinate units, not metres. Unrounded minima/maxima are approximately 15.0764717358 / 37.5719310124 for World Cup and 15.0096635539 / 40.4209104301 for Euro; the table rounds only for presentation.

In `src/corners/extract.py`, `describe_corner()` classifies a pass as short only when it is a Ground Pass with finite coordinates and Euclidean distance **at most** the configured threshold. Otherwise it recognizes only Inswinging, Outswinging, or Straight as named techniques; shots taken directly from corners receive `direct_shot`. These 92 ground passes all exceed the primary 15-unit threshold and have no recognized exported technique. They therefore remain `unknown` under the current rules. They are not evidence of missing coordinate data, nor should longer ground passes be silently relabelled short.

The export uses `delivery.get("technique", {}).get("name", "Unknown")`. Thus exported `"Unknown"` can be the fallback for a missing technique object or missing name, or a literal raw name. Exported `"Unknown"` alone is **not proof that the provider field was absent**. This verification did not inspect all 92 raw provider records to determine which case applies. No raw-field absence rate is claimed.

## Interpretation and analysis handoff

Retain unknown deliveries in descriptive totals and outcome analysis: they are valid extracted corner records with usable geometry, not automatically invalid observations. Excluding them would change the denominators above and could distort team or competition comparisons.

Exclusion of unknown delivery labels from **delivery prediction scoring** is the analysis module's documented policy as stated for this handoff, not a result verified by this extraction run. It must not be interpreted as exclusion from extraction or from general outcome analysis. No prediction scores, model inputs, or scoring execution were inspected here. The available local `src/analysis/README.md` describes analysis responsibilities but does not spell out this exclusion policy; a versioned analysis-policy citation remains to be supplied by that workstream before publication.

## Remaining validation and discrepancies

- **Independent 100-corner audit with Asaad: pending.** A proposed sample/protocol is preparation, not completed independent judgments or measured agreement. Keep the off-target-without-`out` boundary interpretation open for agreement rather than silently revising the rule.
- **Corpus-wide window sensitivity: pending.** Compare 10, 15, 20 seconds and uncapped sequences on fixed inputs. Earlier single-match smoke checks do not complete this comparison.
- **Short-threshold sensitivity: pending.** Compare the primary 15-unit definition against agreed alternatives, recording settings separately; the unknown distances near 15 illustrate why this matters.
- **League expansion: pending.** This run covers two international tournaments only.

No discrepancy was found between the reported numerical values in the validation request and the inspected local files. All category counts, percentages at the stated precision, coordinate-completeness findings, and rounded distance ranges agree. Evidence limits are explicit above: no raw-technique absence claim, independent scoring-policy verification, formal audit completion, or sensitivity result is implied.

No `AGENTS.md` was found in the repository, its parent directories, or the repository documentation tree when checking guidance. Relevant code and docs inspected were `src/corners/extract.py`, `src/corners/batch.py`, `src/corners/README.md`, `src/corners/BATCH.md`, `docs/corner-extraction-methods.md`, `docs/data-coverage.md`, and `src/analysis/README.md`.

For artifact identification, SHA-256 values at inspection were:

```text
corner_summary.csv  343938466196c8ad377d05eeafd0f9726ac70d269329f4fb853e9b5ac6bec0b7
run_manifest.json   592d9803844e1394a8783e69293a65661d9b2a6eaeae7117728e16badba17141
```

Only this documentation file was created for this task. Saved extraction artifacts, extraction logic, teammate modules, and private audit notes were not modified. No commit or push was performed.
