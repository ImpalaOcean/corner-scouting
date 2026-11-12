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

## Combined-corpus audit preparation

Status: preparation only. No final sample or reviewer judgments are recorded here.
Diego leads sample preparation; Diego and Asaad review independently. The intended
scope is World Cup 2022, Euro 2024, and the 2015/16 Premier League, La Liga,
Serie A and Ligue 1. Asaad's proposed protocol and tool currently live on
`feat/evaluation`; review and integrate them before the formal audit.

### Inputs and sample freeze

1. Finish league ingestion and extraction. Use the primary 15-second window and
   15-unit short-corner threshold for every constituent table. Alternative-window
   outputs are sensitivity experiments, not additional audit observations.
2. Build one combined table and a combined local input manifest. Validate unique
   `(match_id, corner_event_id)` keys, consistent extraction settings and complete
   competition/season/date metadata. Preserve all constituent run manifests.
   Resolve constituent manifest paths before combining them; do not concatenate
   relative event paths into a new directory without rebasing them.
3. Record the source revision, code commit, input-table and manifest SHA-256
   hashes, sampler version, seed 5118, sampling quotas and actual sample size.
   Draw exactly 100 distinct corners using the reviewed rare/boundary-case
   sampler. Report the selected counts by competition-season and by stratum;
   explicitly check that leagues and tournaments are both represented before
   freezing. Any sampling-policy adjustment must be documented, not chosen
   after observing reviewer answers.
4. Share one frozen blank sheet, with separate Diego and Asaad copies. Preserve
   the original sample and hashes; do not regenerate a different sample on
   each reviewer's machine.

### Review rules to reconcile with Asaad's protocol

- Judge delivery, attacking-shot count, goal count and stopping reason against
  the versioned extractor and raw provider records. This is a source-consistency
  audit, not an independently sourced football ground-truth evaluation.
- For each subsequent event, apply the implemented boundary order: period,
  elapsed time greater than the cap, restart, possession, then stoppage.
  Goals and ball-out flags are checked after an event is included. The corner
  itself is checked for a direct goal or out flag first. Exactly-on-cap
  events remain eligible. Do not interpret "earliest ending" as a different
  physical-play rule.
- An off-target shot without an explicit earlier ending can correctly yield
  `time_limit`. Record the missing-out-event case separately; do not infer an
  unrecorded timestamp or equate chain membership with continuous live play.
- Inspect full raw JSON where the timeline omits fields needed for a judgment:
  start/end coordinates, pass height and technique, advantage, out flags,
  period, possession, team and exact timestamps. Rounded timeline text alone
  is insufficient to judge a 15-unit delivery or an exact time boundary.
- Record each judgment personally, with notes for every failure and ambiguous
  case. Do not share judgments until both reviewers have finished.

### Completion and reporting

Verify that both sheets contain all 100 identical corner keys and all required
answers before comparison. Report pre-resolution agreement, disagreements and
confirmed implementation errors; record resolutions separately. If Cohen's
kappa is undefined because both reviewers use one constant label, report it
as undefined rather than perfect agreement. Report missing answers explicitly.

The deliberately enriched sample supports finding edge cases and describing
reviewer agreement on that sample. Its unweighted error frequency is not an
unbiased estimate of corpus-wide extraction accuracy. Maintain this limitation
in the paper. Any confirmed extraction fix requires reviewed code, regression
checks and regenerated affected outputs with recorded provenance.
