# Tournament shared-cluster team profiles

**Full-tournament retrospective descriptions, not prematch profiles.** World Cup
2022 and Euro 2024 corners share one pooled setup-cluster vocabulary. No team was
clustered separately and k was not selected by inspecting football patterns.

## Reuse and provenance

Fetched and inspected main and remote branch inventories. `origin/feat/setups`
has no commits ahead of main; Utkarsh's existing setup pipeline is already merged.
No dedicated shared-cluster team-summary implementation was found. The new
`src/profile_tournament_setups.py` calls that pipeline once for the complete input;
it does not modify `src/setups/`, its eligibility rules, feature vectors or k-means.
The earlier delivery-coverage profiler's validated cache loader is reused.

Base code revision: `6a64fbdde56131077c66d245b2cb59cad60135a0`. Work is on
`codex/tournament-shared-cluster-teams` in the separate worktree. The run used
uncommitted wrapper and test files: their exact hashes, imported code hashes, source
revision, input paths/hashes and all 115 cached-file hashes are recorded in
`outputs/tournament-shared-cluster-teams/run_manifest.json`. The base commit alone
does not contain the new wrapper. Source revision is
`4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.

Inputs are the primary 15-second/short-limit-15 tournament corner table, its
coverage manifest, pinned cached 360 files and the prior coverage-profile
provenance/per-corner table. No data were downloaded or extraction outputs
regenerated. Corner-table SHA-256 is
`343938466196c8ad377d05eeafd0f9726ac70d269329f4fb853e9b5ac6bec0b7`;
coverage-manifest SHA-256 is
`295c84ddc368f205f5ee91eb938bc088802b9d9afdd35d2b997dc260921d7720`.

## Method and fixed settings

Exact match/event joins, coordinate orientation, visibility and player filters
come from the current setup pipeline. Bottom corners are mirrored to a common
orientation. The 18 input features are attacking outfield counts in zones 1–9,
then defending outfield counts in zones 1–9. The actor and keepers are excluded
from these zone counts. These are static snapshots, not runs or marking labels.

Unchanged defaults: k=4, minimum box coverage=0.5, minimum visible players=5,
minimum confident pooled corners=100, minimum cluster size=10, stability
threshold=0.6 and stability seed=0. K-means is deterministic, with the existing
farthest-point initialization and maximum 100 iterations; global IDs are ordered
by cluster size, with existing center tie breaks. Stability is the existing mean
ARI over ten 80% pooled subsample refits. Those diagnostic refits are not per-team
clustering and do not select k.

The original per-corner output and rounded pipeline report are retained. A
separate centers file records unrounded arithmetic means of final member vectors,
integer vector sums and denominators, and exact rational mean values. They agree
with the native report at its three-decimal precision; a post-run check also
confirmed each member is at a nearest empirical center (allowing distance ties),
so the recorded means and assignment form a Lloyd fixed point without another
clustering run. No tactical names were assigned to clusters.

For each `(competition_id, season_id, team_id, cluster_id)`, the count is membership
in that global cluster and share is **cluster count / that team's eligible
corners**. Each team receives every global cluster row, including genuine zero
counts for unused clusters. Coverage fractions use **all of that team's corners**
as denominator. If a team has no eligible corners, shares remain blank/undefined;
if the entire input has no eligible corners, the placeholder has no invented
cluster ID. Excluded corners stay in the native output and membership ledger.

## Measured coverage and reconciliation

| Competition-season | All corners | Matching frames | Eligible frames | Excluded corners | Usable/all |
| --- | ---: | ---: | ---: | ---: | ---: |
| World Cup 2022 | 571 | 302 | 302 | 269 | 52.89% |
| Euro 2024 | 512 | 290 | 289 | 223 | 56.45% |
| Total | 1,083 | 592 | 591 | 492 | 54.57% |

All 115 match files loaded and matched their pinned SHA-256 hashes. There are
491 corners with no matching frame and one matched frame excluded for low
visibility. That frame belongs to Germany, match `3930168`, corner
`6580d401-661a-426a-bbe0-824678c256b6`. No missing/corrupt files or other exclusion
reasons occurred. Unavailable files are nevertheless distinguished from ordinary
unmatched frames by the wrapper's file status and nullable matching field.

The totals reconcile exactly to 1,083/592/591. All per-match counts and all
per-corner matching/eligibility classifications agree with the previous coverage
profile; there are no discrepancies to explain away. This is reuse/reconciliation
of the same provider evidence, not an independent ground-truth audit.

## Pooled clustering and team checks

| Global cluster ID | World Cup members | Euro members | Pooled members |
| --- | ---: | ---: | ---: |
| 0 | 118 | 110 | 228 |
| 1 | 96 | 67 | 163 |
| 2 | 65 | 50 | 115 |
| 3 | 23 | 62 | 85 |
| Total | 302 | 289 | 591 |

Mean subsample stability **ARI=0.864**. All four clusters meet the existing
10-member minimum, pooled usable count exceeds 100, and stability exceeds 0.6;
the native pooled report therefore has `exploratory=false` and no native caveats.
This flag is an implementation threshold, not evidence of predictive validity.

There are **56 competition-season-team rows** (32 World Cup, 24 Euro) and
**224 team-cluster rows**. Every team has at least one eligible corner in this
actual corpus, with a range of **1–24**; all 56 sets of cluster shares sum to one
within 1e-12. Team coverage counts sum to 1,083/592/591, and summed cluster
memberships equal 591. Country IDs appearing in both tournaments remain separate
competition-season profiles while using the same global cluster IDs.

All 56 team profiles carry `team_small_sample=true` and `team_exploratory=true`:
the existing minimum-confident-corners threshold of 100 is conservatively shown
per team as a **reporting flag**, not an added eligibility filter or a claim that
the setup pipeline originally defined a team-level cutoff. Local cluster counts
below 10 are flagged separately. Native pooled non-exploratory status must not
erase these team-level caveats. No team has zero eligible corners in the real
run; synthetic tests verify its preservation and undefined-share behavior.

## Outputs and reproduction

New directory: `outputs/tournament-shared-cluster-teams/` in the original repository.

- `setup_summary.csv`, `setup_report.json`: existing setup schemas, one pooled fit.
- `cluster_membership.csv`: every corner, metadata, file/match/eligibility status,
  exclusion reasons and the shared global cluster ID (blank for excluded corners).
- `pooled_cluster_centers.json`: feature ordering, sizes, sums, exact rational and
  unrounded empirical centers.
- `team_cluster_profiles.csv`: team-cluster counts, eligible denominator, shares
  and small-sample/exploratory flags.
- `team_coverage.csv`: all/matched/eligible/excluded totals, match counts, fraction
  denominators and reason counts per competition-season-team.
- `match_files.csv`, `run_manifest.json`, `RETROSPECTIVE_ONLY.md`: cache access,
  hashes/settings/reconciliation and the explicit scope restriction.

The adjacent `tournament-shared-cluster-teams-verification.json` records post-run
hash, centroid, count and team-share checks. The adjacent execution log preserves
the CLI result. All eight generated artifact hashes and all recorded input/code
hashes were checked; existing outputs were not overwritten.

From the feature worktree, using the original repository's virtual environment:

```powershell
$project = Split-Path (git rev-parse --path-format=absolute --git-common-dir) -Parent
$python = Join-Path $project '.venv/Scripts/python.exe'
& $python -B -m src.profile_tournament_setups `
  --corners "$project/outputs/wc2022-euro2024-corners/corner_summary.csv" `
  --coverage-manifest "$project/data/ingested/wc2022-euro2024/coverage_manifest.json" `
  --frames-dir "$project/data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/three-sixty" `
  --coverage-profile "$project/outputs/tournament-360-delivery-coverage/provenance.json" `
  --output "$project/outputs/tournament-shared-cluster-teams"
```

This is the original command. An existing destination is refused; use a new
directory for reproduction. The script has no k-tuning or cutoff option.

Tests: **14 new focused tests passed; all 174 repository tests passed**.
Commands: `python -B -m unittest discover -s tests -p test_tournament_setup_profiles.py -v`
and `python -B -m unittest discover -s tests` using the same virtual environment.
New tests cover one shared fit and IDs across teams/tournaments, count
reconciliation, eligible-only share denominators, legitimate zero memberships,
excluded and matched-but-ineligible corners, zero-eligible teams/all-excluded
inputs, unavailable versus unmatched files, metadata isolation, input ordering,
exact center bookkeeping, retrospective labeling and local output provenance.

## Interpretation and dossier restriction

These are conditional distributions among usable frames. Missing frames are not
known to be random; prior profiling found lower coverage for short deliveries.
Visibility limits the observed players, and corners are clustered within matches
and teams. Neither the 0.864 stability value nor common IDs prove that these are
stable tactical routines, comparable population rates, or causal effects. No
team-profile confidence intervals or predictive claims are made.

**Do not feed these full-tournament centers, memberships or shares into a prematch
dossier.** For that view, select only source matches strictly before its cutoff
before feature/cluster fitting, then fit the pooled vocabulary on that past-only
data. Filtering a team's rows after fitting on future frames still leaks future
information. Cluster IDs from a new cutoff fit are not automatically comparable
with this retrospective vocabulary. A future prematch implementation must make
its fitting/assignment protocol explicit; this wrapper does not implement one.

The independent human audit remains separate and pending. Existing predictions,
extraction outputs, review artifacts and audit judgments were not changed. No
generated outputs or audit judgments are included in the source change.
