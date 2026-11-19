"""Run the independent DuckDB extractor against a local batch manifest."""
import argparse
import csv
import json
from math import isfinite
from pathlib import Path
from time import perf_counter

import duckdb

from src.corners.batch import FIELDS, LIST_FIELDS, arrow_schema, load_jobs
from .common import environment, new_directory, sha, write_json

SQL_PATH = Path(__file__).with_name('extraction.sql')


def extract_match(events, match_id, window=15, short_limit=15, connection=None):
    """Load raw event objects; SQL performs ordering and every extraction rule."""
    if window is not None and (not isfinite(window) or window <= 0):
        raise ValueError('Window must be positive and finite, or uncapped')
    if not isfinite(short_limit) or short_limit <= 0:
        raise ValueError('Short limit must be positive and finite')
    if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
        raise ValueError('Expected an array of event objects')
    for e in events:
        if not all(k in e for k in ('id', 'period', 'timestamp', 'index')):
            raise ValueError('Event lacks id/period/timestamp/index')
        if not isinstance(e['id'], str) or not e['id']:
            raise ValueError('Event ID must be a nonempty string')
        if type(e['period']) is not int or type(e['index']) is not int:
            raise ValueError('Event period/index must be integers')
        parts = e['timestamp'].split(':')
        if len(parts) != 3 or not all(isfinite(float(p)) for p in parts):
            raise ValueError('Invalid event timestamp')
        int(parts[0]), int(parts[1])
    own = connection is None
    con = connection if connection is not None else duckdb.connect()
    try:
        # Explicit ordinality avoids relying on an unspecified database row order.
        con.execute('CREATE OR REPLACE TEMP TABLE raw_events AS '
                    'SELECT value AS payload, CAST(key AS BIGINT) AS source_position FROM json_each(?)',
                    [json.dumps(events, allow_nan=False)])
        cursor = con.execute(SQL_PATH.read_text(encoding='utf-8'),
                             dict(match_id=match_id, window_seconds=window, short_limit=short_limit))
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, values)) for values in cursor.fetchall()]
    finally:
        if own:
            con.close()


def run_batch(manifest, output, window=15, short_limit=15, parquet=False, threads=1):
    if threads < 1:
        raise ValueError('Threads must be positive')
    if window is not None and (not isfinite(window) or window <= 0):
        raise ValueError('Window must be positive and finite, or uncapped')
    if not isfinite(short_limit) or short_limit <= 0:
        raise ValueError('Short limit must be positive and finite')
    jobs, manifest_hash = load_jobs(manifest)
    evidence = environment()
    writer = None
    with new_directory(output) as stage, duckdb.connect() as con:
        con.execute('SET threads = ?', [threads])
        try:
            if parquet:
                import pyarrow as pa
                import pyarrow.parquet as pq
                schema = arrow_schema(pa)
                writer = pq.ParquetWriter(stage / 'corner_summary.parquet', schema, compression='snappy')
            records, total = [], 0
            with (stage / 'corner_summary.csv').open('w', newline='', encoding='utf-8-sig') as stream:
                csv_writer = csv.DictWriter(stream, fieldnames=FIELDS)
                csv_writer.writeheader()
                for mid, path, metadata, revision in jobs:
                    start = perf_counter()
                    before = sha(path)
                    events = json.loads(path.read_text(encoding='utf-8-sig'))
                    loaded = perf_counter()
                    rows = extract_match(events, mid, window, short_limit, con)
                    extracted = perf_counter()
                    for row in rows:
                        row.update(metadata)
                        csv_writer.writerow({k: json.dumps(v) if k in LIST_FIELDS else v for k, v in row.items()})
                    if writer is not None and rows:
                        writer.write_table(pa.Table.from_pylist(rows, schema=schema))
                    if sha(path) != before:
                        raise ValueError(f'Input changed during extraction: {path}')
                    total += len(rows)
                    records.append(dict(match_id=mid, events_sha256=before, metadata=metadata,
                        source_revision=revision, input_events=len(events), corners=len(rows),
                        shots=sum(r['shot_count'] for r in rows), goals=sum(r['goal_count'] for r in rows),
                        status='ok' if rows else 'no_corners',
                        load_seconds=loaded-start, sql_load_query_fetch_seconds=extracted-loaded))
            if writer is not None:
                writer.close()
                writer = None
            if sha(manifest) != manifest_hash:
                raise ValueError('Input manifest changed during extraction')
            report = dict(schema='corner_summary_batch_v1', implementation='duckdb-sql-v1',
                          manifest_sha256=manifest_hash,
                          settings=dict(window_seconds=window, short_limit=short_limit),
                          threads=threads, matches=records, total_corners=total, environment=evidence,
                          outputs_sha256={p.name: sha(p) for p in stage.iterdir() if p.is_file()})
            write_json(stage / 'run_manifest.json', report)
        finally:
            if writer is not None:
                writer.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--window', choices=['10', '15', '20', 'uncapped'], default='15')
    parser.add_argument('--short-limit', type=float, default=15)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--parquet', action='store_true')
    args = parser.parse_args()
    try:
        report = run_batch(args.manifest, args.output, None if args.window == 'uncapped' else int(args.window),
                           args.short_limit, args.parquet, args.threads)
    except (OSError, ValueError, KeyError, TypeError, duckdb.Error) as exc:
        parser.exit(1, f'SQL extraction failed: {exc}\n')
    print(f"SQL extracted {report['total_corners']} corners from {len(report['matches'])} matches -> {args.output}")


if __name__ == '__main__':
    main()
