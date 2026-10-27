# Metadata, batch processing, and Parquet (Diego)

This runner is local-only. It does not implement Utkarsh's downloader or modify
any other teammate's module. Use provider event files, not the shared synthetic
multi-row corner_events CSV. The existing sample runner remains available.

## Quick start — no teammate output required

From the repository root, in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r src/corners/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_corner*.py" -v
.\.venv\Scripts\python.exe src/run_corner_batch.py --manifest tests/fixtures/corner_batch/manifest.json --output outputs/batch_demo --parquet
```

The fixture is entirely invented. It contains one corner followed by a shot,
plus a zero-corner match. It demonstrates operation, not soccer findings.
The fixture run must produce one summary and a manifest recording two matches.
Choose a new --output directory for every run. Existing directories are rejected.
You may omit --parquet to run CSV-only without installing any dependencies.
Parquet is tested with pyarrow 23.0.1; its version is pinned in the module's
requirements file. Extraction code still uses only Python's standard library.

## Handoff input manifest

Create a JSON file with this shape:

```json
{
  "matches": [
    {
      "match_id": 3857276,
      "events": "events/3857276.json",
      "metadata": "metadata/3857276.json",
      "source_revision": "optional upstream commit or provider revision"
    }
  ]
}
```

Relative paths are resolved from the manifest file's directory, not from the
terminal's working directory. Absolute paths are also accepted. Each match ID
must be unique and must correspond to the supplied event file. Provider event
arrays do not themselves verify the match ID. source_revision is recorded as
supplied, not independently verified; each actual event file is SHA-256 hashed.

Metadata can be an inline object or a JSON-object file. Accepted flat keys:
match_id (optional consistency check), competition_id, competition_name,
season_id, season, match_date, home_team, away_team. Example with invented data:

```json
{
  "match_id": 1,
  "competition_id": 999,
  "competition_name": "Synthetic League",
  "season_id": 999,
  "season": "Synthetic Season",
  "match_date": "2026-01-01",
  "home_team": "Example A",
  "away_team": "Example B"
}
```

A single provider match object is also accepted: nested competition,
season, home_team and away_team are normalized. A whole provider matches array
is not accepted as per-match metadata; select the matching object upstream.
Conflicting IDs/names, mismatched match IDs and invalid dates are errors.
Dates must be YYYY-MM-DD. Missing fields stay null/blank. Never use matches
missing date/competition/season metadata in chronological predictive evaluation.
Metadata normalization is separate from build_corner_summaries, preserving the
existing extraction API. The batch module attaches metadata to its returned rows.

## Outputs

- corner_summary.csv: stable header even when every match has zero corners.
- corner_summary.parquet: optional typed table, including native list columns.
- run_manifest.json: input-manifest hash, per-file event hashes, normalized
  metadata and metadata hash, declared source revision, event/unique-event counts,
  corner/shot/goal counts, parameters and no_corners status for empty matches.

Batch schema = existing summary columns plus competition_id, competition_name,
season_id, season, match_date, home_team, away_team. It is explicitly labelled
corner_summary_batch_v1 in the run manifest. No shared contract or fixture has
been silently replaced. Agree on the final mapping with analysis/dossier owners.

CSV event-ID lists are JSON arrays; blank cells represent null. Parquet keeps
list<string>, int64, float64 and boolean types using an explicit schema, including
when all rows or a column are empty. Dates remain ISO strings in both formats.
An uncapped window is null, and the run manifest records that explicitly.

The runner sorts each match by period, timestamp and provider index before using
the existing extractor. It reads/processes one match at a time and streams its
rows to CSV/Parquet. The match manifest is held in memory. This is a bounded
per-match design, not a measured corpus-throughput claim.

Any missing/corrupt event file, missing ordering fields or extraction error fails
the whole run. Temporary output is removed; no partially successful final run is
published. Existing run folders are protected, including when an input is empty.

## Sensitivity runs

Use the same local manifest for each run so input data remains fixed:

```powershell
foreach ($window in @("10", "15", "20", "uncapped")) {
    .\.venv\Scripts\python.exe src/run_corner_batch.py --manifest data/my_manifest.json --output "outputs/batch_window_$window" --window $window --parquet
    if ($LASTEXITCODE -ne 0) { break }
}
```

Use --short-limit 10, 15 or 20 for the short-corner threshold comparison; give
each setting a distinct output folder. Creating these outputs is extraction
work. Statistical comparisons belong to the analysis workstream.

## Validation and work remaining

Nine batch tests plus the original 15 extraction tests pass with the optional
Parquet dependency installed. They check metadata forms/conflicts/dates,
duplicate match IDs, relative input paths, zero-corner outputs, preserved files,
failed-run cleanup, shuffled input and typed Parquet/list round trips.

Two real local event files were also processed together: matches 3857276 and
3857271 produced 16 corners, five shots and one goal. CSV and Parquet counts and
ID lists agreed. Their raw files and generated results are not checked in.

This completes the first implementation of metadata handoff, local batch runs,
and CSV/Parquet output. It does not complete full-corpus validation, the independent
100-sequence audit with Asaad, sensitivity interpretation or the paper section.
Team approval of the interface is still required before integration is frozen.
