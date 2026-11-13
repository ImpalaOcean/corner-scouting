"""Tests for src/analysis/audit.py (the 100 corner audit tool)."""

import unittest

from src.analysis.audit import agreement, draw_sample, event_timeline
from src.analysis.summary import AnalysisError


def corners(n=300):
    rows = []
    categories = ['inswinging'] * 6 + ['outswinging'] * 4 + ['short', 'unknown']
    reasons = ['time_limit', 'ball_out', 'possession_change', 'stoppage']
    for i in range(n):
        rows.append({
            'match_id': 100 + i // 10, 'corner_event_id': f'c{i:04d}', 'team': 'T',
            'period': 1, 'timestamp': f'00:{i % 60:02d}:00.000',
            'delivery_category': 'direct_shot' if i % 97 == 0 else categories[i % len(categories)],
            'shot_count': 1 if i % 3 == 0 else 0, 'goal_count': 1 if i % 50 == 0 else 0,
            'led_to_shot': i % 3 == 0, 'stop_reason': reasons[i % len(reasons)],
            'window_seconds': 15.0, 'chain_event_ids': '[]'})
    return rows


class SampleTests(unittest.TestCase):
    def test_same_seed_same_sample(self):
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


class TimelineTests(unittest.TestCase):
    def test_window_and_period_limits(self):
        def event(i, t, period=1):
            return {'id': f'e{i}', 'period': period, 'timestamp': f'00:10:{t:06.3f}',
                    'type': {'name': 'Pass'}, 'team': {'name': 'T'}, 'possession': 1}
        events = [event(0, 0), event(1, 5), event(2, 24), event(3, 26), event(4, 27, 2)]
        lines = event_timeline(events, 'e0', seconds=25)
        self.assertEqual(len(lines), 3)
        with self.assertRaises(AnalysisError):
            event_timeline(events, 'missing')


class AgreementTests(unittest.TestCase):
    def sheet(self, answers):
        return {str(i): {'corner_event_id': f'c{i}', 'notes': '', 'delivery_ok': a,
                         'shot_ok': 'y', 'goal_ok': 'y', 'stop_ok': a}
                for i, a in enumerate(answers, start=1)}

    def test_percent_and_kappa(self):
        a = self.sheet(['y', 'y', 'n', 'n'])
        b = self.sheet(['y', 'n', 'n', 'n'])
        summary, disagreements = agreement(a, b)
        delivery = [s for s in summary if s['field'] == 'delivery_ok'][0]
        self.assertEqual(delivery['percent_agreement'], 75.0)
        # observed 0.75, expected 0.5 * 0.25 + 0.5 * 0.75 = 0.5, kappa 0.5
        self.assertEqual(delivery['cohens_kappa'], 0.5)
        self.assertEqual(len(disagreements), 2)

    def test_different_corners_rejected(self):
        a = self.sheet(['y'])
        b = self.sheet(['y'])
        b['1']['corner_event_id'] = 'other'
        with self.assertRaises(AnalysisError):
            agreement(a, b)


if __name__ == '__main__':
    unittest.main()
