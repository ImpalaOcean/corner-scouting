# Team playbook

This repository is organized around a shared data contract and five parallel workstreams. The goal is to keep each teammate independent while still producing a single merged corner-analysis pipeline.

## Team responsibilities

| Teammate | Folder | Responsibility | First deliverable | Deadline |
| --- | --- | --- | --- | --- |
| Utkarsh Kohli | `src/data/` | Data acquisition, caching, and ingestion | Working loader for sample StatsBomb data | By November 1 |
| Diego Fuentes | `src/corners/` | Corner extraction and canonical corner table | Extracted corner table from sample match | By November 1 |
| Asaad Faris Husein | `src/analysis/` | Metrics, analysis, and validation | Baseline analysis notebook or script | By November 1 |
| Ebtesam Aloubid | `src/setups/` | Setup patterns and StatsBomb 360 routine classification | Setup summary table | By November 1 |
| Mohamed Hamail | `src/dossier/` | Reporting, visual summaries, and team dossiers | Draft dossier for one team | By November 1 |

## Working principles

- Everyone should work in their own feature branch and open PRs for review.
- The shared corner-table schema is the contract that all components must follow.
- Analysis and dossier work can proceed using fixture data before the full extractor is complete.
- Components should be reviewed by a teammate before merging to `main`.

## Milestones

- By November 1: each teammate has a working first version of their component.
- By December 18: all five contributors provide material for the ACM paper and each component is reviewed by another teammate.

## Independent audit task

Two members are assigned to independently auditing 100 sampled event sequences:

- Diego Fuentes
- Asaad Faris Husein

These audits are separate from the routine code review and are meant to validate event labeling quality and edge-case handling.

## Suggested workflow

1. Keep the existing `src/extract_corners.py` file intact as the core extraction script.
2. Build around the canonical data contract in `docs/data-contract.md`.
3. Use example fixtures from `tests/fixtures/` for early-stage development.
4. Merge only after local validation, code review, and a brief check that the project-level schema still matches expectations.
