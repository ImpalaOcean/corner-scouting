"""Content evidence for a window-only comparison; never fits or scores models."""
import csv
import hashlib
import json
from math import isfinite
from pathlib import Path

from .summary import AnalysisError, load_corners

# All exported attributes independent of the outcome-window rule.
INVARIANTS = ['match_id', 'corner_event_id', 'team_id', 'team', 'taker', 'period',
              'timestamp', 'minute', 'second', 'possession_id', 'corner_kind',
              'technique', 'foot', 'height', 'delivery_category', 'start_x', 'start_y',
              'end_x', 'end_y', 'short_limit', 'competition_id', 'competition_name',
              'season_id', 'season', 'match_date', 'home_team', 'away_team']
NUMERIC = {'match_id', 'team_id', 'period', 'minute', 'second', 'possession_id',
           'start_x', 'start_y', 'end_x', 'end_y', 'short_limit', 'competition_id', 'season_id'}


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def input_contract(path):
    path = Path(path).resolve()
    before = sha256(path)
    rows = load_corners(path)  # Reject duplicate keys and mixed settings first.
    if not rows:
        raise AnalysisError('Cannot establish a comparison population from an empty input')
    if path.suffix.lower() == '.parquet':
        import pyarrow.parquet as pq
        raw = pq.read_table(path).to_pylist()
        fields = pq.read_schema(path).names
    else:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            raw = list(reader)
    missing = set(INVARIANTS) - set(fields)
    if missing:
        raise AnalysisError('Cannot verify invariant attributes; missing columns: '+', '.join(sorted(missing)))
    canonical = []
    for item in raw:
        values = []
        for field in INVARIANTS:
            value = item[field]
            if value is None or value == '':
                value = None
            elif field in NUMERIC:
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise AnalysisError(f'Invalid invariant {field}: {value!r}') from exc
                if not isfinite(value):
                    raise AnalysisError(f'Nonfinite invariant {field}')
                if field not in {'start_x','start_y','end_x','end_y','short_limit'}:
                    if not value.is_integer():
                        raise AnalysisError(f'Noninteger invariant {field}')
                    value = int(value)
            else:
                value = str(value)
            values.append(value)
        canonical.append(values)
    canonical.sort(key=lambda r: (r[0], r[1]))
    window, short = rows[0]['window_seconds'], rows[0]['short_limit']
    if short is None or not isfinite(short) or short <= 0:
        raise AnalysisError('Short limit must be positive and finite')
    if window is not None and (not isfinite(window) or window <= 0):
        raise AnalysisError('Window must be positive and finite or uncapped')
    after = sha256(path)
    if before != after:
        raise AnalysisError('Input changed while establishing provenance')
    return dict(schema='analysis_input_contract_v1', input_sha256=after,
                corners=len(rows), population_sha256=digest([r[:2] for r in canonical]),
                invariant_fields=INVARIANTS, invariants_sha256=digest(canonical),
                window_seconds=window, short_limit=short)
