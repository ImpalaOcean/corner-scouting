"""Regressions for report evidence and frozen human-audit safeguards."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.analysis import audit, report
from src.analysis.summary import AnalysisError
from tests.test_evaluation import make_league, write_rows

ROOT = Path(__file__).resolve().parents[1]


class ReportEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.runs = []
        for window in (15, 20):
            source = cls.root / f'w{window}.csv'
            write_rows(source, [dict(r, window_seconds=window) for r in make_league('habits')])
            output = cls.root / f'run{window}'
            result = subprocess.run([sys.executable, '-B', '-m', 'src.analysis',
                '--input', str(source), '--output', str(output), '--bootstrap', '10'],
                cwd=ROOT, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            cls.runs.append(output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_valid_windows_and_relocated_identical_input(self):
        with tempfile.TemporaryDirectory() as temp:
            moved = Path(temp) / 'same.csv'
            shutil.copyfile(self.root / 'w15.csv', moved)
            a = report.load_run(self.runs[0], input_override=moved)
            state = report.rebuild(a, moved)
            report.check_reproduction(a, state)
            self.assertEqual(len(report.window_table([a, report.load_run(self.runs[1])])), 8)

    def test_changed_intervals_team_results_and_selection_are_rejected(self):
        for name in ('evaluation_differences.csv', 'team_evaluation.csv', 'alpha_selection.csv'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                run = Path(temp) / 'run'
                shutil.copytree(self.runs[0], run)
                path = run / 'evaluation' / name
                path.write_bytes(path.read_bytes() + b'\n')
                with self.assertRaisesRegex(AnalysisError, 'artifact hash mismatch'):
                    report.load_run(run)

    def test_changed_input_with_identical_scores_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'changed.csv'
            write_rows(source, [dict(r, team='Renamed') for r in make_league('habits')])
            with self.assertRaisesRegex(AnalysisError, 'input hash mismatch'):
                report.load_run(self.runs[0], input_override=source)

    def test_missing_artifact_hash_is_not_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / 'run'
            shutil.copytree(self.runs[0], run)
            path = run / 'analysis_manifest.json'
            meta = json.loads(path.read_text())
            del meta['outputs_sha256']['evaluation/evaluation_differences.csv']
            path.write_text(json.dumps(meta))
            with self.assertRaisesRegex(AnalysisError, 'missing recorded artifact hash'):
                report.load_run(run)

    def test_window_control_mismatch_rejected(self):
        a, b = [report.load_run(p) for p in self.runs]
        b['verified_run'] = copy.deepcopy(b['verified_run'])
        b['verified_run']['manifest']['seed'] = 999
        with self.assertRaisesRegex(AnalysisError, 'incompatible analysis control'):
            report.window_table([a, b])

    def test_window_population_and_threshold_mismatch_rejected(self):
        for field, value in (('invariants_sha256', 'different'), ('short_limit', 999)):
            with self.subTest(field=field):
                a, b = [report.load_run(p) for p in self.runs]
                b['verified_run'] = copy.deepcopy(b['verified_run'])
                b['verified_run']['contract'][field] = value
                with self.assertRaisesRegex(AnalysisError, 'incompatible window comparison'):
                    report.window_table([a, b])

    def test_tampered_report_cli_publishes_no_output(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / 'run'
            shutil.copytree(self.runs[0], run)
            path = run / 'evaluation/evaluation_differences.csv'
            path.write_bytes(path.read_bytes() + b'\n')
            output = Path(temp) / 'report'
            result = subprocess.run([sys.executable, '-B', '-m', 'src.analysis.report',
                '--run', str(run), '--output', str(output)], cwd=ROOT,
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


class FrozenAuditTests(unittest.TestCase):
    @staticmethod
    def write(path, rows):
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=audit.SHEET_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.master = self.root / 'audit_sheet.csv'
        rows = [dict.fromkeys(audit.SHEET_FIELDS, '') for _ in range(100)]
        for i, row in enumerate(rows, 1):
            row.update(audit_id=str(i), match_id='1', corner_event_id=f'c{i}')
        self.write(self.master, rows)
        self.provenance = self.root / 'sample_provenance.json'
        self.provenance.write_text(json.dumps({'artifacts': {'audit_sheet.csv': {
            'sha256': hashlib.sha256(self.master.read_bytes()).hexdigest()}}}))
        self.answers = {r['audit_id']: dict(r, **{f: 'y' for f in audit.REVIEW_FIELDS}) for r in rows}

    def test_complete_copies_match_master(self):
        audit.validate_frozen_sheets(self.master, [self.answers, copy.deepcopy(self.answers)])
        self.assertEqual(audit.agreement(self.answers, self.answers)[0][0]['answered_by_both'], 100)

    def test_equally_truncated_sheets_are_rejected(self):
        del self.answers['100']
        with self.assertRaisesRegex(AnalysisError, 'frozen master population'):
            audit.validate_frozen_sheets(self.master, [self.answers, self.answers])

    def test_changed_master_or_frozen_values_rejected(self):
        self.answers['1']['shot_count'] = '999'
        with self.assertRaisesRegex(AnalysisError, 'frozen corner fields'):
            audit.validate_frozen_sheets(self.master, [self.answers])
        self.master.write_bytes(self.master.read_bytes() + b'\n')
        with self.assertRaisesRegex(AnalysisError, 'master hash mismatch'):
            audit.validate_frozen_sheets(self.master, [self.answers])

    def test_duplicate_audit_ids_and_corner_keys_rejected(self):
        for field in ('audit_id', 'corner_event_id'):
            rows = list(copy.deepcopy(self.answers).values())
            rows[-1][field] = rows[0][field]
            path = self.root / 'duplicate.csv'
            self.write(path, rows)
            with self.assertRaisesRegex(AnalysisError, 'duplicate'):
                audit._read_sheet(path)

    def test_negative_answers_require_notes(self):
        self.answers['1']['shot_ok'] = 'n'
        with self.assertRaisesRegex(AnalysisError, 'require a note'):
            audit.agreement(self.answers, self.answers)

    def test_truncated_cli_rejected_before_publication(self):
        del self.answers['100']
        paths = [self.root / 'a.csv', self.root / 'b.csv']
        for path in paths:
            self.write(path, self.answers.values())
        output = self.root / 'agreement'
        result = subprocess.run([sys.executable, '-B', '-m', 'src.analysis.audit', 'agree',
            '--sheets', *map(str, paths), '--master', str(self.master), '--output', str(output)],
            cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_first_boundary_retained_in_both_evidence_views(self):
        starter = dict(id='c', period=1, timestamp='00:44:59.000', type={'name': 'Pass'})
        for boundary in (dict(id='next', period=2, timestamp='00:00:00.000', type={'name': 'Half Start'}),
                         dict(id='next', period=1, timestamp='00:45:30.000', type={'name': 'Pass'})):
            events = [starter, boundary]
            self.assertEqual([e['id'] for e in audit.raw_events(events, 'c')], ['c', boundary['id']])
            self.assertIn('[' + boundary['id'] + ']', audit.event_timeline(events, 'c')[-1])
