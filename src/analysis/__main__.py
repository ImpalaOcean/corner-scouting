"""Team corner summaries, chronological splits and predictive evaluation.

Run from the repository root:
    python -m src.analysis --input outputs/sample_corners/corner_summary.csv --output outputs/analysis_sample

Prematch (dossier) view using only matches before a date; skips evaluation:
    python -m src.analysis --input ... --output ... --cutoff 2016-03-01
"""

import argparse
import json
from pathlib import Path

from .evaluation import (DIFFERENCE_FIELDS, PREDICTION_FIELDS, RELIABILITY_FIELDS,
                         SELECTION_FIELDS, STABILITY_FIELDS, SUMMARY_FIELDS,
                         TEAM_EVAL_FIELDS, evaluate)
from .summary import (PERIOD_FIELDS, SPLIT_FIELDS, TEAM_SUMMARY_FIELDS, AnalysisError,
                      chronological_splits, load_corners, period_breakdown,
                      team_summaries, write_csv)

PRINT_LIMIT = 15


def _pct(value):
    return '  n/a' if value is None else f'{value * 100:5.1f}%'


def _plot_reliability(rows, path):
    """Optional figure for the paper; skipped quietly without matplotlib."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], linestyle=':', color='grey', label='perfect')
    for method in ('pooled', 'shrunk'):
        pts = [r for r in rows if r['method'] == method and r['corners']]
        ax.plot([r['mean_predicted'] for r in pts], [r['observed_rate'] for r in pts],
                marker='o', label=method)
    ax.set_xlabel('predicted shot probability')
    ax.set_ylabel('observed shot rate')
    ax.set_title('Shot creation reliability (test matches)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


def _print_summaries(summaries):
    print(f"{'team':<20}{'comp/season':<22}{'matches':>8}{'corners':>8}"
          f"{'in':>8}{'out':>8}{'short':>8}{'unknown':>8}{'shot rate':>11}{'goals':>6}")
    for s in summaries[:PRINT_LIMIT]:
        label = f"{s['competition_name'] or '?'} {s['season'] or '?'}"[:21]
        print(f"{str(s['team'])[:19]:<20}{label:<22}{s['matches']:>8}{s['corners']:>8}"
              f"{_pct(s['freq_inswinging']):>8}{_pct(s['freq_outswinging']):>8}"
              f"{_pct(s['freq_short']):>8}{_pct(s['freq_unknown']):>8}"
              f"{_pct(s['shot_rate']):>11}{s['goals']:>6}")
    if len(summaries) > PRINT_LIMIT:
        print(f'... {len(summaries) - PRINT_LIMIT} more rows in team_summary_v1.csv')


def _print_evaluation(tables, meta):
    print()
    print(f"Evaluation: {meta['eligible_teams']} eligible teams, "
          f"{meta['test_corners']} test corners in {meta['test_matches']} test matches")
    if meta['note']:
        print(meta['note'])
        return
    print(f"Chosen on validation: alpha = {meta['alpha']}, beta = {meta['beta']}")
    for row in tables['evaluation_summary']:
        print(f"  {row['target']:<9}{row['metric']:<10}{row['method']:<11}"
              f"{row['score']:.4f}  [{row['ci_low']}, {row['ci_high']}]")
    for row in tables['evaluation_differences']:
        if row['difference'] is None:
            continue
        verdict = ('team history helps' if row['ci_high'] is not None and row['ci_high'] < 0
                   else 'team history hurts' if row['ci_low'] is not None and row['ci_low'] > 0
                   else 'no clear difference')
        print(f"  {row['target']:<9}{row['comparison']:<26}{row['difference']:+.4f}  "
              f"[{row['ci_low']}, {row['ci_high']}]  {verdict}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True,
                        help='corner_summary.csv or .parquet from the batch runner')
    parser.add_argument('--output', type=Path, required=True,
                        help='new folder for results (must not already exist)')
    parser.add_argument('--bootstrap', type=int, default=1000,
                        help='match bootstrap draws for intervals (0 turns them off)')
    parser.add_argument('--seed', type=int, default=5118, help='random seed for the bootstrap')
    parser.add_argument('--cutoff', default=None,
                        help='YYYY-MM-DD; summarise only matches before this date and '
                             'skip evaluation (prematch dossier view)')
    args = parser.parse_args()

    if args.output.exists():
        parser.exit(1, f'Output folder already exists: {args.output}. Choose a new name.\n')
    try:
        rows = load_corners(args.input)
        summaries = team_summaries(rows, args.bootstrap, args.seed, args.cutoff)
        periods = period_breakdown(rows, args.cutoff)
        splits = chronological_splits(rows)
        tables, meta = (None, None) if args.cutoff else evaluate(
            rows, splits, args.bootstrap, args.seed)
    except AnalysisError as exc:
        parser.exit(1, f'Analysis failed: {exc}\n')

    args.output.mkdir(parents=True)
    write_csv(args.output / 'team_summary_v1.csv', TEAM_SUMMARY_FIELDS, summaries)
    write_csv(args.output / 'period_summary.csv', PERIOD_FIELDS, periods)
    write_csv(args.output / 'match_splits.csv', SPLIT_FIELDS, splits)
    figure = False
    if tables is not None:
        folder = args.output / 'evaluation'
        folder.mkdir()
        for name, fields in (('alpha_selection', SELECTION_FIELDS),
                             ('evaluation_summary', SUMMARY_FIELDS),
                             ('evaluation_differences', DIFFERENCE_FIELDS),
                             ('team_evaluation', TEAM_EVAL_FIELDS),
                             ('reliability', RELIABILITY_FIELDS),
                             ('profile_stability', STABILITY_FIELDS),
                             ('team_predictions', PREDICTION_FIELDS)):
            write_csv(folder / f'{name}.csv', fields, tables[name])
        if tables['reliability']:
            figure = _plot_reliability(tables['reliability'], folder / 'reliability.png')

    counts = {}
    for s in splits:
        counts[s['split']] = counts.get(s['split'], 0) + 1
    (args.output / 'analysis_manifest.json').write_text(json.dumps({
        'schema': 'team_summary_v1',
        'input': str(args.input),
        'corners': len(rows),
        'teams': len(summaries),
        'matches_by_split': counts,
        'window_seconds': rows[0]['window_seconds'] if rows else None,
        'short_limit': rows[0]['short_limit'] if rows else None,
        'date_cutoff': args.cutoff,
        'bootstrap_draws': args.bootstrap,
        'seed': args.seed,
        'evaluation': meta,
        'reliability_figure': figure,
    }, indent=2), encoding='utf-8')

    print(f'{len(rows)} corners, {len(summaries)} team rows -> {args.output}')
    _print_summaries(summaries)
    print('Match splits: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    small = sum(1 for s in summaries if s['small_sample'])
    if small:
        print(f'{small} of {len(summaries)} team rows are below 10 matches / 30 corners '
              '(descriptive only, not for prediction).')
    if meta is not None:
        _print_evaluation(tables, meta)
    else:
        print(f'Prematch view before {args.cutoff}; evaluation skipped.')


if __name__ == '__main__':
    main()
