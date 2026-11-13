"""Compare analysis runs made from different corner extraction settings.

This command compares outcome windows only (10, 15, 20 seconds and uncapped),
requiring the same short threshold, corner population and delivery attributes.
Diego's batch runner makes one corner table per setting; run the
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
from .contracts import input_contract, sha256
from .publication import new_output_directory


def _read_csv(path):
    if not path.exists():
        raise AnalysisError(f'missing required analysis artifact: {path}')
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
    warnings = []
    if manifest.get('status') not in (None, 'complete'):
        raise AnalysisError(f'analysis is not complete: {folder}')
    for name, expected in manifest.get('outputs_sha256', {}).items():
        artifact = (folder / name).resolve()
        if not artifact.is_relative_to(folder.resolve()) or not artifact.is_file() or sha256(artifact) != expected:
            raise AnalysisError(f'analysis artifact hash mismatch: {name}')
    contract_path = folder / 'input_contract.json'
    saved = None
    if contract_path.exists() and manifest.get('input_contract_sha256'):
        if sha256(contract_path) != manifest['input_contract_sha256']:
            raise AnalysisError('input contract hash mismatch')
        saved = json.loads(contract_path.read_text(encoding='utf-8'))
    source = Path(manifest['input'])
    if not source.is_absolute():
        # Old manifests stored the path relative to the invocation's repository.
        source = Path.cwd() / source
    current_contract = None
    try:
        if source.is_file():
            current_contract = input_contract(source)
    except OSError as exc:
        warnings.append(f'Original input cannot be read: {exc}')
    if current_contract is not None:
        contract = current_contract
        expected = manifest.get('input_sha256')
        if expected and contract['input_sha256'] != expected:
            raise AnalysisError('analysis input hash mismatch')
        if saved is not None and saved != contract:
            raise AnalysisError('saved contract does not match source input')
        if not expected:
            warnings.append('Legacy run has no recorded input hash; current input compatibility is checked, but its historical association with these results is unverified.')
    elif saved is not None and manifest.get('input_sha256') == saved.get('input_sha256'):
        contract = saved
        warnings.append('Original input unavailable; using the hash-verified saved input contract. Raw bytes cannot be rechecked here.')
    else:
        raise AnalysisError('Cannot verify corner population: original input unavailable and no hash-verified contract')
    if not manifest.get('outputs_sha256'):
        warnings.append('Legacy result artifacts have no recorded content hashes.')
    for field in ('window_seconds', 'short_limit', 'corners'):
        if field not in manifest or manifest[field] != contract[field]:
            raise AnalysisError(f'analysis manifest disagrees with input {field}')
    return {
        'folder': str(folder),
        'label': _label(manifest),
        'manifest': manifest,
        'contract': contract,
        'provenance_warnings': warnings,
        'summary': _read_csv(folder / 'evaluation' / 'evaluation_summary.csv'),
        'differences': _read_csv(folder / 'evaluation' / 'evaluation_differences.csv'),
        'teams': _read_csv(folder / 'team_summary_v1.csv'),
    }


def compare_runs(runs):
    if len(runs) < 2:
        raise AnalysisError('Give at least two runs to compare')
    baseline = runs[0]
    for run in runs:
        contract = run.get('contract')
        if not contract:
            raise AnalysisError('Missing verified corner population contract')
        for field in ('population_sha256', 'invariants_sha256', 'invariant_fields', 'corners', 'short_limit'):
            if contract[field] != baseline['contract'][field]:
                raise AnalysisError(f'incompatible window comparison: {field}')
        for field in ('date_cutoff', 'seed', 'bootstrap_draws', 'evaluation_protocol', 'analysis_code_sha256'):
            if run['manifest'].get(field) != baseline['manifest'].get(field):
                raise AnalysisError(f'incompatible analysis control: {field}')
        for field in ('window_seconds', 'short_limit', 'corners'):
            if run['manifest'].get(field) != contract[field]:
                raise AnalysisError(f'analysis manifest disagrees with input {field}')
        if not run['manifest'].get('analysis_code_sha256'):
            run.setdefault('provenance_warnings', []).append('Analysis code revision/content is not recorded; method equivalence is unverified.')
    team_populations = [sorted((t['competition_id'], t['season_id'], t['team_id'],
                                t['competition_name'], t['season'], t['team'], t['corners'])
                               for t in r['teams']) for r in runs]
    if any(pop != team_populations[0] for pop in team_populations):
        raise AnalysisError('incompatible team-summary populations or metadata')
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
                               'corners': row['corners'], 'status': row.get('status', 'not_recorded'),
                               'reason': row.get('reason', '')})
        for row in run['differences']:
            evaluation.append({'run': run['label'], 'folder': run['folder'],
                               'kind': 'difference', 'target': row['target'],
                               'name': row['comparison'], 'value': row['difference'],
                               'ci_low': row['ci_low'], 'ci_high': row['ci_high'],
                               'alpha': meta.get('alpha'), 'beta': meta.get('beta'),
                               'corners': row['corners'], 'status': row.get('status', 'not_recorded'),
                               'reason': row.get('reason', '')})

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
    with new_output_directory(args.output) as staging:
        write_csv(staging / 'sensitivity_evaluation.csv',
                  ['run', 'folder', 'kind', 'target', 'name', 'value', 'ci_low', 'ci_high',
                   'alpha', 'beta', 'corners', 'status', 'reason'], evaluation)
        write_csv(staging / 'sensitivity_team_rates.csv',
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
        (staging / 'comparison_manifest.json').write_text(json.dumps({
            'comparison': 'outcome-window-only',
            'runs': [{'folder': r['folder'], 'contract': r['contract'], 'provenance_warnings': r['provenance_warnings']} for r in runs]
        }, indent=2), encoding='utf-8')
        for run in runs:
            for warning in run['provenance_warnings']:
                print(f"  Provenance warning ({run['folder']}): {warning}")


if __name__ == '__main__':
    main()
