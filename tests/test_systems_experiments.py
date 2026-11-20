"""Experiment protocol tests; no network or large corpus is required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_DUCKDB = importlib.util.find_spec('duckdb') is not None
if HAS_DUCKDB:
    from src.systems.experiments import experiment, extraction_benchmark, summarize, verify_snapshot


@unittest.skipUnless(HAS_DUCKDB, 'Install systems requirements')
class ExperimentTests(unittest.TestCase):
    def test_summary_reports_variation_and_singleton_unavailable(self):
        result = summarize([1,2,3])
        self.assertEqual(result['mean_seconds'], 2)
        self.assertEqual(result['median_seconds'], 2)
        self.assertEqual(result['sample_sd_seconds'], 1)
        self.assertIsNone(summarize([1])['sample_sd_seconds'])
        with self.assertRaises(ValueError):
            summarize([])

    def test_output_status_records_failure_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)/'run'
            with self.assertRaisesRegex(ValueError, 'test failure'):
                with experiment(destination, 'test'):
                    raise ValueError('test failure')
            self.assertEqual(json.loads((destination/'status.json').read_text())['status'], 'failed')
            with self.assertRaises(FileExistsError):
                with experiment(destination, 'test'):
                    pass

    def test_source_changes_are_rejected(self):
        with patch('src.systems.experiments.source_snapshot', return_value={'changed':True}):
            with self.assertRaisesRegex(ValueError, 'changed'):
                verify_snapshot('unused', {'changed':False})

    def test_benchmark_alternates_order_excludes_warmup_and_checks_every_pair(self):
        calls=[]
        def fake_execute(args, log):
            implementation='python' if 'src/run_corner_batch.py' in args else 'sql'
            calls.append(implementation)
            return 1. if implementation=='python' else 2.
        with tempfile.TemporaryDirectory() as temp, \
             patch('src.systems.experiments.hardware', return_value={}), \
             patch('src.systems.experiments.source_snapshot', return_value={}), \
             patch('src.systems.experiments.verify_snapshot'), \
             patch('src.systems.experiments.execute', side_effect=fake_execute), \
             patch('src.systems.experiments.compare_tables', return_value={'status':'match'}) as checker:
            result=extraction_benchmark('unused', Path(temp)/'run', repetitions=2, warmups=1)
            self.assertEqual(calls, ['python','sql','sql','python','python','sql'])
            self.assertEqual(checker.call_count,3)
            self.assertEqual(result['summaries']['python']['repetitions'],2)
            self.assertEqual(result['sql_over_python_mean'],2)

    def test_benchmark_refuses_incomparable_results(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('src.systems.experiments.hardware', return_value={}), \
             patch('src.systems.experiments.source_snapshot', return_value={}), \
             patch('src.systems.experiments.execute', return_value=1.), \
             patch('src.systems.experiments.compare_tables', return_value={'status':'mismatch'}):
            output=Path(temp)/'run'
            with self.assertRaisesRegex(ValueError, 'disagrees'):
                extraction_benchmark('unused',output,repetitions=2)
            self.assertFalse((output/'report.json').exists())
            self.assertEqual(json.loads((output/'status.json').read_text())['status'],'failed')

    def test_benchmark_requires_repetition_and_warmup(self):
        with self.assertRaises(ValueError):
            extraction_benchmark('unused','unused',repetitions=1)
        with self.assertRaises(ValueError):
            extraction_benchmark('unused','unused',warmups=0)


if __name__=='__main__':
    unittest.main()
