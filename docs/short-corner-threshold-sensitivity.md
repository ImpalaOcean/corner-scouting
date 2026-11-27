# Short-corner threshold sensitivity

## Frozen methods (27 November 2026)

The supplied two-page proposal `P6a_Corner_Kick_Mining_Proposal.pdf` explicitly specifies 10- and 20-unit checks against the primary 15-unit threshold. Its SHA-256 is `44b5b1960e126b9792cd29ea8ff86c94b6c33d0c9dbafe0ae36c655cbccb3ddd`; identity with the actual submitted copy is supplied rather than independently authenticated. Thresholds are native provider coordinate units, not outcome seconds.

Worktree branch: `codex/short-threshold-sensitivity`, frozen main commit `77af6f910935b6b12232b3e60183210c7f175e56`. No production implementation was changed. All ten uncommitted paper files were copied and hash-verified before work began; the paper branch remains untouched.

The existing batch CLI re-extracts the same pinned tournament and league manifests at short limits 10 and 20, always window=15, with CSV and Parquet. The primary 15-unit tables remain unchanged. All 1,632 event hashes match the primary run receipts. Delivery categories and descriptive distributions depend on the threshold; outcome chains and shot/goal attribution do not. Existing analysis is repeated at each threshold, including separate 15-unit current-code controls. League delivery frequencies, pooled priors, validation alpha choice, final fitting, prediction scores and intervals are recalculated; no full-season fitted parameters are reused. The same CLI also recalculates shot models/intervals as a consistency check, even though shot inputs are invariant. Tournament descriptions are repeated, but predictive eligibility is expected to be unavailable under the original rule and will not be relaxed.

The fixed evaluation protocol is chronological 60/20/20 within competition-season, at least 10 training corner-observed matches and 30 training corners; separate validation-only alpha/beta selection from {0,1,2,5,10,20,50,100,200,500,1000}, ties toward greater smoothing, final train+validation fit, 1,000 match-bootstrap draws and seed 5118. The original split membership must match at every threshold. Test scores do not select the threshold, methods or tuning grid. Spatial clustering and dossier generation are excluded.

The new root is `R/outputs/short-threshold-sensitivity-2026-11-27/`, where R is the original repository. `execution-plan.json` was saved before fitting and contains absolute input/output paths, exact argv arrays, source/code hashes and settings. Existing destinations are refused. Each CLI publishes only a complete individual run and processing stops on failure; cross-run validation is a separate stage. No old outputs, raw events or audit artifacts are rewritten.

Relevant tests: `python -B -m unittest discover -s tests -p test_corners.py -v` (15), `test_corner_batch.py` (9), `test_evaluation.py` (21), and `test_analysis_regressions.py` (22): 67 passed using the original absolute `.venv/Scripts/python.exe`. An initial `test_batch.py` pattern matched no files; it was corrected to `test_corner_batch.py` and is not counted as a passing suite.

## Supported workflow and limits

`src.analysis.compare` compares outcome windows only and correctly rejects changed short limits and delivery attributes. Its safeguards are not weakened. A dedicated read-only artifact comparison will check keys, metadata, source hashes, settings, CSV/Parquet, expected category changes, fixed outcomes, split membership, train eligibility, artifact receipts and the new 15-unit control against the original primary scores. Cross-threshold log loss is not performance on identical labels/populations: unknown-to-known changes alter its scoring denominator, so within-threshold baseline contrasts are the relevant comparisons. No new cross-threshold paired significance test or preferred threshold selection is planned.

The methods block above was recorded before inspecting results; the verified results follow below.

## Verified results

All four alternative extractions and six analysis runs completed successfully. The population is unchanged: 1,517 league matches/15,482 corners and 115 tournament matches/1,083 corners. All 35 exported columns agree across thresholds after typed normalization except the intended `short_limit` and `delivery_category`; any tiny provider-xG representation differences are reported below. CSV/Parquet values agree for every row, including lists and nulls. Required metadata is populated, keys are unique and match-level counts agree with the manifests, including any zero-corner matches.

### Delivery definitions (all corners)

| Corpus | Threshold | Corners | Short | Unknown | Direct shot | Inswinging | Outswinging | Straight |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Leagues | 10 | 15482 | 891 | 1817 | 7 | 6091 | 5795 | 881 |
| Leagues | 15 | 15482 | 1491 | 1217 | 7 | 6091 | 5795 | 881 |
| Leagues | 20 | 15482 | 1871 | 837 | 7 | 6091 | 5795 | 881 |
| Tournaments | 10 | 1083 | 84 | 135 | 6 | 455 | 367 | 36 |
| Tournaments | 15 | 1083 | 127 | 92 | 6 | 455 | 367 | 36 |
| Tournaments | 20 | 1083 | 162 | 57 | 6 | 455 | 367 | 36 |

Counts by each of the six competition-seasons, including unknown percentages, shots and goals, are in `delivery_counts.csv`. Unknowns remain in descriptive totals and shot analysis. The independently recomputed distance/height/technique rule agrees with every exported category. Short membership is nested as the threshold increases; direct shots retain their separate category. In this corpus all category changes are between short and unknown; inswinging, outswinging, straight and direct-shot counts do not change.

| Corpus | Comparison | Changed categories | Percentage of that corpus | xG representation differences |
| --- | --- | ---: | ---: | ---: |
| leagues-2015-16 | 10 → 15 units | 600 | 3.88% | 0 |
| leagues-2015-16 | 15 → 20 units | 380 | 2.45% | 0 |
| wc2022-euro2024 | 10 → 15 units | 43 | 3.97% | 0 |
| wc2022-euro2024 | 15 → 20 units | 35 | 3.23% | 0 |

The changed keys and full category transition matrices are retained as separate CSVs. Shots, goals, shot-producing indicators, shot IDs, chains and stop reasons are invariant. League totals remain 5,368 shots, 464 goals and 4,893 shot-producing corners; tournament totals remain 390 shots and 26 goals. A changed delivery label is not a changed outcome or causal effect.

### Prediction comparisons (league held-out data)

All 80 league team profiles remain eligible; none is excluded. Match splits are identical: 910 train, 303 validation and 304 test, with per-league memberships unchanged. Training match/corner counts and exclusion reasons for every team at every threshold are in `training_eligibility.csv`. The held-out all-corner population stays at 3,154; only known-delivery denominators can change. The three methods are pooled, unsmoothed team history and shrinkage, all refitted using the existing procedure.

| Short limit | Known / unknown test deliveries | Alpha / beta | Delivery log loss: pooled / unsmoothed / shrunk | Shrunk − pooled [95% CI] | Shrunk − unsmoothed [95% CI] |
| --- | --- | --- | --- | --- | --- |
| 10 | 2789 / 365 | 50 / 200 | 1.070850 / 1.063376 / 1.039788 | -0.031062 [-0.0437, -0.0186] | -0.023589 [-0.0439, -0.0075] |
| 15 | 2916 / 238 | 50 / 200 | 1.129434 / 1.118664 / 1.096030 | -0.033404 [-0.0466, -0.0201] | -0.022634 [-0.0424, -0.007] |
| 20 | 2996 / 158 | 50 / 200 | 1.157696 / 1.146641 / 1.124358 | -0.033339 [-0.0462, -0.0201] | -0.022283 [-0.0416, -0.0071] |

The paired shrinkage-minus-pooled delivery interval remains wholly below zero at all three thresholds. This supports the original delivery conclusion under these alternative definitions without establishing a preferred threshold. Complete marginal score intervals, paired within-threshold baseline differences, counts, statuses and reasons are in `prediction_metrics.csv` and `prediction_differences.csv`. These are match-level 95% intervals conditional on the selected fitted models, not complete refitting/selection uncertainty.

Shot Brier results and paired intervals are unchanged at all three thresholds: pooled 0.220439, unsmoothed 0.221370 and shrunk 0.220268. Shrunk minus pooled is -0.000170 [-0.0009, 0.0006]; shrunk minus unsmoothed is -0.001102 [-0.0020, -0.0002]. The primary interpretation of no clear shot benefit over pooling is unchanged. Tournament descriptions are exported, but no tournament team meets training eligibility (56 excluded, zero eligible); prediction results remain explicitly unavailable, not zero scores.

The new 15-unit current-code control reproduces the original saved primary score table, paired differences, parameter grid results, match splits and team prediction table exactly as parsed CSV rows. Current main has newer safeguards than the original frozen predictive commit `6a64fbdde56131077c66d245b2cb59cad60135a0`; this control establishes result agreement on these specified artifacts, not byte identity of all code or every output. No original result was replaced.

## Interpretation and limitations

Compare each refitted method with its baselines under the same threshold. Raw log losses across thresholds target changed labels and potentially different known-delivery populations; a smaller value does not identify a better physical definition or justify choosing that threshold. Unknown-to-short transitions can change selective missingness. The unsmoothed baseline still floors probabilities at 1e-6 and renormalizes; its comparison remains floor-dependent. No new floor experiment, cross-threshold paired significance test or selection of a preferred threshold was performed. The primary remains 15 units.

These are robustness analyses on the same seasons and matches, not independent replications. Classification depends on provider coordinates, height and exported technique fallback; exported `Unknown` alone does not prove the raw technique field was absent. Native distance is not a measured ball trajectory. Ligue 1 remains a 377-listed-match catalog. No clustering, pre-cutoff spatial fit, dossier generation or reader evaluation was performed, so those unfinished tasks are not completed by this exercise.

The supported window-only `src.analysis.compare` intentionally rejects this design. Its rules were preserved. A separate read-only verification script checked intended threshold-dependent changes and invariant inputs/results; it does not introduce a new prediction method. Source-hash agreement and independently recomputed categories are consistency checks, not independent football ground truth.

## Reproduction and evidence

The execution plan records every actual command as an absolute argv array, pre-run input/code hashes and all 1,632 source-file receipts. `execution-status.json` records command exits and logs. `verification.json` records the checks, code hashes, prediction counts and output hashes. CSV values normalize JSON-list strings/nulls/numbers; ordered IDs remain exact. Provider xG uses a 1e-12 absolute verification tolerance only when numeric representation differs; those differences are counted rather than hidden and do not affect delivery/shot prediction inputs.

Equivalent commands, run from a clean checkout at the frozen SHA with the original absolute Python executable, are below. `$InputManifest`, `$PrimaryCsv` and `$ThresholdCsv` must be absolute verified inputs; `$NewExtraction` and `$NewAnalysis` must not exist. The actual paths are in `execution-plan.json`.

```powershell
# Repeat for league and tournament manifests, with ShortLimit = 10 and 20.
& $Python -B src/run_corner_batch.py --manifest $InputManifest --output $NewExtraction --window 15 --short-limit $ShortLimit --parquet
if ($LASTEXITCODE -ne 0) { throw 'Extraction failed' }
# Repeat each corpus at limits 10 and 20, plus a new analysis-only 15-unit control.
& $Python -B -m src.analysis --input $ThresholdCsv --output $NewAnalysis --bootstrap 1000 --seed 5118
if ($LASTEXITCODE -ne 0) { throw 'Analysis failed' }
```

No new production code was required. Focused tests ran before corpus analysis (67 passing, with the corrected batch test filename). The new result root was refused if already present. Logs are execution records, not performance benchmarks. Source revision is pinned to `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. Detailed raw-event data remain outside the result package; original reviewer sheets were not inspected. The protected primary files and all ten preserved paper files still match their before-run hashes.

Largest recorded xG representation difference (leagues-2015-16): 0.

Largest recorded xG representation difference (wc2022-euro2024): 0.
