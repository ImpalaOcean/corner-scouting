# SQL extraction and sample reproduction

Owner: Mohammed Hassan. First implementation: November 14, 2026.

This workflow implements the November 20 handoff: an independent DuckDB SQL extractor, a field-level Python comparison, and a sample runner. It preserves the existing Python definitions and does not modify ingestion, analysis, setup, or dossier implementations.

## Setup

Run from the repository root in PowerShell with Python 3.11:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/systems/requirements.txt
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Requirements pin DuckDB 1.4.3 and pyarrow 23.0.1. Parquet is optional at runtime; the complete dependency installation exercises its tests. No external database service is required. CSV extraction and the systems tests require DuckDB. Existing non-systems tests can still run without it; the systems tests explicitly skip if it is absent.

## Fixture run: no downloads

```powershell
.\.venv\Scripts\python.exe -B -m src.systems.run --manifest tests/fixtures/corner_batch/manifest.json --output outputs/systems-fixture --parquet --bootstrap 0
```

Expected: two manifest matches, one invented short corner producing one shot and no goals, zero field mismatches. The second match has zero corners and remains in both extraction manifests. Fixture data demonstrates software behavior, not football results.

## Real two-match sample

```powershell
.\.venv\Scripts\python.exe -B -m src.systems.run --config configs/data/sample.json --output outputs/systems-sample --parquet --bootstrap 100 --frames-dir data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/three-sixty
```

Expected: two matches, 6,671 events at ingestion, nine corners, zero Python/SQL field mismatches, and five usable setups. Analysis produces descriptive results but no eligible prediction teams. Setup results are exploratory. The sample configuration pins provider revision `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.

Ingestion downloads missing inputs to the configured cache. Once the cache is complete, add `--offline` and choose a new output destination to replay it with verified cached bytes. Relative cache/config paths follow the existing loader's repository-root convention. The systems runner overrides only the ingestion output directory, placing it within the run folder.

The default 100 bootstrap draws are a quick sample setting. Use the agreed 1,000-draw analysis setting for final experiments. SQL is single-threaded by default; `--threads N` changes its thread count and is recorded.

All destinations must be new. Existing folders are refused. A failed orchestrated run retains `run.json` with `status=failed`, the failed stage and error, plus any existing logs/comparison evidence. The CLI exits nonzero, and downstream stages do not run. A successful folder has `status=complete`; it does not imply that unrequested stages such as dossiers or benchmarks ran.

## Run layout

```text
outputs/systems-sample/
    ingestion/          # present only with --config
    python/             # reference CSV, optional Parquet, run_manifest.json
    sql/                # SQL CSV, optional Parquet, run_manifest.json
    comparison/         # comparison.json and complete differences.csv
    analysis/           # unless --skip-analysis
    setups/             # only with --frames-dir
    analysis.log
    setups.log          # only when requested
    run.json            # status, settings, timings, provenance, artifact hashes
```

The runner stages output in a sibling directory before publishing it. Relative ingestion/comparison paths survive publication. It explicitly rebases the analysis manifest's absolute input path to the published CSV and records that adjustment. Moving a completed run to a different machine can still require rebasing absolute paths in analysis metadata; recreate results from configuration for a clean reproduction.

## Standalone extraction and comparison

```powershell
.\.venv\Scripts\python.exe -B src/run_corner_batch.py --manifest data/ingested/sample/batch_manifest.json --output outputs/python-check --window 15 --short-limit 15 --parquet
.\.venv\Scripts\python.exe -B -m src.systems.extract --manifest data/ingested/sample/batch_manifest.json --output outputs/sql-check --window 15 --short-limit 15 --parquet
.\.venv\Scripts\python.exe -B -m src.systems.compare --reference outputs/python-check/corner_summary.csv --candidate outputs/sql-check/corner_summary.csv --output outputs/sql-comparison
```

Use a manifest that actually exists; the integrated `--config` command instead writes it under that run's `ingestion/`. The standalone SQL command never downloads data. It supports `--window 10`, `15`, `20`, or `uncapped`, and positive finite `--short-limit` values.

The comparison CLI exits 0 for agreement, 2 for a data/provenance mismatch, and 1 for invalid input or execution failure. `differences.csv` records every field/key difference with JSON-encoded values. `comparison.json` includes counts, up to 20 examples, source manifest evidence and code/input hashes. Missing extraction manifests are explicitly marked unverified. When present, manifest records, input-manifest hashes, settings and totals must agree; SQL output hashes are checked against saved receipts. Recorded source hashes alone do not authenticate the current raw files; the runner snapshots and rechecks those bytes.

All 35 fields are compared after typed CSV normalization. Keys, categories, counts, Booleans, metadata, settings, coordinates and ordered ID lists must agree exactly. Empty values remain null rather than zero. Only `provider_xg_sum` permits an absolute tolerance of `1e-12`, with no relative tolerance; use `--xg-abs-tolerance 0` for exact numeric equality. This tolerance does not apply to delivery classification or coordinates.

## SQL design

`src/systems/extraction.sql` operates on raw event JSON and explicit source ordinality. CTEs decode/order events, identify first qualifying corner starters, establish the first UUID occurrence as the Python anchor, select the first subsequent occurrence of each action UUID per chain, locate the earliest boundary, and aggregate included events and attacking shots. Ordering ties preserve source position.

Period, elapsed time, restart, possession and stoppage checks occur before inclusion, in reference priority. A goal/out action is included only if it passes those checks. Direct corner shots count themselves; a terminal starter closes immediately. `IS DISTINCT FROM` implements null-aware possession comparisons. Duplicate handling is chain-local, not a global UUID deduplication. Python orchestrates JSON loading/export and metadata normalization; it does not provide SQL delivery labels or chain decisions.

Inputs are the existing provider event domain: string UUIDs, integer period/index and numeric provider identifiers, structured Pass/Shot details and coordinates. Missing required ordering fields and starter possession fail. Malformed or unsupported provider structures must be investigated rather than treated as evidence that the football definitions should change.

## Validation and limitations

See `docs/systems-sample-validation.md` for the measured first-handoff results. Regression coverage includes stopping priority, exact caps and short thresholds, advantage, pressure, opponent shots/goals, terminal/direct shots, missing possession/coordinates, duplicate UUIDs, stable ordering, zero-corner matches, typed Parquet, tampering/provenance errors, mismatch exit codes and runner failure behavior.

This handoff does not establish full-league parity, speed improvement, the independent 100-corner human audit, or a completed clean-checkout reproduction of the final corpus. The scalar JSON event load and per-corner candidate joins prioritize clarity/correctness; larger-run memory and speed must be measured before optimization. Extreme floating-point coordinate/distance edge cases outside ordinary provider pitch coordinates are not a validated input domain.

## Dossier and timing handoff

The cutoff-safe dossier CLI is available through PR #24:

```powershell
.\.venv\Scripts\python.exe -B -m src.dossier select --corners ABSOLUTE_PRIMARY_CSV --coverage-manifest ABSOLUTE_LEAGUE_COVERAGE_JSON --selection NEW_SELECTION_JSON --output NEW_DOSSIER_DIRECTORY
.\.venv\Scripts\python.exe -B -m src.dossier build --selection NEW_SELECTION_JSON
```

The sample runner intentionally stops at analysis/optional setups. It does not select a fixture or generate a dossier from the undersized sample. Coordinate with Mohamed before adding dossier orchestration and decide whether timing includes selection, past-only aggregation/fitting, rendering, or all of them. The dossier must retain its cutoff and historical fitting protections; full-tournament retrospective setup clusters are not prematch inputs.

`run.json` records one execution's stage times and Python/DuckDB/OS/CPU/thread context. SQL match timing includes serializing/loading JSON, the query and fetching rows; total SQL stage time also includes connection, provenance and export. Python runs first, so its file reads can warm the OS cache before SQL. These are diagnostics, not a fair repeated benchmark or evidence of a speed gain. Final benchmarking must record physical hardware/RAM, cache conditions, thread count, repetitions, variability and identical input/output settings, with download time separate.

November 20 update: full configured-corpus comparisons, separate clean-checkout reproduction, repeated extraction benchmarks and agreed dossier timings are complete. See [systems-results.md](systems-results.md) and [systems-experiments.md](systems-experiments.md). The earlier sample limitations above describe that first handoff; current measured scope and remaining artifact-upload/review steps are recorded in the results document.
