# 100 corner audit protocol (Diego and Asaad)

Purpose (proposal Section 3): two members independently check 100 sampled
corner sequences against the raw StatsBomb events and report agreement and
resolved errors. This is a source consistency audit: it checks the versioned
extractor against its source records and its documented rules
(`docs/corner-extraction-methods.md`). It is not an independently sourced
football ground truth evaluation.

This protocol is reconciled with the "Combined-corpus audit preparation"
section of `docs/corner-extraction-methods.md`. Where they differ, that
section's rules win.

## 1. Scope and inputs

Scope: World Cup 2022, Euro 2024 and the 2015/16 Premier League, La Liga,
Serie A and Ligue 1, using only the primary 15 second window and 15 unit
short limit tables. Alternative window tables are sensitivity experiments, not
extra audit observations.

## 2. Draw and freeze one sample

Diego leads the sample. One person draws it once and shares the folder; nobody
regenerates a sample on their own machine.

    python -m src.analysis.audit sample --input outputs/wc2022-euro2024-corners/corner_summary.csv outputs/leagues-2015-16-corners/corner_summary.csv --output outputs/audit-combined-primary-sample

The command combines the tables and refuses duplicate `(match_id,
corner_event_id)` keys, mixed extraction settings, and corners missing
competition, season or date. Input order does not matter. It writes:

* `audit_sheet.csv`: the blank sheet, with competition and season per corner.
* `sample_provenance.json`: sampler version, seed (5118), quotas, population
  size and settings, every input table's path and SHA-256 (plus its
  `run_manifest.json` hash), the sheet's SHA-256, and the selected counts by
  competition season and stratum, including tournament versus league corners.

The output is the format `src/verify_audit.py` reads. Check that the printout
shows both tournament and league corners before freezing. Any change to the
sampling policy is documented before anyone reviews, never after.

The sample is enriched: rare and boundary cases are drawn first (direct shots,
short, unknown and straight deliveries, goals, shots that end on the time
limit, and each stop reason), then the rest at random. Its error rate is not
an unbiased estimate of corpus wide extraction accuracy; the paper must say so.

Reference run (2026-11-18, code commit on this branch): 16,565 corners in the
population, 100 sampled (7 tournament, 93 league; World Cup 3, Euro 4, La Liga
24, Ligue 1 22, Premier League 23, Serie A 24). `src/verify_audit.py` verified
the sheet's provenance and agreed with all 100 corners on every field.

## 3. Review independently

Each reviewer copies the frozen sheet (`audit_asaad.csv`, `audit_diego.csv`),
records every judgment personally and does not share answers until both are
finished. To see the raw events around a corner (give both manifests):

    python -m src.analysis.audit show --manifest data/ingested/wc2022-euro2024/batch_manifest.json data/ingested/leagues-2015-16/batch_manifest.json --sheet outputs/audit-combined-primary-sample/audit_sheet.csv --audit-id 7

The timeline and `--raw` retain the first event beyond the context time/period
boundary so it can be inspected; that event is not thereby included in the extracted
chain. The timeline shows exact timestamps, offsets from the corner, team,
possession, start and end coordinates, pass length, height and technique, out
flags, advantage and pressure. Add `--raw` for the full event JSON whenever a
judgment depends on a field or precision the timeline does not show; rounded
text is not enough to judge a 15 unit delivery or an exact time boundary.

Fill each column with `y` (the extractor follows the documented rule) or `n`
(it does not). Every `n` and every ambiguous case needs a note.

| Column | Question |
| --- | --- |
| delivery_ok | Is `delivery_category` what the rules give? Direct shot when the corner itself is a shot; short when it is a ground pass ending within the short limit; otherwise the provider technique (inswinging, outswinging, straight) or unknown when it is missing. |
| shot_ok | Does `shot_count` equal the attacking team's shots inside the chain? |
| goal_ok | Does `goal_count` equal the goals inside the chain? |
| stop_ok | Is `stop_reason` what the implemented boundary order gives (below)? |

### Boundary order for stop_ok

Judge against the implemented rule, not a different idea of when play
physically stopped:

1. The corner itself is checked first for a direct goal or out flag.
2. For each later event, in order: a new period, then elapsed time greater
   than the cap, then a new restart, then a possession change, then a stoppage
   ends the chain before that event.
3. Goals and ball out flags are checked after an event is included.
4. An event exactly on the cap is still included.

### Missing ball out events

StatsBomb often records no event when an off target shot goes out. If no
event inside the window shows an earlier ending, `time_limit` is correct
(`stop_ok = y`). Note "no out event" and record these cases separately. Do not
infer an unrecorded timestamp, and do not treat chain membership as continuous
live play. Shot and goal counts are unaffected.

Before handing in, check your own sheet:

    python -m src.analysis.audit check --sheet audit_asaad.csv

It lists missing answers and `n` answers without a note.

## 4. Compare and resolve

    python -m src.analysis.audit agree --sheets audit_asaad.csv audit_diego.csv --master outputs/audit-combined-primary-sample/audit_sheet.csv --output outputs/audit_agreement

The command verifies the original master against its adjacent `sample_provenance.json`,
rejects duplicate IDs/keys and changes to frozen columns, and refuses unless both
sheets match all 100 master corners and every
answer is filled in and each `n` has a note. It writes per column percent agreement, missing answer
counts and Cohen's kappa (`agreement.csv`), and every disagreement
(`disagreements.csv`). When both reviewers give one and the same label to every
corner, kappa is reported as `undefined`, not as perfect agreement.

Resolve each disagreement together and record the resolution separately from
the original answers. Report in the paper: agreement before resolution, kappa,
missing answers, confirmed extractor errors per column and what was fixed. Any
confirmed extraction fix needs reviewed code, regression tests and regenerated
affected outputs with recorded provenance.
