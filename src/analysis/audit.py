"""Independent 100 corner audit (Diego and Asaad), see docs/audit-protocol.md.

Three steps, all from the repository root:

1. Pick the same corners for both reviewers from the primary 15/15 tables of
   every competition in the audit (same inputs and seed = same sample). Writes
   the blank sheet and sample_provenance.json (hashes, settings, counts):
    python -m src.analysis.audit sample --input outputs/wc2022-euro2024-corners/corner_summary.csv outputs/leagues-2015-16-corners/corner_summary.csv --output outputs/audit-combined-primary-sample

2. Look at the raw StatsBomb events around one corner while filling the sheet
   (give every manifest the sample came from; --raw prints full event JSON):
    python -m src.analysis.audit show --manifest data/ingested/wc2022-euro2024/batch_manifest.json data/ingested/leagues-2015-16/batch_manifest.json --sheet outputs/audit-combined-primary-sample/audit_sheet.csv --audit-id 7

3. Compare the two filled sheets (refuses while any answer is missing):
    python -m src.analysis.audit agree --sheets audit_asaad.csv audit_diego.csv --master outputs/audit-combined-primary-sample/audit_sheet.csv --output outputs/audit_agreement
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random

from .publication import new_output_directory
from .summary import AnalysisError, check_corners, load_corners, write_csv

SAMPLER_VERSION = 2  # selection rule unchanged from version 1; v2 adds provenance and inputs
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
SHEET_FIELDS = (['audit_id', 'stratum', 'match_id', 'corner_event_id', 'competition_name',
                 'season', 'team', 'period', 'timestamp', 'delivery_category', 'shot_count',
                 'goal_count', 'led_to_shot', 'stop_reason', 'window_seconds', 'short_limit',
                 'chain_event_ids']
                + REVIEW_FIELDS + ['notes'])
SHOW_SECONDS = 25
# Tournaments in the audit corpus; everything else counts as a league.
TOURNAMENT_COMPETITIONS = {43, 55}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _seconds(timestamp):
    hours, minutes, seconds = str(timestamp).split(':')
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _load_with_extras(path):
    """load_corners plus the audit only columns it does not keep."""
    rows = load_corners(path)
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        extras = {(int(float(r['match_id'])), r['corner_event_id']): r for r in csv.DictReader(handle)}
    for r in rows:
        raw = extras[(r['match_id'], r['corner_event_id'])]
        r['stop_reason'] = raw.get('stop_reason', '')
        r['timestamp'] = raw.get('timestamp', '')
        r['chain_event_ids'] = raw.get('chain_event_ids', '')
    return rows


def load_population(paths):
    """Combine several corner tables into one audit population. Refuses
    duplicate corner keys, mixed extraction settings and missing
    competition, season or date metadata."""
    rows = []
    for path in paths:
        rows.extend(_load_with_extras(path))
    check_corners(rows)
    missing = [r for r in rows if r['competition_id'] is None or r['season_id'] is None
               or not r['match_date']]
    if missing:
        raise AnalysisError(f'{len(missing)} corners lack competition, season or date '
                            f"(first: match {missing[0]['match_id']})")
    return rows


def draw_sample(rows, size=SAMPLE_SIZE, seed=5118):
    """Deterministic stratified sample: same rows and seed give the same
    corners on every computer, whatever order the inputs were given in."""
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
            'corner_event_id': r['corner_event_id'],
            'competition_name': r.get('competition_name'), 'season': r.get('season'),
            'competition_id': r.get('competition_id'), 'team': r['team'],
            'period': r['period'], 'timestamp': r['timestamp'],
            'delivery_category': r['delivery_category'], 'shot_count': r['shot_count'],
            'goal_count': r['goal_count'], 'led_to_shot': r['led_to_shot'],
            'stop_reason': r['stop_reason'], 'window_seconds': r['window_seconds'],
            'short_limit': r.get('short_limit'), 'chain_event_ids': r['chain_event_ids'],
            **{f: '' for f in REVIEW_FIELDS}, 'notes': ''})
    return sheet


def sample_counts(sheet):
    by_competition = Counter(f"{r['competition_name']} {r['season']}" for r in sheet)
    by_stratum = Counter(r['stratum'] for r in sheet)
    tournaments = sum(1 for r in sheet if r.get('competition_id') in TOURNAMENT_COMPETITIONS)
    return {'by_competition_season': dict(sorted(by_competition.items())),
            'by_stratum': dict(by_stratum),
            'tournament_corners': tournaments, 'league_corners': len(sheet) - tournaments}


def _relative(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sample_provenance(input_paths, rows, sheet, sheet_path, seed, size):
    settings = {(r['window_seconds'], r['short_limit']) for r in rows}
    window, short_limit = settings.pop()
    inputs = []
    for path in input_paths:
        entry = {'path': _relative(path), 'sha256': _sha256(path)}
        run_manifest = Path(path).with_name('run_manifest.json')
        if run_manifest.exists():
            entry['run_manifest'] = _relative(run_manifest)
            entry['run_manifest_sha256'] = _sha256(run_manifest)
        inputs.append(entry)
    return {
        'sampler': {'module': 'src.analysis.audit', 'version': SAMPLER_VERSION,
                    'seed': seed, 'quotas': {name: quota for name, _, quota in STRATA}},
        'population': {'corners': len(rows), 'matches': len({r['match_id'] for r in rows}),
                       'settings': {'window_seconds': window, 'short_limit': short_limit}},
        'sample': dict({'size': len(sheet), 'requested_size': size}, **sample_counts(sheet)),
        'inputs': inputs,
        'artifacts': {'audit_sheet.csv': {'sha256': _sha256(sheet_path)}},
    }


def _detail(event):
    parts = []
    for key in ('pass', 'shot', 'clearance', 'goalkeeper', 'duel'):
        block = event.get(key)
        if not isinstance(block, dict):
            continue
        for name in ('type', 'outcome', 'technique', 'height', 'body_part'):
            if isinstance(block.get(name), dict) and 'name' in block[name]:
                parts.append(block[name]['name'])
        if block.get('end_location'):
            parts.append('end ' + ','.join(str(v) for v in block['end_location']))
        if 'length' in block:
            parts.append(f"length {block['length']}")
        if block.get('out'):
            parts.append('OUT')
    if event.get('location'):
        parts.append('at ' + ','.join(str(v) for v in event['location']))
    if event.get('out'):
        parts.append('OUT')
    for flag in ('under_pressure', 'counterpress', 'off_camera'):
        if event.get(flag):
            parts.append(flag)
    if any(isinstance(v, dict) and v.get('advantage') for v in event.values()):
        parts.append('advantage')
    return ', '.join(parts)


def event_timeline(events, corner_event_id, seconds=SHOW_SECONDS):
    """Readable lines for the events from the corner until `seconds` later in
    the same period, with exact timestamps. Judgments that depend on fields not
    shown here need the full JSON (--raw)."""
    start = next((i for i, e in enumerate(events) if e.get('id') == corner_event_id), None)
    if start is None:
        raise AnalysisError(f'corner {corner_event_id} not found in the event file')
    corner = events[start]
    t0 = _seconds(corner['timestamp'])
    lines = []
    for e in events[start:]:
        boundary = (e.get('period') != corner.get('period')
                    or _seconds(e['timestamp']) - t0 > seconds)
        lines.append(f"{e['timestamp']} (+{_seconds(e['timestamp']) - t0:.3f}s)  "
                     f"{(e.get('team') or {}).get('name', ''):<18.18} "
                     f"{e['type']['name']:<16.16} poss {e.get('possession', ''):<4} "
                     f"{(e.get('player') or {}).get('name', ''):<24.24} {_detail(e)}"
                     f"  [{e['id']}]")
        if boundary:
            lines[-1] += ' [context boundary; not an included-chain judgment]'
            break
    return lines


def raw_events(events, corner_event_id, seconds=SHOW_SECONDS):
    start = next((i for i, e in enumerate(events) if e.get('id') == corner_event_id), None)
    if start is None:
        raise AnalysisError(f'corner {corner_event_id} not found in the event file')
    corner = events[start]
    t0 = _seconds(corner['timestamp'])
    out = []
    for e in events[start:]:
        out.append(e)
        if e.get('period') != corner.get('period') or _seconds(e['timestamp']) - t0 > seconds:
            break
    return out


def find_events_file(manifest_paths, match_id):
    """Locate one match's event file across several manifests, resolving each
    relative path against its own manifest's folder."""
    found = []
    for manifest_path in manifest_paths:
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        for entry in manifest['matches']:
            if str(entry['match_id']) == str(match_id):
                found.append((Path(manifest_path).parent / entry['events']).resolve())
    if not found:
        raise AnalysisError(f'match {match_id} not in any given manifest')
    if len(set(found)) > 1:
        raise AnalysisError(f'match {match_id} appears in more than one manifest')
    return found[0]


def _read_sheet(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not {'audit_id', 'match_id', 'corner_event_id'} <= set(reader.fieldnames or []):
            raise AnalysisError('sheet lacks audit/corner identity columns')
        sheet, corners = {}, set()
        for row in reader:
            audit_id = row['audit_id']
            key = (row['match_id'], row['corner_event_id'])
            if (not audit_id or not audit_id.isdigit() or not all(key)
                    or audit_id in sheet or key in corners):
                raise AnalysisError('blank or duplicate audit ID/corner key')
            sheet[audit_id] = row
            corners.add(key)
        return sheet


def validate_frozen_sheets(master_path, sheets):
    """Require the original hash-verified 100-row master, including all values
    being judged. Matching two equally truncated/modified copies is insufficient.
    """
    master_path = Path(master_path)
    provenance_path = master_path.with_name('sample_provenance.json')
    if not provenance_path.is_file():
        raise AnalysisError('frozen master requires sample_provenance.json beside it')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    expected = provenance.get('artifacts', {}).get('audit_sheet.csv', {}).get('sha256')
    if not expected or _sha256(master_path) != expected:
        raise AnalysisError('frozen master hash mismatch')
    master = _read_sheet(master_path)
    if len(master) != SAMPLE_SIZE:
        raise AnalysisError('frozen master must contain exactly 100 corners')
    # Judge against the authenticated original schema, not columns introduced
    # after that sample was frozen. Never migrate a completed reviewer sheet.
    fixed = [f for f in next(iter(master.values())) if f not in REVIEW_FIELDS + ['notes']]
    required = set(SHEET_FIELDS) - set(REVIEW_FIELDS + ['notes', 'competition_name', 'season', 'short_limit'])
    if not required <= set(fixed):
        raise AnalysisError('frozen master lacks required historical corner fields')
    for sheet in sheets:
        if set(sheet) != set(master):
            raise AnalysisError('reviewer sheet differs from frozen master population')
        for key, row in master.items():
            if any(f not in row or sheet[key].get(f) != row[f] for f in fixed):
                raise AnalysisError(f'audit {key}: frozen corner fields were changed')
    return master


def _answer(value):
    text = (value or '').strip().lower()
    if text in ('y', 'yes', '1', 'true'):
        return 'y'
    if text in ('n', 'no', '0', 'false'):
        return 'n'
    return None


def missing_answers(sheet):
    """(audit_id, field) pairs with no readable y/n answer, plus n answers
    without a note."""
    missing, unexplained = [], []
    for key in sorted(sheet, key=int):
        row = sheet[key]
        for field in REVIEW_FIELDS:
            answer = _answer(row.get(field))
            if answer is None:
                missing.append((key, field))
            elif answer == 'n' and not (row.get('notes') or '').strip():
                unexplained.append((key, field))
    return missing, unexplained


def cohens_kappa(pairs):
    """Kappa for y/n pairs. Undefined (None) when chance agreement is 1, which
    happens when both reviewers used one and the same label throughout."""
    n = len(pairs)
    if not n:
        return None
    observed = sum(1 for a, b in pairs if a == b) / n
    ya = sum(1 for a, _ in pairs if a == 'y') / n
    yb = sum(1 for _, b in pairs if b == 'y') / n
    expected = ya * yb + (1 - ya) * (1 - yb)
    if expected >= 1:
        return None
    return round((observed - expected) / (1 - expected), 4)


def agreement(sheet_a, sheet_b, require_complete=True):
    """Per field percent agreement and Cohen's kappa between two reviewers,
    plus every disagreement to resolve together. Refuses incomplete sheets
    unless require_complete is False, and always reports missing answers."""
    if set(sheet_a) != set(sheet_b):
        raise AnalysisError('the two sheets do not contain the same audit_ids')
    for key in sheet_a:
        if (sheet_a[key]['match_id'], sheet_a[key]['corner_event_id']) != \
                (sheet_b[key]['match_id'], sheet_b[key]['corner_event_id']):
            raise AnalysisError(f'audit_id {key} points at different corners in the two sheets')
    missing_a, unexplained_a = missing_answers(sheet_a)
    missing_b, unexplained_b = missing_answers(sheet_b)
    if require_complete and (missing_a or missing_b):
        raise AnalysisError(f'sheets are incomplete: {len(missing_a)} missing answers in the first, '
                            f'{len(missing_b)} in the second (first missing: '
                            f'{(missing_a or missing_b)[0]}); finish both reviews first')
    if require_complete and (unexplained_a or unexplained_b):
        raise AnalysisError('n judgments require a note before agreement is reported')
    summary, disagreements = [], []
    for field in REVIEW_FIELDS:
        both = [(_answer(sheet_a[k][field]), _answer(sheet_b[k][field])) for k in sheet_a]
        pairs = [(a, b) for a, b in both if a and b]
        n = len(pairs)
        agree = sum(1 for a, b in pairs if a == b)
        kappa = cohens_kappa(pairs)
        summary.append({'field': field, 'answered_by_both': n,
                        'missing_a': sum(1 for a, _ in both if a is None),
                        'missing_b': sum(1 for _, b in both if b is None),
                        'agree': agree,
                        'percent_agreement': round(100 * agree / n, 1) if n else None,
                        'cohens_kappa': kappa if kappa is not None else 'undefined',
                        'reviewer_a_marked_correct':
                            round(100 * sum(1 for a, _ in pairs if a == 'y') / n, 1) if n else None,
                        'reviewer_b_marked_correct':
                            round(100 * sum(1 for _, b in pairs if b == 'y') / n, 1) if n else None})
    for key in sorted(sheet_a, key=int):
        a, b = sheet_a[key], sheet_b[key]
        for field in REVIEW_FIELDS:
            if _answer(a[field]) != _answer(b[field]):
                disagreements.append({'audit_id': key, 'match_id': a['match_id'],
                                      'corner_event_id': a['corner_event_id'],
                                      'field': field, 'reviewer_a': a[field],
                                      'reviewer_b': b[field], 'notes_a': a['notes'],
                                      'notes_b': b['notes']})
    return summary, disagreements


AGREEMENT_FIELDS = ['field', 'answered_by_both', 'missing_a', 'missing_b', 'agree',
                    'percent_agreement', 'cohens_kappa', 'reviewer_a_marked_correct',
                    'reviewer_b_marked_correct']
DISAGREEMENT_FIELDS = ['audit_id', 'match_id', 'corner_event_id', 'field', 'reviewer_a',
                       'reviewer_b', 'notes_a', 'notes_b']


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('sample', help='pick the audit corners')
    s.add_argument('--input', type=Path, nargs='+', required=True,
                   help='one or more primary corner_summary.csv tables')
    s.add_argument('--output', type=Path, required=True)
    s.add_argument('--size', type=int, default=SAMPLE_SIZE)
    s.add_argument('--seed', type=int, default=5118)
    v = sub.add_parser('show', help='print raw events around one audit corner')
    v.add_argument('--manifest', type=Path, nargs='+', required=True,
                   help='batch_manifest.json files the sample came from')
    v.add_argument('--sheet', type=Path, required=True)
    v.add_argument('--audit-id', required=True)
    v.add_argument('--seconds', type=float, default=SHOW_SECONDS)
    v.add_argument('--raw', action='store_true', help='print the full event JSON')
    c = sub.add_parser('check', help='list missing answers and n answers without notes')
    c.add_argument('--sheet', type=Path, required=True)
    a = sub.add_parser('agree', help='compare two filled sheets')
    a.add_argument('--sheets', type=Path, nargs=2, required=True)
    a.add_argument('--master', type=Path, required=True,
                   help='original frozen audit_sheet.csv, beside sample_provenance.json')
    a.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == 'sample':
            rows = load_population(args.input)
            sheet = draw_sample(rows, args.size, args.seed)
            with new_output_directory(args.output) as staging:
                write_csv(staging / 'audit_sheet.csv', SHEET_FIELDS, sheet)
                provenance = sample_provenance(args.input, rows, sheet,
                                               staging / 'audit_sheet.csv', args.seed, args.size)
                (staging / 'sample_provenance.json').write_text(
                    json.dumps(provenance, indent=2), encoding='utf-8')
            counts = provenance['sample']
            print(f"{counts['size']} corners from {provenance['population']['corners']} -> "
                  f"{args.output / 'audit_sheet.csv'}")
            print('By competition: ' + ', '.join(f'{k} {v}' for k, v in
                                                 counts['by_competition_season'].items()))
            print('By stratum: ' + ', '.join(f'{k} {v}' for k, v in counts['by_stratum'].items()))
            if not counts['tournament_corners'] or not counts['league_corners']:
                print('WARNING: the sample does not contain both tournament and league corners. '
                      'Check the inputs before freezing; do not change the policy after reviewing.')
            print('Freeze this folder and share it. Each reviewer copies audit_sheet.csv and '
                  'fills delivery_ok, shot_ok, goal_ok, stop_ok with y or n, independently.')
        elif args.command == 'show':
            row = _read_sheet(args.sheet).get(str(args.audit_id))
            if row is None:
                raise AnalysisError(f'audit_id {args.audit_id} not in {args.sheet}')
            path = find_events_file(args.manifest, row['match_id'])
            events = json.loads(path.read_text(encoding='utf-8'))
            print(f"Audit {row['audit_id']} ({row['stratum']}): {row['team']}, "
                  f"{row.get('competition_name', '')} {row.get('season', '')}, "
                  f"match {row['match_id']}, period {row['period']} at {row['timestamp']}")
            print(f"Extractor says: {row['delivery_category']}, shots {row['shot_count']}, "
                  f"goals {row['goal_count']}, stopped by {row['stop_reason']} "
                  f"(window {row['window_seconds']}s, short limit {row.get('short_limit', '')})")
            print(f"Chain events: {row['chain_event_ids']}")
            print()
            if args.raw:
                print(json.dumps(raw_events(events, row['corner_event_id'], args.seconds), indent=1))
            else:
                for line in event_timeline(events, row['corner_event_id'], args.seconds):
                    print(line)
        elif args.command == 'check':
            missing, unexplained = missing_answers(_read_sheet(args.sheet))
            print(f'{len(missing)} missing answers, {len(unexplained)} n answers without a note')
            for key, field in missing[:20]:
                print(f'  missing: audit {key} {field}')
            for key, field in unexplained[:20]:
                print(f'  needs note: audit {key} {field}')
        else:
            sheets = [_read_sheet(p) for p in args.sheets]
            validate_frozen_sheets(args.master, sheets)
            summary, disagreements = agreement(*sheets)
            with new_output_directory(args.output) as staging:
                write_csv(staging / 'agreement.csv', AGREEMENT_FIELDS, summary)
                write_csv(staging / 'disagreements.csv', DISAGREEMENT_FIELDS, disagreements)
            for row in summary:
                print(f"{row['field']:<13} agreement {row['percent_agreement']}%  "
                      f"kappa {row['cohens_kappa']}  (n = {row['answered_by_both']})")
            print(f'{len(disagreements)} disagreements to resolve -> {args.output}')
    except (AnalysisError, FileExistsError) as exc:
        parser.exit(1, f'Audit failed: {exc}\n')


if __name__ == '__main__':
    main()
