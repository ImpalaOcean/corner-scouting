"""Local, match-at-a-time corner batch processing; no network or loader dependency."""
import argparse
import csv
from datetime import date
import hashlib
import json
from math import isfinite
from pathlib import Path
import shutil
import tempfile

from .extract import build_corner_summaries

CORE_FIELDS = ['match_id', 'corner_event_id', 'team_id', 'team', 'taker', 'period',
               'timestamp', 'minute', 'second', 'possession_id', 'corner_kind',
               'technique', 'foot', 'height', 'delivery_category', 'start_x', 'start_y',
               'end_x', 'end_y', 'shot_count', 'goal_count', 'led_to_shot',
               'provider_xg_sum', 'shot_event_ids', 'chain_event_ids', 'stop_reason',
               'window_seconds', 'short_limit']
META_FIELDS = ['competition_id', 'competition_name', 'season_id', 'season',
               'match_date', 'home_team', 'away_team']
FIELDS = CORE_FIELDS + META_FIELDS
LIST_FIELDS = {'shot_event_ids', 'chain_event_ids'}
INT_FIELDS = {'match_id', 'team_id', 'period', 'minute', 'second', 'possession_id',
              'shot_count', 'goal_count', 'competition_id', 'season_id'}
FLOAT_FIELDS = {'start_x', 'start_y', 'end_x', 'end_y', 'provider_xg_sum',
                'window_seconds', 'short_limit'}


def identifier(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f'{label} must be a positive integer')
    result = int(value)
    if result <= 0 or str(result) != str(value):
        raise ValueError(f'{label} must be a positive integer')
    return result


def text(value, label):
    if value is not None and not isinstance(value, str):
        raise ValueError(f'{label} must be a string or null')
    return value


def normalize_metadata(metadata, match_id):
    """Accept agreed flat fields or one provider match record. Never invent dates."""
    if not isinstance(metadata, dict):
        raise ValueError('Metadata must be one JSON object, not a match list')
    if metadata.get('match_id') is not None:
        if identifier(metadata['match_id'], 'metadata match_id') != match_id:
            raise ValueError('Metadata match_id does not match the manifest')
    result = {key: None for key in META_FIELDS}
    for flat_id, flat_name, nested_key, nested_id, nested_name in (
        ('competition_id', 'competition_name', 'competition', 'competition_id', 'competition_name'),
        ('season_id', 'season', 'season', 'season_id', 'season_name'),
    ):
        nested = metadata.get(nested_key)
        obj = nested if isinstance(nested, dict) else {}
        flat_value = metadata.get(flat_name)
        flat_value = None if isinstance(flat_value, dict) else flat_value
        if obj.get(nested_id) is not None and metadata.get(flat_id) is not None:
            if identifier(obj[nested_id], flat_id) != identifier(metadata[flat_id], flat_id):
                raise ValueError(f'Conflicting {flat_id} metadata')
        if flat_value is not None and obj.get(nested_name) is not None and flat_value != obj[nested_name]:
            raise ValueError(f'Conflicting {flat_name} metadata')
        raw_id = metadata.get(flat_id) if metadata.get(flat_id) is not None else obj.get(nested_id)
        result[flat_id] = identifier(raw_id, flat_id) if raw_id is not None else None
        result[flat_name] = text(flat_value if flat_value is not None else obj.get(nested_name), flat_name)
    for team in ('home_team', 'away_team'):
        raw = metadata.get(team)
        result[team] = text(raw.get(team + '_name') if isinstance(raw, dict) else raw, team)
    raw_date = text(metadata.get('match_date'), 'match_date')
    if raw_date is not None and date.fromisoformat(raw_date).isoformat() != raw_date:
        raise ValueError('match_date must use YYYY-MM-DD')
    result['match_date'] = raw_date
    return result


def read_json(path):
    raw = path.read_bytes()
    return json.loads(raw.decode('utf-8-sig')), hashlib.sha256(raw).hexdigest()


def resolve_path(base, value):
    if not isinstance(value, str) or not value:
        raise ValueError('File paths must be nonempty strings')
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_jobs(manifest):
    manifest = Path(manifest).resolve()
    document, digest = read_json(manifest)
    jobs = document.get('matches') if isinstance(document, dict) else None
    if not isinstance(jobs, list) or not jobs:
        raise ValueError('Manifest requires a nonempty matches array')
    seen, result = set(), []
    for entry in jobs:
        if not isinstance(entry, dict):
            raise ValueError('Each manifest match must be an object')
        mid = identifier(entry.get('match_id'), 'match_id')
        if mid in seen:
            raise ValueError(f'Duplicate match_id: {mid}')
        seen.add(mid)
        path = resolve_path(manifest.parent, entry.get('events'))
        meta = entry.get('metadata')
        if isinstance(meta, str):
            meta, _ = read_json(resolve_path(manifest.parent, meta))
        elif meta is None:
            meta = {}
        normalized = normalize_metadata(meta, mid)
        revision = text(entry.get('source_revision'), 'source_revision')
        result.append((mid, path, normalized, revision))
    return result, digest


def arrow_schema(pa):
    fields = []
    for key in FIELDS:
        kind = (pa.list_(pa.string()) if key in LIST_FIELDS else pa.int64() if key in INT_FIELDS
                else pa.float64() if key in FLOAT_FIELDS else pa.bool_() if key == 'led_to_shot'
                else pa.string())
        fields.append(pa.field(key, kind))
    return pa.schema(fields)


def run_batch(manifest, output, window=15, short_limit=15, parquet=False):
    """Publish one complete run, or leave no output directory on failure.

    Existing run folders are never overwritten. Raw input and summaries are
    processed one match at a time. Metadata/date ordering is not a train split.
    """
    if window is not None and (not isfinite(window) or window <= 0):
        raise ValueError('Window must be positive and finite, or uncapped')
    if not isfinite(short_limit) or short_limit <= 0:
        raise ValueError('Short limit must be positive and finite')
    jobs, manifest_hash = load_jobs(manifest)
    output = Path(output)
    if output.exists():
        raise FileExistsError('Output already exists; choose a new run directory')
    pa = pq = schema = None
    if parquet:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ValueError('Parquet requires: python -m pip install -r src/corners/requirements.txt') from exc
        schema = arrow_schema(pa)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.corner-run-', dir=output.parent))
    writer = None
    try:
        if parquet:
            writer = pq.ParquetWriter(stage / 'corner_summary.parquet', schema, compression='snappy')
        records, total = [], 0
        with (stage / 'corner_summary.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            csv_writer = csv.DictWriter(stream, fieldnames=FIELDS)
            csv_writer.writeheader()
            for mid, path, metadata, revision in jobs:
                events, source_hash = read_json(path)
                if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
                    raise ValueError(f'Match {mid}: expected an array of event objects')
                # Normalize input ordering; timestamps reset at each period.
                for e in events:
                    if not all(k in e for k in ('id', 'period', 'timestamp', 'index')):
                        raise ValueError(f'Match {mid}: event lacks id/period/timestamp/index')
                from .extract import timestamp_seconds
                events.sort(key=lambda e: (e['period'], timestamp_seconds(e['timestamp']), e['index']))
                rows = build_corner_summaries(events, mid, max_seconds=window, short_limit=short_limit)
                for row in rows:
                    row.update(metadata)
                    csv_writer.writerow({k: json.dumps(v) if k in LIST_FIELDS else v for k, v in row.items()})
                if writer is not None and rows:
                    writer.write_table(pa.Table.from_pylist(rows, schema=schema))
                total += len(rows)
                record = dict(match_id=mid, events_sha256=source_hash,
                              metadata=metadata, source_revision=revision,
                              metadata_sha256=hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest(),
                              input_events=len(events), unique_events=len({e['id'] for e in events}),
                              corners=len(rows), shots=sum(r['shot_count'] for r in rows),
                              goals=sum(r['goal_count'] for r in rows),
                              status='ok' if rows else 'no_corners')
                records.append(record)
        if writer is not None:
            writer.close()
            writer = None
        report = dict(schema='corner_summary_batch_v1', manifest_sha256=manifest_hash,
                      settings=dict(window_seconds=window, short_limit=short_limit),
                      matches=records, total_corners=total,
                      metadata_note='Missing metadata is null; exclude incomplete dates/strata from predictive evaluation.')
        (stage / 'run_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        stage.rename(output)
        return report
    except BaseException:
        if writer is not None:
            writer.close()
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New run directory; never overwritten')
    parser.add_argument('--window', choices=['10', '15', '20', 'uncapped'], default='15')
    parser.add_argument('--short-limit', type=float, default=15)
    parser.add_argument('--parquet', action='store_true', help='Write typed Parquet alongside CSV')
    args = parser.parse_args()
    try:
        report = run_batch(args.manifest, args.output,
                           window=None if args.window == 'uncapped' else int(args.window),
                           short_limit=args.short_limit, parquet=args.parquet)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Batch failed: {exc}\n')
    print(f"Processed {len(report['matches'])} matches; {report['total_corners']} corners -> {args.output}")
