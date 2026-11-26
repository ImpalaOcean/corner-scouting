# Source-Consistency Audit of the StatsBomb Corner-Kick Extraction Pipeline

**Reviewers:** Diego (reviewer A), Asaad (reviewer B)
**Report date:** 2026-11-25 (America/Toronto)
**Extraction settings audited:** 15-second window, 15-unit short-corner threshold (primary tables only)
**Sampling seed:** 5118
**Resolutions confirmed:** 2026-11-25 by Diego and Asaad

## Scope and interpretation

This audit checks the versioned corner extractor against its own source records (StatsBomb open-data event JSON) and its documented rules in `docs/corner-extraction-methods.md` and `docs/audit-protocol.md`. It is a source-consistency audit. It does not measure the extractor against an independently sourced football ground truth, and a `y` judgment means only that the recorded value is what the implemented rule produces from the raw events.

The sample was deliberately enriched with rare and boundary cases. Unweighted agreement and error rates computed on it are therefore **not** unbiased estimates of corpus-wide extraction accuracy, and should not be quoted as such.

## 1. Sample and provenance

### Population and sampler

Per `sample_provenance.json`, the population is 16,565 corners drawn from 1,632 manifest matches covering FIFA World Cup 2022, UEFA Euro 2024, and the 2015/16 Premier League, La Liga, Serie A and Ligue 1. The sampler (`src.analysis.audit`, commit `ecfd3f0abde02f10a18c82934698cba90948437a`, code SHA-256 `62618e35…7ad8c`, Python 3.13.0) drew 100 distinct corners with seed 5118. Six audit tests passed before sampling. The provenance file records that exactly one seed was used and no cases were substituted.

The 100 corners come from 99 distinct matches (match 3825806 contributes audit IDs 40 and 41).

| Corpus | Competition / season | Corners |
|---|---|---:|
| League (93) | La Liga 2015/16 | 24 |
| | Serie A 2015/16 | 24 |
| | Premier League 2015/16 | 23 |
| | Ligue 1 2015/16 | 22 |
| Tournament (7) | UEFA Euro 2024 | 4 |
| | FIFA World Cup 2022 | 3 |

### Strata

Strata were filled in a fixed order, without replacement, before the remaining slots were filled at random:

| Stratum | Quota | Selected |
|---|---:|---:|
| direct_shot | 10 | 10 |
| short | 15 | 15 |
| unknown_delivery | 8 | 8 |
| straight | 6 | 6 |
| goal | 8 | 8 |
| shot_then_time_limit | 8 | 8 |
| new_restart | 6 | 6 |
| stoppage | 6 | 6 |
| possession_change | 6 | 6 |
| ball_out | 6 | 6 |
| period_end | 4 | **0** |
| random (fill) | — | 21 |
| **Total** | | **100** |

The `period_end` stratum produced no candidates under the primary settings. Per the recorded quota policy, the shortage was left as a shortage and the four slots went to the random fill. No sampled corner has `stop_reason = period_end`, so that boundary is not exercised by this audit.

### Integrity checks

`sample_provenance.json` records that every sampled key is in the combined population, every match is in the combined manifest, all sampled event paths existed, review fields were blank at freeze, both corpora are present, a replay of the sampler was byte-identical, and the master sheet and both reviewer copies were identical at freeze (SHA-256 `fe7d9119…f5bcf011`).

`preparation_provenance.json` (2026-11-25, comparison code `843ab3c6…`) records validation of both completed reviewer sheets against the hash-authenticated master, with no errors, and identical before/after digests showing the originals were read only. The SHA-256 values of the files attached for this report were recomputed and match those records:

| File | SHA-256 | Matches provenance |
|---|---|---|
| `audit_sheet.csv` (master) | `fe7d9119b7b5c44c8e443d4d8fd819abd5f26c8a8a100f276f7fc56bb5bcf011` | yes |
| `audit_diego.csv` | `f1fd2446e2e212d476bf669f71a423beb30af1ef40626619b7d60a2943112cd7` | yes |
| `audit_asaad.csv` | `0e07b615d120698d5c6bfe802634aa2eb53bc113dbba12f2c237ece0ca347a70` | yes |
| `sample_provenance.json` | `8a9bcf69566bb8c8818e3f7447a66558cfa71ede94caf1bb5bfae0851aaa280e` | yes |
| `agreement.csv` | `987bf112e3b4f6e8a07ba88beb751437df613ef9ad1a4da263a4e8ff7eaa9046` | yes |
| `disagreements.csv` | `c25bc8a0beff07efcaa2f3054419c88d782b2ddc5def926a20c110a0984794f8` | yes |
| `call_review_worksheet.csv` (preparation worksheet, resolution columns blank) | `687b2848ad900b75411693ef84e923ab1619b2f30aa1581da9d9f8239e2ec9ef` | yes |

The filled worksheet from Section 3 is a separate file, `call_review_worksheet_resolved.csv` (SHA-256 `032fb5b630d8578d5560067ecb18b3219211b6b530873dbf5f034f30b16bb07b`). The original reviewer sheets, `agreement.csv`, `disagreements.csv` and the preparation worksheet were not modified, and their digests above were rechecked after it was written.

The protocol's reference-run paragraph was dated 2026-11-18, while `sample_provenance.json` gives a preparation date of 2026-11-12. The counts in both agree, so the sample is unaffected. A corrected `audit-protocol.md` (Section 4.5) now dates the draw by the provenance file. If 2026-11-18 was a separate later run of `src/verify_audit.py`, that run should be recorded as its own line rather than as the draw date.

## 2. Inter-reviewer agreement (pre-resolution)

Both reviewers answered all 400 judgments (100 corners × 4 fields). There were no missing answers and no disagreements; `disagreements.csv` contains only its header.

| Field | Answered by both | Missing (A / B) | Agree | % agreement | Cohen's κ | Marked `y` (A / B) |
|---|---:|---:|---:|---:|---|---:|
| delivery_ok | 100 | 0 / 0 | 100 | 100.0 | undefined | 100% / 100% |
| shot_ok | 100 | 0 / 0 | 100 | 100.0 | undefined | 100% / 100% |
| goal_ok | 100 | 0 / 0 | 100 | 100.0 | undefined | 100% / 100% |
| stop_ok | 100 | 0 / 0 | 100 | 100.0 | undefined | 100% / 100% |

Cohen's kappa is reported as `undefined`, not as 1.0. Both reviewers gave the label `y` to every item in every field, so the expected chance agreement p<sub>e</sub> equals 1 and the kappa denominator (1 − p<sub>e</sub>) is zero. Kappa only measures agreement beyond what the marginal label frequencies would produce, and with a single constant label there is no variation for it to measure. The protocol requires this case to be reported as undefined.

Neither reviewer marked any field `n`, so the pre-resolution comparison found no extractor errors and no code fix is triggered. These figures come from `agreement.csv` as produced before discussion. Nothing in the later call changes them.

### Sample distributions

These describe the extractor's recorded values on the 100 sampled corners. Because of enrichment, they do not represent corpus proportions.

**delivery_category:** outswinging 30, short 19, inswinging 17, unknown 15, direct_shot 10, straight 9.

**stop_reason:** time_limit 33, possession_change 25, ball_out 18, goal 11, stoppage 7, new_restart 6. (period_end 0.)

**shot_count:** 54 corners with 0 shots, 44 with 1, 2 with 2 — **48 attacking shots across 46 corners.**

**goal_count:** 89 corners with 0 goals, 11 with 1 — **11 goals across 11 corners.** All 11 have `stop_reason = goal`.

## 3. Call triage and resolutions for six ambiguous `stop_ok` cases

The call worksheet was built from the union of disagreements (none), `n` answers (none), and reviewer notes matching an explicit-ambiguity pattern. Six corners qualified, all on `stop_ok`. In every case both reviewers had answered `y`, and one or both reviewers' notes recorded that an alternative reading would change the outcome. Diego's notes raise the alternative in all six. Asaad's notes raise it in IDs 59, 74, 79 and 83 and are blank for IDs 35 and 57.

Each chain was re-derived from the raw match JSON twice. The first pass was a manual timeline read. The second was an independent re-implementation of the boundary rules: events ordered by period, timestamp and provider index; then, for each later event, period → time over cap → restart → possession → stoppage, with goal and top-level `out` flags checked after inclusion and on the corner itself first. Both passes reproduced the master sheet's `chain_event_ids` (same IDs, same order) and `stop_reason` for all six. The result did not change whether possession change was keyed on `possession_team` or on the provider's `possession` counter.

Each case was proposed as `y` under the documented rules, and both reviewers confirmed all six on 2026-11-25. The resolutions are recorded in `call_review_worksheet_resolved.csv`, kept separate from the preparation worksheet. The pre-resolution agreement figures in Section 2 are unchanged.

### 3.1 `Half End` as a stoppage (1 case)

**Audit ID 57** — match 3879575 (Udinese v Hellas Verona), corner `b8e0a006-5a5a-43d0-8b8a-7cfaeaf1588c`, period 1, 00:45:51.107.

Diego's note questioned whether `Half End` is a stoppage, since it did not appear among the stoppage examples he was working from (Asaad's note for this corner is blank). A strict reading would have included both `Half End` events and ended at the period-2 `Half Start` as `period_end` (10 events). The methods document settles this: its sequence-boundary section lists "half-end events" alongside non-advantage fouls, offside, injury stoppages and referee ball drops as events that close the sequence.

In the raw file the last included event is a Hellas Verona recovery pass at +11.301 s (`9877079e-b299-416c-8f14-42e121b9abd3`), with possession 90 unchanged. The first `Half End` at +13.175 s (`afae3071-4c47-4691-bd4a-73a24a614571`) is still in period 1, inside the cap, not a restart and in the same possession, so the stoppage check fires before it. The second `Half End` (`9090f871-dab2-450f-81d0-1b862c9a9b22`) and the period-2 `Half Start` are never reached. Recorded `stoppage` with 8 chain events is correct.

This is a documentation clarification rather than an ambiguity in the rule. The corrected `audit-protocol.md` (Section 4.5) now states that Half End is a stoppage, in line with the methods document, so the question should not recur.

### 3.2 `pass.outcome = "Out"` without a top-level `out: true` (5 cases)

In each of these, a pass inside the chain carries the nested provider outcome `pass.outcome.name = "Out"`, but the `out` key is absent from the event's top level (absent, not `false`). The implemented rule reads only the top-level `out` flag ("ball-out flags"), so none of these passes gives the extractor a ball-out signal, and none ends the chain as `ball_out`. Both reviewers recorded `y` under that flag-only rule. One or both reviewers' notes pointed out that an outcome-based rule would end the chain at the "Out" pass instead: Diego's in all five cases, and Asaad's in IDs 59, 74, 79 and 83 (his note for ID 35 is blank).

| ID | Match | Corner | "Out" pass (offset, event ID) | What follows | Recorded stop | Verified |
|---|---|---|---|---|---|---|
| 35 | 3825697 (Valencia, P2 00:08:30.800) | `48c0f150-2682-43b2-91cf-52b40bc883bd` | The corner itself, +0.000 s | `Ball Receipt*` +3.773 s (`fcb8cfb1-4ee6-4379-b750-dae002fcbc39`), included; `Injury Stoppage` +13.963 s (`192799f9-6af0-4fdb-b67e-2da4a48ddaf2`) | stoppage | yes |
| 59 | 3879656 (Bologna, P2 00:25:55.428) | `2ef518dc-4bdd-4b84-888d-6ae9d5df3110` | +3.573 s, `0b4073f2-c8b3-45eb-9faf-873636e77ac2` | `Substitution` +32.441 s (`6c35dadd-9ad3-4ed2-a798-05431728f6fb`), beyond 15 s cap | time_limit | yes |
| 74 | 3879807 (Carpi, P1 00:45:12.339) | `a46fdd00-74f4-42d2-a2cc-8a379407203d` | +3.396 s, `c033665d-bb2b-4d0a-98f1-7a996b4eb071` | `Ball Receipt*` +5.394 s (`3a82a5e6-6f8b-4622-892c-bf4a60228bf2`), included; `Goal Kick` +14.269 s (`46291fac-72b9-497b-89ee-b9a89bfcde61`) | new_restart | yes |
| 79 | 3900506 (Stade de Reims, P2 00:42:11.000) | `ebaf7a3c-9a69-4cc6-8259-884fa4b48158` | +7.362 s, defending team (Gazélec Ajaccio), `c3eca15e-5f45-45bc-9bf2-224a4c89becf` | `Ball Receipt*` +9.618 s (`fb98b1ce-8563-46e7-ab34-7dbeaff4a084`), included; `Throw-in` +14.987 s (`edf6408f-84b3-44e4-82de-046a29b53be8`) | new_restart | yes |
| 83 | 3900564 (AS Monaco, P1 00:05:52.581) | `fa0d6b56-c815-4f52-96d0-061042cb56c3` | +3.441 s, `047cc286-4ef8-4d24-85a2-cae5d29ed220` | `Goal Kick` +28.705 s (`3d74a977-90f3-41fc-9d83-5fe32394995d`), beyond 15 s cap | time_limit | yes |

Notes on the boundary order in individual cases:

- **ID 35.** Because the corner has no top-level `out` flag, the corner-level check does not fire and the chain continues. The `Injury Stoppage` is in the same possession (121) and within the cap, so `stoppage` is the first boundary reached.
- **IDs 59 and 83.** The "Out" pass is the last included event. The next recorded event lies well past the cap, and the time check precedes every other boundary, so `time_limit` is correct under the rule.
- **ID 74.** The goal kick is both a new restart and a possession change (95 → 96). Restart precedes possession in the implemented order, so `new_restart` is the recorded reason.
- **ID 79.** The "Out" pass is by the defending team, but `possession` (185) and `possession_team` are unchanged, so it does not trigger a possession change. The throw-in at +14.987 s falls within the cap and ends the chain as `new_restart`.

If the rule treated the nested outcome as a ball-out signal, all five would be recorded as `ball_out` at the "Out" pass. That would change `stop_reason`, and for IDs 35, 74 and 79 chain membership, but not `shot_count` or `goal_count`, since none of the five contains a shot after the "Out" pass. This is a difference between two rules applied to the same recorded events. It says nothing about when play actually stopped, which the source does not record. Section 4.3 returns to this.

### 3.3 Resolution summary

| ID | Category | Resolution | Reviewer confirmation | Supporting raw events |
|---|---|---|---|---|
| 35 | Nested "Out", no top-level flag | y | Diego; Asaad — 2026-11-25 | corner, `fcb8cfb1…`, `192799f9…` |
| 57 | Half End stoppage | y | Diego; Asaad — 2026-11-25 | corner, `9877079e…`, `afae3071…`, `9090f871…` |
| 59 | Nested "Out", no top-level flag | y | Diego; Asaad — 2026-11-25 | corner, `0b4073f2…`, `6c35dadd…` |
| 74 | Nested "Out", no top-level flag | y | Diego; Asaad — 2026-11-25 | corner, `c033665d…`, `3a82a5e6…`, `46291fac…` |
| 79 | Nested "Out", no top-level flag | y | Diego; Asaad — 2026-11-25 | corner, `c3eca15e…`, `fb98b1ce…`, `edf6408f…` |
| 83 | Nested "Out", no top-level flag | y | Diego; Asaad — 2026-11-25 | corner, `047cc286…`, `3d74a977…` |

Full UUIDs are stored as JSON arrays in `supporting_event_ids` in `call_review_worksheet_resolved.csv`. With all six resolutions confirmed as `y`, no extractor errors were identified in any of the four fields.

## 4. Traceability issues and methodological limitations

### 4.1 Audit ID 1: local source-file identifier problem (resolved; not an extractor error)

Both reviewers independently reported a problem with the local copy of `events/267576.json` (Barcelona, period 2, 00:03:38.635, corner `817898d0-a9a3-499c-89c1-2af2556cad5b`). It is reported separately from the six call cases and is not counted as an extractor error, because both reviewers judged all four fields `y` and the sampled corner key carries the original UUID.

**Finding.** The local file did **not** match its recorded hash. Every events file in the folder has a `.sha256.json` sidecar naming source revision `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. Across all 1,632 files, 1,631 match their sidecar and `267576.json` is the only mismatch:

| | SHA-256 |
|---|---|
| Recorded (sidecar) | `6de94032e22da90bb4ef4d0eca01295c0e42198cc5fd63332f0711d07080eecf` |
| Local file as found | `d08a43c9a3cd983c6e1a2b0b264523a5093c6a2a41c668155cb379a6b5437c9f` |

The sidecars were written on 2026-11-12. The local file's modification time was 2026-11-19 21:17 UTC, a week later than the rest. This differs from Diego's note, which said the copy he judged from matched the stored hash; that was an attached copy, not this local file, and the local cache copy did not match. The six raw files used for the call (3825697, 3879575, 3879656, 3879807, 3900506, 3900564) all match their sidecars.

**What differed.** The altered file has `id: " "` at provider index 2048, a `Pass` of type `Corner` by Barcelona, period 2, 00:03:38.635. The next event (index 2049, `b1b2b2a7-38b5-4568-83ef-e2481d4be36d`) still lists `817898d0-a9a3-499c-89c1-2af2556cad5b` in `related_events`, which is how both reviewers linked the blank record to the sampled corner.

**Recovery.** Upstream was not reachable from this environment, so the original was reconstructed from the local file by a one-field change: setting that `id` back to the UUID in the sampled key and the `related_events` reference. The resulting bytes hash to exactly `6de94032…eecf`, the recorded value. A structural comparison of the two files shows one differing event (index 2048) out of 3,784, and no other difference. On the restored file, the extractor rules reproduce the sheet's chain for audit 1 (4 events, ending in `possession_change` before `Goal Keeper` `1a514563-cc4b-4055-8197-566dbba481ab` at 00:03:43.558), consistent with both reviewers' `y`.

**Actions taken.** The altered file was kept as `267576.json.altered-local-2026-11-19` (SHA-256 `d08a43c9…c9f`) and the verified original was written in place as `267576.json`. Nothing was deleted. This was not an upstream re-download, so a fetch from the pinned revision would be an independent check if one is wanted. The cause of the change on 2026-11-19 is not established by anything in the files. Anything generated from this cache between 2026-11-19 and now should be checked, since it would have seen the blanked ID.

### 4.2 No recorded out signal after shots

After many off-target, saved or blocked shots, the StatsBomb record has no explicit out flag and no out event. When nothing inside the window records an earlier ending, the extractor has no boundary to find and correctly ends the chain on `time_limit`, as both the methods document and the protocol state. Reviewers were told not to infer an unrecorded timestamp and to note these cases separately.

In the sample, **22 corners** have `shot_count > 0` and `stop_reason = time_limit` (audit IDs 5, 17, 21, 28, 31, 33, 38, 39, 42, 46, 50, 52, 58, 62, 63, 69, 77, 85, 87, 88, 91, 95). Across both reviewers' notes, **28 distinct corners** were noted as having no recorded out event in connection with a shot (Diego 22, Asaad 17). These 28 are the 22 above plus six whose chains ended on another recorded boundary after the shot: ID 18 (stoppage), ID 19 (goal), IDs 45, 73 and 89 (new_restart) and ID 78 (possession_change). Including notes that mention no recorded out event without referring to a shot, 37 corners were noted in total.

All were judged `y`, and shot and goal counts are unaffected. What this changes is interpretation. A `time_limit` ending after a shot means only that the source records no boundary signal inside the window. The data do not show whether or when play stopped in that interval. Chain duration and post-shot event membership should therefore not be read as continuous live play, and no stopping time should be assigned that the source does not record.

### 4.3 Nested `pass.outcome = "Out"` without a top-level flag

The five cases in Section 3.2 show that a pass event can carry the nested provider outcome `"Out"` while the top-level `out` key is absent. What the source records here is that outcome attribute plus the events that follow, for example a goal kick, a throw-in or a substitution. It records no separate ball-out event and no timestamp for when play stopped. The extractor's flag-only rule does not treat the nested outcome as a boundary. That matches the current specification, so these cases are correctly `y`.

It is still a known edge case in the stopping rule, because the two signals can lead to different chains. If a future rule also treated `pass.outcome = "Out"` as a boundary signal, IDs 35, 74 and 79 would end at the "Out" pass instead of at the later recorded boundary event. That later event comes about 14 s after it for ID 35 (injury stoppage, +13.963 s), about 10.9 s for ID 74 (goal kick, +14.269 s) and about 7.6 s for ID 79 (throw-in, +14.987 s). IDs 59 and 83 would keep the same membership but be recorded as `ball_out` instead of `time_limit`. These differences come from comparing rules on the same recorded events. Neither rule measures when the ball physically left play, and the source does not establish that timing. Adopting the outcome-based signal would be a specification change, not a bug fix. It would need to be documented before use, implemented with reviewed code and regression tests, and followed by regeneration of affected outputs with recorded provenance, as the protocol requires. It would also shift the `stop_reason` distribution, so results under the two rules should not be mixed.

### 4.4 Other limitations

- **Enriched sample.** Restated because it governs how every number in this report is read: the 100% agreement and zero identified errors describe this edge-case-weighted sample, not the 16,565-corner corpus.
- **Uninformative kappa.** With a constant label, kappa cannot show whether reviewers would agree on harder cases. Agreement here is strong evidence that the extractor follows its rules on the sampled cases, and weak evidence about reviewer calibration.
- **No `period_end` coverage.** The stratum was empty and no sampled corner ended on a period change, so that boundary is untested here.
- **Near-threshold cases.** Several deliveries sat close to the 15-unit short threshold (e.g. 13.909, 14.262, 14.610 and 15.340 units) and several boundary events fell just past the 15 s cap (15.021–15.136 s). All were judged `y` from raw values, but results are sensitive to these thresholds, which is why the alternative-window tables exist as sensitivity analyses.
- **Provider dependence.** Chain membership relies on StatsBomb possession labels and event ordering. Recorded ending reasons follow rule priority, not necessarily the physical instant play stopped.

### 4.5 Protocol alignment

`audit-protocol.md` has been corrected in a copy delivered with this report (`audit-protocol.md`, with `audit-protocol.diff` showing the exact change). It now (a) dates the reference run by the `prepared_date` in `sample_provenance.json`, (b) adds `--master` to the `agree` command, as used in the 2026-11-25 comparison run, and (c) adds a block labelled as post-audit clarifications dated 2026-11-25. That block states that Half End is a stoppage provided no earlier-priority boundary has already ended the sequence (consistent with the methods document and audit 57), and that ball out is judged from the top-level `out` flag only. The clarifications restate existing rules and change no judgment or agreement result. The flag-only sentence in (c) goes beyond what was requested, so drop it if you would rather handle that separately. The repository copy was not edited, because only the events folder is connected here; the change needs to be applied on `feat/evaluation`.

## 5. Summary

| Item | Result |
|---|---|
| Corners reviewed | 100 (99 matches; 93 league, 7 tournament) |
| Missing answers | 0 |
| Pre-resolution disagreements | 0 of 400 judgments |
| Percent agreement (each field) | 100.0% |
| Cohen's κ (each field) | undefined (constant `y` label) |
| Proposed resolutions | 6 (`stop_ok`): 1 Half End clarification, 5 nested "Out" without top-level flag; all `y` |
| Reviewer confirmation | Diego and Asaad, 2026-11-25 (all six) |
| Extractor errors identified | 0 (pre-resolution and after confirmed resolutions) |
| Separate traceability issue | Audit ID 1: local `267576.json` had a blanked corner ID and failed its recorded hash; original restored and verified (hash match) |
| Documented provider limitation | 22 shot + `time_limit` corners; 28 corners noted for no recorded out event after shots |
| Known rule edge case | Nested `pass.outcome = "Out"` not treated as a boundary when the top-level `out` key is absent |

Remaining actions: apply the `audit-protocol.md` changes in the repository (Section 4.5), and optionally confirm the restored `267576.json` against the pinned upstream revision.
