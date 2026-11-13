"""Predictive evaluation of team corner profiles (Asaad).

Research question 1 of the proposal: does a team's corner history predict
its later corners better than the competition average?

Three methods predict each team's corners in later matches:
  pooled      the competition average from the history matches
  unsmoothed  the team's own raw frequencies from the history matches
  shrunk      the proposal's formula, blending the two:
                  p = (n_team_d + alpha * p_comp_d) / (N_team + alpha)

Two stages, so the test matches are never used to make a choice:
  selection   history = train matches, target = validation matches.
              Picks alpha (deliveries) and beta (shot rate).
  final       history = train + validation matches, target = test matches.
              Scores all three methods once with the chosen alpha and beta.

Deliveries are scored with log loss over the five known categories.
Corners labelled 'unknown' are missing data, not a team choice, so they are
left out of delivery scoring (their share is reported). Shot creation is
scored with the Brier score on led_to_shot, over every corner.
"""

from collections import defaultdict
import math
import random

from .summary import MIN_CORNERS, MIN_MATCHES, bootstrap_interval

SCORED_CATEGORIES = ['short', 'inswinging', 'outswinging', 'straight', 'direct_shot']
METHODS = ['pooled', 'unsmoothed', 'shrunk']
ALPHA_GRID = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
# Smallest probability allowed, so one never seen category cannot make the
# unsmoothed baseline's log loss infinite.
EPSILON = 1e-6
RELIABILITY_BINS = 10

TEAM_EVAL_FIELDS = (
    ['competition_id', 'competition_name', 'season_id', 'season', 'team_id',
     'team', 'history_matches', 'history_corners', 'test_matches',
     'test_corners_scored', 'test_corners_unknown', 'test_corners_known',
     'delivery_status', 'delivery_reason', 'shot_status', 'shot_reason']
    + [f'logloss_{m}' for m in METHODS]
    + [f'brier_{m}' for m in METHODS]
    + ['logloss_shrunk_minus_pooled', 'logloss_diff_ci_low', 'logloss_diff_ci_high',
       'brier_shrunk_minus_pooled', 'brier_diff_ci_low', 'brier_diff_ci_high']
)
SUMMARY_FIELDS = ['target', 'metric', 'method', 'score', 'ci_low', 'ci_high',
                  'corners', 'matches', 'teams', 'status', 'reason',
                  'eligible_corners', 'known_delivery_corners', 'unknown_delivery_corners']
DIFFERENCE_FIELDS = ['target', 'metric', 'comparison', 'difference', 'ci_low',
                     'ci_high', 'better_if', 'corners', 'matches', 'status', 'reason']
SELECTION_FIELDS = ['parameter', 'value', 'validation_score', 'metric', 'chosen']
RELIABILITY_FIELDS = ['method', 'bin', 'bin_low', 'bin_high', 'corners',
                      'mean_predicted', 'observed_rate']
STABILITY_FIELDS = ['competition_id', 'competition_name', 'season_id', 'season',
                    'team_id', 'team', 'history_corners_scored', 'test_corners_scored',
                    'tvd_team_history_vs_test', 'tvd_pooled_vs_test']
PREDICTION_FIELDS = (['competition_id', 'competition_name', 'season_id', 'season',
                      'team_id', 'team', 'method']
                     + [f'p_{c}' for c in SCORED_CATEGORIES] + ['p_shot', 'delivery_status', 'shot_status'])


# Fitting (uses history corners only)

def _stratum(row):
    return (row['competition_id'], row['season_id'])


def fit_history(history):
    """Count everything the predictions need from the history corners.
    Nothing here ever looks at target corners."""
    comp_counts = defaultdict(lambda: {c: 0 for c in SCORED_CATEGORIES})
    comp_known = defaultdict(int)
    comp_corners = defaultdict(int)
    comp_shots = defaultdict(int)
    team_counts = defaultdict(lambda: {c: 0 for c in SCORED_CATEGORIES})
    team_known = defaultdict(int)
    team_corners = defaultdict(int)
    team_shots = defaultdict(int)
    team_matches = defaultdict(set)
    for r in history:
        s = _stratum(r)
        t = (s, r['team_id'])
        comp_corners[s] += 1
        team_corners[t] += 1
        team_matches[t].add(r['match_id'])
        if r['led_to_shot']:
            comp_shots[s] += 1
            team_shots[t] += 1
        if r['delivery_category'] in SCORED_CATEGORIES:
            comp_counts[s][r['delivery_category']] += 1
            comp_known[s] += 1
            team_counts[t][r['delivery_category']] += 1
            team_known[t] += 1
    k = len(SCORED_CATEGORIES)
    pooled = {}
    pooled_shot = {}
    for s in comp_corners:
        # Add one smoothing keeps the competition average away from zero.
        pooled[s] = {c: (comp_counts[s][c] + 1) / (comp_known[s] + k)
                     for c in SCORED_CATEGORIES}
        pooled_shot[s] = (comp_shots[s] + 1) / (comp_corners[s] + 2)
    return {
        'pooled': pooled, 'pooled_shot': pooled_shot,
        'team_counts': team_counts, 'team_known': team_known,
        'team_corners': team_corners, 'team_shots': team_shots,
        'team_matches': team_matches,
    }


def delivery_probabilities(fit, stratum, team_id, method, alpha):
    pooled = fit['pooled'].get(stratum)
    if pooled is None:
        return None
    key = (stratum, team_id)
    counts = fit['team_counts'].get(key, {c: 0 for c in SCORED_CATEGORIES})
    known = fit['team_known'].get(key, 0)
    if method == 'pooled' or known == 0:
        return dict(pooled)
    if method == 'unsmoothed':
        raw = {c: counts[c] / known for c in SCORED_CATEGORIES}
    else:
        raw = {c: (counts[c] + alpha * pooled[c]) / (known + alpha)
               for c in SCORED_CATEGORIES}
    return _clip(raw)


def _clip(probabilities):
    """Raise any zero probability to EPSILON and renormalise. With alpha
    above zero nothing is zero, so this only affects alpha = 0 and the
    unsmoothed baseline."""
    raw = {c: max(v, EPSILON) for c, v in probabilities.items()}
    total = sum(raw.values())
    return {c: v / total for c, v in raw.items()}


def shot_probability(fit, stratum, team_id, method, beta):
    pooled = fit['pooled_shot'].get(stratum)
    if pooled is None:
        return None
    key = (stratum, team_id)
    corners = fit['team_corners'].get(key, 0)
    shots = fit['team_shots'].get(key, 0)
    if method == 'pooled' or corners == 0:
        return pooled
    if method == 'unsmoothed':
        return shots / corners
    return (shots + beta * pooled) / (corners + beta)


# Scoring

def eligible_teams(train_rows):
    """Proposal rule: team specific prediction needs at least MIN_MATCHES
    matches and MIN_CORNERS corners in the training split."""
    matches = defaultdict(set)
    corners = defaultdict(int)
    for r in train_rows:
        key = (_stratum(r), r['team_id'])
        matches[key].add(r['match_id'])
        corners[key] += 1
    return {key for key in corners
            if len(matches[key]) >= MIN_MATCHES and corners[key] >= MIN_CORNERS}


def score_corners(fit, targets, teams, alpha, beta):
    """One record per target corner of an eligible team, with each method's
    loss. Delivery loss is None for unknown deliveries."""
    records = []
    for r in targets:
        stratum = _stratum(r)
        if (stratum, r['team_id']) not in teams:
            continue
        record = {'match_id': r['match_id'], 'stratum': stratum,
                  'team_id': r['team_id'], 'shot': 1 if r['led_to_shot'] else 0,
                  'known': r['delivery_category'] in SCORED_CATEGORIES}
        for m in METHODS:
            p = delivery_probabilities(fit, stratum, r['team_id'], m, alpha) if alpha is not None else None
            q = shot_probability(fit, stratum, r['team_id'], m, beta) if beta is not None else None
            record[f'logloss_{m}'] = (-math.log(p[r['delivery_category']])
                                      if p is not None and record['known'] else None)
            record[f'shot_p_{m}'] = q
            record[f'brier_{m}'] = (q - record['shot']) ** 2 if q is not None else None
        records.append(record)
    return records


def _mean(records, key):
    values = [r[key] for r in records if r[key] is not None]
    return sum(values) / len(values) if values else None


def select_parameter(fit, targets, teams, grid, kind):
    """Score every grid value on the validation corners and keep the best.
    Ties go to the larger value (more smoothing)."""
    table = []
    for value in grid:
        if kind == 'alpha':
            records = score_corners(fit, targets, teams, value, 0)
            score = _mean(records, 'logloss_shrunk')
        else:
            records = score_corners(fit, targets, teams, 0, value)
            score = _mean(records, 'brier_shrunk')
        table.append({'parameter': kind, 'value': value, 'validation_score': score,
                      'metric': 'log_loss' if kind == 'alpha' else 'brier'})
    scored = [t for t in table if t['validation_score'] is not None]
    if not scored:
        chosen = None
    else:
        best = min(t['validation_score'] for t in scored)
        chosen = max(t['value'] for t in scored if t['validation_score'] <= best + 1e-12)
    for t in table:
        t['chosen'] = t['value'] == chosen
        if t['validation_score'] is not None:
            t['validation_score'] = round(t['validation_score'], 6)
    return chosen, table


# Uncertainty

def _by_match(records):
    groups = defaultdict(list)
    for r in records:
        groups[(r['stratum'], r['match_id'])].append(r)
    return [groups[k] for k in sorted(groups, key=str)]


def _mean_of_sample(key):
    def statistic(sample):
        values = [r[key] for match in sample for r in match if r[key] is not None]
        return sum(values) / len(values) if values else None
    return statistic


def _diff_of_sample(key_a, key_b):
    def statistic(sample):
        pairs = [(r[key_a], r[key_b]) for match in sample for r in match
                 if r[key_a] is not None and r[key_b] is not None]
        if not pairs:
            return None
        return sum(a - b for a, b in pairs) / len(pairs)
    return statistic


# Extra diagnostics

def reliability_table(records, bins=RELIABILITY_BINS):
    """Shot probability calibration: within each probability bin, compare the
    average prediction with how often a shot actually followed."""
    out = []
    for m in METHODS:
        buckets = defaultdict(list)
        for r in records:
            p = r[f'shot_p_{m}']
            if p is None:
                continue
            index = min(int(p * bins), bins - 1)
            buckets[index].append(r)
        for index in range(bins):
            group = buckets.get(index, [])
            out.append({
                'method': m, 'bin': index + 1,
                'bin_low': round(index / bins, 2), 'bin_high': round((index + 1) / bins, 2),
                'corners': len(group),
                'mean_predicted': (round(sum(r[f'shot_p_{m}'] for r in group) / len(group), 4)
                                   if group else None),
                'observed_rate': (round(sum(r['shot'] for r in group) / len(group), 4)
                                  if group else None),
            })
    return out


def _distribution(counts):
    total = sum(counts.values())
    if not total:
        return None
    return {c: counts[c] / total for c in SCORED_CATEGORIES}


def _tvd(p, q):
    return round(0.5 * sum(abs(p[c] - q[c]) for c in SCORED_CATEGORIES), 4)


def profile_stability(fit, targets, teams, info):
    """Compare each team's history profile with its profile in the disjoint
    later matches (total variation distance, 0 = identical, 1 = no overlap),
    next to the same distance for the competition average. Descriptive."""
    later = defaultdict(lambda: {c: 0 for c in SCORED_CATEGORIES})
    for r in targets:
        if r['delivery_category'] in SCORED_CATEGORIES:
            later[(_stratum(r), r['team_id'])][r['delivery_category']] += 1
    out = []
    for key in sorted(teams, key=str):
        test_dist = _distribution(later[key]) if key in later else None
        history_dist = _distribution(fit['team_counts'].get(key, {}) or
                                     {c: 0 for c in SCORED_CATEGORIES})
        if test_dist is None or history_dist is None:
            continue
        stratum, team_id = key
        out.append(dict(info[key],
                        history_corners_scored=fit['team_known'].get(key, 0),
                        test_corners_scored=sum(later[key].values()),
                        tvd_team_history_vs_test=_tvd(history_dist, test_dist),
                        tvd_pooled_vs_test=_tvd(fit['pooled'][stratum], test_dist)))
    return out


# Orchestration

def evaluate(rows, splits, bootstrap_draws=1000, seed=5118):
    """Run selection and final scoring. Returns a dict of output tables plus
    a small metadata dict. Works (with empty tables) when no team is eligible."""
    split_of = {s['match_id']: s['split'] for s in splits}
    by_split = defaultdict(list)
    for r in rows:
        by_split[split_of.get(r['match_id'], 'excluded')].append(r)
    train, validation, test = by_split['train'], by_split['validation'], by_split['test']

    teams = eligible_teams(train)
    info = {}
    for r in rows:
        key = (_stratum(r), r['team_id'])
        if key in teams and key not in info:
            info[key] = {k: r[k] for k in ('competition_id', 'competition_name',
                                           'season_id', 'season', 'team_id', 'team')}

    # Stage 1: choose alpha and beta on validation, fitting on train only.
    selection_fit = fit_history(train)
    alpha, alpha_table = select_parameter(selection_fit, validation, teams, ALPHA_GRID, 'alpha')
    beta, beta_table = select_parameter(selection_fit, validation, teams, ALPHA_GRID, 'beta')

    # Stage 2: refit on everything before the test matches, score test once.
    final_fit = fit_history(train + validation)
    records = score_corners(final_fit, test, teams, alpha, beta)

    def availability(target, subset):
        parameter = alpha if target == 'delivery' else beta
        if not teams:
            return 'unavailable', 'no_train_eligible_teams'
        if parameter is None:
            return 'unavailable', ('no_scorable_validation_delivery_labels' if target == 'delivery'
                                   else 'no_eligible_validation_corners')
        if not subset:
            return 'unavailable', 'no_eligible_test_corners'
        if target == 'delivery' and not any(r['known'] for r in subset):
            return 'unavailable', 'no_scorable_test_delivery_labels'
        return 'available', None

    rng = random.Random(seed)
    matches = _by_match(records)
    summary_rows, difference_rows = [], []
    for target, metric, prefix in (('delivery', 'log_loss', 'logloss'),
                                   ('shot', 'brier', 'brier')):
        used = [r for r in records if r[f'{prefix}_shrunk'] is not None]
        n_matches = len({(r['stratum'], r['match_id']) for r in used})
        n_teams = len({(r['stratum'], r['team_id']) for r in used})
        status, reason = availability(target, records)
        for m in METHODS:
            score = _mean(records, f'{prefix}_{m}')
            low, high = bootstrap_interval(matches, _mean_of_sample(f'{prefix}_{m}'),
                                           bootstrap_draws, rng)
            summary_rows.append({'target': target, 'metric': metric, 'method': m,
                                 'score': None if score is None else round(score, 6),
                                 'ci_low': low, 'ci_high': high, 'corners': len(used),
                                 'matches': n_matches, 'teams': n_teams,
                                 'status': status, 'reason': reason,
                                 'eligible_corners': len(records),
                                 'known_delivery_corners': sum(r['known'] for r in records),
                                 'unknown_delivery_corners': sum(not r['known'] for r in records)})
        for other in ('pooled', 'unsmoothed'):
            values = [r[f'{prefix}_shrunk'] - r[f'{prefix}_{other}'] for r in used]
            diff = sum(values) / len(values) if values else None
            low, high = bootstrap_interval(
                matches, _diff_of_sample(f'{prefix}_shrunk', f'{prefix}_{other}'),
                bootstrap_draws, rng)
            difference_rows.append({
                'target': target, 'metric': metric, 'comparison': f'shrunk_minus_{other}',
                'difference': None if diff is None else round(diff, 6),
                'ci_low': low, 'ci_high': high,
                'better_if': 'negative (shrunk has lower loss)',
                'corners': len(used), 'matches': n_matches, 'status': status, 'reason': reason})

    # Per team scores with their own match bootstrap.
    team_rows = []
    history = train + validation
    for key in sorted(teams, key=str):
        team_records = [r for r in records if (r['stratum'], r['team_id']) == key]
        if not team_records:
            continue
        team_matches = _by_match(team_records)
        row = dict(info[key])
        row.update({
            'history_matches': len(final_fit['team_matches'].get(key, ())),
            'history_corners': final_fit['team_corners'].get(key, 0),
            'test_matches': len(team_matches),
            'test_corners_scored': sum(1 for r in team_records if r['logloss_shrunk'] is not None),
            'test_corners_known': sum(1 for r in team_records if r['known']),
            'test_corners_unknown': sum(1 for r in team_records if not r['known']),
        })
        for target in ('delivery', 'shot'):
            row[target+'_status'], row[target+'_reason'] = availability(target, team_records)
        for prefix in ('logloss', 'brier'):
            for m in METHODS:
                value = _mean(team_records, f'{prefix}_{m}')
                row[f'{prefix}_{m}'] = None if value is None else round(value, 6)
            pairs = [r[f'{prefix}_shrunk'] - r[f'{prefix}_pooled'] for r in team_records
                     if r[f'{prefix}_shrunk'] is not None]
            row[f'{prefix}_shrunk_minus_pooled'] = (round(sum(pairs) / len(pairs), 6)
                                                    if pairs else None)
            low, high = bootstrap_interval(
                team_matches, _diff_of_sample(f'{prefix}_shrunk', f'{prefix}_pooled'),
                bootstrap_draws, rng)
            name = 'logloss' if prefix == 'logloss' else 'brier'
            row[f'{name}_diff_ci_low'], row[f'{name}_diff_ci_high'] = low, high
        team_rows.append(row)

    # Final predicted profiles (what the dossier can show as "expected").
    predictions = []
    for key in sorted(teams, key=str):
        stratum, team_id = key
        for m in METHODS:
            p = delivery_probabilities(final_fit, stratum, team_id, m, alpha) if alpha is not None else None
            q = shot_probability(final_fit, stratum, team_id, m, beta) if beta is not None else None
            if p is None and q is None:
                continue
            row = dict(info[key], method=m, p_shot=round(q, 4) if q is not None else None,
                       delivery_status='available' if p is not None else 'unavailable',
                       shot_status='available' if q is not None else 'unavailable')
            row.update({f'p_{c}': round(p[c], 4) if p is not None else None for c in SCORED_CATEGORIES})
            predictions.append(row)

    meta = {
        'eligible_teams': len(teams),
        'scored_teams': len(team_rows),
        'alpha': alpha, 'beta': beta,
        'test_corners': len(records),
        'test_matches': len(matches),
        'history_corners': len(history),
        'bootstrap_draws': bootstrap_draws, 'seed': seed,
        'targets': {target: dict(zip(('status','reason'), availability(target, records)))
                    for target in ('delivery','shot')},
        'validation_corners': sum((_stratum(r),r['team_id']) in teams for r in validation),
        'validation_known_delivery_corners': sum((_stratum(r),r['team_id']) in teams and
                                                  r['delivery_category'] in SCORED_CATEGORIES for r in validation),
        'test_corners_known_delivery': sum(r['known'] for r in records),
        'test_corners_unknown_delivery': sum(not r['known'] for r in records),
        'note': None if records else
                'No eligible team has test corners; nothing was scored. '
                'Needs competition seasons where teams reach 10 training matches.',
    }
    return {
        'alpha_selection': alpha_table + beta_table,
        'evaluation_summary': summary_rows,
        'evaluation_differences': difference_rows,
        'team_evaluation': team_rows,
        'reliability': reliability_table(records) if records and beta is not None else [],
        'profile_stability': profile_stability(final_fit, test, teams, info),
        'team_predictions': predictions,
    }, meta
