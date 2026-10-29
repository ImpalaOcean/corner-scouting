"""Summarise a corner table by team and assign chronological match splits.

Run from the repository root:
    python -m src.analysis --input outputs/sample_corners/corner_summary.csv --output outputs/analysis_sample
"""

import argparse
import json
from pathlib import Path

from .summary import (SPLIT_FIELDS, TEAM_SUMMARY_FIELDS, AnalysisError,
                      chronological_splits, load_corners, team_summaries,
                      write_csv)


def _pct(value):
    return '  n/a' if value is None else f'{value * 100:5.1f}%'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True,
                        help='corner_summary.csv or .parquet from the batch runner')
    parser.add_argument('--output', type=Path, required=True,
                        help='new folder for results (must not already exist)')
    args = parser.parse_args()

    if args.output.exists():
        parser.exit(1, f'Output folder already exists: {args.output}. Choose a new name.\n')
    try:
        rows = load_corners(args.input)
        summaries = team_summaries(rows)
        splits = chronological_splits(rows)
    except AnalysisError as exc:
        parser.exit(1, f'Analysis failed: {exc}\n')

    args.output.mkdir(parents=True)
    write_csv(args.output / 'team_summary_v1.csv', TEAM_SUMMARY_FIELDS, summaries)
    write_csv(args.output / 'match_splits.csv', SPLIT_FIELDS, splits)
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
    }, indent=2), encoding='utf-8')

    print(f'{len(rows)} corners, {len(summaries)} team rows -> {args.output}')
    print(f"{'team':<20}{'comp/season':<22}{'matches':>8}{'corners':>8}"
          f"{'in':>8}{'out':>8}{'short':>8}{'unknown':>8}{'shot rate':>11}{'goals':>6}")
    for s in summaries:
        label = f"{s['competition_name'] or '?'} {s['season'] or '?'}"[:21]
        print(f"{str(s['team'])[:19]:<20}{label:<22}{s['matches']:>8}{s['corners']:>8}"
              f"{_pct(s['freq_inswinging']):>8}{_pct(s['freq_outswinging']):>8}"
              f"{_pct(s['freq_short']):>8}{_pct(s['freq_unknown']):>8}"
              f"{_pct(s['shot_rate']):>11}{s['goals']:>6}")
    print('Match splits: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    small = sum(1 for s in summaries if s['small_sample'])
    if small:
        print(f'{small} of {len(summaries)} team rows are below 10 matches / 30 corners '
              '(descriptive only, not for prediction).')


if __name__ == '__main__':
    main()
