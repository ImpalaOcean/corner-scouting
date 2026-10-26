# src/corners/

This folder contains the corner extraction pipeline, including event filtering and canonical corner-table construction.

Owner: Diego Fuentes

Responsibilities:
- Identify corner events in StatsBomb event streams.
- Build the shared corner table schema used by all teammates.
- Keep the `extract_corners.py` workflow aligned with the team data contract.

First deliverable (by November 1):
- A script that extracts a valid corner table from a sample match and writes a CSV/Parquet output.
