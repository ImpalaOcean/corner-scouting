"""Independent 100 corner audit (Diego and Asaad), see docs/audit-protocol.md.

Three steps, all from the repository root:

1. Pick the same corners for both reviewers (same input and seed = same sample):
    python -m src.analysis.audit sample --input outputs/wce_corners/corner_summary.csv --output outputs/audit

2. Look at the raw StatsBomb events around one corner while filling the sheet:
    python -m src.analysis.audit show --manifest data/ingested/wc2022-euro2024/batch_manifest.json --sheet outputs/audit/audit_sheet.csv --audit-id 7

3. Compare the two filled sheets:
    python -m src.analysis.audit agree --sheets audit_asaad.csv audit_diego.csv --output outputs/audit_agreement
"""

import argparse
import csv
import json
from pathlib import Path
import random

from .summary import AnalysisError, load_corners, write_csv

SAMPLE_SIZE = 100
# Quotas, filled in this order; a corner is only ever picked once. Rare and
# boundary cases come first so the audit covers them (proposal Section 3),
# the rest of the 100 is a plain random sample.
STRATA = [
    ('direct_shot', lambda r: r['delivery_category'] == 'direct_shot', 10),
    ('short', lambda r: r['delivery_category'] == 'short', 15),
    ('unknown_delivery', lambda r: r['delivery_category'] == 'unknown', 8),
    ('straight', lambda r: r['delivery_category'] == 'straight', 6),
    ('goal', lambda r: r['goal_count'] > 0, 8),
    ('shot_then_time_limit', lambda r: r['led_to_shot'] and r['stop_reason'] == 'time_limit', 8),
    ('new_restart', lambda r: r['stop_reason'] == 'new_restart', 6),
    ('stoppage', lambda r: r['stop_reason'] == 'stoppage', 6),
    ('possession_change', lambda r: r['stop_reason'] == 'possession_change', 6),
    ('ball_out', lambda r: r['stop_reason'] == 'ball_out', 6),
    ('period_end', lambda r: r['stop_reason'] in ('period_end', 'end_of_data'), 4),
]
REVIEW_FIELDS = ['delivery_ok', 'shot_ok', 'goal_ok', 'stop_ok']
SHEET_FIELDS = (['audit_id', 'stratum', 'match_id', 'corner_event_id', 'team', 'period',
                 'timestamp', 'delivery_category', 'shot_count', 'goal_count',
                 'led_to_shot', 'stop_reason', 'window_seconds', 'chain_event_ids']
                + REVIEW_FIELDS + ['notes'])
SHOW_SECONDS = 25


def _seconds(timestamp):
    hours, minutes, seconds = str(timestamp).split(':')
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _load_with_extras(path):
    """load_corners plus the audit only columns it does not keep."""
    rows = load_corners(path)
    path = Path(path)
    with path.open(newline='', encoding='utf-8-sig') as handle:
        extras = {(int(float(r['match_id'])), r['corner_event_id']): r for r in csv.DictReader(handle)}
    for r in rows:
        raw = extras[(r['match_id'], r['corner_event_id'])]
        r['stop_reason'] = raw.get('stop_reason', '')
        r['timestamp'] = raw.get('timestamp', '')
        r['chain_event_ids'] = raw.get('chain_event_ids', '')
    return rows


def draw_sample(rows, size=SAMPLE_SIZE, seed=5118):
    """Deterministic stratified sample: same rows and seed give the same
    corners on every computer."""
    rng = random.Random(seed)
    ordered = sorted(rows, key=lambda r: (r['match_id'], r['corner_event_id']))
    chosen, picked = [], set()
    for name, test, quota in STRATA:
        candidates = [r for r in ordered if test(r)
                      and (r['match_id'], r['corner_event_id']) not in picked]
        rng.shuffle(candidates)
        for r in candidates[:min(quota, size - len(chosen))]:
            picked.add((r['match_id'], r['corner_event_id']))
            chosen.append((name, r))
    rest = [r for r in ordered if (r['match_id'], r['corner_event_id']) not in picked]
    rng.shuffle(rest)
    for r in rest[:max(0, size - len(chosen))]:
        chosen.append(('random', r))
    chosen.sort(key=lambda item: (item[1]['match_id'], _seconds(item[1]['timestamp'] or '0:0:0')))
    sheet = []
    for number, (name, r) in enumerate(chosen, start=1):
        sheet.append({
            'audit_id': number, 'stratum': name, 'match_id': r['match_id'],
            'corner_event_id': r['corner_event_id'], 'team': r['team'],
            'period': r['period'], 'timestamp': r['timestamp'],
            'delivery_category': r['delivery_category'], 'shot_count': r['shot_count'],
            'goal_count': r['goal_count'], 'led_to_shot': r['led_to_shot'],
            'stop_reason': r['stop_reason'], 'window_seconds': r['window_seconds'],
            'chain_event_ids': r['chain_event_ids'],
            **{f: '' for f in REVIEW_FIELDS}, 'notes': ''})
    return sheet


def event_timeline(events, corner_event_id, seconds=SHOW_SECONDS):
    """Readable lines for the events from the corner until `seconds` later
    in the same period."""
    start = next((i for i, e in enumerate(events) if e.get('id') == corner_event_id), None)
    if start is None:
        raise AnalysisError(f'corner {corner_event_id} not found in the event file')
    corner = events[start]
    t0 = _seconds(corner['timestamp'])
    lines = []
    for e in events[start:]:
        if e.get('period') != corner.get('period') or _seconds(e['timestamp']) - t0 > seconds:
            break
        detail = ''
        for key in ('pass', 'shot', 'clearance', 'goalkeeper', 'duel'):
            if key in e:
                part = e[key]
                bits = [part[k]['name'] for k in ('type', 'outcome', 'technique', 'height')
                        if isinstance(part.get(k), dict) and 'name' in part[k]]
                detail = ', '.join(bits)
        lines.append(f"+{_seconds(e['timestamp']) - t0:5.1f}s  "
                     f"{(e.get('team') or {}).get('name', ''):<18.18} "
                     f"{e['type']['name']:<16.16} poss {e.get('possession', ''):<4} "
                     f"{(e.get('player') or {}).get('name', ''):<24.24} {detail}"
                     f"  [{e['id'][:8]}]")
    return lines


def _read_sheet(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        return {row['audit_id']: row for row in csv.DictReader(handle)}


def _answer(value):
    text = (value or '').strip().lower()
    if text in ('y', 'yes', '1', 'true'):
        return 'y'
    if text in ('n', 'no', '0', 'false'):
        return 'n'
    return None


def agreement(sheet_a, sheet_b):
    """Per field percent agreement and Cohen's kappa between two reviewers,
    plus every disagreement to resolve together."""
    if set(sheet_a) != set(sheet_b):
        raise AnalysisError('the two sheets do not contain the same audit_ids')
    for key in sheet_a:
        if sheet_a[key]['corner_event_id'] != sheet_b[key]['corner_event_id']:
            raise AnalysisError(f'audit_id {key} points at different corners in the two sheets')
    summary, disagreements = [], []
    for field in REVIEW_FIELDS:
        pairs = [(_answer(sheet_a[k][field]), _answer(sheet_b[k][field])) for k in sheet_a]
        pairs = [(a, b) for a, b in pairs if a and b]
        n = len(pairs)
        agree = sum(1 for a, b in pairs if a == b)
        observed = agree / n if n else None
        ya = sum(1 for a, _ in pairs if a == 'y') / n if n else 0
        yb = sum(1 for _, b in pairs if b == 'y') / n if n else 0
        expected = ya * yb + (1 - ya) * (1 - yb)
        kappa = (None if not n else 1.0 if expected == 1 else
                 round((observed - expected) / (1 - expected), 4))
        summary.append({'field': field, 'answered_by_both': n, 'agree': agree,
                        'percent_agreement': None if observed is None else round(100 * observed, 1),
                        'cohens_kappa': kappa,
                        'reviewer_a_marked_correct': round(100 * ya, 1) if n else None,
                        'reviewer_b_marked_correct': round(100 * yb, 1) if n else None})
    for key in sorted(sheet_a, key=int):
        a, b = sheet_a[key], sheet_b[key]
        for field in REVIEW_FIELDS:
            if _answer(a[field]) != _answer(b[field]):
                disagreements.append({'audit_id': key, 'corner_event_id': a['corner_event_id'],
                                      'field': field, 'reviewer_a': a[field],
                                      'reviewer_b': b[field], 'notes_a': a['notes'],
                                      'notes_b': b['notes']})
    return summary, disagreements


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('sample', help='pick the audit corners')
    s.add_argument('--input', type=Path, required=True)
    s.add_argument('--output', type=Path, required=True)
    s.add_argument('--size', type=int, default=SAMPLE_SIZE)
    s.add_argument('--seed', type=int, default=5118)
    v = sub.add_parser('show', help='print raw events around one audit corner')
    v.add_argument('--manifest', type=Path, required=True, help="Ebtesam's batch_manifest.json")
    v.add_argument('--sheet', type=Path, required=True)
    v.add_argument('--audit-id', required=True)
    a = sub.add_parser('agree', help='compare two filled sheets')
    a.add_argument('--sheets', type=Path, nargs=2, required=True)
    a.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == 'sample':
            if args.output.exists():
                parser.exit(1, f'Output folder already exists: {args.output}. Choose a new name.\n')
            sheet = draw_sample(_load_with_extras(args.input), args.size, args.seed)
            args.output.mkdir(parents=True)
            write_csv(args.output / 'audit_sheet.csv', SHEET_FIELDS, sheet)
            counts = {}
            for row in sheet:
                counts[row['stratum']] = counts.get(row['stratum'], 0) + 1
            print(f'{len(sheet)} corners -> {args.output / "audit_sheet.csv"}')
            print('By stratum: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
            print('Each reviewer copies the sheet and fills delivery_ok, shot_ok, goal_ok, '
                  'stop_ok with y or n, without looking at the other copy.')
        elif args.command == 'show':
            row = _read_sheet(args.sheet).get(str(args.audit_id))
            if row is None:
                raise AnalysisError(f'audit_id {args.audit_id} not in {args.sheet}')
            manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
            entry = next((m for m in manifest['matches']
                          if str(m['match_id']) == str(row['match_id'])), None)
            if entry is None:
                raise AnalysisError(f"match {row['match_id']} not in the manifest")
            events_path = (args.manifest.parent / entry['events']).resolve()
            events = json.loads(events_path.read_text(encoding='utf-8'))
            print(f"Audit {row['audit_id']} ({row['stratum']}): {row['team']}, "
                  f"match {row['match_id']}, period {row['period']} at {row['timestamp']}")
            print(f"Extractor says: {row['delivery_category']}, shots {row['shot_count']}, "
                  f"goals {row['goal_count']}, stopped by {row['stop_reason']} "
                  f"(window {row['window_seconds']}s)")
            print()
            for line in event_timeline(events, row['corner_event_id']):
                print(line)
        else:
            if args.output.exists():
                parser.exit(1, f'Output folder already exists: {args.output}. Choose a new name.\n')
            summary, disagreements = agreement(_read_sheet(args.sheets[0]),
                                               _read_sheet(args.sheets[1]))
            args.output.mkdir(parents=True)
            write_csv(args.output / 'agreement.csv',
                      ['field', 'answered_by_both', 'agree', 'percent_agreement',
                       'cohens_kappa', 'reviewer_a_marked_correct',
                       'reviewer_b_marked_correct'], summary)
            write_csv(args.output / 'disagreements.csv',
                      ['audit_id', 'corner_event_id', 'field', 'reviewer_a', 'reviewer_b',
                       'notes_a', 'notes_b'], disagreements)
            for row in summary:
                print(f"{row['field']:<13} agreement {row['percent_agreement']}%  "
                      f"kappa {row['cohens_kappa']}  (n = {row['answered_by_both']})")
            print(f'{len(disagreements)} disagreements to resolve -> {args.output}')
    except AnalysisError as exc:
        parser.exit(1, f'Audit failed: {exc}\n')


if __name__ == '__main__':
    main()
