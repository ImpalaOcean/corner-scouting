"""Tests for src/analysis/report.py (paper tables and review checks)."""

import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_evaluation import make_league, write_rows

ROOT = Path(__file__).resolve().parents[1]


def run(cmd):
    return subprocess.run([sys.executable, '-m'] + cmd, cwd=ROOT, capture_output=True, text=True)


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp())
        rows = make_league('habits')
        rows += [dict(r, competition_id=901, competition_name='Second League',
                      match_id=r['match_id'] + 10000,
                      corner_event_id='b' + r['corner_event_id'])
                 for r in make_league('same', seed=3)]
        cls.rows = rows
        cls.analyses = {}
        for window in (15, 20):
            path = cls.temp / f'w{window}.csv'
            write_rows(path, [dict(r, window_seconds=window) for r in rows])
            out = cls.temp / f'analysis_w{window}'
            result = run(['src.analysis', '--input', str(path), '--output', str(out),
                          '--bootstrap', '50'])
            assert result.returncode == 0, result.stderr
            cls.analyses[window] = out
        cls.report = cls.temp / 'report'
        result = run(['src.analysis.report', '--run', str(cls.analyses[15]), '--windows',
                      str(cls.analyses[20]), '--output', str(cls.report), '--bootstrap', '50'])
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp)

    def read(self, name):
        with (self.report / name).open(encoding='utf-8') as handle:
            return list(csv.DictReader(handle))

    def test_files_written(self):
        for name in ('eligibility_by_competition.csv', 'eligibility_teams.csv',
                     'results_overall.csv', 'results_by_competition.csv',
                     'window_sensitivity.csv', 'review_checks.json', 'results.md'):
            self.assertTrue((self.report / name).exists(), name)

    def test_eligibility_matches_analysis(self):
        comps = self.read('eligibility_by_competition.csv')
        self.assertEqual(len(comps), 2)
        teams = self.read('eligibility_teams.csv')
        self.assertEqual(sum(t['eligible'] == 'True' for t in teams), 8)
        manifest = json.loads((self.analyses[15] / 'analysis_manifest.json').read_text())
        self.assertEqual(manifest['evaluation']['eligible_teams'], 8)
        for c in comps:
            self.assertEqual(int(c['train_matches']) + int(c['validation_matches'])
                             + int(c['test_matches']), int(c['matches']))

    def test_by_competition_shows_where_history_helps(self):
        rows = {(r['competition_name'], r['target']): r
                for r in self.read('results_by_competition.csv')}
        self.assertEqual(rows[('Invented League', 'delivery')]['verdict_vs_pooled'], 'shrunk better')
        self.assertNotEqual(rows[('Second League', 'delivery')]['verdict_vs_pooled'], 'shrunk better')

    def test_checks_and_windows(self):
        checks = json.loads((self.report / 'review_checks.json').read_text())
        self.assertTrue(checks['rebuilt_scores_match_saved_run'])
        windows = {r['window'] for r in self.read('window_sensitivity.csv')}
        self.assertEqual(windows, {'15s', '20s'})

    def test_refuses_when_input_does_not_match_run(self):
        changed = self.temp / 'changed.csv'
        write_rows(changed, [dict(r, window_seconds=15,
                                  delivery_category='straight' if i % 3 == 0 else r['delivery_category'])
                             for i, r in enumerate(self.rows)])
        result = run(['src.analysis.report', '--run', str(self.analyses[15]), '--input',
                      str(changed), '--output', str(self.temp / 'bad')])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('do not match', result.stderr)
        self.assertFalse((self.temp / 'bad').exists())


if __name__ == '__main__':
    unittest.main()
