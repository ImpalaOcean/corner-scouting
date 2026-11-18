"""Tests for src/analysis/audit.py (the 100 corner audit tool)."""

import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.analysis.audit import (agreement, cohens_kappa, draw_sample, event_timeline,
                                find_events_file, missing_answers, sample_counts)
from src.analysis.summary import AnalysisError
from src.corners.batch import FIELDS

ROOT = Path(__file__).resolve().parents[1]


def corners(n=300, offset=0, competition=2, name='League'):
    rows = []
    categories = ['inswinging'] * 6 + ['outswinging'] * 4 + ['short', 'unknown']
    reasons = ['time_limit', 'ball_out', 'possession_change', 'stoppage']
    for i in range(n):
        rows.append({
            'match_id': 100 + offset + i // 10, 'corner_event_id': f'c{offset + i:05d}',
            'team': 'T', 'team_id': 1, 'period': 1, 'timestamp': f'00:{i % 60:02d}:00.000',
            'delivery_category': 'direct_shot' if i % 97 == 0 else categories[i % len(categories)],
            'shot_count': 1 if i % 3 == 0 else 0, 'goal_count': 1 if i % 50 == 0 else 0,
            'led_to_shot': i % 3 == 0, 'stop_reason': reasons[i % len(reasons)],
            'window_seconds': 15.0, 'short_limit': 15.0, 'chain_event_ids': '[]',
            'competition_id': competition, 'competition_name': name, 'season_id': 27,
            'season': '2015/2016', 'match_date': '2016-01-01', 'provider_xg_sum': 0.0})
    return rows


class SampleTests(unittest.TestCase):
    def test_same_seed_same_sample_any_input_order(self):
        a = [r['corner_event_id'] for r in draw_sample(corners(), seed=1)]
        b = [r['corner_event_id'] for r in draw_sample(list(reversed(corners())), seed=1)]
        self.assertEqual(a, b)
        self.assertNotEqual(a, [r['corner_event_id'] for r in draw_sample(corners(), seed=2)])

    def test_size_unique_and_rare_cases_included(self):
        sheet = draw_sample(corners())
        self.assertEqual(len(sheet), 100)
        self.assertEqual(len({r['corner_event_id'] for r in sheet}), 100)
        strata = {r['stratum'] for r in sheet}
        for name in ('direct_shot', 'short', 'goal', 'shot_then_time_limit'):
            self.assertIn(name, strata)
        self.assertEqual(sum(1 for r in sheet if r['delivery_category'] == 'direct_shot'), 4)

    def test_small_input_returns_everything(self):
        self.assertEqual(len(draw_sample(corners(40))), 40)

    def test_counts_split_tournaments_and_leagues(self):
        rows = corners(200) + corners(200, offset=5000, competition=43, name='FIFA World Cup')
        counts = sample_counts(draw_sample(rows))
        self.assertGreater(counts['tournament_corners'], 0)
        self.assertGreater(counts['league_corners'], 0)
        self.assertEqual(counts['tournament_corners'] + counts['league_corners'], 100)


class TimelineTests(unittest.TestCase):
    def event(self, i, t, period=1, **extra):
        return dict({'id': f'e{i}', 'period': period, 'timestamp': f'00:10:{t:06.3f}',
                     'type': {'name': 'Pass'}, 'team': {'name': 'T'}, 'possession': 1}, **extra)

    def test_window_and_period_limits(self):
        events = [self.event(0, 0), self.event(1, 5), self.event(2, 24), self.event(3, 26),
                  self.event(4, 27, 2)]
        self.assertEqual(len(event_timeline(events, 'e0', seconds=25)), 3)
        with self.assertRaises(AnalysisError):
            event_timeline(events, 'missing')

    def test_exact_timestamps_coordinates_and_out_flag(self):
        events = [self.event(0, 0, location=[120, 0.1],
                             **{'pass': {'end_location': [108.4, 39.9], 'out': True,
                                         'height': {'name': 'High Pass'}}})]
        line = event_timeline(events, 'e0')[0]
        self.assertIn('00:10:00.000', line)
        self.assertIn('end 108.4,39.9', line)
        self.assertIn('OUT', line)
        self.assertIn('at 120,0.1', line)


class ManifestTests(unittest.TestCase):
    def test_finds_match_across_manifests_with_own_relative_paths(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        for name, match in (('a', 1), ('b', 2)):
            (temp / name).mkdir()
            (temp / name / 'batch_manifest.json').write_text(json.dumps(
                {'matches': [{'match_id': match, 'events': f'../raw/{match}.json'}]}))
        paths = [temp / 'a' / 'batch_manifest.json', temp / 'b' / 'batch_manifest.json']
        self.assertEqual(find_events_file(paths, 2), (temp / 'raw' / '2.json').resolve())
        with self.assertRaises(AnalysisError):
            find_events_file(paths, 3)


class AgreementTests(unittest.TestCase):
    def sheet(self, answers, notes='checked'):
        return {str(i): {'match_id': '1', 'corner_event_id': f'c{i}', 'notes': notes,
                         'delivery_ok': a, 'shot_ok': 'y', 'goal_ok': 'y', 'stop_ok': a}
                for i, a in enumerate(answers, start=1)}

    def test_percent_and_kappa(self):
        summary, disagreements = agreement(self.sheet(['y', 'y', 'n', 'n']),
                                           self.sheet(['y', 'n', 'n', 'n']))
        delivery = [s for s in summary if s['field'] == 'delivery_ok'][0]
        self.assertEqual(delivery['percent_agreement'], 75.0)
        # observed 0.75, expected 0.5 * 0.25 + 0.5 * 0.75 = 0.5, kappa 0.5
        self.assertEqual(delivery['cohens_kappa'], 0.5)
        self.assertEqual(len(disagreements), 2)

    def test_constant_labels_give_undefined_kappa_not_perfect(self):
        self.assertIsNone(cohens_kappa([('y', 'y')] * 10))
        summary, _ = agreement(self.sheet(['y'] * 4), self.sheet(['y'] * 4))
        shot = [s for s in summary if s['field'] == 'shot_ok'][0]
        self.assertEqual(shot['percent_agreement'], 100.0)
        self.assertEqual(shot['cohens_kappa'], 'undefined')

    def test_incomplete_sheets_refused_and_reported(self):
        a = self.sheet(['y', 'y', ''])
        with self.assertRaises(AnalysisError):
            agreement(a, self.sheet(['y', 'y', 'y']))
        summary, _ = agreement(a, self.sheet(['y', 'y', 'y']), require_complete=False)
        delivery = [s for s in summary if s['field'] == 'delivery_ok'][0]
        self.assertEqual((delivery['missing_a'], delivery['answered_by_both']), (1, 2))

    def test_n_without_note_flagged(self):
        missing, unexplained = missing_answers(self.sheet(['n'], notes=''))
        self.assertEqual(missing, [])
        self.assertEqual(unexplained, [('1', 'delivery_ok'), ('1', 'stop_ok')])

    def test_different_corners_rejected(self):
        a, b = self.sheet(['y']), self.sheet(['y'])
        b['1']['corner_event_id'] = 'other'
        with self.assertRaises(AnalysisError):
            agreement(a, b)


class CommandLineTests(unittest.TestCase):
    def write_table(self, path, rows):
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow({f: r.get(f, '') for f in FIELDS})

    def test_sample_from_two_tables_writes_provenance_for_crosscheck(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        league, cup = temp / 'league.csv', temp / 'cup.csv'
        self.write_table(league, corners(200))
        self.write_table(cup, corners(200, offset=5000, competition=43, name='FIFA World Cup'))
        out = temp / 'sample'
        result = subprocess.run([sys.executable, '-m', 'src.analysis.audit', 'sample', '--input',
                                 str(cup), str(league), '--output', str(out)],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        provenance = json.loads((out / 'sample_provenance.json').read_text())
        # Fields read by src/verify_audit.py
        import hashlib
        sheet_hash = hashlib.sha256((out / 'audit_sheet.csv').read_bytes()).hexdigest()
        self.assertEqual(provenance['artifacts']['audit_sheet.csv']['sha256'], sheet_hash)
        self.assertEqual(provenance['sample']['size'], 100)
        self.assertEqual(provenance['population']['settings'],
                         {'window_seconds': 15, 'short_limit': 15})
        self.assertEqual(len(provenance['inputs']), 2)
        self.assertTrue(all(len(i['sha256']) == 64 for i in provenance['inputs']))
        self.assertGreater(provenance['sample']['tournament_corners'], 0)
        # Same inputs in the other order give the identical sheet.
        out2 = temp / 'sample2'
        subprocess.run([sys.executable, '-m', 'src.analysis.audit', 'sample', '--input',
                        str(league), str(cup), '--output', str(out2)], cwd=ROOT, check=True,
                       capture_output=True)
        self.assertEqual((out / 'audit_sheet.csv').read_bytes(),
                         (out2 / 'audit_sheet.csv').read_bytes())

    def test_duplicate_corner_across_tables_refused(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        a, b = temp / 'a.csv', temp / 'b.csv'
        self.write_table(a, corners(50))
        self.write_table(b, corners(50))
        result = subprocess.run([sys.executable, '-m', 'src.analysis.audit', 'sample', '--input',
                                 str(a), str(b), '--output', str(temp / 'out')],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((temp / 'out').exists())


if __name__ == '__main__':
    unittest.main()
