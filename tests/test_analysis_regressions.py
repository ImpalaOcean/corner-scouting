"""Synthetic regressions for the integration review; never opens corpus/audit data."""
import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.analysis import __main__ as cli
from src.analysis.compare import compare_runs, load_run
from src.analysis.contracts import input_contract
from src.analysis.evaluation import evaluate, eligible_teams
from src.analysis.summary import AnalysisError, chronological_splits
from test_evaluation import corner, make_league, table, write_rows


class TemporaryAnalysis(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def analyse(self, rows, name, window=15):
        source = self.root / f'{name}.csv'
        output = self.root / name
        write_rows(source, [dict(r, window_seconds=window) for r in rows])
        argv = ['analysis', '--input', str(source), '--output', str(output), '--bootstrap', '0']
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(cli, '_plot_reliability', return_value=False):
            cli.main()
        return output, source


class UnknownTargetsTests(TemporaryAnalysis):
    def changed_partition(self, partition):
        rows = make_league('habits')
        splits = chronological_splits(rows)
        ids = {s['match_id'] for s in splits if s['split'] == partition}
        changed = [dict(r, delivery_category='unknown') if r['match_id'] in ids else r for r in rows]
        return changed, splits

    def test_unknown_validation_preserves_shot_selection_scores_and_counts(self):
        rows, splits = self.changed_partition('validation')
        tables, meta = evaluate(rows, splits, bootstrap_draws=10)
        self.assertIsNone(meta['alpha'])
        self.assertIsNotNone(meta['beta'])
        self.assertEqual(meta['test_corners'], 96)
        self.assertEqual(meta['validation_known_delivery_corners'], 0)
        self.assertEqual(meta['targets']['delivery']['reason'], 'no_scorable_validation_delivery_labels')
        self.assertEqual(meta['targets']['shot']['status'], 'available')
        for r in tables['evaluation_summary']:
            if r['target'] == 'delivery':
                self.assertIsNone(r['score'])
                self.assertEqual(r['eligible_corners'], 96)
                self.assertEqual(r['known_delivery_corners'], 96)
            else:
                self.assertIsNotNone(r['score'])
                self.assertEqual(r['corners'], 96)
        for r in tables['team_predictions']:
            self.assertIsNone(r['p_short'])
            self.assertIsNotNone(r['p_shot'])
        self.assertFalse(any(r['chosen'] for r in tables['alpha_selection'] if r['parameter'] == 'alpha'))
        # The shot component must equal the ordinary run (only delivery labels changed).
        normal, normal_meta = evaluate(make_league('habits'), splits, bootstrap_draws=0)
        self.assertEqual(meta['beta'], normal_meta['beta'])
        self.assertEqual([r['score'] for r in table(tables, 'evaluation_summary', target='shot')],
                         [r['score'] for r in table(normal, 'evaluation_summary', target='shot')])

    def test_unknown_test_cli_succeeds_with_explicit_unavailable_delivery(self):
        rows, _ = self.changed_partition('test')
        output, _ = self.analyse(rows, 'unknown-test')
        manifest = json.loads((output / 'analysis_manifest.json').read_text())
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(manifest['evaluation']['test_corners_unknown_delivery'], 96)
        self.assertEqual(manifest['evaluation']['targets']['delivery']['reason'], 'no_scorable_test_delivery_labels')
        with (output / 'evaluation/evaluation_summary.csv').open() as stream:
            scores = list(csv.DictReader(stream))
        self.assertTrue(all(r['score'] == '' and r['status'] == 'unavailable' and r['corners'] == '0'
                            for r in scores if r['target'] == 'delivery'))
        self.assertTrue(all(r['score'] != '' and r['status'] == 'available' and r['corners'] == '96'
                            for r in scores if r['target'] == 'shot'))
        self.assertEqual(len(load_run(output)['teams']), 4)

    def test_unknown_validation_cli_publishes_shot_only_predictions(self):
        rows, _ = self.changed_partition('validation')
        output, _ = self.analyse(rows, 'unknown-validation')
        meta = json.loads((output / 'analysis_manifest.json').read_text())['evaluation']
        self.assertIsNone(meta['alpha'])
        with (output / 'evaluation/team_predictions.csv').open() as stream:
            predictions = list(csv.DictReader(stream))
        self.assertEqual(len(predictions), 12)
        self.assertTrue(all(r['p_short'] == '' and r['p_shot'] != '' for r in predictions))

    def test_missing_validation_does_not_invent_either_parameter(self):
        rows = make_league('habits')
        splits = chronological_splits(rows)
        val = {s['match_id'] for s in splits if s['split'] == 'validation'}
        tables, meta = evaluate([r for r in rows if r['match_id'] not in val], splits, 0)
        self.assertIsNone(meta['alpha']); self.assertIsNone(meta['beta'])
        self.assertTrue(all(r['score'] is None for r in tables['evaluation_summary']))
        self.assertEqual(tables['team_predictions'], [])

    def test_unavailable_delivery_does_not_introduce_test_selection_leakage(self):
        rows, splits = self.changed_partition('validation')
        a, ma = evaluate(rows, splits, 0)
        ids = {s['match_id'] for s in splits if s['split'] == 'test'}
        changed = [dict(r, led_to_shot=not r['led_to_shot']) if r['match_id'] in ids else r for r in rows]
        b, mb = evaluate(changed, splits, 0)
        self.assertEqual((ma['alpha'], ma['beta']), (mb['alpha'], mb['beta']))
        self.assertEqual(a['team_predictions'], b['team_predictions'])
        self.assertNotEqual(table(a, 'evaluation_summary', target='shot'), table(b, 'evaluation_summary', target='shot'))

    def test_train_thresholds_remain_inclusive_and_train_only(self):
        rows = [corner(i, j, 1, 'short', False, f'2026-01-{i:02d}') for i in range(1, 11) for j in range(3)]
        self.assertEqual(len(eligible_teams(rows)), 1)
        self.assertFalse(eligible_teams(rows[:-1]))
        self.assertFalse(eligible_teams([r for r in rows if r['match_id'] != 10]))


class SensitivityGuardsTests(TemporaryAnalysis):
    def setUp(self):
        super().setUp()
        self.rows = make_league('habits', matches=10)
        self.base, self.source = self.analyse(self.rows, 'base')

    def compare_with(self, rows, name='other', window=20):
        other, _ = self.analyse(rows, name, window)
        return compare_runs([load_run(self.base), load_run(other)])

    def test_same_population_permits_only_outcome_window_changes(self):
        changed = [dict(r, shot_count=2, goal_count=1, led_to_shot=True, provider_xg_sum=.4) for r in self.rows]
        self.assertEqual(len(self.compare_with(changed)[2]), 2)
        self.assertEqual(len(self.compare_with(changed, 'uncapped', None)[2]), 2)

    def test_same_size_different_corner_keys_rejected(self):
        rows = copy.deepcopy(self.rows); rows[0]['corner_event_id'] = 'replacement'
        with self.assertRaisesRegex(AnalysisError, 'population_sha256'):
            self.compare_with(rows)

    def test_delivery_metadata_and_coordinates_are_invariant(self):
        for field, value in [('delivery_category', 'unknown'), ('competition_id', 77),
                             ('competition_name', 'Other league'), ('season', 'Other season'),
                             ('match_date', '2026-01-02'), ('start_x', 119), ('technique', 'Straight')]:
            with self.subTest(field=field):
                rows = [dict(r, **{field: value}) for r in self.rows]
                # write_rows retains supplied values for all exported fields.
                with self.assertRaisesRegex(AnalysisError, 'invariants_sha256'):
                    self.compare_with(rows, field)

    def test_different_short_limit_rejected(self):
        with self.assertRaises(AnalysisError):
            self.compare_with([dict(r, short_limit=10) for r in self.rows])

    def test_mixed_settings_rejected_before_publication(self):
        rows = copy.deepcopy(self.rows); rows[0]['short_limit'] = 10
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as failure:
            self.analyse(rows, 'mixed')
        self.assertEqual(failure.exception.code, 1)
        self.assertIn('mixes extraction settings', stderr.getvalue())
        self.assertFalse((self.root / 'mixed').exists())

    def test_cutoff_seed_and_other_controls_rejected(self):
        other, _ = self.analyse(self.rows, 'other', 20)
        for field, value in [('seed', 99), ('date_cutoff', '2026-01-01'), ('bootstrap_draws', 5),
                             ('evaluation_protocol', 'changed')]:
            a, b = load_run(self.base), load_run(other)
            b['manifest'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(AnalysisError, 'analysis control'):
                compare_runs([a, b])

    def test_changed_input_hash_rejected(self):
        self.source.write_bytes(self.source.read_bytes() + b'\n')
        with self.assertRaisesRegex(AnalysisError, 'input hash mismatch'):
            load_run(self.base)

    def test_changed_result_hash_rejected(self):
        result = self.base / 'team_summary_v1.csv'
        result.write_bytes(result.read_bytes() + b'\n')
        with self.assertRaisesRegex(AnalysisError, 'artifact hash mismatch'):
            load_run(self.base)

    def test_absent_raw_uses_verified_contract_with_explicit_warning(self):
        self.source.unlink()
        run = load_run(self.base)
        self.assertTrue(any('Original input unavailable' in w for w in run['provenance_warnings']))

    def test_absent_raw_without_verified_contract_rejected(self):
        self.source.unlink()
        (self.base / 'input_contract.json').unlink()
        with self.assertRaises(AnalysisError): load_run(self.base)

    def test_unreadable_raw_uses_verified_contract_and_discloses_access_error(self):
        with patch('src.analysis.compare.input_contract', side_effect=PermissionError('fixture permission denied')):
            run = load_run(self.base)
        self.assertTrue(any('cannot be read' in w for w in run['provenance_warnings']))
        self.assertTrue(any('hash-verified saved input contract' in w for w in run['provenance_warnings']))

    def test_legacy_inputs_disclose_unverified_historical_provenance(self):
        path = self.base / 'analysis_manifest.json'
        manifest = json.loads(path.read_text())
        for field in ('input_sha256', 'input_contract_sha256', 'outputs_sha256', 'status'):
            manifest.pop(field)
        path.write_text(json.dumps(manifest))
        run = load_run(self.base)
        self.assertTrue(any('historical association' in w for w in run['provenance_warnings']))

    def test_missing_required_result_file_is_not_silently_empty(self):
        (self.base / 'evaluation/evaluation_summary.csv').unlink()
        with self.assertRaises(AnalysisError): load_run(self.base)


class SafePublicationTests(TemporaryAnalysis):
    def test_write_failure_does_not_publish_or_leave_staging(self):
        original = cli.write_csv
        def failing_write(path, *args):
            if Path(path).name == 'period_summary.csv':
                raise OSError('synthetic write failure')
            return original(path, *args)
        with patch.object(cli, 'write_csv', side_effect=failing_write), self.assertRaisesRegex(OSError, 'synthetic'):
            self.analyse(make_league('habits', matches=10), 'failed')
        self.assertFalse((self.root / 'failed').exists())
        self.assertEqual(list(self.root.glob('.analysis-staging-*')), [])

    def test_render_failure_before_publish_does_not_leave_completed_run(self):
        with patch.object(cli, '_print_evaluation', side_effect=RuntimeError('synthetic render failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                self.analyse(make_league('habits', matches=10), 'failed')
        self.assertFalse((self.root / 'failed').exists())
        self.assertEqual(list(self.root.glob('.analysis-staging-*')), [])

    def test_existing_output_is_preserved(self):
        output, _ = self.analyse(make_league('habits', matches=10), 'existing')
        before = (output / 'analysis_manifest.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.analyse(make_league('habits', matches=10), 'existing')
        self.assertEqual(before, (output / 'analysis_manifest.json').read_bytes())


if __name__ == '__main__': unittest.main()
