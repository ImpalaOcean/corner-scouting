# 100 corner audit protocol (Diego and Asaad)

Purpose (proposal Section 3): two members independently check 100 sampled
corner sequences against the raw StatsBomb events and report agreement and
resolved errors. This checks the extractor against its source records and its
documented rules (`docs/corner-extraction-methods.md`); it is not independent
ground truth.

## 1. Same sample for both

One person draws the sample from the agreed corner table and shares the sheet
(Drive folder). Same input file and seed always give the same 100 corners.

    python -m src.analysis.audit sample --input outputs/<run>/corner_summary.csv --output outputs/audit

Record the input path and the batch run's `run_manifest.json` hash in the
paper. The sample covers rare and boundary cases first (direct shots, short,
unknown and straight deliveries, goals, shots that end on the time limit, and
each stop reason), then fills the rest at random. The `stratum` column says why
each corner was picked.

## 2. Review independently

Each reviewer copies the sheet (`audit_asaad.csv`, `audit_diego.csv`) and does
not discuss answers until both are finished. For each corner, look at the raw
events:

    python -m src.analysis.audit show --manifest data/ingested/<run>/batch_manifest.json --sheet outputs/audit/audit_sheet.csv --audit-id 7

Fill each column with `y` (the extractor follows the documented rule) or `n`
(it does not). Every `n` needs a short note.

| Column | Question |
|---|---|
| delivery_ok | Is `delivery_category` what the rules give? Short: ground pass ending within the short limit; otherwise the technique (inswinging, outswinging, straight) or unknown when missing; direct shot when the corner itself is a shot. |
| shot_ok | Does `shot_count` equal the shots inside the chain as the rules define it? |
| goal_ok | Does `goal_count` equal the goals inside the chain? |
| stop_ok | Is `stop_reason` the earliest ending rule that applies (goal, ball out, possession change, stoppage, new restart, period end, time limit)? |

## 3. Agreed rule for missing "ball out" events

StatsBomb often records no event when an off target shot goes out. Example
(audit sample, Denmark vs Australia): shot off target at 2.7 s, goalkeeper
"Shot Faced" at 3.1 s, next event a substitution at 19.5 s. The extractor ends
the chain at the 15 s limit.

Rule: judge the code against the documented rule. If no event inside the
window shows an earlier ending, `time_limit` is correct, so `stop_ok = y`, with
the note "no out event". The shot and goal counts are unaffected. We report how
many sampled chains end this way, because their recorded duration is longer
than the real play. Changing the ending rule itself is the extractor owner's
decision and would mean rerunning extraction and the audit.

## 4. Compare and resolve

    python -m src.analysis.audit agree --sheets audit_asaad.csv audit_diego.csv --output outputs/audit_agreement

This writes percent agreement and Cohen's kappa per column (`agreement.csv`)
and every disagreement (`disagreements.csv`). Resolve each disagreement
together and record the final answer. Report in the paper: agreement before
resolution, kappa, the number of confirmed extractor errors per column, and
what was fixed.
