"""Tests for src/analysis/evaluation.py and compare.py.

Two invented leagues give known answers:
  habits league   every team always uses one delivery type, and only one
                  team's corners lead to shots. Team history must beat the
                  competition average and little smoothing should be chosen.
  same league     every team draws from the same random mix. Team history
                  should not beat the average, and heavy smoothing is chosen.
"""

import csv
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.analysis.evaluation import (ALPHA_GRID, EPSILON, SCORED_CATEGORIES,
                                     delivery_probabilities, evaluate, fit_history,
                                     shot_probability)
from src.analysis.summary import (DELIVERY_CATEGORIES, chronological_splits,
                                  period_breakdown, team_summaries)
from src.corners.batch import FIELDS

ROOT = Path(__file__).resolve().parents[1]
TEAMS = {1: 'Habit In', 2: 'Habit Out', 3: 'Habit Short', 4: 'Habit Straight'}
HABITS = {1: 'inswinging', 2: 'outswinging', 3: 'short', 4: 'straight'}
PAIRS = [(1, 2), (3, 4), (1, 3), (2, 4), (1, 4), (2, 3)]


def corner(match_id, number, team_id, category, shot, date, period=1,
           competition=900, season=1):
    return {'match_id': match_id, 'corner_event_id': f'{match_id}-{number}',
            'team_id': team_id, 'team': TEAMS.get(team_id, f'Team {team_id}'),
            'delivery_category': category, 'shot_count': 1 if shot else 0,
            'goal_count': 0, 'led_to_shot': bool(shot),
            'provider_xg_sum': 0.05 if shot else 0.0,
            'window_seconds': 15.0, 'short_limit': 15.0,
            'competition_id': competition, 'competition_name': 'Invented League',
            'season_id': season, 'season': 'Invented Season', 'match_date': date,
            'period': period}


def make_league(style, matches=60, per_team=4, seed=7):
    """60 matches over 4 teams: each team plays 30, so the 36 training
    matches give every team 18 matches and 72 corners (eligible)."""
    rng = random.Random(seed)
    rows = []
    for i in range(matches):
        date = f'2026-{1 + i // 28:02d}-{1 + i % 28:02d}'
        match_id = 5000 + i
        for team_id in PAIRS[i % len(PAIRS)]:
            for k in range(per_team):
                if style == 'habits':
                    category = HABITS[team_id]
                    shot = team_id == 1
                else:
                    category = rng.choice(SCORED_CATEGORIES)
                    shot = rng.random() < 0.3
                rows.append(corner(match_id, f'{team_id}{k}', team_id, category, shot,
                                   date, period=1 + k % 2))
    return rows


def as_csv_row(row):
    full = {f: '' for f in FIELDS}
    full.update({k: v for k, v in row.items() if k in full})
    full['chain_event_ids'] = '[]'
    full['shot_event_ids'] = '[]'
    return full


def write_rows(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(as_csv_row(r) for r in rows)


def run(rows, draws=200):
    return evaluate(rows, chronological_splits(rows), bootstrap_draws=draws, seed=1)


def table(tables, name, **match):
    return [r for r in tables[name] if all(r[k] == v for k, v in match.items())]


class ShrinkageMathTests(unittest.TestCase):
    def setUp(self):
        history = ([corner(1, n, 1, 'inswinging', False, '2026-01-01') for n in range(3)]
                   + [corner(1, 3, 1, 'outswinging', True, '2026-01-01')]
                   + [corner(1, 4 + n, 2, 'short', False, '2026-01-01') for n in range(4)])
        self.fit = fit_history(history)
        self.stratum = (900, 1)

    def test_pooled_uses_add_one_smoothing(self):
        p = self.fit['pooled'][self.stratum]
        # 8 known corners, 5 categories: inswinging (3 + 1) / (8 + 5)
        self.assertAlmostEqual(p['inswinging'], 4 / 13)
        self.assertAlmostEqual(p['direct_shot'], 1 / 13)

    def test_proposal_formula(self):
        p = delivery_probabilities(self.fit, self.stratum, 1, 'shrunk', 2)
        # (n_td + alpha * p_cd) / (N_t + alpha) = (3 + 2 * 4/13) / (4 + 2)
        self.assertAlmostEqual(p['inswinging'], (3 + 2 * 4 / 13) / 6)
        self.assertAlmostEqual(sum(p.values()), 1.0)

    def test_alpha_zero_is_raw_and_never_zero(self):
        p = delivery_probabilities(self.fit, self.stratum, 1, 'shrunk', 0)
        self.assertAlmostEqual(p['inswinging'], 0.75, places=4)
        self.assertGreaterEqual(p['short'], EPSILON / 2)

    def test_large_alpha_approaches_pooled(self):
        p = delivery_probabilities(self.fit, self.stratum, 1, 'shrunk', 10 ** 7)
        for c in SCORED_CATEGORIES:
            self.assertAlmostEqual(p[c], self.fit['pooled'][self.stratum][c], places=4)

    def test_shot_shrinkage(self):
        # pooled shot: (1 + 1) / (8 + 2) = 0.2; team 1: (1 + 4 * 0.2) / (4 + 4)
        self.assertAlmostEqual(shot_probability(self.fit, self.stratum, 1, 'pooled', 0), 0.2)
        self.assertAlmostEqual(shot_probability(self.fit, self.stratum, 1, 'shrunk', 4),
                               (1 + 4 * 0.2) / 8)


class KnownAnswerTests(unittest.TestCase):
    def test_habits_league_team_history_wins(self):
        tables, meta = run(make_league('habits'))
        self.assertEqual(meta['eligible_teams'], 4)
        self.assertLessEqual(meta['alpha'], 2)
        diff = table(tables, 'evaluation_differences', target='delivery',
                     comparison='shrunk_minus_pooled')[0]
        self.assertLess(diff['ci_high'], 0)
        shot = table(tables, 'evaluation_differences', target='shot',
                     comparison='shrunk_minus_pooled')[0]
        self.assertLess(shot['ci_high'], 0)

    def test_same_league_team_history_does_not_win(self):
        # 20 corners per team per match, so random noise cannot fake a habit.
        tables, meta = run(make_league('same', per_team=20, seed=1))
        self.assertGreaterEqual(meta['alpha'], 200)
        diff = table(tables, 'evaluation_differences', target='delivery',
                     comparison='shrunk_minus_pooled')[0]
        self.assertLess(abs(diff['difference']), 0.01)

    def test_alpha_table_covers_grid(self):
        tables, meta = run(make_league('habits'))
        alphas = table(tables, 'alpha_selection', parameter='alpha')
        self.assertEqual([a['value'] for a in alphas], ALPHA_GRID)
        self.assertEqual(sum(a['chosen'] for a in alphas), 1)


class LeakageTests(unittest.TestCase):
    def test_changing_test_matches_does_not_change_choices_or_profiles(self):
        rows = make_league('same')
        splits = chronological_splits(rows)
        test_ids = {s['match_id'] for s in splits if s['split'] == 'test'}
        tables_a, meta_a = evaluate(rows, splits, 50, 1)
        changed = [dict(r, delivery_category='straight', led_to_shot=True, shot_count=1)
                   if r['match_id'] in test_ids else r for r in rows]
        tables_b, meta_b = evaluate(changed, chronological_splits(changed), 50, 1)
        self.assertEqual((meta_a['alpha'], meta_a['beta']), (meta_b['alpha'], meta_b['beta']))
        self.assertEqual(tables_a['team_predictions'], tables_b['team_predictions'])
        self.assertNotEqual(tables_a['evaluation_summary'], tables_b['evaluation_summary'])

    def test_no_match_in_two_splits_and_test_is_latest(self):
        splits = chronological_splits(make_league('same'))
        self.assertEqual(len({s['match_id'] for s in splits}), len(splits))
        train = max(s['match_date'] for s in splits if s['split'] == 'train')
        test = min(s['match_date'] for s in splits if s['split'] == 'test')
        self.assertLessEqual(train, test)


class EligibilityAndUnknownTests(unittest.TestCase):
    def test_sparse_team_left_out_of_prediction(self):
        rows = make_league('habits')
        rows += [corner(9000 + i, 0, 7, 'inswinging', False, f'2026-01-{1 + i:02d}')
                 for i in range(3)]
        tables, meta = run(rows)
        self.assertEqual(meta['eligible_teams'], 4)
        self.assertFalse(any(r['team_id'] == 7 for r in tables['team_evaluation']))

    def test_unknown_left_out_of_log_loss_but_kept_for_brier(self):
        rows = make_league('habits')
        splits = chronological_splits(rows)
        test_ids = sorted(s['match_id'] for s in splits if s['split'] == 'test')
        rows = [dict(r, delivery_category='unknown') if r['match_id'] == test_ids[0] else r
                for r in rows]
        tables, meta = run(rows)
        delivery = table(tables, 'evaluation_summary', target='delivery', method='shrunk')[0]
        shot = table(tables, 'evaluation_summary', target='shot', method='shrunk')[0]
        self.assertEqual(shot['corners'] - delivery['corners'], 8)
        self.assertEqual(sum(r['test_corners_unknown'] for r in tables['team_evaluation']), 8)


class UncertaintyAndDiagnosticsTests(unittest.TestCase):
    def test_bootstrap_is_reproducible_and_brackets_estimate(self):
        a, _ = run(make_league('same'))
        b, _ = run(make_league('same'))
        self.assertEqual(a['evaluation_summary'], b['evaluation_summary'])
        for row in a['evaluation_summary']:
            self.assertLessEqual(row['ci_low'], row['score'] + 1e-9)
            self.assertGreaterEqual(row['ci_high'], row['score'] - 1e-9)

    def test_reliability_bins_cover_every_test_corner(self):
        tables, meta = run(make_league('same'))
        for method in ('pooled', 'unsmoothed', 'shrunk'):
            total = sum(r['corners'] for r in table(tables, 'reliability', method=method))
            self.assertEqual(total, meta['test_corners'])

    def test_stability_distances_in_range(self):
        tables, _ = run(make_league('habits'))
        for row in tables['profile_stability']:
            self.assertEqual(row['tvd_team_history_vs_test'], 0.0)
            self.assertGreater(row['tvd_pooled_vs_test'], 0.5)

    def test_no_eligible_teams_is_handled(self):
        rows = [corner(1, 0, 1, 'inswinging', False, '2026-01-01')]
        tables, meta = run(rows)
        self.assertEqual(tables['team_evaluation'], [])
        self.assertIsNotNone(meta['note'])


class SummaryExtrasTests(unittest.TestCase):
    def test_summary_intervals_bracket_frequencies(self):
        for s in team_summaries(make_league('same'), bootstrap_draws=200, seed=1):
            for c in DELIVERY_CATEGORIES:
                self.assertLessEqual(s[f'freq_{c}_ci_low'], s[f'freq_{c}'] + 1e-9)
                self.assertGreaterEqual(s[f'freq_{c}_ci_high'], s[f'freq_{c}'] - 1e-9)

    def test_cutoff_keeps_only_earlier_matches(self):
        rows = make_league('same') + [corner(9999, 0, 1, 'short', False, None)]
        summaries = team_summaries(rows, cutoff='2026-01-15')
        team = [s for s in summaries if s['team_id'] == 1][0]
        self.assertLess(team['last_match_date'], '2026-01-15')
        self.assertEqual(team['date_cutoff'], '2026-01-15')
        self.assertEqual(team['corners'],
                         sum(1 for r in rows if r['team_id'] == 1 and r['match_date']
                             and r['match_date'] < '2026-01-15'))

    def test_period_breakdown_adds_up(self):
        rows = make_league('same')
        periods = period_breakdown(rows)
        for s in team_summaries(rows):
            total = sum(p['corners'] for p in periods if p['team_id'] == s['team_id'])
            self.assertEqual(total, s['corners'])


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp)

    def analyse(self, rows, name, window):
        path = self.temp / f'{name}.csv'
        write_rows(path, [dict(r, window_seconds=window) for r in rows])
        out = self.temp / name
        result = subprocess.run([sys.executable, '-m', 'src.analysis', '--input', str(path),
                                 '--output', str(out), '--bootstrap', '50'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return out

    def test_full_run_and_sensitivity_comparison(self):
        rows = make_league('habits')
        w15 = self.analyse(rows, 'w15', 15)
        w20 = self.analyse(rows, 'w20', 20)
        for name in ('alpha_selection', 'evaluation_summary', 'evaluation_differences',
                     'team_evaluation', 'reliability', 'profile_stability',
                     'team_predictions'):
            self.assertTrue((w15 / 'evaluation' / f'{name}.csv').exists(), name)
        self.assertTrue((w15 / 'period_summary.csv').exists())
        out = self.temp / 'sensitivity'
        result = subprocess.run([sys.executable, '-m', 'src.analysis.compare', '--runs',
                                 str(w15), str(w20), '--output', str(out)],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with (out / 'sensitivity_team_rates.csv').open(encoding='utf-8') as handle:
            header = next(csv.reader(handle))
        self.assertIn('window 15s, short 15', header)
        self.assertIn('window 20s, short 15', header)

    def test_cutoff_run_skips_evaluation(self):
        path = self.temp / 'rows.csv'
        write_rows(path, make_league('same'))
        out = self.temp / 'cut'
        result = subprocess.run([sys.executable, '-m', 'src.analysis', '--input', str(path),
                                 '--output', str(out), '--cutoff', '2026-02-01',
                                 '--bootstrap', '0'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((out / 'evaluation').exists())


if __name__ == '__main__':
    unittest.main()
