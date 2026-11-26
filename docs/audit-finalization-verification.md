# Diego–Asaad audit finalization verification

Verified read-only on 25 November 2026. Branch `codex/finalize-independent-audit` is based on current main `bdcba9a0eaea63196848d6d2458876643f8b4d46`. The original checkout remains unchanged. The paper audit updates are maintained separately on existing draft PR #29, branch `codex/paper-evidence-draft`, preserving its earlier commit `c1a96342ba90c6b5f7ca0462110eeff53e81bf75`. This focused audit branch contains only the protocol, supplied report and verification note. The original five-file state was preserved before separation. No experiment, sampling, extraction, clustering or benchmark was rerun.

## Preserved final artifacts

Local artifact root R: `C:\Users\diego\OneDrive\Documents\CLASSES FOLDERS\Fall 26\COMP 4900H - Big Data Management\04 - Projects\corner-scouting`.

The finalized report is preserved verbatim as [audit-report.md](audit-report.md). Its companion structured evidence remains gitignored, following the repository's documentation/output convention. The original Downloads files also remain unchanged.

| Preserved artifact relative to R | SHA-256 |
| --- | --- |
| `outputs/audit-finalized-2026-11-25/audit_report.md` (also `docs/audit-report.md` in this branch) | `e86cdabd7a98c705a173665afe6419f4e63bfd87cc3f43450df8bcc4868aa7c9` |
| `outputs/audit-finalized-2026-11-25/call_review_worksheet_resolved.csv` | `032fb5b630d8578d5560067ecb18b3219211b6b530873dbf5f034f30b16bb07b` |
| `outputs/audit-finalized-2026-11-25/audit-protocol.md` (supplied proposal, not a replacement for newer main) | `76a2ec875b28514554cdb550513477bd1c48ce83f14d6b081e2c493347563bcf` |
| `outputs/audit-finalized-2026-11-25/audit-protocol.diff` (supplied patch) | `07fbf2742950ee2e963e53cacad6a6d77a4cb7b0d7f96e0c76c572a55f47f935` |

`outputs/audit-finalized-2026-11-25/finalization_manifest.json` records input paths/digests, validation, source checks and preserved artifact hashes. `source_output_investigation.json` records each source-reference finding and its JSON locator. These are new verification records, not retroactive alterations to earlier provenance. The report's statement that the protocol must be applied on `feat/evaluation` is preserved historical author text; actual integration is on this isolated current-main branch.

## Evidence verification

### Shared review bundle

The compact `diego-asaad-finalized-audit-2026-11-25.zip` is published separately in the established [project Drive folder](https://drive.google.com/drive/folders/1VqjDC-j2P2vSXZmH6q83Rtac_39KSRYG). Open that folder using the project-authorized Google account and locate the exact filename; the audit PR supplies its SHA-256 and direct access link. Existing folder permissions are retained. The ZIP contains these audit documents, the six-row consensus worksheet, aggregate pre-discussion agreement and provenance/impact records. Raw provider JSON, original reviewer sheets, frozen master, preparation worksheet, caches and analytical outputs are excluded. Generated evidence is not committed to Git. Its manifest records file sizes and hashes; hashes establish content identity, not ground truth or reviewer independence.

| Check | Result |
| --- | --- |
| Frozen master vs recorded sample hash | Pass: `fe7d9119b7b5c44c8e443d4d8fd819abd5f26c8a8a100f276f7fc56bb5bcf011` |
| Diego's original review | 100 distinct corners; 400 valid complete judgments; required notes satisfied; immutable master fields unchanged. SHA-256 `f1fd2446e2e212d476bf669f71a423beb30af1ef40626619b7d60a2943112cd7` |
| Asaad's original review | Same checks pass. SHA-256 `0e07b615d120698d5c6bfe802634aa2eb53bc113dbba12f2c237ece0ca347a70` |
| Original sample provenance | SHA-256 `8a9bcf69566bb8c8818e3f7447a66558cfa71ede94caf1bb5bfae0851aaa280e`; matches earlier preparation receipt |
| Existing pre-discussion agreement | All four fields: 100/100 agreement, 400/400 paired judgments in total; both reviews are all `y`; kappa remains undefined. Agreement/differences files match their saved preparation receipts; no new agreement run |
| Six resolved rows | IDs 35, 57, 59, 74, 79, 83; all `resolution=y`, reason and JSON supporting IDs populated; `confirmed: Diego; Asaad (2026-11-25)` recorded on every row. Original identities, judgments and notes match the untouched preparation worksheet |
| Source support | All supplied supporting UUIDs exist in the respective raw JSONs. Each of the six source files matches its sidecar. This is not a fresh independent derivation of every chain |
| Original preservation | Before/after hashes match for both reviews, master/provenance, original call worksheet, agreement, disagreements, preparation receipt and README, plus primary/alternative corner tables and extraction manifests |

The confirmations are the reviewers' supplied record; this verification does not claim to authenticate who typed them or reconstruct the independence of their historical work. Six rule-consistent resolutions and no identified errors are the audit's recorded outcome, not an unbiased corpus accuracy estimate or independent football ground truth.

## Source recovery: audit #1

The restored pinned-cache `data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/events/267576.json` matches both its `.sha256.json` sidecar and the league coverage/extraction receipts:

`6de94032e22da90bb4ef4d0eca01295c0e42198cc5fd63332f0711d07080eecf`.

The altered backup `267576.json.altered-local-2026-11-19` remains present with SHA-256:

`d08a43c9a3cd983c6e1a2b0b264523a5093c6a2a41c668155cb379a6b5437c9f`.

A structural comparison of the two files finds one differing event among 3,784: provider index 2048 has `id=" "` in the backup and `id="817898d0-a9a3-499c-89c1-2af2556cad5b"` in the restored version; all other event attributes compare equal. This supports byte identity with the locally recorded original. Recovery was already performed before this integration, not by this task. No upstream download, raw repair, or permission change was performed. The origin of the alteration and its precise exposure interval are not established by timestamps. The report's broader 1,632-sidecar census was not independently repeated here.

## Saved-output impact investigation

Scanned the local `outputs/`, `data/ingested/` and `data/audit/` JSON receipts and logs, decoding UTF-16 logs when marked by a BOM, plus JSON/log records in the supplied Mo systems ZIP. The investigation identified 61 source-referencing files, with no access errors in this scan. It searched source records for match 267576 and both exact digests; dates were not used as evidence of consumed bytes. No extraction or other saved output was regenerated.

| Output group | Evidence and classification |
| --- | --- |
| Primary and 10/20/uncapped league extraction | Each `run_manifest.json` records the original digest for match 267576. No altered digest recorded. This is positive recorded input identity, not a timestamp inference |
| Primary and alternative league prediction | Current input-table hashes and all 11 recorded output artifacts per analysis match their existing receipts. They consume the saved corner tables, not raw 267576 JSON. No evidence of alteration through the raw cache |
| Saved dossier | Source is the unchanged saved league corner CSV, not raw events; cutoff also precedes this January 2016 match. Original dossier outputs were not changed or rerun |
| Tournament coverage/shared clusters | This league match is outside their tournament population; the corrupted league event is not an input |
| Automated audit reviews and November 16 access verification | Records contain actual and expected original digests. They do not record the altered digest. Preserve those historical receipts unchanged |
| Combined audit preparation | Previously inaccessible files are now readable and match all three expected hashes in `sample_provenance.json`: combined CSV `1a8b686c…f74ddc8`, batch manifest `0c15dba9…16241a`, preparation `cb27eafb…a04aa5`. Its source-event map records the original digest |
| Mo's November 20 league comparisons, benchmark pairs and clean reproduction | Archived runtime/source snapshots and Python/SQL manifests record the original digest; none records the altered digest. These were on Mo's separate machine. This corroborates their recorded input identity; no experiments were reproduced here |
| Human review #1 and supplied recovery report | Notes explicitly describe a fallback/altered record, and the final report documents restoration. These are known source-traceability qualifications, not demonstrated regenerated extraction/model errors. Retrospective proof of precisely which raw bytes each human inspected is unavailable |
| Path-only batch/access manifests and ad-hoc/manual event views | A path without a content receipt cannot establish which bytes were read after November 19. Treat actual historical consumption as unverifiable, not as proof of no impact or of corrupted computational output |

No scanned computational input receipt identifies the altered digest. Therefore **no affected saved computational run is identified**, while unlogged/manual operations and omitted external artifacts remain unverifiable. This is not a universal assertion that nothing used the altered file. The snapshot does not scan arbitrary user folders, private cloud logs, unsaved terminal history, or every CSV body. The retained altered backup is evidence, not a candidate to repair or delete. Any later-discovered run recording its digest requires investigation before regeneration is proposed.

## Documentation integration and remaining scope

The protocol preserves current main's context-boundary evidence wording and frozen-master validation safeguards. Its November 25 block is explicitly post-audit: Half End is a stoppage only after earlier-priority checks pass, and nested pass outcome `Out` without top-level `out` is not a boundary under the current rule. The preparation date is tied to provenance rather than inventing a checker execution date. Neither definitions nor pre-discussion answers were changed.

The separate paper updates in draft PR #29 record the completed enriched source-consistency audit and separate the six confirmed resolutions from pre-discussion agreement. The original report is preserved as supplied; its raw-chain derivation and full-cache census claims remain author-reported except for the receipt/UUID/structural checks specified above. Paper sections unrelated to the audit originated in the November 19 draft and still need owner refresh against current-main systems/spatial work; this audit integration does not certify every other paper claim as current. External references and other remaining evaluation requirements are not silently marked complete.
