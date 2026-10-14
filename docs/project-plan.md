# Project Plan

## Project scope

Analyze team corner-kick tendencies and outcomes using StatsBomb open data. Deliver a reproducible analysis pipeline that:

- Downloads and caches StatsBomb match/event data programmatically (no large datasets checked into Git).
- Cleans and standardizes event-level data for corner-kick extraction.
- Produces reproducible exploratory analysis, visualizations, and per-team corner dossiers.
- Evaluates outcomes and tendencies (e.g., set-piece goals, shot creation, defensive patterns) and documents findings.

## Team responsibilities

Assign each responsibility to a team member (use GitHub usernames). Replace the placeholders below.

1. Project lead — coordinates milestones, merges PRs, and keeps the team on schedule.
2. Data acquisition & storage — scripts to download StatsBomb data and store raw files outside the repo.
3. Data cleaning & preprocessing — event-level cleaning, corner extraction, and canonical schemas.
4. Analysis & modeling — compute metrics, run statistical tests, and build simple predictive models.
5. Reporting & outputs — create figures, notebooks for dossiers, and assemble the final report.

## Deadlines / Milestones

- 2026-10-21 — Finalize project scope, confirm teammates and responsibilities, and set up repo structure.
- 2026-10-28 — Complete data acquisition scripts and initial data ingestion for at least two competitions.
- 2026-11-11 — Finish exploratory analysis and baseline models; produce sample team dossier.
- 2026-11-18 — Finalize figures and all team dossiers; prepare slides or final report draft.
- 2026-11-25 — Final edits and submission.

## Communication & workflow

- Branching: feature/<short-task> branches; open pull requests and request at least one reviewer before merging to main.
- Issues: use GitHub Issues to track tasks, bugs, and enhancements.
- Meetings: weekly sync (pick a recurring time) and ad-hoc Slack/Discord for quick questions.

## Notes / TODO

- Replace role placeholders with actual GitHub usernames.
- Add contact information and meeting cadence.
- Add dataset access instructions (credentials or locations) in a secure manner.
