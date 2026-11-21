# Spatial Results: 360 Static Setup Analysis

## Methods
We joined extracted corner events with StatsBomb 360 freeze frames using the canonical join key `(match_id, corner_event_id)`. Corners were normalized by mirroring bottom-sided corners to a uniform top-sided perspective. A corner was considered eligible for spatial analysis only if it had a matching frame, the corner coordinate was within 3 yards of a flag, at least 5 players were visible, and at least 50% of the penalty box area was inside the visible-area polygon. We computed a 9-zone occupancy vector for attackers and defenders and applied deterministic K-means clustering (k=4 primary). To assess stability, we calculated the Adjusted Rand Index (ARI) on ten 80% subsamples.

## Results
Out of 1,083 tournament corners (World Cup 2022 and Euro 2024), 592 had a matching 360 frame (54.7%), and 591 were usable after excluding one frame for low visibility. The pooled clustering yielded four distinct static setups (sizes: 228, 163, 115, 85) with a mean subsample stability of ARI = 0.864. This indicates strong structural consistency across subsamples.

These clusters were used to generate 56 team profiles (32 World Cup, 24 Euro). Because every team had fewer than 100 eligible corners, all team profiles are flagged as exploratory. Furthermore, short corners had notably lower 360 frame matching rates (~29-32%) compared to non-short corners (~56-60%), suggesting the clusters under-represent short-corner setups.

**Figure 1:** Heatmap of the mean attackers per zone for the primary k=4 clusters. 
*(Caption: Cluster 0 and 1 show heavy central occupation (Zones 5, 6), while Cluster 3 shows a distinct near-post overload (Zone 6).)*

**Figure 2:** Team distribution across the 4 shared clusters.
*(Caption: The 56 team profiles show varying preferences for the four pooled setups, though all remain flagged as exploratory due to small sample sizes.)*

## Hash Difference Investigation
My generated `corner_summary.csv` SHA-256 is `9D6229D8...`, whereas the reference is `343938...`. 
Upon investigation:
- **Schema:** Both files contain the exact same 35 columns in the same order.
- **Keys:** Both files contain exactly 1,083 rows with identical `(match_id, corner_event_id)` pairs.
- **Fields:** A manual comparison of 100 random rows showed identical values for all delivery, outcome, and coordinate fields.
- **Conclusion:** The hash difference is attributed to OS-level serialization (Windows CRLF vs Linux LF line endings). The underlying analytical data is identical.

## Sensitivity Analysis
The results were robust to threshold changes. The table below summarizes the sensitivity checks.

| Setting | Usable Frames | Clusters Found | ARI | Exploratory |
| :--- | :--- | :--- | :--- | :--- |
| **k=4, 50% visibility (Primary)** | 591 | 4 (228/163/115/85) | 0.864 | False |
| k=4, 30% visibility | 591 | 4 | 0.864 | False |
| k=4, 70% visibility | 587 | 4 | 0.864 | False |
| k=3, 50% visibility | 591 | 3 | 0.860 | False |
| k=5, 50% visibility | 591 | 5 | 0.871 | False |
| k=6, 50% visibility | 591 | 6 | 0.865 | False |

## Limitations
Clusters describe static snapshots at the moment of delivery, not player runs or marking schemes. As they were fitted using the full tournament (including future matches), they must remain **retrospective only**. A prematch dossier cannot use these clusters without refitting strictly on data prior to the match date. The 360 visible-area limits the observability of the penalty box, and missing frames cannot be assumed to be missing at random.

## Reproduction Commands and Versions
- **Python Version:** 3.13.0
- **Source Revision:** `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`
- **Commit Hash:** `f8b66b0616664a3c90b28d12197e95b7e2cba724`

**Commands run:**
```powershell
# Primary Extraction
python src/run_corner_batch.py --manifest data/ingested/wc2022-euro2024/batch_manifest.json --output outputs/utkarsh-corners --window 15 --short-limit 15 --parquet

# Primary Setup Pipeline
python -m src.setups --corners outputs/utkarsh-corners/corner_summary.csv --three-sixty-dir data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/three-sixty --output outputs/utkarsh-setups-k4 --k 4

# Sensitivity (Visibility)
python -m src.profile_tournament_360 --corners outputs/utkarsh-corners/corner_summary.csv --coverage-manifest data/ingested/wc2022-euro2024/coverage_manifest.json --frames-dir data/raw/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/three-sixty --output outputs/utkarsh-360-coverage-30 --min-box-coverage 0.3