import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from corners.batch import FIELDS, normalize_metadata, run_batch


def events():
    base = dict(period=1, possession=17, team={'id':1,'name':'Example A'}, minute=0)
    return [dict(base,id='corner-1',index=1,timestamp='00:00:00.000',second=0,
                 type={'name':'Pass'},location=[120,0],
                 **{'pass':{'type':{'name':'Corner'},'end_location':[110,0],
                            'height':{'name':'Ground Pass'}}}),
            dict(base,id='shot-1',index=2,timestamp='00:00:04.000',second=4,
                 type={'name':'Shot'},shot={'outcome':{'name':'Saved'},'statsbomb_xg':0.12})]


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'events.json').write_text(json.dumps(events()))
        (self.root/'empty.json').write_text('[]')

    def manifest(self, jobs):
        p=self.root/'matches.json';p.write_text(json.dumps({'matches':jobs}));return p

    def test_metadata_provider_record_and_missing_values(self):
        obj=dict(match_id=1, competition={'competition_id':72,'competition_name':'Example League'},
                 season={'season_id':9,'season_name':'2025/26'},match_date='2026-01-01',
                 home_team={'home_team_name':'Example A'})
        result=normalize_metadata(obj,1)
        self.assertEqual(result['season'],'2025/26')
        self.assertEqual(result['home_team'],'Example A')
        self.assertIsNone(result['away_team'])
        self.assertTrue(all(v is None for v in normalize_metadata({},1).values()))

    def test_rejects_mismatches_invalid_dates_and_conflicts(self):
        for obj in ({'match_id':2},{'match_date':'2026-02-30'},
                    {'match_date':'20260101'}, {'season_id':True},
                    {'season_id':2,'season':{'season_id':3}}, []):
            with self.subTest(obj=obj), self.assertRaises((ValueError,TypeError)):
                normalize_metadata(obj,1)

    def test_batch_metadata_file_and_empty_match(self):
        (self.root/'meta.json').write_text(json.dumps(dict(match_id=1,match_date='2026-01-01',season='2025/26')))
        manifest=self.manifest([dict(match_id=1,events='events.json',metadata='meta.json'),
                                dict(match_id=2,events='empty.json')])
        result=run_batch(manifest,self.root/'out')
        self.assertEqual(result['total_corners'],1)
        self.assertEqual(result['matches'][1]['status'],'no_corners')
        self.assertEqual(len(result['matches'][0]['events_sha256']),64)
        with (self.root/'out/corner_summary.csv').open(encoding='utf-8-sig') as f:
            reader=csv.DictReader(f);self.assertEqual(reader.fieldnames,FIELDS);rows=list(reader)
        self.assertEqual(rows[0]['match_date'],'2026-01-01')
        self.assertEqual(json.loads(rows[0]['shot_event_ids']),['shot-1'])
        self.assertEqual(rows[0]['shot_count'],'1')
        self.assertEqual(rows[0]['competition_id'],'')

    def test_duplicate_manifest_matches_rejected(self):
        job=dict(match_id=1,events='events.json')
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            run_batch(self.manifest([job,job]),self.root/'out')
        self.assertFalse((self.root/'out').exists())

    def test_failed_batch_does_not_publish_partial_results(self):
        manifest=self.manifest([dict(match_id=1,events='events.json'),dict(match_id=2,events='missing.json')])
        with self.assertRaises(OSError):run_batch(manifest,self.root/'out')
        self.assertFalse((self.root/'out').exists())
        self.assertEqual(list(self.root.glob('.corner-run-*')),[])

    def test_existing_output_protected(self):
        output=self.root/'out';output.mkdir();(output/'keep').write_text('keep')
        with self.assertRaises(FileExistsError):
            run_batch(self.manifest([dict(match_id=1,events='events.json')]),output)
        self.assertEqual((output/'keep').read_text(),'keep')

    def test_all_empty_batch_has_csv_header(self):
        run_batch(self.manifest([dict(match_id=1,events='empty.json')]),self.root/'out')
        with (self.root/'out/corner_summary.csv').open(encoding='utf-8-sig') as f:
            reader=csv.DictReader(f);self.assertEqual(reader.fieldnames,FIELDS);self.assertEqual(list(reader),[])

    def test_normalizes_shuffled_events(self):
        data=events();(self.root/'events.json').write_text(json.dumps(list(reversed(data))))
        result=run_batch(self.manifest([dict(match_id=1,events='events.json')]),self.root/'out')
        self.assertEqual(result['matches'][0]['shots'],1)

    @unittest.skipUnless(importlib.util.find_spec('pyarrow'), 'Parquet optional dependency not installed')
    def test_parquet_typed_lists_and_empty_schema(self):
        import pyarrow.parquet as pq
        for filename,expected in [('events.json',1),('empty.json',0)]:
            with self.subTest(filename=filename):
                out=self.root/filename.replace('.json','-out')
                run_batch(self.manifest([dict(match_id=1,events=filename)]),out,parquet=True)
                table=pq.read_table(out/'corner_summary.parquet')
                self.assertEqual(table.num_rows,expected)
                self.assertEqual(table.schema.names,FIELDS)
                self.assertEqual(str(table.schema.field('shot_event_ids').type),'list<element: string>')
                if expected:
                    row=table.to_pylist()[0]
                    self.assertEqual(row['shot_event_ids'],['shot-1'])
                    self.assertIsNone(row['match_date'])
                    self.assertEqual(row['shot_count'],1)


if __name__=='__main__':unittest.main()
