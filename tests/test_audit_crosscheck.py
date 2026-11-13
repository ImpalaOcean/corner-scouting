import importlib.util
from pathlib import Path
import unittest
from decimal import Decimal
import tempfile
import csv
import json
import subprocess
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('independent_checker',Path(__file__).resolve().parents[1]/'src/verify_audit.py')
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def event(kind, t, eid=None, team=1, possession=17, period=1, **kwargs):
    result=dict(id=eid or f'{kind}-{t}',type={'name':kind}, timestamp=f'00:00:{t:06.3f}',
                index=int(t*1000)+1,period=period,team={'id':team},possession=possession)
    result.update(kwargs)
    return result


def corner():
    return event('Pass',0,location=[120,0],**{'pass':{'type':{'name':'Corner'},'height':{'name':'Ground Pass'},'end_location':[108,9]}})


def shot(t=4, outcome='Saved', **kwargs):
    return event('Shot',t,shot={'outcome':{'name':outcome}},**kwargs)


class CheckerTests(unittest.TestCase):
    def check(self, following, **kwargs):
        start=corner()
        return c.compute([start]+following,start,kwargs.get('window',Decimal(15)),15)

    def test_exact_time_limit_and_later(self):
        self.assertEqual(self.check([shot(15)])['shot_count'],1)
        self.assertEqual(self.check([shot(15.001)])['shot_count'],0)

    def test_exact_short_distance_and_above(self):
        start=corner()
        self.assertEqual(c.compute([start],start,15,15)['delivery_category'],'short')
        start['pass']['end_location']=[108,9.001]
        self.assertEqual(c.compute([start],start,15,15)['delivery_category'],'unknown')

    def test_high_pass_and_missing_coordinates(self):
        start=corner(); start['pass']['height']['name']='High Pass'
        self.assertEqual(c.compute([start],start,15,15)['delivery_category'],'unknown')
        start['pass']['height']['name']='Ground Pass'; del start['location']
        self.assertEqual(c.compute([start],start,15,15)['delivery_category'],'unknown')

    def test_direct_goal_and_out_priority(self):
        start=shot(0,'Goal',out=True); start['shot']['type']={'name':'Corner'}
        result=c.compute([start],start,15,15)
        self.assertEqual((result['delivery_category'],result['goal_count'],result['stop_reason']),('direct_shot',1,'goal'))

    def test_all_preinclusion_priorities(self):
        restart=event('Pass',20,period=2,possession=18,**{'pass':{'type':{'name':'Free Kick'}}})
        self.assertEqual(self.check([restart])['stop_reason'],'period_end')
        restart['period']=1
        self.assertEqual(self.check([restart])['stop_reason'],'time_limit')
        restart['timestamp']='00:00:04.000'
        self.assertEqual(self.check([restart])['stop_reason'],'new_restart')
        foul=event('Foul Committed',4,possession=18)
        self.assertEqual(self.check([foul])['stop_reason'],'possession_change')
        foul['possession']=17
        self.assertEqual(self.check([foul])['stop_reason'],'stoppage')

    def test_duplicate_ids_count_once(self):
        attempt=shot()
        self.assertEqual(self.check([attempt,attempt])['shot_count'],1)
        start=corner()
        self.assertEqual(c.compute([start,start,attempt],start,15,15)['chain_event_ids'],[start['id'],attempt['id']])

    def test_match_isolation_same_event_ids(self):
        start=corner()
        matches={'1':[start,shot()], '2':[start,event('Carry',4)]}
        one,s1=c.locate(matches,'1',start['id']); two,s2=c.locate(matches,'2',start['id'])
        self.assertEqual(c.compute(one,s1,15,15)['shot_count'],1)
        self.assertEqual(c.compute(two,s2,15,15)['shot_count'],0)

    def test_offtarget_absent_false_true(self):
        for value, present in [(None,False),(False,True),(True,True)]:
            with self.subTest(value=value,present=present):
                attempt=shot(outcome='Off T')
                if present: attempt['out']=value
                result=self.check([attempt,event('Pass',20,possession=18)])
                self.assertEqual(result['stop_reason'],'ball_out' if value else 'time_limit')
                self.assertEqual(any(x.startswith('off-target') for x in result['ambiguities']),not bool(value))
                raw=result['supporting_events'][1]
                self.assertEqual(raw['out_field_present'],present)

    def test_attacking_shots_only(self):
        self.assertEqual(self.check([shot(team=2)])['shot_count'],0)

    def test_advantage_and_terminal_inclusion(self):
        foul=event('Foul Committed',2,foul_committed={'advantage':True})
        result=self.check([foul,shot(outcome='Goal')])
        self.assertEqual((result['shot_count'],result['goal_count'],result['stop_reason']),(1,1,'goal'))

    def test_uncapped_still_stops(self):
        result=self.check([shot(20),event('Carry',25,possession=18),shot(30)],window=None)
        self.assertEqual((result['shot_count'],result['stop_reason']),(1,'possession_change'))

    def test_missing_possession_unverifiable(self):
        start=corner(); start.pop('possession')
        with self.assertRaises(ValueError): c.compute([start],start,15,15)

    def test_ordering(self):
        start=corner(); late=shot(); early=event('Carry',2)
        self.assertEqual([e['id'] for e in c.ordered([late,start,early])],[start['id'],early['id'],late['id']])

    def test_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError): c.run(Path(tmp),Path(tmp))




class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root/'review'
        self.sample = self.root/'outputs/audit-combined-primary-sample/audit_sheet.csv'
        self.provenance = self.sample.with_name('sample_provenance.json')
        self.sheet_rows = []
        self.raw_paths = []
        self.run_paths = []
        for mid, run_name, input_name in [(1,'wc2022-euro2024-corners','wc2022-euro2024'),(2,'leagues-2015-16-corners','leagues-2015-16')]:
            raw_path = self.root/f'data/raw/{mid}.json'
            start=corner(); start['id']=f'corner-{mid}'
            attempt=shot(); attempt['id']=f'shot-{mid}'
            self.write_json(raw_path,[start,attempt]); self.raw_paths.append(raw_path)
            manifest_path=self.root/'data/ingested'/input_name/'batch_manifest.json'
            self.write_json(manifest_path,{'matches':[{'match_id':mid,'events':f'../../raw/{mid}.json','source_revision':'fixture-revision'}]})
            run_path=self.root/'outputs'/run_name/'run_manifest.json'; self.run_paths.append(run_path)
            self.write_json(run_path,{'manifest_sha256':c.sha(manifest_path),'settings':{'window_seconds':15,'short_limit':15.0},'matches':[{'match_id':mid,'source_revision':'fixture-revision','events_sha256':c.sha(raw_path)}]})
            row={'audit_id':str(mid),'match_id':str(mid),'corner_event_id':start['id'],'delivery_category':'short',
                 'shot_count':'1','goal_count':'0','shot_event_ids':json.dumps([attempt['id']]),
                 'chain_event_ids':json.dumps([start['id'],attempt['id']]),'stop_reason':'end_of_data',
                 'window_seconds':'15','short_limit':'15'}
            self.write_csv(self.root/'outputs'/run_name/'corner_summary.csv',[row])
            self.sheet_rows.append(row)
        self.write_csv(self.sample,self.sheet_rows)
        self.refresh_provenance()
        # Make only the files required for source/test hashes available to run().
        script_dest=self.root/'src/verify_audit.py'
        script_dest.parent.mkdir(parents=True)
        script_dest.write_bytes(Path(c.__file__).read_bytes())
        test_dest=self.root/'tests/test_audit_crosscheck.py'
        test_dest.parent.mkdir(parents=True)
        test_dest.write_bytes(Path(__file__).read_bytes())
        self.previous_file = c.__file__
        c.__file__ = str(script_dest)
        self.addCleanup(setattr,c,'__file__',self.previous_file)

    def write_json(self,path,data):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data),encoding='utf-8')

    def write_csv(self,path,rows):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

    def refresh_provenance(self):
        self.write_json(self.provenance,{'artifacts':{'audit_sheet.csv':{'sha256':c.sha(self.sample)}},
            'sample':{'size':2},'population':{'settings':{'window_seconds':15,'short_limit':15}},
            'inputs':[{'path':'outputs/audit-combined-primary/preparation_manifest.json','sha256':'recorded-but-inaccessible'}]})

    def run_checker(self):
        # Git metadata is external to the checking workflow; fixture directories are not repositories.
        import contextlib
        import io
        with patch.object(subprocess,'check_output',side_effect=['fixture-commit\n','']), contextlib.redirect_stdout(io.StringIO()):
            c.run(self.root,self.output,expected_size=2)
        return c.table(self.output/'automated_crosscheck.csv'),c.load(self.output/'review_manifest.json')

    def test_successful_run_with_verified_frozen_sheet_and_fallback(self):
        original=c.sha(self.sample)
        rows,manifest=self.run_checker()
        self.assertEqual([r['overall_status'] for r in rows],['match','match'])
        self.assertTrue(manifest['frozen_sample_provenance_verified'])
        self.assertFalse(manifest['combined_preparation_verified'])
        self.assertEqual(manifest['inputs']['outputs/audit-combined-primary/preparation_manifest.json']['provenance_status'],'unverified')
        self.assertEqual(c.sha(self.sample),original)
        self.assertTrue((self.output/'evidence.md').exists())

    def test_changed_exported_answer_produces_mismatch(self):
        # Re-freeze an intentionally wrong exported classification to isolate calculation checking.
        self.sheet_rows[0]['delivery_category']='outswinging'
        self.write_csv(self.sample,self.sheet_rows)
        self.write_csv(self.root/'outputs/wc2022-euro2024-corners/corner_summary.csv',[self.sheet_rows[0]])
        self.refresh_provenance()
        rows,_=self.run_checker()
        self.assertEqual(rows[0]['delivery_category_status'],'mismatch')
        self.assertEqual(rows[0]['overall_status'],'mismatch')
        self.assertEqual(rows[0]['exported_delivery_category'],'outswinging')
        self.assertEqual(rows[0]['computed_delivery_category'],'short')
        self.assertEqual(rows[1]['overall_status'],'match')

    def test_wrong_source_hash_leaves_case_unresolved(self):
        report=c.load(self.run_paths[0]); report['matches'][0]['events_sha256']='0'*64
        self.write_json(self.run_paths[0],report)
        rows,_=self.run_checker()
        self.assertEqual(rows[0]['overall_status'],'unresolved')
        self.assertEqual(rows[0]['provenance_status'],'unresolved')
        self.assertEqual(rows[0]['computed_shot_count'],'')
        self.assertEqual(rows[0]['actual_source_sha256'],c.sha(self.raw_paths[0]))
        self.assertIn('Raw source hash mismatch',rows[0]['error'])
        self.assertEqual(rows[1]['overall_status'],'match')

    def test_changed_frozen_sheet_rejected_without_outputs(self):
        self.sample.write_bytes(self.sample.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'Frozen sample hash differs'):
            self.run_checker()
        self.assertFalse(self.output.exists())

    def test_readable_preparation_without_expected_hash_is_unverified(self):
        preparation=self.root/'outputs/audit-combined-primary/preparation_manifest.json'
        self.write_json(preparation,{'fixture':'readable preparation'})
        for include_entry in (False,True):
            with self.subTest(include_entry=include_entry):
                provenance=c.load(self.provenance)
                provenance['inputs'] = [{'path':'outputs/audit-combined-primary/preparation_manifest.json'}] if include_entry else []
                self.write_json(self.provenance,provenance)
                self.output=self.root/f'review-without-hash-{include_entry}'
                _,manifest=self.run_checker()
                self.assertFalse(manifest['combined_preparation_verified'])
                record=manifest['inputs']['outputs/audit-combined-primary/preparation_manifest.json']
                self.assertEqual(record['status'],'readable')
                self.assertEqual(record['sha256'],c.sha(preparation))
                self.assertNotEqual(record.get('provenance_status'),'verified')

    def test_readable_preparation_with_matching_expected_hash_is_verified(self):
        preparation=self.root/'outputs/audit-combined-primary/preparation_manifest.json'
        self.write_json(preparation,{'fixture':'verified preparation'})
        provenance=c.load(self.provenance)
        provenance['inputs'][0]['sha256']=c.sha(preparation)
        self.write_json(self.provenance,provenance)
        _,manifest=self.run_checker()
        self.assertTrue(manifest['combined_preparation_verified'])
        record=manifest['inputs']['outputs/audit-combined-primary/preparation_manifest.json']
        self.assertEqual(record['provenance_status'],'verified')
        self.assertEqual(record['sha256'],record['expected_sha256'])

    def test_changed_readable_sampling_input_rejected(self):
        combined=self.root/'outputs/audit-combined-primary/preparation_manifest.json'
        self.write_json(combined,{'fixture':'changed bytes'})
        with self.assertRaisesRegex(ValueError,'Recorded sampling input hash mismatch'):
            self.run_checker()
        self.assertFalse(self.output.exists())


if __name__=='__main__': unittest.main()
