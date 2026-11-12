# World Cup 2022 and Euro 2024 extraction run

Inspected on 2026-11-09. The existing run is preserved at `outputs/wc2022-euro2024-corners/`; no extraction was rerun or output overwritten for this check. It contains `corner_summary.csv`, `corner_summary.parquet`, and `run_manifest.json`. Source-file locations and optional match metadata come from `data/ingested/wc2022-euro2024/batch_manifest.json`.

## Recorded results

| Competition | Matches | Corner summaries | Attributed attacking shots | Attributed goals |
| --- | ---: | ---: | ---: | ---: |
| FIFA World Cup 2022 | 64 | 571 | 195 | 14 |
| UEFA Euro 2024 | 51 | 512 | 195 | 12 |
| Total | 115 | 1,083 | 390 | 26 |

The manifest records 422,561 input events. There are 356 corner summaries with at least one attacking shot; multiple shots can belong to a single corner. These figures are extraction outputs, not manually validated results or estimates of extraction accuracy.

The run uses a 15-second outcome window and a 15-unit short-ground-delivery threshold. Possession, period, restart, stoppage, goal, and explicit ball-out boundaries also apply. The source revision for the inputs is `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. The input manifest SHA-256 is `291858343eb806d3cae667660bd5d65165266ff1e073b6055ca2b324d3df7e0c`.

## Read-only consistency checks

The CSV has 1,083 unique `(match_id, corner_event_id)` keys. Its per-match corner, shot, and goal totals agree with the run manifest. All 115 source event files exist and their SHA-256 hashes agree with the recorded input hashes; the input manifest hash also matches. Exported metadata agrees with both the saved run metadata and the input manifest. No CSV rows are missing competition name, season, or match date. This checks internal consistency with pinned inputs, not a new independent review of every provider metadata record.

Each CSV chain starts with its corner ID and contains no duplicate IDs. Shot-ID list lengths match shot counts, and every attributed shot ID appears in its chain. The applied window and short threshold are consistent across all rows. These structural checks do not independently establish that every included event belongs to the intended football sequence. The Parquet artifact is present and its hash is recorded; row-by-row CSV/Parquet equivalence was not checked in this preparation step. No new test-suite run was needed for these documentation and audit-packet changes; the earlier 37-test integration result remains a previously reported checkpoint.

| Recorded ending reason | Corners |
| --- | ---: |
| time_limit | 521 |
| ball_out | 224 |
| possession_change | 186 |
| stoppage | 108 |
| goal | 27 |
| new_restart | 17 |

There are 27 sequences ending with reason `goal`, but 26 attributed attacking goals. Match `3938639`, corner `9076d6af-e8fc-4ba3-a719-c32b77c9b201` (Georgia), has `stop_reason=goal` and zero attacking shots/goals. The function can stop on a goal by either team but counts only attacking-team shots. Flag this record for a separate diagnostic source check; its football interpretation has not been independently established here, and it must not be silently added to or substituted into the probability sample.

## Audit preparation and limits

A proposed 100-corner packet has been saved separately under `data/audit/wc2022-euro2024-proposed-100/`. It spans 63 matches, with 50 corners per competition selected without reference to predicted outcomes. The selected outputs include 38 corners with shots and one with a goal; this is not a dedicated rare-goal validation sample. The packet records source paths, revisions, file hashes, run hashes, and an extraction-module hash. See [the proposed audit protocol](corner-audit-protocol.md).

The earlier off-target issue remains unresolved: without an explicit `out` flag, `time_limit` can be recorded at the next event without proving that play continued until the cap. Reason priority and any proposed physical-boundary interpretation must be agreed with Asaad before independent review. The audit has not started, agreement has not been received, and no judgments or accuracy statistics have been produced. Extraction rules remain unchanged.
