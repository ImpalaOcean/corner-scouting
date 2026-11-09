"""Compare analysis runs made from different corner extraction settings.

The proposal asks how sensitive the findings are to the outcome chain
definition (10, 15, 20 second and uncapped windows) and to the short corner
limit. Diego's batch runner makes one corner table per setting; run the
analysis once on each, then compare the folders here:

    python -m src.analysis.compare --runs outputs/analysis_w10 outputs/analysis_w15 outputs/analysis_w20 outputs/analysis_uncapped --output outputs/sensitivity

Writes:
  sensitivity_evaluation.csv   headline scores and differences per run
  sensitivity_team_rates.csv   each team's shot rate per run, with the spread
"""

import argparse
import csv
import json
from pathlib import Path

from .summary import AnalysisError, write_csv


def _read_csv(path):
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def _label(manifest):
    window = manifest.get('window_seconds')
    window = 'uncapped' if window is None else f'{float(window):g}s'
    return f"window {window}, short {float(manifest.get('short_limit') or 0):g}"


def load_run(folder):
    folder = Path(folder)
    manifest_path = folder / 'analysis_manifest.json'
    if not manifest_path.exists():
        raise AnalysisError(f'not an analysis output folder: {folder}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    return {
        'folder': str(folder),
        'label': _label(manifest),
        'manifest': manifest,
        'summary': _read_csv(folder / 'evaluation' / 'evaluation_summary.csv'),
        'differences': _read_csv(folder / 'evaluation' / 'evaluation_differences.csv'),
        'teams': _read_csv(folder / 'team_summary_v1.csv'),
    }


def compare_runs(runs):
    labels = [r['label'] for r in runs]
    if len(set(labels)) != len(labels):
        raise AnalysisError('two runs have the same extraction settings; compare different ones')
    evaluation = []
    for run in runs:
        meta = run['manifest'].get('evaluation') or {}
        for row in run['summary']:
            evaluation.append({'run': run['label'], 'folder': run['folder'],
                               'kind': 'score', 'target': row['target'],
                               'name': row['method'], 'value': row['score'],
                               'ci_low': row['ci_low'], 'ci_high': row['ci_high'],
                               'alpha': meta.get('alpha'), 'beta': meta.get('beta'),
                               'corners': row['corners']})
        for row in run['differences']:
            evaluation.append({'run': run['label'], 'folder': run['folder'],
                               'kind': 'difference', 'target': row['target'],
                               'name': row['comparison'], 'value': row['difference'],
                               'ci_low': row['ci_low'], 'ci_high': row['ci_high'],
                               'alpha': meta.get('alpha'), 'beta': meta.get('beta'),
                               'corners': row['corners']})

    rates = {}
    for run in runs:
        for t in run['teams']:
            key = (t['competition_id'], t['season_id'], t['team_id'])
            entry = rates.setdefault(key, {'competition_name': t['competition_name'],
                                           'season': t['season'], 'team': t['team'],
                                           'corners': t['corners']})
            entry[run['label']] = t['shot_rate']
    team_rows = []
    for key in sorted(rates):
        entry = rates[key]
        values = [float(entry[l]) for l in labels if entry.get(l) not in (None, '')]
        entry['shot_rate_spread'] = round(max(values) - min(values), 4) if values else None
        team_rows.append(entry)
    team_rows.sort(key=lambda e: -(e['shot_rate_spread'] or 0))
    return evaluation, team_rows, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runs', nargs='+', required=True, type=Path,
                        help='two or more analysis output folders')
    parser.add_argument('--output', type=Path, required=True, help='new folder for the comparison')
    args = parser.parse_args()
    if len(args.runs) < 2:
        parser.exit(1, 'Give at least two runs to compare.\n')
    if args.output.exists():
        parser.exit(1, f'Output folder already exists: {args.output}. Choose a new name.\n')
    try:
        runs = [load_run(folder) for folder in args.runs]
        evaluation, team_rows, labels = compare_runs(runs)
    except AnalysisError as exc:
        parser.exit(1, f'Comparison failed: {exc}\n')
    args.output.mkdir(parents=True)
    write_csv(args.output / 'sensitivity_evaluation.csv',
              ['run', 'folder', 'kind', 'target', 'name', 'value', 'ci_low', 'ci_high',
               'alpha', 'beta', 'corners'], evaluation)
    write_csv(args.output / 'sensitivity_team_rates.csv',
              ['competition_name', 'season', 'team', 'corners'] + labels + ['shot_rate_spread'],
              team_rows)
    print(f'Compared {len(runs)} runs -> {args.output}')
    for row in evaluation:
        if row['kind'] == 'difference' and row['name'] == 'shrunk_minus_pooled':
            print(f"  {row['run']:<27}{row['target']:<9}shrunk minus pooled {row['value']} "
                  f"[{row['ci_low']}, {row['ci_high']}]")
    if team_rows:
        top = team_rows[0]
        print(f"  Largest shot rate change: {top['team']} ({top['competition_name']} "
              f"{top['season']}), spread {top['shot_rate_spread']}")


if __name__ == '__main__':
    main()
