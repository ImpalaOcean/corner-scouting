# src/setups/

Static corner setups from StatsBomb 360 freeze frames (snapshots only: no player
runs, no marking classification).

Maintained by Utkarsh Kohli (took over from Ebtesam Aloubid, who covered `src/data/`).

Run from the repository root:

    python -m src.setups --corners outputs/sample_corners/corner_summary.csv --three-sixty-dir data/raw/<revision>/data/three-sixty --output outputs/sample_setups

Reads Diego's `corner_summary.csv` and the 360 files downloaded by `src/data`; writes
`setup_summary.csv` (`setup_summary_v1`) and `setup_report.json`. See `docs/360-coverage.md`
for definitions, thresholds, exclusion reasons and limitations.

Modules: `geometry.py` (pitch, zones, visible-area coverage), `features.py` (per-corner
features), `cluster.py` (deterministic grouping + stability), `loader.py` (read inputs),
`pipeline.py` (join, filter, cluster, report), `__main__.py` (command line).
