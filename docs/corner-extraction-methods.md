# Corner extraction methods — draft

## Input data

The extraction module accepts a list of StatsBomb event records loaded from provider-format JSON. It constructs summaries in memory without downloading data or writing files. The batch runner receives match IDs, paths to local event files, and optional match metadata through a manifest; it orders events by period, timestamp, and provider index before extraction. Missing metadata remains unfilled rather than being inferred.

## Corner identification

A corner begins with a Pass or Shot event whose nested type is Corner. This includes both delivered corners and shots taken directly from the corner. Identification retains the first qualifying record for each event ID, so duplicate corner records contribute only one summary; duplicate IDs within a sequence are also included once.

## Sequence boundaries

Starting with the corner, the extractor follows subsequent events until the period changes, the configured time window is exceeded, a new restart occurs, possession changes, or play stops. Non-advantage fouls, offside, injury stoppages, referee ball drops, and half-end events close the sequence; pressure by the defending team alone does not. Restart, possession-change, and stoppage boundary records are excluded, while a terminal shot or ball-out action is included before closing. Events exactly at the time limit remain eligible. The runner supports 10-, 15-, and 20-second windows and an uncapped setting that retains all other boundaries. When conditions overlap, the implemented order determines the recorded reason: period, time, restart, possession, then stoppage; included actions are subsequently checked for goals and ball-out flags.

## Delivery classification

Corners are classified as short, inswinging, outswinging, straight, unknown, or direct_shot. A short corner is a ground pass with available finite start and end coordinates whose Euclidean distance is at most 15 native pitch-coordinate units; the distance threshold is configurable. Short classification takes precedence over the provider technique, while the original technique is retained separately. Other passes use the recorded Inswinging, Outswinging, or Straight technique, with unknown as the fallback; direct corner shots receive direct_shot. Missing coordinate pairs remain empty rather than becoming zero.

## Recorded outcomes

Each summary counts shots taken by the corner-taking team and records how many have the provider outcome Goal. A direct corner shot counts itself. Provider StatsBomb xG values are summed over these shots, treating missing or null values as zero for this sum. The output retains the corner ID, associated shot IDs, all included chain event IDs, and the reason extraction stopped, together with timing, delivery details, coordinates, and the applied window and short-corner threshold. CSV exports encode event-ID lists as JSON arrays for later inspection.

## Checks and limitations

Fifteen automated tests use invented events to check identification and duplicate handling, attacking-team selection, direct shots, possession and period boundaries, restarts, stoppages, advantage, terminal goals and ball-out actions, time limits including uncapped play, delivery categories, missing coordinates, and summary construction. Sample runs on two matches check that the workflow operates beyond one fixture, but larger-data validation is still pending. Sequence membership relies on provider possession labels and event ordering, and recorded ending reasons follow rule priority rather than necessarily identifying the physical instant play stopped. Provider xG is not a model fitted by this project. The three local practice inspections are preliminary; the formal 100-sequence audit requires an agreed sample with Asaad and separate individual judgments until both reviews are complete.
