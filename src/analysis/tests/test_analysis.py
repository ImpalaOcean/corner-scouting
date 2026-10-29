"""Tests for src/analysis using the invented fixture tests/fixtures/corners_v1.csv.

Expected numbers below were worked out by hand from the fixture (10 corners,
3 teams, 6 matches, one match with no date).
"""

import csv
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.analysis.summary import (AnalysisError, chronological_splits,
                                  load_corners, team_summaries)
from src.corners.batch import FIELDS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'corners_v1.csv'


def by_team(summaries):
    return {s['team']: s for s in summaries}


class FixtureContractTests(unittest.TestCase):
    def test_fixture_columns_match_batch_output(self):
        # If Diego's output columns change, this fails so we notice.
        with FIXTURE.open(newline='', encoding='utf-8-sig') as handle:
            header = next(csv.reader(handle))
        self.assertEqual(header, FIELDS)


class TeamSummaryTests(unittest.TestCase):
    def setUp(self):
        self.rows = load_corners(FIXTURE)
        self.teams = by_team(team_summaries(self.rows))

    def test_counts_per_team(self):
        self.assertEqual(len(self.rows), 10)
        self.assertEqual({t: s['corners'] for t, s in self.teams.items()},
                         {'Example A': 5, 'Example B': 3, 'Example C': 2})
        self.assertEqual(self.teams['Example A']['matches'], 4)

    def test_delivery_frequencies(self):
        a = self.teams['Example A']
        self.assertEqual((a['n_inswinging'], a['n_outswinging'], a['n_straight']), (3, 1, 1))
        self.assertAlmostEqual(a['freq_inswinging'], 0.6)
        b = self.teams['Example B']
        self.assertEqual((b['n_short'], b['n_direct_shot'], b['n_inswinging']), (1, 1, 1))
        self.assertAlmostEqual(self.teams['Example C']['freq_unknown'], 0.5)
        for s in self.teams.values():
            total = sum(s[k] for k in s if k.startswith('freq_'))
            self.assertAlmostEqual(total, 1.0, places=3)

    def test_outcomes(self):
        a = self.teams['Example A']
        self.assertEqual((a['corners_with_shot'], a['shots'], a['goals']), (2, 3, 1))
        self.assertAlmostEqual(a['shot_rate'], 0.4)
        self.assertAlmostEqual(a['xg_sum'], 0.6)
        self.assertAlmostEqual(self.teams['Example B']['shot_rate'], 0.6667)
        self.assertEqual(self.teams['Example C']['shot_rate'], 0.0)

    def test_dates_ignore_missing_and_small_sample_flag(self):
        a = self.teams['Example A']
        self.assertEqual((a['first_match_date'], a['last_match_date']),
                         ('2026-01-01', '2026-01-15'))
        self.assertTrue(all(s['small_sample'] for s in self.teams.values()))


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.splits = chronological_splits(load_corners(FIXTURE))
        self.by_match = {s['match_id']: s['split'] for s in self.splits}

    def test_expected_assignment(self):
        # 5 dated matches -> 3 train, 1 validation, 1 test. 1006 has no date.
        self.assertEqual(self.by_match, {1001: 'train', 1002: 'train', 1003: 'train',
                                         1004: 'validation', 1005: 'test',
                                         1006: 'excluded'})

    def test_each_match_in_exactly_one_split(self):
        ids = [s['match_id'] for s in self.splits]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_future_data_in_training(self):
        dated = [s for s in self.splits if s['split'] in ('train', 'validation', 'test')]
        latest_train = max(s['match_date'] for s in dated if s['split'] == 'train')
        earliest_test = min(s['match_date'] for s in dated if s['split'] == 'test')
        self.assertLess(latest_train, earliest_test)

    def test_small_competition_season_not_split(self):
        rows = [r for r in load_corners(FIXTURE) if r['match_id'] in (1001, 1002)]
        splits = chronological_splits(rows)
        self.assertEqual({s['split'] for s in splits}, {'too_few_matches'})

    def test_same_date_tie_broken_by_match_id(self):
        orders = {s['match_id']: s['order'] for s in self.splits}
        self.assertLess(orders[1002], orders[1003])


class InputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        with FIXTURE.open(newline='', encoding='utf-8') as handle:
            self.rows = list(csv.DictReader(handle))

    def write(self, rows, fields=FIELDS):
        path = self.dir / 'input.csv'
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_duplicate_corner_rejected(self):
        with self.assertRaises(AnalysisError):
            load_corners(self.write(self.rows + [self.rows[0]]))

    def test_mixed_windows_rejected(self):
        self.rows[0]['window_seconds'] = '10'
        with self.assertRaises(AnalysisError):
            load_corners(self.write(self.rows))

    def test_missing_column_rejected(self):
        fields = [f for f in FIELDS if f != 'match_date']
        rows = [{k: v for k, v in r.items() if k in fields} for r in self.rows]
        with self.assertRaises(AnalysisError):
            load_corners(self.write(rows, fields))

    def test_unexpected_category_rejected(self):
        self.rows[0]['delivery_category'] = 'banana'
        with self.assertRaises(AnalysisError):
            load_corners(self.write(self.rows))


class CommandLineTests(unittest.TestCase):
    def test_runs_and_refuses_existing_folder(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        out = temp / 'run'
        cmd = [sys.executable, '-m', 'src.analysis', '--input', str(FIXTURE), '--output', str(out)]
        first = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        for name in ('team_summary_v1.csv', 'match_splits.csv', 'analysis_manifest.json'):
            self.assertTrue((out / name).exists())
        second = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(second.returncode, 0)


if __name__ == '__main__':
    unittest.main()
