# First SQL systems handoff: sample validation

Owner: Mohammed Hassan. Validation date: November 14, 2026.

## Scope

Implemented an independent DuckDB SQL extractor, all-field CSV comparison, and an ingestion/local-manifest sample runner on branch `feat/sql-reproducibility`, based on `origin/main` commit `f8b66b0`. These results were measured before committing the implementation; manifests record working-tree status and actual source-content hashes. No change was made to the Python reference or other members' implementations.

## Test results

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

**211 tests passed, with no failures or skips**, including **23 new systems tests**. The systems tests include 160 seeded differential sequence cases (40 generated sequences across four time-window settings), hand-checked boundary examples, comparison failures, provenance checks, Parquet round trips, incomplete-ingestion handling and output-path publication checks.

Environment: Windows, Python 3.11.9, DuckDB 1.4.3, pyarrow 23.0.1. Full output is retained locally at `outputs/systems-final-test-suite.log`; generated outputs and raw data are not committed.

## Real-data comparison

Input: the existing two-match sample manifest, `data/ingested/learning-sample/batch_manifest.json`, with provider revision `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. It contains Qatar–Ecuador (3857286) and Germany–Scotland (3930158): 6,671 events and nine distinct corners. Both extractors read the same referenced raw provider JSON and normalized match metadata.

| Window | Short limit | Matches | Corners | Attacking shots | Attacking goals | Field mismatches | Provenance differences |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10 seconds | 15 | 2 | 9 | 4 | 0 | 0 | 0 |
| 15 seconds | 15 | 2 | 9 | 5 | 0 | 0 | 0 |
| 20 seconds | 15 | 2 | 9 | 5 | 0 | 0 | 0 |
| Uncapped | 15 | 2 | 9 | 7 | 0 | 0 | 0 |
| 15 seconds | 10 | 2 | 9 | 5 | 0 | 0 | 0 |
| 15 seconds | 20 | 2 | 9 | 5 | 0 | 0 | 0 |

These are 54 corner comparisons over six configurations, **not 54 unique corners**. Every comparison checks all 35 fields, including ordered chain and shot UUID lists. Counts, keys, delivery classes, stop reasons, metadata and settings agree; xG is compared with the documented absolute tolerance `1e-12`. Missing/extra keys are zero in every run.

Local evidence lives under `outputs/systems-sample-validation/`, in `w10`, `w15`, `w20`, `wuncapped`, `short10` and `short20`. Each has `python/`, `sql/`, a runner manifest and `final-comparison/comparison.json` plus the empty-with-header `differences.csv`. The final comparisons were rerun after the provenance validation was tightened. SQL extraction logic did not change between these runs and the final comparisons.

Analysis and setups completed in each of the four time-window runs. All three descriptive team rows are below prediction eligibility; there are no scored prediction teams. The setup stage retains all nine corners, with five usable frames, four unmatched corners and exploratory clustering. This reproduces software operation on a small sample, not stable tactical findings.

## Integrated ingestion workflow

The following separate run also completed:

```powershell
.\.venv\Scripts\python.exe -B -m src.systems.run --config configs/data/sample.json --offline --output outputs/systems-ingestion-validation --parquet --frames-dir data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/three-sixty
```

It replayed the verified cache, ingested two matches, reconciled ingestion corner counts against extraction, ran Python/SQL comparison, analysis and setups, and published a complete run. Both event-file paths in the published ingestion manifest were checked after the staging directory was renamed and remained accessible. The runner also rebases analysis's recorded input to its published path.

This destination already exists. A repeat must use a new `--output` name. If the provider cache has not been populated, omit `--offline` for the first run. Fresh setup and no-download fixture commands are in `docs/reproducibility.md`.

## Content fingerprints

Final checked implementation/test files:

```text
src/systems/extraction.sql
36e0a42202fe072df48af95ab24bb61165b65189910230200006feecc561bc05
src/systems/extract.py
12c5101c737027065b6fe6b8723157cb7008ab74ceccdc7bb726c42506c13ef7
src/systems/compare.py
8d1bfbc623f9db2a9abbd916b3b42e0c860f3c9439a8c0eb141e0b72749aee38
src/systems/run.py
108509a6b9e82689f5899c4f1eae47b44565a78512f0631564bef4bc7b11d96d
tests/test_systems.py
d6a5794b92328e8e24b95e8ae8badb85b4bf80fd2eadb755fecb1f732c68881d
configs/data/sample.json
95fde14484df6eb24149189f04eb956b683966fc550b08621e7677209ca3cb67
```

Primary sample Python CSV SHA-256:

```text
3a9ead96ad4d489a2c8b57cb8dbc5e14391cc15776f45a5c87345f104c3e1bea
```

Hashes identify the tested local content; they do not imply these files were committed during execution. Output manifests contain additional input/artifact hashes, settings, code hashes and environment details.

## Remaining work and interpretation

- Complete team review and investigate discrepancies if larger inputs expose them; preserve the Python definitions unless their owner agrees otherwise.
- Run full tournament/league field comparisons. Sample agreement does not establish corpus-wide agreement.
- Reproduce the committed implementation from a separate clean checkout with the agreed inputs. The current run used an existing verified cache and working tree; it is not that final clean-checkout result.
- Agree dossier timing scope and inputs with Mohamed, then collect repeated benchmarks with physical hardware/RAM, software/thread settings and explicit cache conditions. Current stage timings are single-run diagnostics, with Python reading first; no speedup claim is made.
- Write the final systems/reproducibility methods, measured results and limitations for the paper once those experiments are complete.

The dossier dependency is available through PR #24. It is not run on this undersized sample. The separate human audit is unchanged and is not completed by automated Python/SQL agreement.
