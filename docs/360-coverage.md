# 360 static setup analysis and coverage

Scope: snapshots of player positions at the moment of a corner. No player runs and no
marking classification. Code: `src/setups/`; tests: `tests/test_setups.py`.

## Inputs

- Corner table: `corner_summary.csv` from the corner extractor (uses `match_id`,
  `corner_event_id`, `team_id`, `team`, `start_x`, `start_y`).
- 360 files: `<match_id>.json` (list of frames with `event_uuid`, `visible_area`,
  `freeze_frame`), as downloaded by `src/data`.
- Join key: `(match_id, corner_event_id)` = `(match_id, event_uuid)`.

## Method

1. **Join.** Each corner is matched to its 360 frame. Every corner stays in the output
   with a status; none is silently dropped.
2. **Orientation.** Frames use event orientation: the team taking the corner attacks toward
   x=120, so corners are taken at x=120 from y near 0 or 80. `teammate=true` means the
   corner-taking team. Bottom corners (y<40) are mirrored (y -> 80-y), together with the
   visible area, so all corners are analysed as if taken from y=80. The side comes from the
   corner table; if both coordinates are blank, from the corner taker (`actor`) in the frame.
   A location counts as a corner only if it is within 3 yards of a corner flag on the goal
   line (x 117-120, y 0-3 or 77-80); anything else (mid-pitch, off the pitch, not a number)
   is excluded as `invalid_corner_location`, never guessed.
3. **Zones.** The penalty box (x 102-120, y 18-62) is split 3x3 into nine zones, numbered
   row by row: 1-3 is the band nearest y=18 and 7-9 the band nearest y=62; within a row
   x increases from the 18-yard line to the goal line. Players outside the box are in no
   zone. The corner taker and goalkeepers are not counted in the outfield zone counts; the
   opponent keeper's zone is reported separately (`keeper_zone`, 0 = outside the box).
4. **Visibility.** `box_coverage` is the share of the penalty-box area inside the frame's
   `visible_area` polygon. Players outside the visible area are not recorded by the provider,
   so low coverage means zone counts are incomplete, not that the zone was empty.
5. **Grouping.** The 18-number vector (attackers per zone, then defenders per zone) is
   clustered with deterministic k-means (farthest-point start, fixed order, no randomness
   except in the stability check, which is seeded). Identical setups always share a cluster.
6. **Stability.** The clustering is repeated on ten random 80% subsamples; the mean adjusted
   Rand index against the full clustering is reported (1 = identical, about 0 = chance). It is
   only computed with at least 10 corners per cluster.

## Exclusion rules (reason recorded per corner)

| Reason | Meaning |
| --- | --- |
| `no_360_file` | The match has no 360 file (normal: only some matches have 360). |
| `no_360_frame` | The match file exists but has no frame for this corner. |
| `invalid_frame` | Frame is malformed: bad coordinates or flags, or a visible area that is empty, has fewer than three points or has zero area. Applies whatever the coverage threshold. |
| `no_corner_location` | Coordinates blank in the table and no corner taker in the frame. |
| `invalid_corner_location` | Coordinates present but not a corner position (see Method step 2). |
| `too_few_visible_players` | Fewer than `--min-visible-players` (default 5) players visible. |
| `low_visibility` | `box_coverage` below `--min-box-coverage` (default 0.5). |

The two thresholds are provisional defaults and are configurable; changing them is a
sensitivity analysis, not a bug fix.

## Outputs (`setup_summary_v1`)

`setup_summary.csv`, one row per input corner: `match_id`, `corner_event_id`, `team_id`,
`team`, `status` (`ok`/`excluded`), `exclusion_reason`, `corner_side`, `visible_players`,
`visible_attackers`, `visible_defenders`, `visible_keepers`, `box_coverage`, `att_in_box`,
`def_in_box`, `keeper_zone`, `att_z1`-`att_z9`, `def_z1`-`def_z9`, `cluster_id` (blank when
excluded).

`setup_report.json`: counts by exclusion reason, usable fraction, clusters found, stability,
cluster sizes and mean attackers/defenders per zone, `exploratory` flag and `caveats`.

## Coverage and limitations

- Coverage is the usable fraction in `setup_report.json`. At the time of writing, the
  two-match sample from the data module has 9 corners, of which 5 have a matching 360 frame.
  The full-corpus coverage audit is still pending.
- Results are labelled **exploratory** when fewer than `--min-corners-confident` (default 100)
  corners are usable, when stability is below 0.6, when stability cannot be estimated (too few
  corners, or all corners fall in a single group), or when any cluster has fewer than
  `--min-cluster-size` (default 10) corners. Each cluster in `setup_report.json` carries a
  `meets_min_size` flag. No generalisation claim should be made from exploratory clusters.
- A frame is one instant; cluster membership is not a routine label, and cluster numbers
  are not comparable between runs with different data.
- The default of four clusters is a convention, not a selected optimum.
