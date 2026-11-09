"""Team corner summaries and chronological match splits (Asaad).

Input is Diego's corner table (corner_summary_batch_v1): one row per corner,
CSV or Parquet. Only the Python standard library is needed for CSV.
Parquet input additionally needs pyarrow.
"""

from collections import defaultdict
import csv
from pathlib import Path
import random

DELIVERY_CATEGORIES = ['short', 'inswinging', 'outswinging', 'straight',
                       'unknown', 'direct_shot']

# Columns this module actually needs from the corner table.
REQUIRED_COLUMNS = ['match_id', 'corner_event_id', 'team_id', 'team',
                    'delivery_category', 'shot_count', 'goal_count',
                    'led_to_shot', 'provider_xg_sum', 'window_seconds',
                    'short_limit', 'competition_id', 'competition_name',
                    'season_id', 'season', 'match_date', 'period']

# A competition season needs this many dated matches before it is split;
# with fewer, the 60/20/20 shares round to empty partitions.
MIN_MATCHES_TO_SPLIT = 5

# Proposal rule: predictive evaluation needs at least this much history.
MIN_MATCHES = 10
MIN_CORNERS = 30

TEAM_SUMMARY_FIELDS = (
    ['competition_id', 'competition_name', 'season_id', 'season', 'team_id',
     'team', 'window_seconds', 'short_limit', 'date_cutoff', 'first_match_date',
     'last_match_date', 'matches', 'corners']
    + [f'n_{c}' for c in DELIVERY_CATEGORIES]
    + [f'freq_{c}' for c in DELIVERY_CATEGORIES]
    + [f'freq_{c}_{b}' for c in DELIVERY_CATEGORIES for b in ('ci_low', 'ci_high')]
    + ['corners_with_shot', 'shot_rate', 'shot_rate_ci_low', 'shot_rate_ci_high',
       'shots', 'goals', 'goal_rate', 'xg_sum', 'xg_per_corner', 'small_sample']
)

PERIOD_FIELDS = ['competition_id', 'competition_name', 'season_id', 'season',
                 'team_id', 'team', 'period_group', 'corners',
                 'corners_with_shot', 'shot_rate', 'goals']

SPLIT_FIELDS = ['competition_id', 'competition_name', 'season_id', 'season',
                'match_id', 'match_date', 'order', 'split']


class AnalysisError(ValueError):
    """Raised when the input corner table cannot be analysed safely."""


# Loading

def _blank(value):
    return value is None or (isinstance(value, str) and value.strip() == '')


def _to_int(value, column, row_number):
    if _blank(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        raise AnalysisError(f'row {row_number}: {column} is not a number: {value!r}')


def _to_float(value, column, row_number):
    if _blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise AnalysisError(f'row {row_number}: {column} is not a number: {value!r}')


def _to_bool(value, column, row_number):
    if isinstance(value, bool):
        return value
    if _blank(value):
        return None
    text = str(value).strip().lower()
    if text in ('true', '1'):
        return True
    if text in ('false', '0'):
        return False
    raise AnalysisError(f'row {row_number}: {column} is not True/False: {value!r}')


def _clean(raw, row_number):
    row = {
        'match_id': _to_int(raw['match_id'], 'match_id', row_number),
        'corner_event_id': None if _blank(raw['corner_event_id']) else str(raw['corner_event_id']),
        'team_id': _to_int(raw['team_id'], 'team_id', row_number),
        'team': raw['team'],
        'delivery_category': (raw['delivery_category'] or 'unknown'),
        'shot_count': _to_int(raw['shot_count'], 'shot_count', row_number) or 0,
        'goal_count': _to_int(raw['goal_count'], 'goal_count', row_number) or 0,
        'led_to_shot': _to_bool(raw['led_to_shot'], 'led_to_shot', row_number),
        'provider_xg_sum': _to_float(raw['provider_xg_sum'], 'provider_xg_sum', row_number) or 0.0,
        'window_seconds': _to_float(raw['window_seconds'], 'window_seconds', row_number),
        'short_limit': _to_float(raw['short_limit'], 'short_limit', row_number),
        'competition_id': _to_int(raw['competition_id'], 'competition_id', row_number),
        'competition_name': raw['competition_name'] or None,
        'season_id': _to_int(raw['season_id'], 'season_id', row_number),
        'season': None if _blank(raw['season']) else str(raw['season']),
        'match_date': None if _blank(raw['match_date']) else str(raw['match_date']),
        'period': _to_int(raw['period'], 'period', row_number),
    }
    if row['match_id'] is None or row['corner_event_id'] is None or row['team_id'] is None:
        raise AnalysisError(f'row {row_number}: match_id, corner_event_id and team_id are required')
    if row['delivery_category'] not in DELIVERY_CATEGORIES:
        raise AnalysisError(f"row {row_number}: unexpected delivery_category {row['delivery_category']!r}")
    if row['led_to_shot'] is None:
        row['led_to_shot'] = row['shot_count'] > 0
    return row


def load_corners(path):
    """Read a corner table (CSV or Parquet) and return a list of typed dicts."""
    path = Path(path)
    if not path.exists():
        raise AnalysisError(f'input file not found: {path}')
    if path.suffix.lower() == '.parquet':
        try:
            import pyarrow.parquet as pq
        except ImportError:
            raise AnalysisError('reading Parquet needs pyarrow; use the CSV or pip install pyarrow')
        raw_rows = pq.read_table(path).to_pylist()
        columns = raw_rows[0].keys() if raw_rows else pq.read_schema(path).names
    else:
        # utf-8-sig strips the byte order mark the batch runner writes.
        with path.open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames or []
            raw_rows = list(reader)
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise AnalysisError(f'input is missing columns: {", ".join(missing)}')
    rows = [_clean(raw, number) for number, raw in enumerate(raw_rows, start=2)]
    check_corners(rows)
    return rows


def check_corners(rows):
    """Refuse inputs that would silently distort the statistics."""
    keys = set()
    for row in rows:
        key = (row['match_id'], row['corner_event_id'])
        if key in keys:
            raise AnalysisError(f'duplicate corner key {key}')
        keys.add(key)
    settings = {(r['window_seconds'], r['short_limit']) for r in rows}
    if len(settings) > 1:
        raise AnalysisError('input mixes extraction settings (window/short limit); '
                            'analyse one batch run at a time')


# Team summaries

def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def apply_cutoff(rows, cutoff):
    """Keep only corners from matches strictly before the cutoff date
    (YYYY-MM-DD), so a prematch view never sees the match itself or later
    ones. Matches without a date are dropped, since we cannot prove they
    came first."""
    if cutoff is None:
        return rows
    return [r for r in rows if r['match_date'] and r['match_date'] < cutoff]


def bootstrap_interval(match_values, statistic, draws, rng):
    """Match bootstrap: resample whole matches with replacement and return
    the 2.5th and 97.5th percentiles of the statistic. match_values is a list
    with one entry per match; statistic turns a resampled list into a number
    (or None when undefined)."""
    if draws <= 0 or not match_values:
        return None, None
    results = []
    n = len(match_values)
    for _ in range(draws):
        sample = [match_values[rng.randrange(n)] for _ in range(n)]
        value = statistic(sample)
        if value is not None:
            results.append(value)
    if not results:
        return None, None
    results.sort()
    low = results[int(0.025 * (len(results) - 1))]
    high = results[int(round(0.975 * (len(results) - 1)))]
    return round(low, 4), round(high, 4)


def _ratio_statistic(numerator_key, denominator_key='corners'):
    def statistic(sample):
        denominator = sum(m[denominator_key] for m in sample)
        if not denominator:
            return None
        return sum(m[numerator_key] for m in sample) / denominator
    return statistic


def team_summaries(rows, bootstrap_draws=0, seed=5118, cutoff=None):
    """One summary row per (competition, season, team). With bootstrap_draws
    above zero, adds match bootstrap 95% intervals for every frequency and
    for the shot rate."""
    rng = random.Random(seed)
    rows = apply_cutoff(rows, cutoff)
    groups = defaultdict(list)
    for row in rows:
        groups[(row['competition_id'], row['season_id'], row['team_id'])].append(row)

    summaries = []
    for key in sorted(groups, key=lambda k: tuple(-1 if v is None else v for v in k)):
        corners = groups[key]
        first = corners[0]
        dates = sorted({r['match_date'] for r in corners if r['match_date']})
        matches = {r['match_id'] for r in corners}
        n = len(corners)
        counts = {c: 0 for c in DELIVERY_CATEGORIES}
        for r in corners:
            counts[r['delivery_category']] += 1
        with_shot = sum(1 for r in corners if r['led_to_shot'])
        goals = sum(r['goal_count'] for r in corners)
        xg = sum(r['provider_xg_sum'] for r in corners)
        summary = {
            'competition_id': first['competition_id'],
            'competition_name': first['competition_name'],
            'season_id': first['season_id'],
            'season': first['season'],
            'team_id': first['team_id'],
            'team': first['team'],
            'window_seconds': first['window_seconds'],
            'short_limit': first['short_limit'],
            'date_cutoff': cutoff,
            'first_match_date': dates[0] if dates else None,
            'last_match_date': dates[-1] if dates else None,
            'matches': len(matches),
            'corners': n,
        }
        for c in DELIVERY_CATEGORIES:
            summary[f'n_{c}'] = counts[c]
        for c in DELIVERY_CATEGORIES:
            summary[f'freq_{c}'] = _rate(counts[c], n)
        summary.update({
            'corners_with_shot': with_shot,
            'shot_rate': _rate(with_shot, n),
            'shots': sum(r['shot_count'] for r in corners),
            'goals': goals,
            'goal_rate': _rate(goals, n),
            'xg_sum': round(xg, 4),
            'xg_per_corner': _rate(xg, n),
            'small_sample': len(matches) < MIN_MATCHES or n < MIN_CORNERS,
        })
        # Per match totals for this team, so the bootstrap keeps each
        # match's corners together.
        per_match = defaultdict(lambda: dict({c: 0 for c in DELIVERY_CATEGORIES},
                                             corners=0, with_shot=0))
        for r in corners:
            m = per_match[r['match_id']]
            m['corners'] += 1
            m[r['delivery_category']] += 1
            m['with_shot'] += 1 if r['led_to_shot'] else 0
        match_values = [per_match[k] for k in sorted(per_match)]
        for c in DELIVERY_CATEGORIES:
            low, high = bootstrap_interval(match_values, _ratio_statistic(c),
                                           bootstrap_draws, rng)
            summary[f'freq_{c}_ci_low'], summary[f'freq_{c}_ci_high'] = low, high
        low, high = bootstrap_interval(match_values, _ratio_statistic('with_shot'),
                                       bootstrap_draws, rng)
        summary['shot_rate_ci_low'], summary['shot_rate_ci_high'] = low, high
        summaries.append(summary)
    return summaries


def _period_group(period):
    if period in (1, 2):
        return f'half_{period}'
    if period in (3, 4):
        return 'extra_time'
    return 'other'


def period_breakdown(rows, cutoff=None):
    """Descriptive context table: corners and shot rate per team per period
    group (first half, second half, extra time). Descriptive only; the
    proposal makes no causal claims about context."""
    rows = apply_cutoff(rows, cutoff)
    groups = defaultdict(list)
    for r in rows:
        groups[(r['competition_id'], r['season_id'], r['team_id'],
                _period_group(r['period']))].append(r)
    out = []
    for key in sorted(groups, key=lambda k: tuple(-1 if v is None else v for v in k)):
        corners = groups[key]
        first = corners[0]
        with_shot = sum(1 for r in corners if r['led_to_shot'])
        out.append({
            'competition_id': first['competition_id'],
            'competition_name': first['competition_name'],
            'season_id': first['season_id'], 'season': first['season'],
            'team_id': first['team_id'], 'team': first['team'],
            'period_group': key[3], 'corners': len(corners),
            'corners_with_shot': with_shot,
            'shot_rate': _rate(with_shot, len(corners)),
            'goals': sum(r['goal_count'] for r in corners),
        })
    return out


# Chronological splits

def chronological_splits(rows, train=0.6, validation=0.2):
    """Assign whole matches to train/validation/test by date within each
    competition season. Matches without a date or competition/season are
    marked excluded, never placed in a split. Competition seasons with fewer
    than MIN_MATCHES_TO_SPLIT dated matches are marked too_few_matches. Ties on date are broken by
    match_id so the result is always the same."""
    matches = {}
    for r in rows:
        info = (r['competition_id'], r['competition_name'], r['season_id'],
                r['season'], r['match_date'])
        previous = matches.setdefault(r['match_id'], info)
        if previous != info:
            raise AnalysisError(f"match {r['match_id']} has inconsistent metadata across rows")

    by_stratum = defaultdict(list)
    assignments = []
    for match_id, (comp, comp_name, season_id, season, match_date) in matches.items():
        if match_date is None or comp is None or season_id is None:
            assignments.append({
                'competition_id': comp, 'competition_name': comp_name,
                'season_id': season_id, 'season': season, 'match_id': match_id,
                'match_date': match_date, 'order': None, 'split': 'excluded'})
        else:
            by_stratum[(comp, season_id)].append(
                (match_date, match_id, comp_name, season))

    for (comp, season_id), items in sorted(by_stratum.items()):
        items.sort()
        n = len(items)
        train_end = int(n * train)
        validation_end = int(n * (train + validation))
        for position, (match_date, match_id, comp_name, season) in enumerate(items):
            if n < MIN_MATCHES_TO_SPLIT:
                split = 'too_few_matches'
            elif position < train_end:
                split = 'train'
            elif position < validation_end:
                split = 'validation'
            else:
                split = 'test'
            assignments.append({
                'competition_id': comp, 'competition_name': comp_name,
                'season_id': season_id, 'season': season, 'match_id': match_id,
                'match_date': match_date, 'order': position + 1, 'split': split})

    assignments.sort(key=lambda a: (a['split'] in ('excluded', 'too_few_matches'),
                                    a['competition_id'] or 0, a['season_id'] or 0,
                                    a['order'] or 0, a['match_id']))
    return assignments


# Writing

def write_csv(path, fields, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ('' if row.get(k) is None else row.get(k)) for k in fields})
