# Proposed independent 100-corner audit

Prepared 2026-11-09 for Diego Fuentes and Asaad Faris Husein. Status: proposed sample and instructions, awaiting both reviewers' agreement. Preparing a packet does not constitute agreement or a completed audit.

## Scope and frozen inputs

Audit the saved 15-second, short-limit-15 run at `outputs/wc2022-euro2024-corners/`. Preserve it during review. The population is 1,083 extracted corner summaries across 115 matches. This design assesses the validity of extracted records and their sequences; it cannot estimate missed-corner recall because non-extracted events are not sampled.

The local packet is `data/audit/wc2022-euro2024-proposed-100/`. All paths in `sample.csv` are relative to the project root. `selection.json` records the source artifacts' hashes, extraction-module hash, selection algorithm and seed, sample counts, and initial CSV hashes. A local preparation helper is retained at `data/audit/prepare_wc2022_euro2024_audit.py`; it refuses to overwrite an existing packet. The data directory is gitignored: these files are local and have not been sent to Asaad.

## Proposed sample

Select 50 corners from World Cup 2022 and 50 from Euro 2024, without replacement. Within each competition, rank each corner by the hexadecimal SHA-256 of `seed|match_id|corner_event_id`, using seed `corner-audit-proposal-2026-11-09-v1`, and take the lowest 50 ranks. This gives a reproducible selection independent of row order and predicted outcomes. The resulting 100 unique corners span 63 matches. Both reviewers must use these exact IDs; do not replace difficult, ambiguous, or previously seen records. Mark prior exposure in notes.

The equal competition allocation is a proposal, not an already agreed design. After agreement, freeze the sample and instructions and record the date and both reviewers' approval. For population-level descriptive agreement, weight competition results by their population sizes (571/1,083 and 512/1,083); also show unweighted audit results and the per-competition denominators. Events from the same match are correlated. Do not treat 100 observations as independent matches or infer broad model performance from this audit. Rare cases may be inspected separately as diagnostics, with those checks clearly outside the fixed 100.

## Packet files and independent review

- `sample.csv`: the shared 100 IDs, source locators, fixture information, and provenance; no extractor outcomes.
- `diego-review.csv`: Diego's blank worksheet.
- `asaad-review.csv`: Asaad's identical blank worksheet, to be kept private while reviewing.
- `extractor-reference-after-review.csv`: saved predictions for comparison only after both independent source reviews are locked.
- `selection.json`: selection and provenance record.

Supply Asaad only the agreed instructions, sample, his blank worksheet, and access to the pinned source files. Keep the prediction reference and Diego's judgments out of his initial packet. The assistant has not filled in either reviewer's judgments. Worksheet identity at preparation is intentional: reviewer name, date, and all observed findings start empty. Original preparation hashes cease matching completed worksheets; retain original blanks and save completed versions separately.

## Review instructions

1. Start in the pinned source event file, locate `corner_event_id`, and confirm that the starter is a Corner-type pass or direct corner shot. Use period-relative timestamps; do not interpret second-half timestamps as full-match minute values. Follow the batch ordering: period, timestamp, then provider index.
2. Independently record the delivery category and eligible events, using provider possession IDs and the frozen rules. A short corner requires a ground pass travelling at most 15 native coordinate units with usable coordinates. Keep missing coordinates unknown, not zero. Retain the first instance of repeated event IDs.
3. Record attacking shot and goal counts, observed shot IDs, and ordered chain IDs as JSON arrays. Include the starter and terminal shot or explicitly out action; exclude restart, possession-change, and stoppage boundary records. Record the last included and first excluded IDs. Use `[]` for no shots, not an empty cell. A direct corner shot counts itself.
4. Apply the current rule priority: duplicate records are skipped; then check period change, elapsed time greater than 15 seconds, new restart, possession change, and explicit stoppage/non-advantage foul. Only after including an eligible action check its goal outcome and then its out flag. Events exactly at 15 seconds qualify. Advantage continues play. Goals by either team end the chain, but only attacking-team Shot events contribute to the shot/goal counts. Valid reasons are `period_end`, `time_limit`, `new_restart`, `possession_change`, `stoppage`, `goal`, `ball_out`, or `end_of_data`.
5. Record ambiguity separately in `boundary_interpretation` and `notes`. For an off-target shot without an explicit out flag, do not silently infer ball out under the current implementation. A subsequent `time_limit` label is an algorithmic stopping reason, not proof that play continued to the cap. Record any alternative physical interpretation as uncertain unless independently supported. Agree on this distinction before review; do not change the production rule during the audit.
6. Fill `reviewer` and `reviewed_at`; use `is_corner` values `yes`, `no`, or `unsure`, and confidence `high`, `medium`, or `low`. Leave uncertain counts blank and explain them rather than guessing. Do not consult the other worksheet or the prediction reference while forming initial judgments.

## Comparison after both reviews finish

Lock both independent versions before comparing. Calculate exact agreement separately for corner identification, delivery category, shot count, goal count, shot-ID set, ordered chain IDs, and stopping reason. Report reviewed, uncertain, and evaluable denominators per field; do not count missing judgments as agreement. Compare each review with the frozen predictions as well as comparing the reviewers. Preserve original judgments and keep adjudicated decisions in a separate file with reasons. Describe disagreements about rule interpretation separately from implementation errors. Any rule revision requires a versioned change, regression checks, and fresh extraction; it must not retroactively replace the frozen audited run.

## Coordination draft — not sent

Asaad, the World Cup 2022/Euro 2024 run has 1,083 corner summaries from 115 matches. I have prepared a proposed common sample of 100 corners, 50 per competition, with separate blank worksheets and pinned source-file hashes. Before either of us starts, can we agree on these exact IDs and the attached review instructions, particularly how to record off-target shots without an explicit out flag and competing stopping reasons? We should review source events independently, keep our judgments private, and compare only after both versions are complete. The saved extractor predictions will be held separately until then.
