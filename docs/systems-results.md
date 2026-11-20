# Systems validation, reproduction and benchmark results

Owner: Mohammed Hassan. Executed November 20, 2026, for the November 27 handoff.

## Summary

All 16,565 configured corners agree between the merged Python reference and DuckDB implementation across the four outcome windows. A separate clean checkout reproduced both full primary pipelines and the cutoff-safe dossier. Five measured extraction pairs per corpus and five measured dossier selection/build repetitions completed after warmup. The SQL prototype is slower than Python in this operational batch measurement; no speedup is claimed.

## Versions and input identity

- Agreed merged implementation: `1ac3c3ffcdd16af67c5961b7dd0a71c5d9e097d3` (PRs #25/#26 integrated).
- Experiment driver: committed as `5ed6bf2`; repeated measurements recorded checkout `24f08618d9d4e728a5cdd2ca22b4e82beff20bb2` (same source plus input-fingerprint tables).
- Provider revision: `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.
- Python 3.11.9, DuckDB 1.4.3, pyarrow 23.0.1. Separate environments installed the pinned dependencies.
- AMD Ryzen 7 7700X, 8 physical cores / 16 logical processors; OS-reported RAM 16,901,890,048 bytes (15.74 GiB). Python reports OS as `Windows-10-10.0.26300-SP0`.
- SQL thread count 1. Python uses its standard single-process batch implementation. Runs were not CPU-affinity/frequency isolated; the workspace is under OneDrive and background synchronization was not disabled or measured.

The pinned corpus was rebuilt locally: 115 tournament matches / 422,561 events / 1,083 corners and 1,517 league matches / 5,321,459 events / 15,482 corners. Every selected match was usable. The league catalogs still contain only 377 Ligue 1 fixtures; this does not establish the reason for the three missing scheduled matches. League frames were not requested, not measured unavailable. The download preparation receipt covers 1,747 event/360 files and 5,787,291,527 bytes; preparation/download time is outside all benchmark intervals.

Per-competition counts are in [coverage.csv](tables/systems/coverage.csv). All 1,632 event-file hashes and metadata fingerprints are in [input-events.csv](tables/systems/input-events.csv). Tournament comparisons began before the experiment driver was committed; the unchanged source-content hashes identify that executed code. Later measurements used a clean working tree at the recorded commit.

## Full Python-SQL comparisons

| Corpus | Window | Matches | Corners | Shots | Goals | Missing / extra | Field mismatches |
|---|---|---:|---:|---:|---:|---|---:|
| tournament | 10 | 115 | 1,083 | 353 | 24 | 0 / 0 | 0 |
| tournament | 15 | 115 | 1,083 | 390 | 26 | 0 / 0 | 0 |
| tournament | 20 | 115 | 1,083 | 399 | 27 | 0 / 0 | 0 |
| tournament | uncapped | 115 | 1,083 | 446 | 31 | 0 / 0 | 0 |
| league | 10 | 1,517 | 15,482 | 4,951 | 428 | 0 / 0 | 0 |
| league | 15 | 1,517 | 15,482 | 5,368 | 464 | 0 / 0 | 0 |
| league | 20 | 1,517 | 15,482 | 5,598 | 486 | 0 / 0 | 0 |
| league | uncapped | 1,517 | 15,482 | 6,033 | 517 | 0 / 0 | 0 |

These are 66,260 corner/configuration comparisons on 16,565 distinct corners, not 66,260 distinct corners. Short limit is fixed at 15 native coordinate units throughout. All 35 fields are compared: exact typed equality for keys, counts, settings, categories, coordinates, metadata and ordered ID lists; absolute tolerance `1e-12` only for provider xG sums. Every run also has zero recorded provenance differences. These are extraction comparisons; no new predictive protocol or football definition was introduced.

Raw per-window CSVs, reports, input/code fingerprints and differences files are in the evidence bundle. [comparisons.csv](tables/systems/comparisons.csv) is the compact result table.

## Clean-checkout reproduction

A separate local clone, `../corner-scouting-clean-nov27`, was detached at `1ac3c3f`, given a new virtual environment and tested: **224 tests passed, no skips**. The handoff branch's experiment tests bring its suite to **230 passing tests, no skips**. The source checkout stayed clean before and after both full workflows and dossier generation; no source overlays or developer packages were copied.

Each full reproduction used verified offline raw-cache files, Parquet and 1,000-draw analysis. Tournament setups reproduced 591 usable frames, clusters 228/163/115/85 and ARI 0.864. League analysis reproduced 80 eligible/scored teams, alpha 50, beta 200, 3,154 test corners and 2,916 known deliveries. Tournament predictive targets remain unavailable because no team meets training eligibility. The dossier reproduced fixture 3754117 (Aston Villa-Arsenal, December 13, 2015), excluding the entire target date; its analytical JSON matches every timed build exactly.

For both corpora, clean and development primary Python tables are byte-identical, and the corresponding SQL tables are byte-identical. All captured per-match raw hashes, metadata, source revisions, counts and settings agree. Input-manifest byte hashes differ because the path strings to the shared raw cache differ:

| Corpus | Main input-manifest SHA-256 | Clean input-manifest SHA-256 |
|---|---|---|
| tournament | `291858343eb806d3cae667660bd5d65165266ff1e073b6055ca2b324d3df7e0c` | `b988fbb8ae6eb1c9a88b4842cfa52fcaaa9ad3bc8e5878f76510b37df1a60f1a` |
| league | `ff5629a6d9f6524c41eb39590130b8a21ac7531f4f3fbe931a0ee5f9e357cec9` | `a4edd2f02b979db384ef5e7de08e07740458f7626fb53cca3138fa2fbf6b154e` |

The standalone copied-table comparisons have an explicit missing-sibling-manifest warning. Their source provenance is checked separately by full equality of captured per-match source records in `reproduction-proof/report.json`; the warning is not silently suppressed. [clean-reproduction.csv](tables/systems/clean-reproduction.csv) records the outcomes. Reusing a verified cache is an offline workflow reproduction, not an independent second download or cold-cache benchmark.

## Reconciliation with the published league CSV hash

The current primary Python league CSV SHA-256 is `1f155755b3413b163ff5d52ae598e1d4d6dcf668607e05914c8f50df2ffb69ec`; the older published hash is `425f08f3d659391ede373b77ea15da95c468b435b1a53f299f6064758bb627d8`.

We reconstructed the exact published hash in a diagnostic copy by writing the numeric short limit as `15.0` rather than `15` and replacing five multi-shot xG sums with accurately rounded `math.fsum` values. The maximum numeric difference is 2.220446049250313e-16. Strict comparison reports exactly five `provider_xg_sum` differences; comparison with the predefined tolerance reports agreement. The five differences are in [xg-rounding.csv](tables/systems/xg-rounding.csv). This identifies the actual representation/numeric differences; the original software version causing them is not established. The saved primary tables, reference implementation and extraction definitions were preserved. The current tournament Python CSV already matches its published `34393846...c6bec0b7` hash exactly.

## Repeated extraction timings

One untimed warmup pair, followed by five measured pairs per corpus. Implementation order alternates. Both fresh-process batch CLIs read/hash the same event files and export CSV plus Parquet with 15/15 settings. Startup/imports, loading, extraction, provenance and output writing are included. Download, ingestion, pair comparison and downstream analysis are excluded. Every warmup/measured pair passes field comparison outside timing. OS caches were not flushed or guaranteed resident; these are warm-cache-intent desktop measurements.

| Corpus | Implementation | Mean +/- sample SD (s) | Median (s) | Min-max (s) |
|---|---|---:|---:|---:|
| tournament | python | 4.414 +/- 0.061 | 4.437 | 4.337-4.474 |
| tournament | sql | 23.480 +/- 0.249 | 23.471 | 23.163-23.789 |
| league | python | 71.487 +/- 0.579 | 71.808 | 70.645-72.014 |
| league | sql | 326.720 +/- 2.195 | 326.863 | 323.744-329.872 |

Mean SQL/Python runtime ratios are 5.319 for tournaments and 4.570 for leagues. Thus SQL is slower in the tested shipped workflow. This is not an isolated-query comparison or a universal engine-performance claim; wrapper/provenance overhead and output representation are included. Raw repetitions and aggregates are in [extraction-repetitions.csv](tables/systems/extraction-repetitions.csv) and [extraction-benchmarks.csv](tables/systems/extraction-benchmarks.csv).

## Dossier timing

Uses Mohamed's November 17 timing proposal and the existing fixture 3754117. One untimed warmup and five measured repetitions, always fresh selection plans/output folders, 1,000 bootstrap draws and seed 5118. Selection immediately precedes build and can warm source pages.

| Stage | Mean +/- sample SD (s) | Median (s) | Min-max (s) |
|---|---:|---:|---:|
| selection | 0.615 +/- 0.012 | 0.613 | 0.601-0.632 |
| build | 0.452 +/- 0.005 | 0.453 | 0.447-0.459 |

**Build is the main dossier measurement.** It includes CLI startup/imports, plan/code/source verification hashes, input CSV loading, strictly historical filtering, eligibility/statistics, alpha/beta selection and past-only refit, bootstrap intervals, Markdown/JSON/CSV rendering/export, output hashes and the final source rehash. Full-file loading/hashing is included for identity, while analytical quantities use only past rows. Downloading, ingestion and corner extraction are excluded. Selection separately includes metadata-only fixture choice, hashes and plan writing. Rendering-only was optional and was not measured separately.

All six analytical dossier JSON files (warmup plus measured builds) have the same hash and match the independent clean reproduction. See [dossier-benchmarks.csv](tables/systems/dossier-benchmarks.csv) and [dossier-repetitions.csv](tables/systems/dossier-repetitions.csv). These timings measure generation, not scouting usefulness or predictive accuracy.

## Reproduction commands and evidence

The fixed protocol and exact commands are in [systems-experiments.md](systems-experiments.md). Source preparation, comparisons and benchmarks each require new destinations. The completed clean commands, configs, dependency versions and logs are recorded in the bundle under `clean-checkout/clean-execution.json` and adjacent files. The clean source is the agreed merged implementation; experiment orchestration is added in this handoff.

The compact bundle has 260 files and has passed ZIP CRC plus per-entry SHA-256 verification:

- Local path: `outputs/nov27/evidence-publication/systems-evidence-2026-11-20.zip` (44,880,751 bytes).
- SHA-256: `55b0990f0fe0866edb9123ef2e35074325814b69797667af48b85c6908d0d4a8`.
- Detailed run trees: `outputs/nov27/` and `../corner-scouting-clean-nov27/outputs/nov27/`.
- Upload to the existing project Drive folder was attempted and returned HTTP 403, `insufficientParentPermissions`. The connected account cannot add files there. A folder editor must upload the verified ZIP; no hosted bundle link is claimed yet.

Small tables, input fingerprints and the artifact receipt are committed; large generated tables and raw provider data remain outside Git. The evidence index is [systems-evidence-index.csv](systems-evidence-index.csv). To regenerate tables and package completed runs:

```powershell
.\.venv\Scripts\python.exe -B scripts/build_systems_evidence.py --output outputs/nov27/new-evidence-publication
```

The publisher verifies completion, field agreement, source-content hashes and dossier reproducibility before packaging. Use a new output folder. The report/ZIP is a snapshot, not a portable raw-data cache; manifests retain their original execution paths.

## Limitations and remaining human handoff

Implementation parity is agreement with provider events and the existing rules, not independent football ground truth or completion of the human audit. The comparisons cover the agreed configured corpus and four time windows at short limit 15, not every open-data season or full-corpus short-threshold sensitivity. Timing describes one unisolated desktop with warm-cache intent, including background/OneDrive limitations. No causal, tactical-quality or universal speed claim follows. Full-tournament clusters stay retrospective and do not enter the prematch dossier.

The technical checks, repeated measurements and paper material are complete. Team review/merge and uploading the detailed ZIP through an account with folder permission remain human handoff steps.
