# src/dossier/

This folder is for the final team dossiers and reporting materials that summarize findings for each team.

Owner: Mohamed Hamail

Responsibilities:
- Compile the per-team scouting dossier and narrative recommendations.
- Build polished plots and summary tables for the final paper.
- Ensure outputs match the agreed reporting format.

First deliverable (by November 1):
- A team-scouting template or draft dossier for one team using example data and the shared corner metrics.

## Cutoff-safe prematch implementation

The first implementation lives here (`prematch.py`, `__main__.py`) and reuses
`src.analysis` loading, summaries, chronological splits, training eligibility,
selection grid and model formulas. No full-season fitted parameters are loaded.

From the feature worktree, use the original project's `.venv` Python:

```powershell
python -B -m src.dossier select --corners ABSOLUTE_PRIMARY_CSV --coverage-manifest ABSOLUTE_LEAGUE_COVERAGE_JSON --selection NEW_SELECTION_JSON --output NEW_DOSSIER_DIRECTORY
python -B -m src.dossier build --selection NEW_SELECTION_JSON
```

`select` reads only projected dates, identities and corner coverage. It fixes the
earliest qualifying Premier League 2015/16 fixture and records the cutoff, source
hashes, code hashes and policy before any dossier is generated. Both teams must
have 10 matches/30 corners in the selection-training prefix and validation corner
coverage. Target results or delivery patterns are not selection criteria.

`build` excludes the target ID and all rows on/after its date before outcome typing,
validation, eligibility, pooling or fitting. Existing 60/20/20 chronological splits
are applied within past-only competition-season history: select alpha/beta on the
first 60% training and next 20% validation, do not score the remaining past 20%,
then refit on all strictly earlier history for the target fixture. Eligibility
remains based on the selection-training prefix. Whole target dates are excluded
because kickoff ordering is not supplied. Undated rows are excluded.

Outputs are a readable Markdown dossier, structured JSON, included historical
corner IDs, historical selection roles, and a provenance manifest. New folders
are staged/published safely and existing destinations refused. Descriptive
intervals use 1,000 match-bootstrap draws and seed 5118. Known-category delivery
predictions and all-corner shot predictions retain the documented denominators.

The league 360 section is explicitly unavailable when suitable verified pre-cutoff
frames are not supplied. Downloads disabled/not-requested is not measured 0%
provider availability. No full-tournament retrospective centers or shares are read;
a future setup view requires a separate strictly pre-cutoff fit.

Tests: `python -B -m unittest discover -s tests -p test_prematch_dossier.py -v`.
They mutate target/future outcomes, append future teams/corners, check same-day
exclusion, verify all fitting/eligibility inputs, and exercise filtering before
typing and source-hash/selection-plan enforcement. Full source-file provenance
hashes necessarily change if future file bytes change; the dossier's analytical
content and fitted quantities do not use those future values.
