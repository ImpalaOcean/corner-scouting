# Corner scouting from event histories and partial spatial snapshots

**Draft status (27 November 2026):** Refreshed against merged methods, spatial, systems and audit evidence. Saved-artifact verification is distinguished from supplied experimental reports. Proposal deviations and unfinished dossier work remain explicit; this is not a submission-ready paper.

Working paper draft, assembled 19 November 2026. This is an evidence-backed draft, not a submission-ready manuscript. Evidence identifiers below resolve in [paper-evidence-index.md](paper-evidence-index.md). No extraction, fitting, bootstrap experiment or clustering was rerun to assemble this text. Verification here means rereading saved artifacts, checking recorded hashes, recomputing tabular totals and inspecting implementation; it does not mean independent replication of the experiments.

## Research questions and scope

We investigate whether a team's historical corner-delivery distribution predicts later deliveries better than its competition-season average, and whether the same approach improves prediction of a shot following a corner. A separate descriptive question concerns what partial StatsBomb 360 snapshots reveal about shared spatial configurations and their coverage. Finally, we demonstrate how earlier history can be presented in a cutoff-safe prematch dossier. These questions follow the recovered local proposal and the course's P6-a brief. The completion checklist maps the promised work to evidence and scope deviations; the local proposal source has not been authenticated as the submitted version [M1].

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

The league subset contains 1,517 matches and 15,482 corners; the tournaments contain 115 matches and 1,083 corners. Ligue 1 has 377 source-listed matches and is not represented as a complete 380-match season. Neither primary table has duplicate `(match_id, corner_event_id)` keys or missing required identifiers and competition/season/date metadata. These statements were checked against the constituent CSVs and manifests, rather than the combined audit directory; the latter's recorded hashes were subsequently verified during audit finalization. This corpus is not claimed to satisfy a “tens of thousands” target [D1, M1].

## Related work

Pappalardo et al.'s [open soccer event dataset](https://www.nature.com/articles/s41597-019-0247-7) describes action times, positions, outcomes and player attributes, and distinguishes event logs from tracking data. That distinction matters for our scope: action histories do not reconstruct all players' movement. We use StatsBomb, not their dataset, and do not assume interchangeable provider definitions. Source pinning and traceable event IDs make our own sequence definitions inspectable [L1].

[TacticAI](https://www.nature.com/articles/s41467-024-45965-x) uses tracking-derived player graphs for receiver and shot prediction, retrieval and positional recommendations, with expert assessment. Our partial-snapshot zone clusters are descriptive and do not reproduce that system; our history-based frequency forecasts also have different inputs and targets. No cross-study performance comparison is justified by these task and data differences [L1].

[Gneiting and Raftery](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf) develop proper scoring rules, including logarithmic and quadratic scores. We score full delivery distributions and shot probabilities, while keeping validation-only smoothing selection separate from test scoring. Scoring-rule theory does not validate our labels. The raw baseline's probability floor and changed-label populations under threshold sensitivity still constrain interpretation [L1, P1, S2].

[Davis et al.](https://link.springer.com/article/10.1007/s10994-024-06585-0) distinguish model accuracy from indicator usefulness and discuss dependence in evaluation. We accordingly separate chronological prediction, retrospective spatial description and the past-only dossier demonstration. Match bootstrap intervals condition on fitted models, and prediction gains do not establish reader usefulness. Additional team examples and reader evaluation remain pending [L1, C1].

## Ingestion and extraction

The ingestion pipeline caches original provider JSON, records file status and SHA-256 receipts, validates events and metadata, and exports tables plus a batch manifest for extraction. Exact duplicate events are removed in the cleaned ingestion representation; conflicting duplicate identifiers reject a match. Raw JSON remains unchanged. Optional spatial-file failures are recorded separately from valid event ingestion. Missing optional fields remain missing rather than being replaced by inferred values. Valid matches with no corners remain in the manifest [M2].

The batch runner orders source events by period, timestamp and provider index, preserving source order for ties. A corner starter is a Pass or Shot with nested type `Corner`; the first qualifying event per identifier is retained. A direct corner shot counts as its own attacking shot. Starting at that event, subsequent unique actions are checked in this priority: period change, elapsed time greater than the cap, a restart, possession change, and explicit stoppage or non-advantage foul. Actions satisfying these pre-inclusion boundaries are excluded. An otherwise eligible goal or ball-out action is included before the chain closes. Pressure alone does not end possession; a foul with advantage does not itself stop the chain. Exactly-on-cap events remain eligible. Uncapped extraction removes only the time constraint [M3].

Delivery classification first recognizes direct shots. A pass is short when its height is `Ground Pass`, all start/end coordinates are finite, and Euclidean distance is at most the threshold. Otherwise recognized Inswinging, Outswinging or Straight techniques determine the category; remaining cases are unknown. Short classification takes precedence over technique, which is also exported independently. Exported technique `Unknown` alone does not establish that the raw provider field was absent. Unknown deliveries remain in descriptive totals and outcome analysis; their exclusion from delivery prediction scoring is an analysis policy [M3, P1].

Each row retains delivery attributes and coordinates, attacking shot/goal counts, provider xG sum, ordered shot and chain identifiers, applied settings and stop reason. Provider xG is not a model fitted by this project. Shot counts, goal counts and corners producing a shot are distinct quantities. A stop reason reflects implementation priority, not necessarily the physical moment the ball left play. In particular, an off-target shot lacking an explicit out flag can precede a time-limit termination without demonstrating uninterrupted live play [M3].

### Validation status

The completed Diego-Asaad source-consistency audit covers 100 corners and 400 paired judgments. Both reviews are complete and match the hash-verified frozen master. Pre-discussion agreement is 100% for delivery, shot count, goal count and stop reason; Cohen's kappa is undefined because both reviewers marked every field y. Six note-flagged termination cases have separately recorded rule-consistent resolutions confirmed by both reviewers on November 25, 2026. No extractor errors were identified under the audited rules. This enriched sample is not independent football ground truth or an unbiased corpus-wide accuracy estimate. Automated verification remains separate from the human audit [A1].

Source traceability for audit #1 was separately investigated. The restored local event JSON matches the original recorded sidecar and extraction hash; the altered backup is preserved. Its only structural difference is the corner identifier at provider index 2048. This verifies local recorded-byte identity, not a fresh upstream download or proof of historical reviewer access. Available run receipts identify the original source hash; no affected computational run is identified, while path-only or unlogged historical reads remain unverifiable. Combined preparation records are now readable and match the frozen sample's recorded input hashes [A1].

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

Delivery scores and paired delivery intervals are identical across windows. Shot attribution rises as the window widens, but these counts measure attribution, not a causal effect. The primary conclusion of no clear shot-prediction benefit over pooling is not decisively reversed. The 10-second interval's upper endpoint rounds to zero at saved precision; its unrounded sign cannot be established from that CSV, and we do not claim strict superiority. Window-only comparisons do not establish short-threshold robustness; the separate short-distance analysis below addresses that question [S1, S2].

## Short-corner distance robustness

The proposal's 10- and 20-native-unit alternatives were evaluated against primary 15, always retaining the 15-second outcome window. The same pinned league and tournament population, source hashes and match splits were retained. Each threshold reran the documented validation-only smoothing selection and final fitting without test-based method changes; the primary stayed fixed. Frozen code was main `77af6f910935b6b12232b3e60183210c7f175e56`; a separate current-code 15-unit control reproduced the original primary score, parameter, split and prediction tables [S2].

**Table 7. Short-distance robustness at a fixed 15-second outcome window.** All runs use the same 3,154 held-out league corners, but known-delivery scoring counts differ. Lower log loss is better within each definition. Paired 95% intervals use 1,000 whole-match draws, seed 5118; alpha=50 and beta=200 at every threshold.

| Short limit | Known / unknown test deliveries | Pooled log loss | Unsmoothed log loss | Shrunk log loss | Shrunk minus pooled [95% interval] |
| --- | --- | ---: | ---: | ---: | --- |
| 10 | 2789 / 365 | 1.070850 | 1.063376 | 1.039788 | -0.031062 [-0.0437, -0.0186] |
| 15 | 2916 / 238 | 1.129434 | 1.118664 | 1.096030 | -0.033404 [-0.0466, -0.0201] |
| 20 | 2996 / 158 | 1.157696 | 1.146641 | 1.124358 | -0.033339 [-0.0462, -0.0201] |

The delivery shrinkage advantage over pooling remains supported at all three thresholds. Shot scores and paired intervals are identical, retaining the primary finding of no clear advantage over pooling. All 80 league teams remain eligible; no tournament team meets the unchanged predictive eligibility rule. League short counts are 891/1,491/1,871 and tournament short counts 84/127/162 at 10/15/20 units. All observed category transitions are between short and unknown; raw outcomes, chains, shot IDs and stop reasons are invariant [S2].

These are definition-sensitivity checks on reused matches, not independent replications. Raw log losses across thresholds predict different labels and score different known-delivery populations; they cannot select a preferred physical short-corner definition. Retain within-threshold baseline comparisons, the unsmoothed floor-probability caveat and conditional-bootstrap limitations. Primary short limit remains 15. No spatial clustering, dossier builds or reader evaluation were rerun [S2].

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

The existing zone-mean figure is now included in the LaTeX paper as two enlarged, source-checked panels (F2), retaining all four clusters. Its means are static observations, not marking-scheme or tactical-success labels. See [figure sources](../paper/figure-sources.md).

These full-tournament centers and shares are strictly retrospective. A prematch view requires a separate pooled fit on strictly pre-cutoff data; filtering team rows after fitting future frames would leak information. Merged supporting reports now provide visibility and cluster-count robustness checks: k=4 at coverage 0.3 retains 591 corners and ARI 0.864; coverage 0.7 retains 587 with ARI 0.8589. At coverage 0.5, k=3, 5 and 6 have ARI 0.841, 0.7267 and 0.7074, respectively. Saved JSON reports reconcile with the committed sensitivity table; these fits were not rerun here. This differs from the proposal's 80%/90% thresholds and training/validation choice over k=2–8. The completed exploratory fit is not a validation-selected predictive setup model, and visible-player-count confounding remains untested [X3, M1].

## Cutoff-safe dossier example

The saved historical example is Aston Villa versus Arsenal, fixture 3754117 on 2015-12-13. A pre-generation selection record chose the earliest qualifying Premier League fixture using date, identity and coverage only. Every analytical stage filters to dates strictly before 2015-12-13 and excludes the entire target date because reliable kickoff ordering is unavailable. The target result is not part of this demonstration [C1].

The pooled earlier history contains 156 matches and 1,655 corners. Its selection split is 93 training, 31 validation and 32 refit-only historical matches. Eligibility uses the training prefix; parameter choice uses past-only validation; final fitting uses all strictly earlier history. Alpha and beta both select 1000, the grid maximum, so they are not claimed globally optimal. Only 41 eligible validation corners, including 39 known deliveries, support that selection [C1].

**Table 6. Dossier history, not target outcomes.**

| Team | Prior observed matches | Prior corners | Unknown deliveries | Corners with shots | Selection-training matches / corners |
| --- | ---: | ---: | ---: | ---: | --- |
| Aston Villa | 15 | 63 | 1 | 21 (33.3%) | 10 / 40 |
| Arsenal | 15 | 94 | 5 | 29 (30.9%) | 10 / 69 |

The dossier supplies distributions, observed-frequency intervals, separately labelled model estimates and supporting historical identifiers. Its four generated artifact hashes match the recorded receipts. Source history identities and date restrictions can be checked without evaluating the target. The existing regression tests support cutoff enforcement, but the separate real-data perturbation probe remains a recorded prior check, not a rerun here. Frequency intervals do not quantify model-estimate uncertainty. Historical provider publication timing is unverified. Suitable pre-cutoff spatial evidence is unavailable, and retrospective tournament centers are not loaded. This is an implementation demonstration, not completed predictive or reader-usefulness evaluation of dossiers [C1].

## Systems validation and reproducibility

The supplied systems handoff reports agreement between Python and DuckDB over all 16,565 corners at 10, 15, 20 seconds and uncapped, with short limit 15. Its compact comparison table records zero missing/extra keys, zero field mismatches and zero provenance errors in eight corpus/window runs. This represents 66,260 corner/configuration comparisons, not that many unique corners. All 35 fields use exact typed comparison except provider xG sums, whose absolute tolerance is 1e-12. We checked the committed tables against the hash-verified supplied ZIP; no extraction comparison was rerun [R1].

On the supplied desktop measurements, five extraction pairs per corpus followed an excluded warmup, alternated implementation order, and were compared outside timing. Mean Python/SQL runtimes were 4.414/23.480 seconds for tournaments and 71.487/326.720 seconds for leagues. SQL was slower in this shipped workflow. Timing includes startup, loading, hashing, extraction and CSV/Parquet output, excludes download and comparison, and does not isolate engine query time. The recorded machine was a Ryzen 7 7700X with 15.74 GiB OS-reported RAM, Windows, Python 3.11.9, DuckDB 1.4.3 and SQL threads=1. Cache state, CPU scheduling and OneDrive/background activity were not controlled. These are supplied desktop timings, not independently measured speed or universal engine rankings [R1].

The handoff also records separate offline clean-checkout reproduction of both primary pipelines and the existing dossier, using a verified shared raw cache. Its comparison tables report byte-identical Python tables and byte-identical SQL tables between development and clean runs; path-rebased manifest byte hashes differ while per-match source records agree. This is supplied reproduction evidence, not a fresh independent download or a reproduction performed for this paper. The clean suite's 224 passing tests and handoff suite's 230 passing tests are author-reported run results. Dossier selection/build means were 0.615/0.452 seconds over five measured repetitions; generation time does not demonstrate reader usefulness [R1].

Mo's newer league CSV fingerprint differs from the original analytical input. The handoff documents short_limit formatting (15 versus 15.0) and five floating-point xG-sum differences no greater than 2.220446049250313e-16. Its diagnostic reconstruction recovers the original published hash; attribution of that representation difference to an exact originating software version is unresolved. We preserve the original analysis and do not substitute this newer table or present its bytes as identical to the original input [R1, P2].

Only two distinct team dossier views are evidenced locally, Aston Villa and Arsenal in one fixture; the clean/timing builds repeat those teams. At least three further distinct, adequately supported team views are needed for the proposal's five-team target. Reader evaluation by Mohamed and Asaad and any rolling fixture-level predictive evaluation remain pending. The [dossier completion plan](dossier-completion-plan.md) separates those tasks from the completed season-level evaluation [C2].

## Limitations and next evidence needed

The selected seasons do not establish generalization to modern leagues or new providers. Possession labels, missing technique information, provider revisions and explicit out flags constrain extraction. Unknown-category scoring exclusions may be selective. Date/identifier ordering keeps matches intact but does not guarantee that every same-date fixture within an evaluation season lies in the same split; the dossier's stricter whole-date cutoff is a separate protection. Match bootstrap intervals do not account fully for team dependence, model refitting or selection uncertainty. Observational outcome attribution and static setup clusters do not establish causal effects, marking schemes or tactical success.

The recovered proposal and course requirements now support the [completion checklist](paper-completion-checklist.md). The selected corpus does not establish the promised tens-of-thousands scale. Short-distance sensitivity at 10/20 units is complete [S2]. Visible-player-count controls, pre-cutoff spatial fitting, target-zone maps, additional dossier teams, and reader evaluation remain incomplete or need explicitly agreed scope reductions. The current static spatial fit departs from the proposal's visibility/selection protocol. No usefulness result or approval of these deviations is claimed. Final references, authorship, figure mappings, owner sign-off and a compiled minimum-seven-page ACM paper remain to be completed [M1, C2, F1].

## References and materials

- Hudl/StatsBomb. StatsBomb Open Data, pinned revision 4b73468fc5b0f1950f9f66fada70ad3a4f9327cb. [Source repository](https://github.com/hudl/open-data/tree/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb).
- Jesse Davis et al. 2024. Methodology and evaluation in sports analytics: challenges, approaches, and lessons learned. Machine Learning 113, 6977–7010. [Publisher record](https://doi.org/10.1007/s10994-024-06585-0). This supports the distinction between model performance and usefulness evaluation, not our numerical results.
- CARDS. 2026. From Pixels to Decisions, version 1.0, sections 8–9. [Program brief](https://people.scs.carleton.ca/~ahmedelroby/COMP5118_F26/Sports_Analytics_Program.pdf). V4 adds the checked primary publications below; synthesis still requires owner review, and no cross-study performance equivalence is claimed.


- Luca Pappalardo, Paolo Cintia, Alessio Rossi, Emanuele Massucco, Paolo Ferragina, Dino Pedreschi and Fosca Giannotti. 2019. A public data set of spatio-temporal match events in soccer competitions. Scientific Data 6, article236. [Publisher](https://www.nature.com/articles/s41597-019-0247-7).
- Zhe Wang, Petar Veličković, Daniel Hennes et al. 2024. TacticAI: an AI assistant for football tactics. Nature Communications15, article1906. [Publisher](https://www.nature.com/articles/s41467-024-45965-x). All 23 authors are recorded in the checked BibTeX entry.
- Tilmann Gneiting and Adrian E. Raftery. 2007. Strictly Proper Scoring Rules, Prediction, and Estimation. Journal of the American Statistical Association102(477), 359–378. [Author-hosted published paper](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf); DOI10.1198/016214506000001437.


## LaTeX v3 preparation note

The completed methods/results above have been transferred into the LaTeX manuscript without new experiments. Its display order places short-threshold robustness before spatial coverage and the dossier, so automatic table numbers differ from this historical Markdown numbering; stable LaTeX labels and all values are retained. Table typography is natural-size, the window table is split into panels, and dossier history is transposed. The feature definition fixes goal direction toward x120, columns increasing in x, and displayed grid rows increasing in normalized y down the image; the normalized corner at y80 is beyond the bottom, not top, edge. Existing raster values are unchanged. The supplied v2 PDF has five pages; no v3 page-count or final layout claim is made before compilation. Missing examples, reader evaluation and proposal-scope decisions remain pending.


## LaTeX v4 layout and related-work note

The ten-page supplied v3 PDF was inspected. V4 restores ordinary two-column flow around the spatial figures, uses normal-size tables and removes the forced reference-page break. A portable Tectonic/XeTeX build permits local visual checks; exact PDF count/hash and compiler warnings are in the separate v4 verification record. Six primary-source/material references now support the four-part related-work draft [L1]. None supplies new project results. The numerical tables and image bytes are unchanged. Subject review, final-engine approval, author metadata, more dossiers, reader evaluation and scope decisions remain pending.
