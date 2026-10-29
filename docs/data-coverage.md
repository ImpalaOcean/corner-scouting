# Data Acquisition and Coverage

This module implements the project's data acquisition, caching,
validation and ingestion track.

## Source

Data source: https://github.com/hudl/open-data

Pinned source revision:
4b73468fc5b0f1950f9f66fada70ad3a4f9327cb

The loader downloads competition, match, event and optional
StatsBomb 360 files. Original JSON is preserved in a local cache.
SHA-256 checksums identify files and detect accidental corruption.

## Running

Run commands from the repository root.

Install Parquet support:

    python -m pip install -r src/data/requirements.txt

Run the automated tests:

    python -m unittest discover -s tests -v

Download and process the two-match sample:

    python -m src.data --config configs/data/sample.json --parquet

Run the existing corner extractor:

    python src/run_corner_batch.py --manifest data/ingested/sample/batch_manifest.json --output outputs/sample_corners --parquet

Replay cached inputs without network access:

    python -m src.data --config configs/data/sample.json --offline --output data/ingested/sample_replay --parquet

Output directories must be new. Use a different --output path
when repeating a run.

## Outputs

- events.csv: cleaned, ordered event records.
- events.parquet: typed equivalent of the CSV.
- coverage_manifest.json: file statuses, hashes and completeness.
- coverage_summary.json: coverage counts by competition, season and team.
- batch_manifest.json: input for the existing corner extractor.

Original provider attributes remain available in source_event_json.
The ingestion table does not replace the canonical corner table.

## Validation

Exact duplicate event records are removed from the cleaned table.
Conflicting records with the same event ID reject the match.
Raw JSON files are not modified.

Missing optional attributes remain null or blank.
Field completeness reports present, missing, total and fraction_present.
Corner-pass technique and height use corner passes as their denominator.
Zero denominators produce null fractions.

Missing optional 360 files are recorded without rejecting valid events.
Other download and validation failures are reported explicitly.

Finite player coordinates outside nominal pitch bounds are preserved.
A matching 360 snapshot does not establish that it meets the setup
module's visibility threshold.

Only validated, nonempty event files enter the extractor manifest.
Valid matches with zero corners are retained.

## Exit Codes

- 0: requested audit completed.
- 1: configuration, catalogue or output failure.
- 2: audit saved with incomplete coverage.

Inspect incomplete coverage before using downstream results.

## Verification

All 37 automated tests passed.

The real sample processed:
- Two matches from World Cup 2022 and Euro 2024.
- 6,671 unique events.
- Nine corners.
- Five corners with matching 360 snapshots.

The generated manifest ran successfully through the existing
corner extractor and produced nine corner summaries.
Offline replay completed successfully with the same counts.

## Remaining Work

The full-corpus configuration is provided in configs/data/corpus.json.
A full corpus download and coverage audit still need to be performed
before reporting corpus-scale findings.

Statistical evaluation, setup clustering and dossier generation
belong to the other project modules.

Credit StatsBomb and follow the source repository's data terms.
Raw downloads and generated outputs must remain outside Git.