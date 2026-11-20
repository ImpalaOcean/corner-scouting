# Corner scouting from event histories and partial spatial snapshots

Working paper draft, assembled 19 November 2026. This is an evidence-backed draft, not a submission-ready manuscript. Evidence identifiers below resolve in [paper-evidence-index.md](paper-evidence-index.md). No extraction, fitting, bootstrap experiment or clustering was rerun to assemble this text. Verification here means rereading saved artifacts, checking recorded hashes, recomputing tabular totals and inspecting implementation; it does not mean independent replication of the experiments.

## Research questions and scope

We investigate whether a team's historical corner-delivery distribution predicts later deliveries better than its competition-season average, and whether the same approach improves prediction of a shot following a corner. A separate descriptive question concerns what partial StatsBomb 360 snapshots reveal about shared spatial configurations and their coverage. Finally, we demonstrate how earlier history can be presented in a cutoff-safe prematch dossier. These questions follow the repository's project and evaluation plans; the original formal proposal and course specification were not available in the current workspace, so conformity with their full requirements remains to be checked [M1].

The source is the pinned [StatsBomb open-data repository](https://github.com/hudl/open-data/tree/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb). We separate league prediction from retrospective tournament spatial analysis. All primary extraction tables use a 15-second outcome window and a 15-native-coordinate-unit short-delivery threshold [D1].

**Table 1. Primary corpus.** Match counts are processed manifest matches; corner counts are distinct summary keys.

| Competition | Season | Matches | Corners |
| --- | --- | ---: | ---: |
| Premier League | 2015/2016 | 380 | 4,108 |
| Ligue 1 | 2015/2016 | 377 | 3,591 |
| La Liga | 2015/2016 | 380 | 3,842 |
| Serie A | 2015/2016 | 380 | 3,941 |
| FIFA World Cup | 2022 | 64 | 571 |
| UEFA Euro | 2024 | 51 | 512 |
| Total | Separate competition-seasons | 1,632 | 16,565 |

The league subset contains 1,517 matches and 15,482 corners; the tournaments contain 115 matches and 1,083 corners. Ligue 1 has 377 source-listed matches and is not represented as a complete 380-match season. Neither primary table has duplicate `(match_id, corner_event_id)` keys or missing required identifiers and competition/season/date metadata. These statements were checked against the constituent CSVs and manifests, not the currently inaccessible combined audit directory. This corpus is not claimed to satisfy a “tens of thousands” target [D1, M1].

## Ingestion and extraction

The ingestion pipeline caches original provider JSON, records file status and SHA-256 receipts, validates events and metadata, and exports tables plus a batch manifest for extraction. Exact duplicate events are removed in the cleaned ingestion representation; conflicting duplicate identifiers reject a match. Raw JSON remains unchanged. Optional spatial-file failures are recorded separately from valid event ingestion. Missing optional fields remain missing rather than being replaced by inferred values. Valid matches with no corners remain in the manifest [M2].

The batch runner orders source events by period, timestamp and provider index, preserving source order for ties. A corner starter is a Pass or Shot with nested type `Corner`; the first qualifying event per identifier is retained. A direct corner shot counts as its own attacking shot. Starting at that event, subsequent unique actions are checked in this priority: period change, elapsed time greater than the cap, a restart, possession change, and explicit stoppage or non-advantage foul. Actions satisfying these pre-inclusion boundaries are excluded. An otherwise eligible goal or ball-out action is included before the chain closes. Pressure alone does not end possession; a foul with advantage does not itself stop the chain. Exactly-on-cap events remain eligible. Uncapped extraction removes only the time constraint [M3].

Delivery classification first recognizes direct shots. A pass is short when its height is `Ground Pass`, all start/end coordinates are finite, and Euclidean distance is at most the threshold. Otherwise recognized Inswinging, Outswinging or Straight techniques determine the category; remaining cases are unknown. Short classification takes precedence over technique, which is also exported independently. Exported technique `Unknown` alone does not establish that the raw provider field was absent. Unknown deliveries remain in descriptive totals and outcome analysis; their exclusion from delivery prediction scoring is an analysis policy [M3, P1].

Each row retains delivery attributes and coordinates, attacking shot/goal counts, provider xG sum, ordered shot and chain identifiers, applied settings and stop reason. Provider xG is not a model fitted by this project. Shot counts, goal counts and corners producing a shot are distinct quantities. A stop reason reflects implementation priority, not necessarily the physical moment the ball left play. In particular, an off-target shot lacking an explicit out flag can precede a time-limit termination without demonstrating uninterrupted live play [M3].

### Validation status

Automated boundary tests, schema checks and provenance records support implementation consistency. Diego's 100-corner review passed completeness checks. Asaad's completion, agreement and adjudication remain pending. Neither reviewer's judgments were inspected while drafting this paper. The frozen sample is enriched for rare and boundary cases, so its eventual unweighted error frequency must not be presented as an unbiased corpus accuracy estimate. Automated checks are not human judgments or ground truth [A1].

## Prediction methods

Within each competition-season, matches are ordered by date and then match identifier and split chronologically into 60% training, 20% validation and 20% test, using the documented integer boundaries. Whole matches remain together. Eligibility requires at least 10 training matches and 30 training corners. These are corner-observed matches: zero-corner team appearances cannot be recovered from a corner-only table. Missing-date matches are excluded. Eligibility is fixed on training data [P1].

We compare pooled competition-season rates, unsmoothed team history, and shrinkage toward pooled rates. For delivery category d, the shrunk estimate is `(n_td + alpha * p_cd) / (N_t + alpha)`, with counts over known deliveries. Pooled deliveries use add-one smoothing across the five scored categories; pooled shot probability uses add-one binary smoothing. The unsmoothed delivery distribution has probabilities floored at `1e-6` and renormalized to avoid infinite loss. Shot shrinkage uses an independently selected weight beta and all corners [P1].

Alpha minimizes validation multiclass log loss and beta minimizes validation Brier score on the fixed grid `{0,1,2,5,10,20,50,100,200,500,1000}`; ties favor larger weights. Final fitting uses training plus validation, without changing training eligibility. Unknown categories remain in descriptions and shot scoring but are excluded from delivery scoring. The delivery and shot targets have separate availability handling. Goals are descriptive, not a scored prediction target. The frozen execution plan prohibits method changes based on held-out results [P1].

Intervals are the saved 95% match-level percentile bootstrap intervals, with 1,000 draws and seed 5118. Whole-match resampling preserves within-match dependence, and paired comparisons use the same sampled matches for both methods. These intervals condition on fitted models; they do not quantify the complete uncertainty from fitting and parameter selection [P1].

## Primary league results

The frozen experiment used code `6a64fbdde56131077c66d245b2cb59cad60135a0`. The per-league split is 228/76/76 matches for Premier League, La Liga and Serie A, and 226/75/76 for Ligue 1: 910/303/304 overall. All 80 team profiles were eligible and scored. Validation selected alpha=50 and beta=200. The test set contains 3,154 corners; 2,916 have known delivery labels and 238 unknowns remain in shot scoring. Every one of the 11 recorded artifact hashes in this run matched its current file, as did the input hash [P2].

**Table 2. Primary held-out scores.** Lower is better; intervals are saved 95% bootstrap intervals. Delivery scores use 2,916 corners and shot scores use 3,154 corners from 304 test matches.

| Target | Method | Score | 95% interval |
| --- | --- | ---: | --- |
| Delivery log loss | Pooled | 1.129434 | [1.1028, 1.1574] |
| Delivery log loss | Unsmoothed | 1.118664 | [1.0829, 1.1611] |
| Delivery log loss | Shrunk | 1.096030 | [1.0666, 1.1276] |
| Shot Brier score | Pooled | 0.220439 | [0.2141, 0.2268] |
| Shot Brier score | Unsmoothed | 0.221370 | [0.2148, 0.2278] |
| Shot Brier score | Shrunk | 0.220268 | [0.2138, 0.2269] |

**Table 3. Primary paired differences: shrunk minus baseline.** Negative favors shrinkage; these are paired intervals, not differences between marginal interval endpoints.

| Target | Baseline | Difference | 95% interval |
| --- | --- | ---: | --- |
| Delivery | Pooled | -0.033404 | [-0.0466, -0.0201] |
| Delivery | Unsmoothed | -0.022634 | [-0.0424, -0.0070] |
| Shot | Pooled | -0.000170 | [-0.0009, 0.0006] |
| Shot | Unsmoothed | -0.001102 | [-0.0020, -0.0002] |

Team history with shrinkage improves delivery prediction over pooling in this corpus. The primary shot comparison with pooling provides no clear improvement. Shrinkage also has lower saved losses than unsmoothed history, but the delivery contrast depends on the unsmoothed baseline's artificial floor: rare categories absent in team history incur large log losses. It should not be interpreted as a floor-independent gain over all reasonable team-history baselines. No extra floor-sensitivity experiment is claimed here [P1, P2].

## Outcome-window robustness analyses

The alternative 10-second, 20-second and uncapped runs retain the same corner population, invariant attributes, short threshold, chronological protocol, eligibility, methods, bootstrap controls and recorded analysis-code hashes. Parameters were selected independently on each window's validation data, not selected by test performance. Rechecking the existing comparison contracts passed with no provenance warnings. All recorded analysis artifact receipts matched. These are robustness analyses on reused matches, not independent replications and not grounds for choosing a preferred window [S1].

**Table 4. Window robustness.** Attributed outcomes cover all 15,482 league corners. Brier scores and paired differences cover the same 3,154 held-out corners. Alpha=50 for every window.

| Window | Shots | Goals | Corners with shots (%) | Beta | Shot Brier pooled / unsmoothed / shrunk | Shrunk minus pooled [95% interval] |
| --- | ---: | ---: | --- | ---: | --- | --- |
| 10 s | 4,951 | 428 | 4,560 (29.45%) | 500 | 0.213014 / 0.213300 / 0.212676 | -0.000338 [-0.0008, 0.0000] |
| 15 s, primary | 5,368 | 464 | 4,893 (31.60%) | 200 | 0.220439 / 0.221370 / 0.220268 | -0.000170 [-0.0009, 0.0006] |
| 20 s | 5,598 | 486 | 5,069 (32.74%) | 200 | 0.223592 / 0.224710 / 0.223442 | -0.000149 [-0.0009, 0.0006] |
| Uncapped | 6,033 | 517 | 5,401 (34.89%) | 200 | 0.230459 / 0.231987 / 0.230517 | 0.000059 [-0.0008, 0.0008] |

Delivery scores and paired delivery intervals are identical across windows. Shot attribution rises as the window widens, but these counts measure attribution, not a causal effect. The primary conclusion of no clear shot-prediction benefit over pooling is not decisively reversed. The 10-second interval's upper endpoint rounds to zero at saved precision; its unrounded sign cannot be established from that CSV, and we do not claim strict superiority. Short-threshold robustness is not established by these window-only comparisons [S1].

## Retrospective spatial analysis

The setup pipeline joins on match identifier and exact event UUID, distinguishes unavailable files from unmatched frames, and retains exclusions. Bottom-corner coordinates are mirrored to a common orientation. Eligibility requires valid geometry, at least five visible players and rounded box coverage of at least 0.5. The clustering vector contains attacking and defending outfield counts across nine penalty-box zones, excluding the actor and keepers. One deterministic pooled k-means fit spans both tournaments, using the existing default k=4. Stability is the mean ARI over ten 80% subsample refits with seed 0 and reassignment of all vectors to subsample centers [X1].

**Table 5. Spatial coverage.** Matching and usable percentages divide by all corners, not only matched frames.

| Tournament | All corners | Matched frames | Eligible frames | Matched/all | Eligible/all |
| --- | ---: | ---: | ---: | ---: | ---: |
| World Cup 2022 | 571 | 302 | 302 | 52.89% | 52.89% |
| Euro 2024 | 512 | 290 | 289 | 56.64% | 56.45% |
| Total | 1,083 | 592 | 591 | 54.66% | 54.57% |

All tournament match files loaded in the recorded coverage run; the exclusions are 491 unmatched corners and one low-visibility frame. Shared cluster memberships are 228, 163, 115 and 85. Saved stability is ARI=0.864: its artifact hash was verified, but clustering and stability were not independently rerun for this draft. There are 56 competition-season-team profiles and 224 team-cluster rows. Shares divide by each team's eligible corners and sum to one; eligible counts range from 1 to 24 per team. No actual team has zero eligible corners. The implementation preserves such teams with undefined shares, supported by synthetic tests rather than an observed zero-eligible case [X1].

Matching coverage is lower for short than non-short corners: 19/65 (29.23%) versus 283/506 (55.93%) in the World Cup, and 20/62 (32.26%) versus 270/450 (60.00%) at Euro. These are descriptive, match-clustered observations. They neither identify why frames are missing nor prove random availability. Team profiles are exploratory because of small local samples even when pooled clustering passes its native confidence thresholds [X2].

These full-tournament centers and shares are strictly retrospective. A prematch view requires a separate pooled fit on strictly pre-cutoff data; filtering team rows after fitting future frames would leak information. Alternative visibility-threshold and cluster-count sensitivity results are not included because supporting artifacts are unavailable [X3].

## Cutoff-safe dossier example

The saved historical example is Aston Villa versus Arsenal, fixture 3754117 on 2015-12-13. A pre-generation selection record chose the earliest qualifying Premier League fixture using date, identity and coverage only. Every analytical stage filters to dates strictly before 2015-12-13 and excludes the entire target date because reliable kickoff ordering is unavailable. The target result is not part of this demonstration [C1].

The pooled earlier history contains 156 matches and 1,655 corners. Its selection split is 93 training, 31 validation and 32 refit-only historical matches. Eligibility uses the training prefix; parameter choice uses past-only validation; final fitting uses all strictly earlier history. Alpha and beta both select 1000, the grid maximum, so they are not claimed globally optimal. Only 41 eligible validation corners, including 39 known deliveries, support that selection [C1].

**Table 6. Dossier history, not target outcomes.**

| Team | Prior observed matches | Prior corners | Unknown deliveries | Corners with shots | Selection-training matches / corners |
| --- | ---: | ---: | ---: | ---: | --- |
| Aston Villa | 15 | 63 | 1 | 21 (33.3%) | 10 / 40 |
| Arsenal | 15 | 94 | 5 | 29 (30.9%) | 10 / 69 |

The dossier supplies distributions, observed-frequency intervals, separately labelled model estimates and supporting historical identifiers. Its four generated artifact hashes match the recorded receipts. Source history identities and date restrictions can be checked without evaluating the target. The existing regression tests support cutoff enforcement, but the separate real-data perturbation probe remains a recorded prior check, not a rerun here. Frequency intervals do not quantify model-estimate uncertainty. Historical provider publication timing is unverified. Suitable pre-cutoff spatial evidence is unavailable, and retrospective tournament centers are not loaded. This is an implementation demonstration, not completed predictive or reader-usefulness evaluation of dossiers [C1].

## Reproducibility and unfinished validation

The project includes pinned inputs, settings, typed schemas, event identifiers, content receipts and an independent DuckDB implementation of the extraction rules. The systems owner reports successful two-match SQL/Python sample comparisons. Their cited output directories are absent in this checkout, so those numerical sample results are not adopted as independently verified paper results. Full-corpus SQL parity, clean-checkout final-corpus reproduction, controlled repeated performance benchmarks, and dossier evaluation remain pending [R1].

Spatial handoff of complete checked methods/results text and sensitivity evidence remains pending despite the available primary spatial artifacts [X3].

## Limitations and next evidence needed

The selected seasons do not establish generalization to modern leagues or new providers. Possession labels, missing technique information, provider revisions and explicit out flags constrain extraction. Unknown-category scoring exclusions may be selective. Date/identifier ordering keeps matches intact but does not guarantee that every same-date fixture within an evaluation season lies in the same split; the dossier's stricter whole-date cutoff is a separate protection. Match bootstrap intervals do not account fully for team dependence, model refitting or selection uncertainty. Observational outcome attribution and static setup clusters do not establish causal effects, marking schemes or tactical success.

The formal proposal/course requirements, external literature review and complete bibliographic references still need supplying. No external literature claims are invented here. Pending human agreement/adjudication, short-threshold sensitivity, spatial sensitivity receipts, SQL corpus checks, clean-checkout reproduction, fair benchmarks, reader evaluation and cutoff-safe spatial handoff must be completed or explicitly scoped out before submission. Existing figures are not embedded until their provenance is tied to the checked tables [M1, A1, S1, X3, R1, F1].
