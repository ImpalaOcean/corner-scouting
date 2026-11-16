"""Run ingestion or a local manifest through both extractors, comparison and analysis."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

from src.corners.batch import load_jobs, run_batch as python_batch
from src.data.pipeline import ingest
from .common import ROOT, environment, new_directory, sha, write_json
from .compare import compare_tables, load_table
from .extract import run_batch as sql_batch


def run(output, *, manifest=None, config=None, offline=False, window=15, short_limit=15,
        parquet=False, threads=1, bootstrap=100, analysis=True, frames_dir=None):
    if (manifest is None) == (config is None):
        raise ValueError('Supply exactly one of manifest or config')
    if bootstrap < 0:
        raise ValueError('Bootstrap draws cannot be negative')
    stage_times, evidence = {}, environment()
    config_before = sha(config) if config is not None else None
    current_stage = 'initialization'
    started = perf_counter()
    with new_directory(output) as stage:
        def timed(name, function):
            nonlocal current_stage
            current_stage = name
            begin = perf_counter()
            result = function()
            stage_times[name] = perf_counter() - begin
            return result

        def command(name, args):
            def invoke():
                result = subprocess.run([sys.executable, '-B', '-m', *args], cwd=ROOT,
                                        text=True, encoding='utf-8', errors='replace', capture_output=True,
                                        env={**os.environ, 'PYTHONUTF8': '1'})
                (stage / f'{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
                if result.returncode:
                    raise ValueError(f'{name} exited {result.returncode}: {result.stderr[-2000:]}')
            timed(name, invoke)

        try:
            coverage = None
            if config is not None:
                settings = json.loads(Path(config).read_text(encoding='utf-8'))
                settings['output_dir'] = str(stage / 'ingestion')
                coverage = timed('ingestion', lambda: ingest(settings, offline=offline, parquet=parquet))
                if not coverage['complete']:
                    raise ValueError('Incomplete ingestion coverage; downstream processing refused')
                manifest = stage / 'ingestion/batch_manifest.json'
            manifest = Path(manifest).resolve()
            jobs, manifest_hash = load_jobs(manifest)
            snapshots = {str(path.resolve()): sha(path) for _, path, _, _ in jobs}
            snapshots[str(manifest)] = manifest_hash
            raw_manifest = json.loads(manifest.read_text(encoding='utf-8'))
            for entry in raw_manifest['matches']:
                if isinstance(entry.get('metadata'), str):
                    meta_path = (manifest.parent / entry['metadata']).resolve()
                    snapshots[str(meta_path)] = sha(meta_path)
            reference = timed('python_extraction', lambda: python_batch(manifest, stage / 'python', window, short_limit, parquet))
            candidate = timed('sql_extraction', lambda: sql_batch(manifest, stage / 'sql', window, short_limit, parquet, threads))
            comparison = timed('comparison', lambda: compare_tables(stage / 'python/corner_summary.csv',
                                    stage / 'sql/corner_summary.csv', stage / 'comparison'))
            if comparison['status'] != 'match':
                raise ValueError('Python/SQL mismatch; see comparison/differences.csv')
            current_stage = 'reconciliation'
            rows = load_table(stage / 'python/corner_summary.csv')
            for key, row in rows.items():
                if (row['led_to_shot'] != (row['shot_count'] > 0)
                    or len(row['shot_event_ids']) != row['shot_count']
                    or len(set(row['shot_event_ids'])) != len(row['shot_event_ids'])
                    or not set(row['shot_event_ids']).issubset(row['chain_event_ids'])):
                    raise ValueError(f'Invalid shot/chain reconciliation: {key}')
            if coverage:
                expected = {m['match_id']: m['corner_count'] for m in coverage['matches']}
                actual = {m['match_id']: m['corners'] for m in reference['matches']}
                if expected != actual:
                    raise ValueError('Ingestion/extraction per-match corner counts disagree')
            if analysis:
                command('analysis', ['src.analysis', '--input', str(stage / 'python/corner_summary.csv'),
                                    '--output', str(stage / 'analysis'), '--bootstrap', str(bootstrap)])
                # Analysis records an absolute input path. Point it at the
                # published location instead of the soon-to-be-renamed staging tree.
                analysis_manifest = stage / 'analysis/analysis_manifest.json'
                details = json.loads(analysis_manifest.read_text(encoding='utf-8'))
                details['input'] = str(Path(output).resolve() / 'python/corner_summary.csv')
                details['runner_rebased_input_path'] = True
                write_json(analysis_manifest, details)
            if frames_dir is not None:
                frames_dir = Path(frames_dir).resolve()
                if not frames_dir.is_dir():
                    raise ValueError(f'Frame directory does not exist: {frames_dir}')
                for mid, _, _, _ in jobs:
                    frame = frames_dir / f'{mid}.json'
                    if frame.is_file():
                        snapshots[str(frame)] = sha(frame)
                command('setups', ['src.setups', '--corners', str(stage / 'python/corner_summary.csv'),
                                   '--three-sixty-dir', str(frames_dir), '--output', str(stage / 'setups')])
                with (stage / 'setups/setup_summary.csv').open(encoding='utf-8-sig', newline='') as stream:
                    setup_rows = list(csv.DictReader(stream))
                setup_keys = [(int(r['match_id']), r['corner_event_id']) for r in setup_rows]
                if len(setup_keys) != len(rows) or set(setup_keys) != set(rows):
                    raise ValueError('Setup rows do not reconcile with corner keys')
            current_stage = 'final_input_verification'
            if any(sha(p) != digest for p, digest in snapshots.items()):
                raise ValueError('An input changed during the run')
            if config is not None and sha(config) != config_before:
                raise ValueError('Configuration changed during the run')
            report = dict(schema='systems_run_v1', status='complete', environment=evidence,
                          settings=dict(window_seconds=window, short_limit=short_limit, parquet=parquet,
                                        threads=threads, bootstrap_draws=bootstrap, analysis=analysis),
                          manifest_sha256=manifest_hash, config_sha256=config_before,
                          input_files=[dict(path=os.path.relpath(p, stage), sha256=d) for p, d in snapshots.items()],
                          matches=len(jobs), corners=reference['total_corners'], comparison_status=comparison['status'],
                          stage_seconds=stage_times, total_seconds=perf_counter()-started,
                          timing_note='Single-run diagnostics, not a repeated benchmark. Python and SQL share the OS cache; SQL runs second. SQL stage includes connection, provenance and export.',
                          dossier_status='not_run: separate select/build CLI available; timing scope remains to be agreed',
                          artifacts_sha256={p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob('*') if p.is_file()})
            write_json(stage / 'run.json', report)
        except (Exception, KeyboardInterrupt) as exc:
            # Retain comparison/log evidence in a clearly failed run, never as success.
            write_json(stage / 'run.json', dict(schema='systems_run_v1', status='failed', failed_stage=current_stage,
                        error=str(exc), environment=evidence, stage_seconds=stage_times))
            report = None
    if report is None:
        raise ValueError(f'Run failed; inspect {Path(output) / "run.json"}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--manifest', type=Path)
    inputs.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--window', choices=['10', '15', '20', 'uncapped'], default='15')
    parser.add_argument('--short-limit', type=float, default=15)
    parser.add_argument('--parquet', action='store_true')
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--bootstrap', type=int, default=100)
    parser.add_argument('--skip-analysis', action='store_true')
    parser.add_argument('--frames-dir', type=Path)
    args = parser.parse_args()
    try:
        report = run(args.output, manifest=args.manifest, config=args.config, offline=args.offline,
                     window=None if args.window == 'uncapped' else int(args.window), short_limit=args.short_limit,
                     parquet=args.parquet, threads=args.threads, bootstrap=args.bootstrap,
                     analysis=not args.skip_analysis, frames_dir=args.frames_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Systems run failed: {exc}\n')
    print(f"Complete: {report['matches']} matches, {report['corners']} corners; SQL/Python agreement -> {args.output}")


if __name__ == '__main__':
    main()
