# First cutoff-safe prematch dossier

The existing `src/dossier/` package previously contained only its owner/template
README. Main and all inspected remote branches had no executable dossier to
reuse. This feature fills that package and reuses the existing `src.analysis`
loader, summaries, chronological splits, eligibility, smoothing selection and
model formulas; it does not create a second analysis or setup implementation.

## Selection recorded before generation

Fixture: **Aston Villa vs Arsenal**, Premier League 2015/2016, match **3754117**,
dated **2015-12-13**. Cutoff: **strictly before 2015-12-13**, excluding the target
ID and the entire target date. No reliable kickoff ordering is supplied by the
saved corner table.

The predeclared rule chose the earliest Premier League 2015/16 fixture, sorted by
date then numeric match ID, with both teams meeting 10 observed matches and 30
corners in the selection-training prefix of strictly earlier history, plus at
least one validation-period corner each. Selection projected only dates,
competition/team/fixture identities and corner coverage. Delivery labels, shots,
goals and the target result did not select the fixture. The source hashes,
fixture, rule, cutoff and settings were saved to
`outputs/dossier-first-cutoff-safe-prematch-selection.json` **before** running the
build command. No target outcome was inspected or evaluated.

## Past-only fitting policy

Filter before outcome typing, data validation, eligibility or aggregation. The
existing 60/20/20 chronological function is applied inside the already-filtered
competition-season history: 93 training matches, 31 validation matches and 32
remaining historical matches. That last historical fold retains the original
`split=test` label for provenance, but its explicit `selection_role=refit_only`
means it is neither scored nor used to select smoothing. After selection, final
models fit all **156 strictly earlier matches / 1,655 corners** to predict the
chosen future fixture. This is not an evaluation of that fixture.

Prediction eligibility stays fixed on the selection-training prefix. Alpha uses
known-delivery validation log loss and beta uses all-corner validation Brier score,
on the existing grid `[0,1,2,5,10,20,50,100,200,500,1000]` with the documented
larger-weight tie break. Both selected weights are **1000**, from this past-only
history; no full-season fitted parameters or test scores are loaded. Because both
choices reach the top of the predefined grid, they must not be described as
globally optimal. No grid extension or method tuning followed these results.

## Dossier contents and measured history

| Team | Prior corner-observed matches | Prior corners | Unknown deliveries | Shot-producing corners | Training matches / corners |
| --- | ---: | ---: | ---: | ---: | --- |
| Aston Villa | 15 | 63 | 1 | 21 (33.3%) | 10 / 40 |
| Arsenal | 15 | 94 | 5 | 29 (30.9%) | 10 / 69 |

Both teams are eligible under the training-only rule. Their latest included team
match date is 2015-12-05. The readable dossier shows all six observed delivery
categories, counts, shares and match-bootstrap intervals; raw observed shot
frequencies; and pooled, unsmoothed and shrunk known-category delivery estimates
and all-corner shot estimates. Observed intervals use 1,000 match-bootstrap draws
and seed 5118. Shrunk shot estimates are approximately **30.6%** for Aston Villa
and **30.5%** for Arsenal. These are model expectations, not observed target outcomes.

Only six and eleven validation corners belong to the two target teams,
respectively; the selection uses every train-eligible team's past validation
corners within the competition. Limited history and selection uncertainty remain
important even when the eligibility minimum is met.

## 360 setup coverage

The section is **unavailable**. All 156 included historical matches have coverage
records with `frames_status=not_requested`. This is disabled ingestion, not a
measured 0% provider-availability rate. No retrospective tournament centers,
memberships or team shares from PR #23 were read. The current dossier package
does not implement a cutoff-safe setup fit; future setup use would need suitably
verified earlier frames and a separate pooled fit performed strictly before the
cutoff, never filtering after future-inclusive cluster fitting.

## Validation

**14 new focused tests passed and are included in the 174-test full-suite run
(160 base tests + 14 prematch tests, not 174 + 14).** The prior shared-cluster
feature also reported 174, but it added a different 14-test module that is absent
from this base/branch. These totals must not be conflated. Tests
change target/future outcomes, append future teams and enough corners to promote
eligibility if filtering were wrong, exclude all same-day matches, guard target
identity even with a wrong date, inspect every fitting/selection/eligibility
input, and show filtering occurs before typing malformed future values. Other
checks cover unknown validation labels, probability denominators, frozen-plan
hash enforcement and future 360 records not changing the unavailable section.

A post-publication check independently projected only source date/identity
columns and reconciled all 1,655 historical corner keys and 156 match IDs.
It verified source, code, selection-plan and all four generated artifact hashes.
An additional probe appended **43 invented excluded records** (target, same-day,
misdated-target and future records) to the real past-only history. Recomputing
the same past-only view preserved every analytical quantity, fitted estimate
and eligibility decision. Invented records were copied from prior data; real
target or future outcomes were not opened. The original data file was not changed.

The full source CSV hash necessarily includes future file bytes as an identity
check. Changing those bytes would change provenance or fail the frozen input-hash
guard; it does not mean the dossier uses those outcomes. The included analytical
scope is separately recorded by match IDs, corner keys and a history fingerprint.

## Artifacts and reproduction

In the original repository:

- `outputs/dossier-first-cutoff-safe-prematch/dossier.md`: readable dossier.
- `dossier.json` in that folder: complete structured results and selection scores.
- `historical_corners.csv`: all pooled supporting historical IDs and labels.
- `history_roles.csv`: match identities, dates and selection/refit roles.
- `provenance.json`: cutoff, included match/corner IDs, code and input hashes,
  settings and output hashes.
- Adjacent `dossier-first-cutoff-safe-prematch-selection.json`, execution log and
  `dossier-first-cutoff-safe-prematch-verification.json`: frozen choice and checks.

Base Git SHA is `6a64fbdde56131077c66d245b2cb59cad60135a0`; new dossier files and
tests remain uncommitted and are identified by exact source hashes in the plan
and provenance. The branch is `codex/cutoff-safe-prematch-dossier`. Existing
extraction, predictive sensitivity, setup and audit artifacts remain unchanged.

Run from this feature worktree with the original repository's `.venv` Python:

```powershell
$project = Split-Path (git rev-parse --path-format=absolute --git-common-dir) -Parent
$python = Join-Path $project '.venv/Scripts/python.exe'
& $python -B -m src.dossier select `
  --corners "$project/outputs/leagues-2015-16-corners/corner_summary.csv" `
  --coverage-manifest "$project/data/ingested/leagues-2015-16/coverage_manifest.json" `
  --selection NEW_SELECTION_JSON --output NEW_DOSSIER_DIRECTORY
& $python -B -m src.dossier build --selection NEW_SELECTION_JSON
& $python -B -m unittest discover -s tests -p test_prematch_dossier.py -v
& $python -B -m unittest discover -s tests
```

Existing selection files and dossier destinations are refused. No extraction
rerun, commit, push, merge, human-judgment inspection or target-match scoring was
performed. This is a historical prematch simulation using match-date restrictions
on a pinned provider snapshot, not proof of what that provider published at the
original kickoff. Zero-corner appearances are not observable from a corner-only
table; missing dates are excluded; unknown labels may be non-random. The
independent human audit is still pending.
