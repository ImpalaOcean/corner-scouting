# Diego integration validation

Recorded on 2026-10-29 from the completed integration checks and source reviews reported in this workflow.

All 37 tests passed. The loader processed two matches and identified nine corners; the extraction module consumed its output and produced nine corner summaries. Results are retained in `outputs/diego_integration_01/`, with source-file references in `data/ingested/diego_integration_01/batch_manifest.json`.

Both matches had populated competition, season, and match-date fields, with zero rows missing these values. The metadata matched the source records pinned at revision `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`:

| Match ID | Fixture | Competition | Season | Match date | Source |
| --- | --- | --- | --- | --- | --- |
| 3857286 | Qatar–Ecuador | FIFA World Cup | 2022 | 2022-11-20 | [Match records](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/matches/43/106.json) |
| 3930158 | Germany–Scotland | UEFA Euro | 2024 | 2024-06-14 | [Match records](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/matches/55/282.json) |

Three practice sequences from match 3930158 each contained one attacking shot and zero goals within 15 seconds, matching the [pinned source events](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/events/3930158.json). The shots followed corners at 34:19.531, 11:03.517, and 20:20.182 by 4.339, 3.567, and 3.423 seconds respectively. A further shot 26.081 seconds after the 11:03 corner was correctly excluded from that window. Detailed practice findings remain local in `data/audit/diego-practice.md`.

Off-target shots without an explicit `out` flag remain a boundary question. The current extractor reports `time_limit` when the next event exceeds the cap, which follows the implementation but does not establish that play continued for 15 seconds. No extraction rule was changed in response to the practice review.

These checks establish sample integration, not completion of larger-corpus validation or the formal audit. Before the 100-sequence audit, Diego and Asaad must agree on the same sampled corner IDs and review instructions, including how to judge the open boundary question. Each reviewer should record judgments independently and compare them only after both reviews are finished; that coordination is still pending.
