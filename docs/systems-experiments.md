# Corpus comparisons and benchmark protocol

Owner: Mohammed Hassan. Protocol fixed November 20, 2026, before measured benchmark runs.

Use the merged Python and SQL definitions unchanged. Run from the repository root with `src/systems/requirements.txt` installed. Every output directory must be new. An experiment writes `status.json` as running/complete/failed and retains failure evidence. Do not interpret an existing directory as success without checking status.

## Inputs

Use the existing pinned configurations:

```powershell
.\.venv\Scripts\python.exe -B -m src.data --config configs/data/wc2022-euro2024.json --output data/ingested/nov27-wc2022-euro2024 --parquet
.\.venv\Scripts\python.exe -B -m src.data --config configs/data/leagues-2015-16.json --output data/ingested/nov27-leagues-2015-16 --parquet
```

Source revision: `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. Add `--offline` to replay a complete verified cache. League 360 downloads remain disabled; this is not measured provider unavailability. The four league catalogs list 1,517 matches, including only 377 Ligue 1 matches. Expected tournament count is 115. Verify coverage manifests; do not infer complete ingestion from expected counts alone.

## All-window field comparisons

```powershell
.\.venv\Scripts\python.exe -B -m src.systems.experiments corpus --manifest data/ingested/nov27-wc2022-euro2024/batch_manifest.json --output outputs/nov27/tournament-comparisons
.\.venv\Scripts\python.exe -B -m src.systems.experiments corpus --manifest data/ingested/nov27-leagues-2015-16/batch_manifest.json --output outputs/nov27/league-comparisons
```

Each command runs 10/15/20-second and uncapped windows at short limit 15, with one SQL thread, CSV and Parquet exports, unchanged Python reference rules and all 35 CSV fields compared. xG absolute tolerance is `1e-12`; all other fields use exact typed equality. It records key differences, field differences, source/metadata/settings agreement, raw input hashes and code environment. No statistical model is refitted in these comparison runs. A discrepancy stops that corpus experiment, preserves evidence and exits nonzero.

## Repeated extraction measurement

After source preparation, other validation jobs and correctness checks finish:

```powershell
.\.venv\Scripts\python.exe -B -m src.systems.experiments extraction-benchmark --manifest data/ingested/nov27-wc2022-euro2024/batch_manifest.json --output outputs/nov27/tournament-benchmark --warmups 1 --repetitions 5 --threads 1
.\.venv\Scripts\python.exe -B -m src.systems.experiments extraction-benchmark --manifest data/ingested/nov27-leagues-2015-16/batch_manifest.json --output outputs/nov27/league-benchmark --warmups 1 --repetitions 5 --threads 1
```

The timing unit is a fresh-process local batch CLI invocation. Both implementations load/hash the same provider files, extract the same 15/15 table, and write CSV plus Parquet. Startup/imports, provenance work, JSON loading, extraction and export are included. Network download, ingestion, source-snapshot checks, pair comparison and downstream analysis are outside timing. SQL-specific provenance/connection overhead is part of its shipped CLI; this is an operational batch comparison, not a pure-query microbenchmark.

Each corpus has one untimed warmup pair and five measured pairs. Execution order alternates, including warmup. One SQL thread; Python reference is its standard single-process implementation. Each pair is verified outside timing. The OS cache is not flushed and residency is not guaranteed: these are warm-cache-intent runs after warmup, with cache conditions disclosed, not cold-disk tests. Do not intentionally run other experiment jobs concurrently with benchmarks.

Save raw repetitions, mean, median, sample SD, min/max and coefficient of variation. Interpret SQL/Python ratios as measured runtime ratios on this machine, not as proof that either implementation is universally faster. CPU model/core count, physical RAM, OS, Python/DuckDB versions and code/input hashes are recorded. Repeat on another machine if portability of performance claims is needed.

## Dossier timing

Mohamed's November 17 proposal supplies the measurement boundary: selection separately, dossier build as the main timing, rendering-only optional, and upstream downloading/ingestion/extraction excluded. Use the existing Aston Villa–Arsenal fixture dated December 13, 2015. Confirm that the metadata-only selection rule still chooses that fixture; the experiment refuses a different one.

```powershell
.\.venv\Scripts\python.exe -B -m src.systems.experiments dossier-benchmark --corners outputs/nov27/league-comparisons/w15/python/corner_summary.csv --coverage-manifest data/ingested/nov27-leagues-2015-16/coverage_manifest.json --output outputs/nov27/dossier-benchmark --warmups 1 --repetitions 5
```

Every repetition uses a new selection plan and output folder. Timing includes fresh CLI startup/imports. Selection includes metadata reads, fixture choice, source/code hashes and plan writing. Build includes plan/source/code verification, loading and historical filtering, eligibility/statistics, alpha/beta selection, past-only refit, 1,000-draw bootstrap intervals with seed 5118, Markdown/JSON/CSV rendering/export, output hashes and final source rehash. Loading/hashing of full source files is included for identity verification even though analytical filtering/fitting uses strictly past rows. Target and future match values cannot enter calculations.

Rendering-only timing is not required and is not included as a separate measurement here. The analytical `dossier.json` must have the same hash across all repetitions. Full provenance files legitimately vary in timestamps and output paths. Report that selection immediately precedes build and can warm the OS cache.

## Clean-checkout reproduction

Create a separate clone at the exact agreed merged implementation commit, install a separate virtual environment, and verify `git status --short` is empty before/after execution. Reusing a checksum-verified pinned raw cache is permitted for an offline reproduction; disclose that it is neither an independent source download nor a cold-cache performance experiment.

Generate local input configs under ignored `outputs/` with the same provider revision/selections but an absolute path to the verified cache. Run the existing `src.systems.run` CLI on each full corpus, with Parquet and 1,000-draw analysis, plus tournament setups where appropriate. Do not copy source edits or installed packages from the developer environment.

Compare parsed primary tables and path-independent per-match raw hashes/metadata/settings against the main validation run. Input-manifest byte hashes may differ because relative paths to the shared cache change; report the actual hashes and this path difference explicitly. A byte-identical output CSV is stronger evidence when observed, but must be measured rather than assumed. Keep any field differences distinct from serialization differences.

Record checkout commit, dependency versions, commands, tests, coverage, per-target analysis availability, setup eligibility and dossier behavior. These checks establish reproduction of the specified snapshot and inputs, not independent football ground truth or the separate human audit.
