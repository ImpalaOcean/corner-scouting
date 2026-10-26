# src/data/

This folder is for loading raw StatsBomb data, storing local cache files, and manufacturing the canonical input tables used by the rest of the project.

Owner: Utkarsh Kohli

Responsibilities:
- Download or cache competition, match, and event data from StatsBomb.
- Validate file integrity and schema on ingestion.
- Produce the baseline event files that downstream modules can consume.

First deliverable (by November 1):
- A working loader or notebook that reads a sample match and outputs a cleaned event table.
