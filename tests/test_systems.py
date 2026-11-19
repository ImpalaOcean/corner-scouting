"""Differential extraction, hand-checked boundaries, and runnable handoff checks."""
import copy
import csv
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.corners.extract import build_corner_summaries, timestamp_seconds
from src.corners.batch import FIELDS, LIST_FIELDS, run_batch as python_batch

HAS_DUCKDB = importlib.util.find_spec('duckdb') is not None
if HAS_DUCKDB:
    import duckdb
    from src.systems.extract import extract_match, run_batch as sql_batch
    from src.systems.compare import compare_tables, load_table
    from src.systems.run import run


def action(kind='Pass', seconds=0, eid=None, possession=17, team=1, period=1, **details):
    minutes, sec = divmod(seconds, 60)
    event = dict(id=eid or f'{kind}-{seconds}', type={'name': kind}, index=int(seconds*1000)+1,
                 period=period, timestamp=f'00:{int(minutes):02}:{sec:06.3f}',
                 possession=possession, team={'id': team, 'name': f'Team {team}'})
    event[kind.lower().replace(' ', '_')] = details
    return event


def corner(**kwargs):
    event = action(type={'name': 'Corner'}, **kwargs)
    event['location'] = [120, 0]
    event['pass'].update(end_location=[108, 9], height={'name': 'Ground Pass'}, technique={'name': 'Inswinging'})
    return event


def shot(seconds=4, outcome='Saved', team=1, **kwargs):
    return action('Shot', seconds, team=team, outcome={'name': outcome}, statsbomb_xg=0.12, **kwargs)


@unittest.skipUnless(HAS_DUCKDB, 'Install src/systems/requirements.txt for SQL systems tests')
class SQLRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connection = duckdb.connect()
        cls.connection.execute('SET threads=1')

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def agrees(self, events, window=15, short_limit=15):
        ordered = sorted(copy.deepcopy(events), key=lambda e: (e['period'], timestamp_seconds(e['timestamp']), e['index']))
        expected = build_corner_summaries(ordered, 1, max_seconds=window, short_limit=short_limit)
        actual = extract_match(events, 1, window, short_limit, self.connection)
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertEqual(set(a), set(b))
            for field in a:
                if field == 'provider_xg_sum':
                    self.assertAlmostEqual(a[field], b[field], delta=1e-12)
                else:
                    self.assertEqual(a[field], b[field], field)
        return actual

    def test_hand_checked_rebound_goal(self):
        rows = self.agrees([corner(), shot(4), shot(8, outcome='Goal'), shot(10)])
        self.assertEqual((rows[0]['shot_count'], rows[0]['goal_count'], rows[0]['stop_reason']), (2, 1, 'goal'))
        self.assertEqual(rows[0]['shot_event_ids'], ['Shot-4', 'Shot-8'])
        self.assertEqual(rows[0]['delivery_category'], 'short')

    def test_time_cap_and_uncapped(self):
        events = [corner(), shot(10), shot(15), shot(15.001), shot(20), shot(21)]
        for window, shots in ((10, 1), (15, 2), (20, 4), (None, 5)):
            with self.subTest(window=window):
                row = self.agrees(events, window)[0]
                self.assertEqual(row['shot_count'], shots)

    def test_restart_stoppage_and_priority(self):
        for restart in ('Corner', 'Free Kick', 'Goal Kick', 'Kick Off', 'Throw-in', 'Penalty'):
            for kind in ('Pass', 'Shot'):
                with self.subTest(restart=restart, kind=kind):
                    boundary = action(kind, 2, type={'name': restart}, possession=18)
                    row = self.agrees([corner(), boundary, shot(4)])[0]
                    self.assertEqual(row['stop_reason'], 'new_restart')
                    self.assertNotIn(boundary['id'], row['chain_event_ids'])
        for kind in ('Half End', 'Injury Stoppage', 'Offside', 'Referee Ball-Drop', 'Foul Won', 'Foul Committed'):
            row = self.agrees([corner(), action(kind, 2), shot(4)])[0]
            self.assertEqual(row['stop_reason'], 'stoppage')
        late = shot(16, outcome='Goal', possession=18, period=2)
        self.assertEqual(self.agrees([corner(), late])[0]['stop_reason'], 'period_end')
        late['period'] = 1
        self.assertEqual(self.agrees([corner(), late])[0]['stop_reason'], 'time_limit')
        late['timestamp'] = '00:00:14.000'
        self.assertEqual(self.agrees([corner(), late])[0]['stop_reason'], 'possession_change')

    def test_advantage_pressure_and_opponent_shots(self):
        for kind in ('Foul Won', 'Foul Committed'):
            row = self.agrees([corner(), action('Pressure', 1, team=2),
                               action(kind, 2, advantage=True), shot(3, team=2), shot(4)])[0]
            self.assertEqual(row['shot_count'], 1)
            self.assertEqual(len(row['chain_event_ids']), 5)

    def test_missing_possession_and_starter_rejection(self):
        missing = shot()
        del missing['possession']
        self.assertEqual(self.agrees([corner(), missing])[0]['stop_reason'], 'possession_change')
        starter = corner()
        del starter['possession']
        with self.assertRaisesRegex(duckdb.Error, 'no possession'):
            extract_match([starter], 1, connection=self.connection)

    def test_terminal_out_and_opponent_goal(self):
        last = shot()
        last['out'] = True
        row = self.agrees([corner(), last, shot(8)])[0]
        self.assertEqual((row['shot_count'], row['stop_reason']), (1, 'ball_out'))
        row = self.agrees([corner(), shot(4, outcome='Goal', team=2), shot(8)])[0]
        self.assertEqual((row['goal_count'], row['shot_count'], row['stop_reason']), (0, 0, 'goal'))

    def test_direct_shots_and_starter_terminal(self):
        for terminal in ('none', 'goal', 'out'):
            starter = shot(0, outcome='Goal' if terminal == 'goal' else 'Saved', type={'name': 'Corner'})
            starter['out'] = terminal == 'out'
            row = self.agrees([starter, shot(4)])[0]
            self.assertEqual(row['shot_count'], 2 if terminal == 'none' else 1)
            self.assertEqual(row['delivery_category'], 'direct_shot')

    def test_short_threshold_technique_and_missing_coordinates(self):
        for limit in (10, 15, 20):
            for length in (limit-0.001, limit, limit+0.001):
                c = corner()
                c['pass']['end_location'] = [120-length, 0]
                row = self.agrees([c], short_limit=limit)[0]
                self.assertEqual(row['delivery_category'], 'short' if length <= limit else 'inswinging')
        for technique, category in (('Inswinging', 'inswinging'), ('Outswinging', 'outswinging'), ('Straight', 'straight'), ('Other', 'unknown')):
            c = corner()
            c['pass'].update(height={'name': 'High Pass'}, technique={'name': technique})
            self.assertEqual(self.agrees([c])[0]['delivery_category'], category)
        for coords in (None, [], [120]):
            c = corner()
            c['location'] = coords
            c['pass'].pop('technique')
            self.assertEqual(self.agrees([c])[0]['delivery_category'], 'unknown')
        c = corner()
        c['team']['name'] = None
        self.assertIsNone(self.agrees([c])[0]['team'])

    def test_duplicates_are_chain_local(self):
        c = corner()
        attempt = shot()
        self.agrees([c, copy.deepcopy(c), attempt, copy.deepcopy(attempt)])
        earlier = shot(0, eid='repeat')
        later = shot(4, eid='repeat')
        self.assertEqual(self.agrees([earlier, corner(seconds=2), later])[0]['shot_count'], 1)
        # A non-corner with the starter UUID appears first; Python anchors there.
        first = action(seconds=0, eid='same')
        self.agrees([first, shot(1), corner(seconds=2, eid='same'), shot(4)])
        # The first post-starter occurrence wins even if a later duplicate scores.
        self.agrees([corner(), shot(2, eid='dup'), shot(4, eid='dup', outcome='Goal'), shot(8)])

    def test_stable_ordering_and_empty_match(self):
        first, second = shot(4, eid='first'), shot(4, eid='second')
        first['index'] = second['index'] = 5
        row = self.agrees([first, corner(), second])[0]
        self.assertEqual(row['shot_event_ids'], ['first', 'second'])
        self.agrees([])
        self.agrees([action('Pressure', 2)])

    def test_seeded_differential_sequences(self):
        rng = random.Random(5118)
        for case in range(40):
            events = [corner()]
            for i in range(1, 16):
                kind = rng.choice(['Pass', 'Shot', 'Pressure', 'Foul Won', 'Clearance'])
                event = action(kind, i*1.75, eid=f'e{i}', team=rng.choice([1, 1, 2]),
                               possession=rng.choice([17, 17, 17, 18]))
                if kind == 'Shot':
                    event['shot'] = dict(outcome={'name': rng.choice(['Saved', 'Goal', 'Off T'])}, statsbomb_xg=rng.random())
                if kind == 'Foul Won':
                    event['foul_won']['advantage'] = rng.choice([True, False])
                event['out'] = rng.random() < .08
                events.append(event)
            rng.shuffle(events)
            for window in (10, 15, 20, None):
                with self.subTest(case=case, window=window):
                    self.agrees(events, window)

    def test_invalid_settings_and_ordering_fields(self):
        for limit in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                extract_match([corner()], 1, short_limit=limit, connection=self.connection)
        for window in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                extract_match([corner()], 1, window=window, connection=self.connection)
        invalid = corner()
        del invalid['index']
        with self.assertRaisesRegex(ValueError, 'index'):
            extract_match([invalid], 1, connection=self.connection)


@unittest.skipUnless(HAS_DUCKDB, 'Install src/systems/requirements.txt for SQL systems tests')
class SystemsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.manifest = ROOT / 'tests/fixtures/corner_batch/manifest.json'

    def write_table(self, name, rows):
        path = self.folder / name
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v) if k in LIST_FIELDS else v for k, v in row.items()})
        return path

    def test_fixture_batch_provenance_and_zero_corner_match(self):
        python_batch(self.manifest, self.folder/'python')
        report = sql_batch(self.manifest, self.folder/'sql')
        self.assertEqual([m['corners'] for m in report['matches']], [1, 0])
        compared = compare_tables(self.folder/'python/corner_summary.csv', self.folder/'sql/corner_summary.csv', self.folder/'compare')
        self.assertEqual(compared['status'], 'match')
        self.assertEqual(compared['warnings'], [])
        with self.assertRaises(FileExistsError):
            sql_batch(self.manifest, self.folder/'sql')

    def test_complete_field_comparison_lists_nulls_and_tolerance(self):
        python_batch(self.manifest, self.folder/'python')
        rows = list(load_table(self.folder/'python/corner_summary.csv').values())
        original = self.write_table('original.csv', rows)
        for field, value in [('delivery_category', 'unknown'), ('shot_count', 0), ('goal_count', 1),
                             ('led_to_shot', False), ('stop_reason', 'goal'), ('team', 'different'),
                             ('window_seconds', None), ('shot_event_ids', []),
                             ('chain_event_ids', list(reversed(rows[0]['chain_event_ids'])))]:
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            result = compare_tables(original, self.write_table(f'{field}.csv', changed), self.folder/f'compare-{field}')
            self.assertEqual(result['status'], 'mismatch')
            self.assertIn(field, result['mismatches_by_field'])
        changed = copy.deepcopy(rows)
        changed[0]['provider_xg_sum'] += 1e-14
        self.assertEqual(compare_tables(original, self.write_table('float.csv', changed), self.folder/'float')['status'], 'match')

    def test_extra_missing_and_duplicate_keys(self):
        python_batch(self.manifest, self.folder/'python')
        rows = list(load_table(self.folder/'python/corner_summary.csv').values())
        a, b = self.write_table('a.csv', rows), self.write_table('b.csv', [])
        result = compare_tables(a, b, self.folder/'missing')
        self.assertEqual(result['missing_keys'], 1)
        self.assertEqual(compare_tables(b, a, self.folder/'extra')['extra_keys'], 1)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            load_table(self.write_table('dups.csv', rows*2))

    def test_manifest_mismatch_and_output_tampering(self):
        python_batch(self.manifest, self.folder/'python')
        sql_batch(self.manifest, self.folder/'sql')
        manifest = self.folder/'sql/run_manifest.json'
        content = json.loads(manifest.read_text())
        content['matches'][0]['events_sha256'] = '0' * 64
        manifest.write_text(json.dumps(content))
        result = compare_tables(self.folder/'python/corner_summary.csv', self.folder/'sql/corner_summary.csv', self.folder/'bad')
        self.assertEqual(result['status'], 'mismatch')
        self.assertIn('Extraction manifest matches differs', result['provenance_errors'])
        csv_path = self.folder/'sql/corner_summary.csv'
        csv_path.write_bytes(csv_path.read_bytes()+b'\n')
        result = compare_tables(self.folder/'python/corner_summary.csv', csv_path, self.folder/'tamper')
        self.assertTrue(any('output hash' in e for e in result['provenance_errors']))

    def test_parquet_matches_typed_csv(self):
        if importlib.util.find_spec('pyarrow') is None:
            self.skipTest('Parquet dependency absent')
        import pyarrow.parquet as pq
        sql_batch(self.manifest, self.folder/'sql', parquet=True)
        self.assertEqual(pq.read_table(self.folder/'sql/corner_summary.parquet').to_pylist(),
                         list(load_table(self.folder/'sql/corner_summary.csv').values()))

    def test_comparison_cli_nonzero_on_mismatch(self):
        python_batch(self.manifest, self.folder/'python')
        rows = list(load_table(self.folder/'python/corner_summary.csv').values())
        rows[0]['goal_count'] = 1
        changed = self.write_table('changed.csv', rows)
        result = subprocess.run([sys.executable, '-B', '-m', 'src.systems.compare', '--reference',
                    str(self.folder/'python/corner_summary.csv'), '--candidate', str(changed),
                    '--output', str(self.folder/'cli')], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue((self.folder/'cli/differences.csv').is_file())

    def test_runner_analysis_and_published_paths(self):
        report = run(self.folder/'run', manifest=self.manifest, bootstrap=0)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['corners'], 1)
        analysis = json.loads((self.folder/'run/analysis/analysis_manifest.json').read_text())
        self.assertTrue(Path(analysis['input']).is_file())
        comparison = json.loads((self.folder/'run/comparison/comparison.json').read_text())
        for item in comparison['inputs'].values():
            self.assertTrue((self.folder/'run/comparison'/item['path']).is_file())
        with self.assertRaises(FileExistsError):
            run(self.folder/'run', manifest=self.manifest)

    def test_runner_preserves_failure_evidence_and_stops_analysis(self):
        def bad_comparison(*args, **kwargs):
            return {'status': 'mismatch'}
        with patch('src.systems.run.compare_tables', side_effect=bad_comparison):
            with self.assertRaisesRegex(ValueError, 'Run failed'):
                run(self.folder/'run', manifest=self.manifest)
        status = json.loads((self.folder/'run/run.json').read_text())
        self.assertEqual(status['status'], 'failed')
        self.assertFalse((self.folder/'run/analysis').exists())

    def test_runner_refuses_incomplete_coverage(self):
        config = self.folder/'config.json'
        config.write_text('{}')
        with patch('src.systems.run.ingest', return_value={'complete': False}):
            with self.assertRaisesRegex(ValueError, 'Run failed'):
                run(self.folder/'run', config=config)
        status = json.loads((self.folder/'run/run.json').read_text())
        self.assertEqual(status['failed_stage'], 'ingestion')
        self.assertFalse((self.folder/'run/python').exists())

    def test_incomplete_provenance_is_not_reported_verified(self):
        python_batch(self.manifest, self.folder/'python')
        manifest = self.folder/'python/run_manifest.json'
        manifest.write_text(json.dumps({'total_corners': 1, 'matches': []}))
        with self.assertRaisesRegex(ValueError, 'incomplete extraction provenance'):
            compare_tables(self.folder/'python/corner_summary.csv', self.folder/'python/corner_summary.csv', self.folder/'bad')

    def test_ingestion_relative_paths_survive_runner_publication(self):
        from src.corners.batch import load_jobs
        config = self.folder/'config.json'
        config.write_text('{}')
        def fixture_ingestion(settings, **kwargs):
            destination = Path(settings['output_dir'])
            destination.mkdir()
            source = json.loads(self.manifest.read_text())
            for entry in source['matches']:
                entry['events'] = os.path.relpath(self.manifest.parent/entry['events'], destination)
            (destination/'batch_manifest.json').write_text(json.dumps(source))
            return dict(complete=True, matches=[dict(match_id=1, corner_count=1), dict(match_id=2, corner_count=0)])
        with patch('src.systems.run.ingest', side_effect=fixture_ingestion):
            report = run(self.folder/'run', config=config, analysis=False)
        self.assertEqual(report['status'], 'complete')
        jobs, _ = load_jobs(self.folder/'run/ingestion/batch_manifest.json')
        self.assertTrue(all(path.is_file() for _, path, _, _ in jobs))


if __name__ == '__main__':
    unittest.main()
