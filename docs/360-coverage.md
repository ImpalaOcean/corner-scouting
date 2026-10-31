# 360 Static Setup Analysis Coverage

This document describes the implementation and coverage of the 360 static setup analysis module (Track 4).

## Data Join
- **Join Key:** `(match_id, corner_event_id)` matches with StatsBomb's `event_uuid`.
- **Source:** Reads Diego's `corner_summary.csv` and Ebtesam's cached 360 JSON files.
- **Coverage:** In the 2-match sample, 9 corners were processed and exactly 5 had matching 360 freeze frames. The 4 corners without 360 frames are explicitly flagged as `frame_360: None` and excluded from clustering.

## Feature Extraction
- **Normalization:** Coordinates are normalized so that left-side corners are flipped to match right-side corners. This ensures setups are compared independent of which side the corner was taken from.
- **Zones:** The penalty box is divided into a 3x3 grid (9 zones). Attacking and defending players are counted per zone. Keepers are tracked separately.
- **Visibility:** The module counts total visible players, attacking players, defending players, and goalkeepers. It handles missing data gracefully (e.g., heavy occlusion where only 11 players are visible).

## Clustering & Limitations
- **Clustering:** We use a simple K-Means approach over the 18-dimensional zone occupancy vector (9 zones x 2 teams).
- **Risk Rule:** As stated in the team playbook, if sample sizes are too small, we label clusters as exploratory. The current 5-corner sample is for pipeline validation, not for drawing soccer conclusions. Full-corpus runs will be required to establish stable routine clusters.
- **Out of Scope:** This module does NOT classify player runs or marking schemes (man/zonal), which are scheduled for Stage 3 (P6-b).