"""Corpus comparisons and repeated, explicitly scoped systems measurements."""
import argparse
from contextlib import contextmanager
import csv
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter

from src.corners.batch import load_jobs
from .common import ROOT, environment, sha, write_json
from .compare import compare_tables
from .run import run as pipeline


def summarize(values):
    """Sample SD is undefined for a single repetition, not silently zero."""
    if not values:
        raise ValueError('At least one timing is required')
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else None
    return dict(repetitions=len(values), mean_seconds=mean, median_seconds=statistics.median(values),
                min_seconds=min(values), max_seconds=max(values), sample_sd_seconds=sd,
                coefficient_of_variation=sd / mean if sd is not None and mean else None)


def hardware():
    result = environment()
    if platform.system() == 'Windows':
        command = ('$p=Get-CimInstance Win32_Processor; $m=Get-CimInstance Win32_ComputerSystem; '
                   '@{cpu=$p.Name;physical_cores=$p.NumberOfCores;logical_processors=$p.NumberOfLogicalProcessors;'
                   'physical_memory_bytes=$m.TotalPhysicalMemory}|ConvertTo-Json -Compress')
        result['hardware'] = json.loads(subprocess.check_output(
            ['powershell', '-NoProfile', '-Command', command], text=True))
    else:
        result['hardware'] = dict(cpu=platform.processor(), physical_memory_bytes=None,
                                  note='Supply physical RAM and CPU details if not reported by this host')
    return result


@contextmanager
def experiment(output, kind):
    output = Path(output).resolve()
    # Keep experiment paths stable: dossier selection plans freeze absolute paths.
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'status.json', dict(status='running', kind=kind))
    try:
        yield output
        write_json(output / 'status.json', dict(status='complete', kind=kind))
    except BaseException as exc:
        write_json(output / 'status.json', dict(status='failed', kind=kind, error=str(exc)))
        raise


def execute(args, log, cwd=ROOT):
    """Fresh-process CLI wall time: startup, loading/hashing, computation and export."""
    start = perf_counter()
    result = subprocess.run([sys.executable, '-B', *args], cwd=cwd,
                            env={**os.environ, 'PYTHONUTF8': '1'},
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    elapsed = perf_counter() - start
    Path(log).write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError(f'Command exited {result.returncode}; inspect {log}')
    return elapsed


def source_snapshot(manifest):
    jobs, digest = load_jobs(manifest)
    return dict(manifest_sha256=digest, matches=[dict(match_id=mid, events_sha256=sha(path),
                metadata=meta, source_revision=rev) for mid, path, meta, rev in jobs])


def verify_snapshot(manifest, snapshot):
    if source_snapshot(manifest) != snapshot:
        raise ValueError('Manifest or raw inputs changed during experiment')


def write_table(path, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def corpus(manifest, output, threads=1, parquet=True):
    with experiment(output, 'corpus-comparison') as folder:
        evidence = hardware()
        snapshot = source_snapshot(manifest)
        rows = []
        for window in (10, 15, 20, None):
            label = 'uncapped' if window is None else str(window)
            print(f'Comparing window {label}: {len(snapshot["matches"])} matches', flush=True)
            pipeline(folder / f'w{label}', manifest=manifest, window=window, threads=threads,
                     parquet=parquet, analysis=False)
            reference = json.loads((folder / f'w{label}/python/run_manifest.json').read_text())
            comparison = json.loads((folder / f'w{label}/comparison/comparison.json').read_text())
            rows.append(dict(window=label, short_limit=15, matches=len(reference['matches']),
                             corners=reference['total_corners'], shots=sum(m['shots'] for m in reference['matches']),
                             goals=sum(m['goals'] for m in reference['matches']),
                             missing_keys=comparison['missing_keys'], extra_keys=comparison['extra_keys'],
                             field_mismatches=comparison['field_mismatches'],
                             provenance_errors=len(comparison['provenance_errors']), status=comparison['status']))
            print(rows[-1], flush=True)
        verify_snapshot(manifest, snapshot)
        write_table(folder / 'summary.csv', rows)
        write_json(folder / 'report.json', dict(status='complete', environment=evidence, source=snapshot,
                   settings=dict(windows=[10,15,20,None], short_limit=15, threads=threads, parquet=parquet),
                   comparisons=rows, artifacts_sha256={p.relative_to(folder).as_posix():sha(p)
                       for p in folder.rglob('*') if p.is_file() and p.name != 'status.json'}))
    return rows


def extraction_benchmark(manifest, output, repetitions=5, warmups=1, threads=1, parquet=True):
    if repetitions < 2 or warmups < 1 or threads < 1:
        raise ValueError('Require >=2 measured repetitions, >=1 warmup and >=1 SQL thread')
    with experiment(output, 'extraction-benchmark') as folder:
        evidence, snapshot, rows = hardware(), source_snapshot(manifest), []
        samples = dict(python=[], sql=[])
        for iteration in range(warmups + repetitions):
            phase = 'warmup' if iteration < warmups else 'measured'
            pair = folder / f'{iteration:02}-{phase}'
            pair.mkdir()
            order = ('python', 'sql') if iteration % 2 == 0 else ('sql', 'python')
            for implementation in order:
                args = (['src/run_corner_batch.py'] if implementation == 'python'
                        else ['-m', 'src.systems.extract'])
                args += ['--manifest', str(Path(manifest).resolve()), '--output', str(pair / implementation),
                         '--window', '15', '--short-limit', '15']
                if parquet:
                    args += ['--parquet']
                if implementation == 'sql':
                    args += ['--threads', str(threads)]
                elapsed = execute(args, pair / f'{implementation}.log')
                rows.append(dict(iteration=iteration, phase=phase, order=order.index(implementation)+1,
                                 implementation=implementation, seconds=elapsed))
                if phase == 'measured':
                    samples[implementation].append(elapsed)
                print(f'{phase} {iteration} {implementation}: {elapsed:.3f}s', flush=True)
            comparison = compare_tables(pair/'python/corner_summary.csv', pair/'sql/corner_summary.csv', pair/'comparison')
            if comparison['status'] != 'match':
                raise ValueError('Benchmark pair disagrees; performance conclusion refused')
        verify_snapshot(manifest, snapshot)
        summaries = {k:summarize(v) for k,v in samples.items()}
        write_table(folder / 'timings.csv', rows)
        report = dict(status='complete', environment=evidence, source=snapshot, repetitions=repetitions,
                      warmup_pairs=warmups, threads=threads, parquet=parquet, window_seconds=15, short_limit=15,
                      scope='Fresh-process local batch CLI wall time, including startup/imports, loading/hashing, extraction, provenance, CSV/optional Parquet export. No downloading, ingestion, analysis or comparison time.',
                      cache_conditions='One or more untimed warmup pairs; OS cache not flushed or controlled. Alternating implementation order. No concurrent experiment jobs intentionally run. Warm-cache intent, not guaranteed residency.',
                      summaries=summaries, sql_over_python_mean=summaries['sql']['mean_seconds']/summaries['python']['mean_seconds'],
                      comparisons='Every warmup/measured pair checked across all 35 fields outside timing',
                      timings_sha256=sha(folder/'timings.csv'))
        write_json(folder / 'report.json', report)
    return report


def dossier_benchmark(corners, coverage, output, repetitions=5, warmups=1):
    if repetitions < 2 or warmups < 1:
        raise ValueError('Require >=2 measured repetitions and >=1 warmup')
    with experiment(output, 'dossier-benchmark') as folder:
        evidence = hardware()
        sources = dict(corners=sha(corners), coverage=sha(coverage))
        samples = dict(selection=[], build=[])
        rows, fingerprints = [], []
        for iteration in range(warmups + repetitions):
            phase = 'warmup' if iteration < warmups else 'measured'
            pair = folder / f'{iteration:02}-{phase}'
            pair.mkdir()
            plan, dossier = pair/'selection.json', pair/'dossier'
            selection_time = execute(['-m','src.dossier','select','--corners',str(Path(corners).resolve()),
                        '--coverage-manifest',str(Path(coverage).resolve()),'--selection',str(plan),
                        '--output',str(dossier)], pair/'selection.log')
            selection = json.loads(plan.read_text())
            fixture = selection['fixture']
            names = [t['team'] for t in fixture['teams']]
            if fixture['match_date'] != '2015-12-13' or names != ['Aston Villa', 'Arsenal']:
                raise ValueError(f'Dossier selected a different fixture: {fixture}')
            build_time = execute(['-m','src.dossier','build','--selection',str(plan)], pair/'build.log')
            result = json.loads((dossier/'dossier.json').read_text())
            # Content identity excludes variable selection timestamps/provenance paths.
            fingerprints.append(sha(dossier/'dossier.json'))
            if result['cutoff'] != '2015-12-13':
                raise ValueError('Dossier cutoff changed')
            for stage, elapsed in (('selection', selection_time), ('build', build_time)):
                rows.append(dict(iteration=iteration, phase=phase, stage=stage, seconds=elapsed))
                if phase == 'measured':
                    samples[stage].append(elapsed)
            print(f'{phase} {iteration}: selection {selection_time:.3f}s; build {build_time:.3f}s', flush=True)
        if len(set(fingerprints)) != 1:
            raise ValueError('Repeated dossiers have differing analytical content')
        if sources != dict(corners=sha(corners), coverage=sha(coverage)):
            raise ValueError('Dossier input changed during timing')
        write_table(folder/'timings.csv', rows)
        report = dict(status='complete', environment=evidence, input_sha256=sources, fixture=fixture,
                      repetitions=repetitions, warmups=warmups, bootstrap_draws=selection['settings']['bootstrap_draws'],
                      seed=selection['settings']['seed'], threads='Python process; no explicit numerical thread setting',
                      cache_conditions='Fresh process each command; untimed warmup, no OS-cache flushing. Selection immediately precedes build and can warm input pages.',
                      selection_scope='CLI startup/imports, metadata-only fixture selection, source hashing, code evidence, selection-plan serialization.',
                      build_scope='CLI startup/imports, selection-plan loading, code/source verification hashes, CSV loading and past-only filtering, eligibility/statistics, alpha/beta selection, refit, 1000-draw bootstrap intervals, rendering and all dossier exports/output hashes, final source rehash. Upstream download/ingestion/extraction excluded.',
                      rendering_only='not measured separately (optional)', summaries={k:summarize(v) for k,v in samples.items()},
                      dossier_json_sha256=fingerprints[0], timings_sha256=sha(folder/'timings.csv'))
        write_json(folder/'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    for name in ('corpus', 'extraction-benchmark', 'dossier-benchmark'):
        item = sub.add_parser(name)
        item.add_argument('--output', type=Path, required=True)
        if name != 'dossier-benchmark':
            item.add_argument('--manifest', type=Path, required=True)
            item.add_argument('--threads', type=int, default=1)
            item.add_argument('--csv-only', action='store_true')
        else:
            item.add_argument('--corners', type=Path, required=True)
            item.add_argument('--coverage-manifest', type=Path, required=True)
        if name != 'corpus':
            item.add_argument('--repetitions', type=int, default=5)
            item.add_argument('--warmups', type=int, default=1)
    args = parser.parse_args()
    try:
        if args.mode == 'corpus':
            corpus(args.manifest, args.output, args.threads, not args.csv_only)
        elif args.mode == 'extraction-benchmark':
            extraction_benchmark(args.manifest, args.output, args.repetitions, args.warmups, args.threads, not args.csv_only)
        else:
            dossier_benchmark(args.corners, args.coverage_manifest, args.output, args.repetitions, args.warmups)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Experiment failed: {exc}\n')


if __name__ == '__main__':
    main()
