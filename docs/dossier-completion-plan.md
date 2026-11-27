# Remaining dossier examples: inventory and proposed frozen plan

Prepared November 27, 2026; no fixtures selected, outcomes examined or new dossiers built in this task. Reuse [prematch.py](https://github.com/ImpalaOcean/corner-scouting/blob/77af6f910935b6b12232b3e60183210c7f175e56/src/dossier/prematch.py) rather than a parallel implementation. Methods are described in [first-cutoff-safe-prematch-dossier.md](https://github.com/ImpalaOcean/corner-scouting/blob/77af6f910935b6b12232b3e60183210c7f175e56/docs/first-cutoff-safe-prematch-dossier.md) and [dossier-evaluation-plan.md](https://github.com/ImpalaOcean/corner-scouting/blob/77af6f910935b6b12232b3e60183210c7f175e56/docs/dossier-evaluation-plan.md).

## Verified inventory

Local artifact `R/outputs/dossier-first-cutoff-safe-prematch/dossier.json` contains fixture 3754117, Aston Villa–Arsenal, cutoff 2015-12-13: two distinct team views, not five. Its four output hashes match the saved provenance. The supplied hash-verified systems ZIP contains seven dossier JSON copies (clean reproduction, warmup and five measured builds), all for the same fixture and same two teams. Those are reproduction/timing repetitions, not new team examples. No other local `outputs/**/dossier.json` was found in the original repository scan; unshared teammate artifacts are not ruled out. Reviewers must confirm whether five team views packaged in paired-fixture dossiers satisfy the proposal wording; repeated teams never increase distinct-team count.

## Outcome-blind selection policy proposed for the remaining teams

1. Freeze input SHA-256 for the existing primary league corner CSV and coverage manifest, code SHA and this policy in a NEW selection-plan JSON before any build. Primary window=15, short=15, seed=5118, bootstrap=1000; no full-season parameters or retrospective tournament centers.
2. Read a projection containing only match ID, ISO date, competition/season, home/away identities, corner keys/team identities and coverage. Never inspect target delivery, shot, goal, score or xG values for selection. Corner counts are coverage; outcome frequencies are not selection criteria.
3. Restrict to Premier League 2015/16 first to reuse the selector's existing scope. Sort fixture dates then numeric match ID. For each candidate exclude its entire date and all later matches; split remaining distinct matches 60/20/20 by existing integer rules. Require each target team >=10 corner-observed training matches, >=30 training corners and at least one validation corner. Coverage eligibility does not guarantee validation has known deliveries; report unavailable metrics if necessary without replacing a fixture for an attractive output.
4. Skip a qualifying fixture only if it adds no new team beyond the inventory. Select the earliest qualifying fixture that adds a team, then repeat until at least five distinct teams are covered. Record all candidate IDs, dates, coverage counts and rejection reasons. If a paired fixture yields a sixth team, keep it; do not cherry-pick exactly five after seeing profiles. Stop and disclose insufficient support rather than lowering thresholds.
5. Freeze each chosen fixture/cutoff before build. Fit only strictly past rows: training-prefix eligibility, validation-only grid selection, then refit on all earlier history. Keep all target-date outcomes out of the dossier. No outcome-based replacement; failed builds retain their error record for investigation.

## Existing CLI boundary and reproducible execution plan

Current `python -B -m src.dossier select` always chooses the first qualifying PL fixture and refuses overwrite; rerunning it on the unchanged corpus would select the SAME existing example. It has no explicit-fixture or additional-team option. Therefore the policy above is not claimed executable as-is. Mohamed should extend the existing selection entry point to accept the predeclared additional-team policy (or validated explicit fixture plan), keeping hash/code-plan checks and adding tests. Do not fabricate a selection JSON to bypass the builder's checks. No source change or fitting is performed here.

After a reviewed selector extension, freeze exact code and CLI help and append the executable selection command. The existing build interface remains:

```powershell
# From an isolated checkout at the recorded implementation SHA, using the original .venv.
& $Python -B -m src.dossier build --selection $AbsoluteNewSelectionJson
```

`$Python` is the original repository's absolute `.venv/Scripts/python.exe`; the selection plan must name a new output destination under `outputs/dossier-five-team-examples/` and bind the original absolute primary CSV/coverage paths. Refuse existing plans/destinations. The generation command is a future plan, not a command run during this documentation task.

For every future build verify fixture/cutoff, all included dates < cutoff, no target IDs, settings/input/output hashes, history keys, training/validation counts, eligibility/exclusions, selected alpha/beta and grid-edge warnings. Mutating target/future outcomes must leave analytical outputs, eligibility and fitting unchanged (source file hashes may change). Repeat the existing dossier focused tests plus new selector coverage tests. Do not use sample counts as evidence of target prediction or usefulness.

## Independent reader evaluation and handoff

Use [dossier-reader-evaluation-form.md](dossier-reader-evaluation-form.md) and separate copies of [dossier-reader-recording-template.md](dossier-reader-recording-template.md) for Mohamed and Asaad. Freeze dossier hashes before reading. Keep individual answers separate until both are complete; then report item-level counts, limitations and unresolved issues. Neither this task nor Codex supplies their judgments. Internal teammate checks are not coach validation or proof of tactical utility. A rolling prematch predictive check remains optional and distinct; predeclare its fixtures/metrics before executing, or scope it out and cite the existing season-level model results.

Questions: Mohamed—any unshared distinct-team examples, and should the deliverable be five per-team views or five separately rendered files? Asaad—confirm independent reader role and whether a rolling predictive check is in scope. Utkarsh—confirm that league pre-cutoff 360 is unavailable rather than reusing retrospective centers. Diego—approve the outcome-blind selection plan before generation. Mo—confirm reproducible commands and separate timing scope; repeated timed examples do not satisfy the team count.
