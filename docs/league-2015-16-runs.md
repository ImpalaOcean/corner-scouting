# League event-data runs (2015/16)

These configurations use the existing data loader and corner batch extractor.
Source revision: `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. No ingestion or extraction code changes.
This is a run plan, not evidence of a completed download.

## Selection

| Competition | Competition ID | Season ID | Listed matches |
| --- | ---: | ---: | ---: |
| Premier League | 2 | 27 | 380 |
| La Liga | 11 | 27 | 380 |
| Serie A | 12 | 27 | 380 |
| Ligue 1 | 7 | 27 | 377 |
| Total | | | 1,517 |

Counts were checked against the pinned provider match catalogues. Ligue 1 is
three matches short of a normal 380-match season; document this source gap
even if the loader successfully ingests every listed match. Actual usable
matches and corner totals must be measured. Do not assume a 15,000-corner total.

These leagues supply event-based descriptive and predictive analysis. The
existing World Cup 2022 / Euro 2024 run remains the separate spatial dataset.
`download_360=false` means frames were not requested; a zero 360 count in this
run is not a measured missing-frame rate.

## Run Premier League first

From the repository root in Windows PowerShell (activation is optional):

```powershell
.\.venv\Scripts\python.exe -m pip install -r src/data/requirements.txt -r src/corners/requirements.txt
.\.venv\Scripts\python.exe -m src.data --config configs/data/premier-league-2015-16.json --parquet
```

Wait for ingestion to finish. If it exits nonzero, inspect its error and coverage
report before extraction; do not automatically continue after incomplete coverage.

```powershell
.\.venv\Scripts\python.exe src/run_corner_batch.py --manifest data/ingested/premier-league-2015-16/batch_manifest.json --output outputs/premier-league-2015-16-corners --window 15 --short-limit 15 --parquet
```

Validate the starter outputs before the larger run. Downloads can be quiet.
Existing output folders are protected: never delete good results simply to
repeat a command. For a repeat, use a new loader `--output` and update the
extractor manifest path accordingly; give extraction a new output directory.

## Expand to all four leagues

```powershell
.\.venv\Scripts\python.exe -m src.data --config configs/data/leagues-2015-16.json --parquet
```

Again, inspect successful completion and coverage before proceeding:

```powershell
.\.venv\Scripts\python.exe src/run_corner_batch.py --manifest data/ingested/leagues-2015-16/batch_manifest.json --output outputs/leagues-2015-16-corners --window 15 --short-limit 15 --parquet
```

The shared pinned cache reuses Premier League downloads. The full output
already includes Premier League: do not append the starter table to it.
Without source failures the full selection is 1,517 matches. Confirm what
was actually usable rather than treating catalogue counts as execution evidence.

## Validate and hand off

- Reconcile loader and extraction match/corner counts, including per-season
  counts and zero-corner matches. Use the manifests for match coverage.
- Check unique `(match_id, corner_event_id)` keys, required metadata,
  consistent settings, and CSV/Parquet agreement.
- Profile unknown delivery labels and raw-field completeness by season.
- Preserve coverage reports and extraction run manifests, source/code revisions,
  file hashes and commands. Keep generated data outside Git.
- Give Asaad the final table and provenance for eligibility and prediction
  evaluation. Compute training eligibility after chronological splitting;
  38 listed matches alone is not proof a team passes every threshold.
- Keep alternative-window runs separate from the primary 15-second table.
- Build the combined tournament + league audit table only after both are
  validated. Use the full four-league output, not the Premier League starter
  in addition, and rebase relative event paths when combining manifests.

The independent 100-sequence audit, final sensitivity analysis and final
predictive evaluation remain pending until actually executed and reviewed.
