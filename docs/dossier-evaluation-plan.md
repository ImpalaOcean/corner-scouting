# Dossier evaluation plan (proposal, Asaad and Mohamed)

Status: proposal for Mohamed to review. Nothing here has been run.

The dossier is judged on two separate questions. They use different evidence
and must not be mixed in the paper.

1. **Predictive accuracy:** are the numbers the dossier shows for an upcoming
   match better than a simple baseline at describing what that team then did?
2. **Report usefulness:** does the report give a reader what they need,
   honestly, and can every number be traced back to source corners?

## 1. Predictive accuracy

The main evaluation (`docs/evaluation.md`) already answers this for the
fitted models: one fit on train plus validation, scored on the locked test
matches. The dossier adds nothing new to that question unless it is scored the
way it is used, one fixture at a time with history up to the day before.

Proposed rolling check (only if time allows; otherwise cite the main result):

* Fixtures: every match in the existing test split of each 2015/16 league,
  in date order. No fixture outside the test split is used, so the locked
  test set is still only scored, never used to choose anything.
* For each fixture, build the dossier inputs exactly as the dossier does:
  history strictly before the fixture date, smoothing chosen on past-only
  validation, eligibility on the past-only training prefix.
* Score both teams' corners in that fixture with the same metrics as the main
  evaluation: delivery log loss (known deliveries only) and shot Brier score
  (all corners), for pooled, unsmoothed and shrunk.
* Report paired differences with a match bootstrap, as in the main evaluation,
  plus how many fixtures had at least one ineligible team.
* Fixed before running: the fixture list, metrics, grid, seed 5118 and 1,000
  bootstrap draws. No settings change after seeing results.

What this adds: it checks that the cutoff logic and the per fixture refits
give the same conclusion as the single fit. If they disagree, the paper says
so.

## 2. Report usefulness

A checklist applied to every generated dossier (at least the five the
proposal promises), scored yes or no by Mohamed and one other member
independently, with disagreements resolved and reported:

| Item | Yes when |
| --- | --- |
| Sample size | Matches and corners are shown next to every percentage |
| Uncertainty | Every share and rate has its interval, shown as a range |
| Small samples | Teams below 10 matches or 30 corners are labelled descriptive |
| Cutoff | The cutoff date is printed and no included match is on or after it |
| Traceability | At least one listed corner per section can be found by its `corner_event_id` in the source events |
| Model vs observed | Model expectations are labelled separately from observed history |
| Limitations | Unknown deliveries, missing 360 data and goal rarity are stated |
| Wording | No causal claims about which delivery "works" |

Optional, if time allows: two or three people outside the team read one
dossier and answer three questions (what is the opponent's most common
delivery, how sure is the report, what is missing). Report their answers
descriptively; this is not a statistical test.

## Timing

Mohamed and Mo agree what the dossier timing covers (loading, fitting,
rendering) separately; timing is not part of either evaluation above.
