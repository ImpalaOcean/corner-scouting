# Systems and reproducibility implementation plan

Owner: Mohammed Hassan (Mo)

Date: November 13, 2026. Reference implementation: corner-scouting commit `6a64fbdde56131077c66d245b2cb59cad60135a0`.

## Objective

Implement the agreed corner-extraction and outcome-chain rules in DuckDB SQL, compare the results automatically against the existing Python reference, and provide a reproducible workflow connecting the project modules. Coordinate measurement of dossier-generation time with Mohamed once the dossier generator is available.

The SQL implementation will reproduce the Python rules. It will not introduce new football definitions or change the reference extractor without discussion with Diego. The comparison is an implementation check against provider events, not independent football ground truth or a replacement for Diego and Asaad's manual audit.

## Deliverables and acceptance criteria

| Deliverable | Artifact | Acceptance criteria |
|---|---|---|
| Declarative extractor | Versioned SQL plus a small Python CLI for loading/configuration/export | One summary per corner, compatible with `corner_summary_batch_v1`; supports 10/15/20-second and uncapped windows plus configurable short limit |
| Automated comparison | CLI, machine-readable report, focused regression tests | Same corner keys and field-level agreement with Python; differences identify match, corner, field and values; mismatch exits nonzero |
| End-to-end workflow | Runner with sample, league-event and optional spatial modes | Executes stages in order; validates handoffs; refuses existing output destinations; records failures and provenance; handles incomplete ingestion explicitly |
| Clean-checkout reproduction | Execution guide and reproduction report | A separate clean checkout runs from documented dependencies/configuration and reproduces the agreed outputs or explicitly records blockers |
| Timing and paper material | Benchmark table, conditions, methods/results/limitations text | Actual measurements with hardware/software/input/cache conditions; dossier timing added with Mohamed when executable |

## Proposed repository organization

Proposed module layout:

```text
src/systems/
    __init__.py
    extraction.sql       # corner detection, delivery rules, boundaries, summaries
    extract.py           # DuckDB input binding and batch output
    compare.py           # typed field-level Python/SQL comparison
    run.py               # orchestration, reconciliation and provenance
    benchmark.py         # repeatable stage timing
    requirements.txt     # tested/pinned DuckDB dependency
tests/test_systems.py
docs/reproducibility.md
```

Reuse the existing manifest parser and metadata normalization where appropriate, while keeping SQL extraction independent of the Python extraction functions. Python may orchestrate and serialize; detection, classification, chain membership, stopping rules and outcome aggregation belong in SQL.

## Extraction semantics to preserve

- Input: the local provider JSON files referenced by `batch_manifest.json`, with match metadata and pinned provider revision.
- Sort by period, timestamp and provider index, preserving source order when all sorting fields tie.
- Detect Pass/Shot events with nested type Corner and deduplicate corner starter UUIDs.
- Classify direct shots first, then short ground passes with finite coordinates and Euclidean distance at most the short limit, then recognized technique, otherwise unknown.
- Default window 15 seconds; events exactly at the cap are eligible; uncapped removes only the time constraint.
- Before including an action, apply Python's priority: period change, time cap, restart, possession change, then stoppage/non-advantage foul.
- Include eligible terminal goal/out actions before closing. Count only attacking-team Shot events as attributed shots/goals. A direct corner shot counts itself.
- Preserve ordered chain/shot UUID lists, stop reason, provider xG sum and all output settings/metadata.
- Handle missing possession with explicit SQL null semantics. Do not assume SQL `NULL <> value` behaves like Python `None != value`.
- Preserve duplicate-action behavior, including the reference's use of the first occurrence of a starter UUID. Test contradictory duplicate records explicitly rather than assuming all duplicates are identical.
- Reject unsupported or invalid input with a clear error instead of producing silently different results.

## Comparison design

Use `(match_id, corner_event_id)` as the primary key. Report missing/extra corners separately from field mismatches. Check all 35 batch-schema fields after documented type normalization.

Identifiers, metadata, categories, counts, Boolean values, settings, stop reasons and ordered event-ID lists must agree. JSON-list CSV cells must be parsed as lists. Empty/null values must remain distinct from zero. Specify an explicit, small floating-point tolerance for provider xG sums if the SQL aggregation order differs; report absolute differences rather than silently rounding them away.

The report should record Python/SQL row counts, key differences, mismatch counts by field, a bounded list of examples, input hashes, code hashes, actual parameters, and dependency versions. Preserve a complete machine-readable difference file where needed. Fail the comparison when an unaccepted discrepancy remains.

Run comparisons on synthetic edge cases, the existing batch fixtures, the real two-match sample, tournament data, then the league corpus as resources permit. Exercise all four windows; short-threshold cases at 10, 15 and 20 units need dedicated tests. The existing analysis window comparator is not a general short-threshold comparison tool.

## Focused regression coverage

Cover exact time/distance thresholds, simultaneous boundary conditions, period changes, possession changes and missing values, every recognized restart, fouls with/without advantage, opponent pressure, opponent shots/goals, terminal ball-out and goal actions, direct corner shots, absent coordinates/technique, duplicate IDs, shuffled event input, same-time ordering, zero-corner matches, and nonzero exits on mismatches.

Use the Python reference to establish expected differential behavior, alongside hand-checked examples so a shared bug is less likely to go unnoticed. Do not claim these tests replace the independent 100-corner source-event audit.

## Workflow and reconciliation

1. Read a run configuration and record repository commit/dirty status, source revision, dependencies, settings, seeds and hardware/software context.
2. Invoke pinned ingestion, optionally using verified offline cache. Inspect exit status and coverage completeness before extraction.
3. Run Python and SQL extraction against the same manifest and immutable inputs.
4. Compare outputs and stop downstream processing on an unaccepted mismatch.
5. Run descriptive/predictive analysis on the agreed table; record per-target availability and eligible team counts.
6. Run setups only in spatial mode with the expected frame sources. Keep unavailable spatial data separate from event-data failures.
7. Invoke the dossier once its CLI/contract is available; otherwise report that stage as unavailable and do not claim a complete dossier run.
8. Write a run manifest, validation report and stage timings. Publish a successful final run only after required stages and checks pass.

Reconciliation will check per-match ingestion/extraction corner counts; unique corner keys; schema, settings and metadata agreement; `led_to_shot == (shot_count > 0)`; shot-list lengths and membership in chains; and one setup record per input corner when setups run. Retain zero-corner matches in coverage/manifests.

Prematch mode must apply the cutoff to source corner rows before aggregation, use only matches strictly before the target date, and exclude undated matches. Agree the setup-cluster fitting policy with Utkarsh and Mohamed before including clusters in prematch predictions.

## Benchmark protocol

Measure JSON loading, extraction, output writing and total stage time separately when feasible. Keep network download time separate from extraction performance. Use identical inputs/settings/output formats for Python/SQL comparisons, verify agreement first, record thread count and warm/cold cache conditions, and perform repeated runs with fresh destinations. Report timings and variability; do not claim SQL is faster without measurements.

For dossier timing, agree whether the benchmark starts with raw corners, precomputed analysis/setup artifacts, or another defined boundary. Record all included stages and inputs, plus CPU, RAM, OS, Python/DuckDB versions, corpus size and repetitions. Dossier timing depends on Mohamed's generator becoming available.

## Milestones

| Date | Planned handoff |
|---|---|
| November 13 | Implementation plan and early scope/dependency concerns |
| November 20 | First working SQL extractor/comparison/runner on the sample; larger-run progress and explicit remaining work |
| November 27 | Checked results, reproducibility report, timing evidence and paper material |
| December 7 | Material integrated into the paper draft |
| December 14 | Final reproducibility and submission checks |

Implementation order: extraction semantics and fixtures -> SQL/sample parity -> batch comparisons -> runner/reconciliation -> larger-corpus reproduction -> timing and paper text. Treat correctness as the gate before performance optimization.

## Dependencies and scope concerns to flag

- Diego: confirm that the checked-out reference rules remain the comparison target; coordinate any rule changes and raw-event discrepancy review.
- Ebtesam: obtain or regenerate the frozen dataset configuration and manifests. Paths in another member's local manifest may require rebasing; ignored data/output directories do not arrive with a Git clone.
- Asaad: use current analysis outputs/availability conventions and preserve training/validation/test separation.
- Utkarsh: agree spatial mode and any historical setup fitting requirement.
- Mohamed: obtain a callable dossier generator, its input contract, cutoff handling, and timing scope. Only a README exists in that directory on reviewed main.
- Large corpus runs are not reproduced by the existing two-match sample. Reserve time/storage and record actual completion rather than equating fixture success with full reproduction.
- A clean-checkout run must use the new feature branch's exact commit and installed dependencies. Running a second command in a developer's already-configured working directory is not sufficient evidence.

## Initial validation

The current suite discovered 160 tests: 158 passed and two optional Parquet tests were skipped because pyarrow is absent. A fresh real-data sample run completed ingestion, Python extraction, analysis and setups: 2 matches, 6,671 events, 9 corners and 5 usable 360 frames. No prediction-eligible teams in this sample is expected. SQL, orchestration, clean-checkout reproduction, Parquet verification and benchmark results are not completed by that run.
