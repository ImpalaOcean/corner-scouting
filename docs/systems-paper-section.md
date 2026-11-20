# Systems and reproducibility

We implemented the agreed corner rules independently in DuckDB SQL and compared them with the existing Python reference. Both implementations process local provider JSON match by match and export the 35-column corner-summary interface. SQL common-table expressions order events, identify corner starters, classify deliveries, locate sequence boundaries and aggregate ordered event IDs and attacking outcomes. Boundary priority and terminal-action inclusion follow the reference exactly; duplicate UUIDs are handled within each chain, and possession comparisons explicitly account for nulls. No Python extraction labels or chain decisions are supplied to SQL.

For the configured World Cup 2022/Euro 2024 and four 2015/16 league seasons, we rebuilt input coverage from provider revision `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. All 1,632 listed matches were usable, yielding 16,565 corners. Ligue 1 still has 377 listed fixtures; processing the catalog does not resolve its three-match schedule gap. We preserve per-match raw-event hashes, metadata, extraction settings, code hashes and output receipts. Each comparison matches `(match_id, corner_event_id)` and checks all fields after typed normalization. Counts, keys, categories, metadata and ordered lists require exact agreement; provider xG sums permit absolute error at most `1e-12`.

Reproduction used a separate, clean checkout of the merged implementation at commit `1ac3c3f`, a separately installed Python environment and the verified pinned raw cache. Both full primary pipelines included Parquet export and 1,000-draw analysis; the tournament run also included setups. We checked captured source hashes and metadata, parsed output values, file hashes, analysis eligibility/settings and setup results. We separately generated the existing cutoff-safe Aston Villa-Arsenal dossier. Reusing the pinned cache is an offline workflow reproduction, not an independent second download or a cold-cache timing test.

The timing protocol uses one untimed warmup and five measured repetitions. Extraction timing covers a fresh local batch CLI process, including startup, loading/hashing, extraction, provenance and CSV/Parquet export. Python/SQL order alternates, and each pair is compared outside the timing interval. SQL uses one thread. Downloading, ingestion and downstream analysis are excluded. This measures the shipped batch workflows, including their differing overhead, rather than isolated SQL query time. Cache state is not flushed or guaranteed, and background desktop/OneDrive activity is not isolated.

Dossier selection and build are measured separately for fixture 3754117, Aston Villa-Arsenal on December 13, 2015. Build is the principal dossier measurement and includes plan/source/code verification, CSV loading, strict historical filtering, eligibility and statistics, past-only alpha/beta selection and refitting, 1,000-draw intervals, rendering, exports and final hashes. It excludes upstream data downloading, ingestion and corner extraction. Rendering-only is optional and not measured separately. We require identical analytical dossier JSON across repetitions and report mean, median, sample SD and range with hardware/software conditions.

Implementation agreement checks consistency with provider events and specified rules; it is not independent video ground truth or the separate human audit. Performance measurements describe one desktop and the tested data sizes. They do not establish universal speed advantages, and dossier timing does not assess scouting usefulness or predictive accuracy. The retrospective tournament clusters remain excluded from prematch fitting.

## Measured results

All eight corpus/window comparisons agreed on all 35 fields under the predefined tolerance, with no missing/extra keys or provenance differences. Primary outputs were byte-identical between development and the separate clean checkout. The older league CSV hash was reconciled through scalar formatting and five xG rounding differences no larger than 2.22e-16, without changing extraction rules.

| Corpus | Implementation | Mean +/- sample SD (s) | Median (s) | Min-max (s) |
|---|---|---:|---:|---:|
| tournament | python | 4.414 +/- 0.061 | 4.437 | 4.337-4.474 |
| tournament | sql | 23.480 +/- 0.249 | 23.471 | 23.163-23.789 |
| league | python | 71.487 +/- 0.579 | 71.808 | 70.645-72.014 |
| league | sql | 326.720 +/- 2.195 | 326.863 | 323.744-329.872 |

Across five measured runs, SQL/Python mean runtime ratios were 5.32 and 4.57 for tournaments and leagues, respectively: the prototype was slower in this end-to-end batch scope.

| Stage | Mean +/- sample SD (s) | Median (s) | Min-max (s) |
|---|---:|---:|---:|
| selection | 0.615 +/- 0.012 | 0.613 | 0.601-0.632 |
| build | 0.452 +/- 0.005 | 0.453 | 0.447-0.459 |

Dossier build is the main measurement. Full statistics, raw repetitions, fingerprints, exact commands and limitations are in `docs/systems-results.md` and `docs/tables/systems/`. This text reports generation cost and implementation consistency; reader usefulness and rolling predictive evaluation are separate team workstreams.
