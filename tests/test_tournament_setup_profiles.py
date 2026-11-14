"""Synthetic shared-fit/denominator regressions, with no real audit answers."""
import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import profile_tournament_setups as profiles


def corner(mid='1', eid='e', team='A', competition='43'):
    return dict(match_id=mid,corner_event_id=eid,team_id=team,team=team,
                competition_id=competition,competition_name='World Cup' if competition=='43' else 'Euro',
                season_id='106' if competition=='43' else '282',season='2022' if competition=='43' else '2024',
                start_x=120.,start_y=80.,window_seconds='15',short_limit='15')


def frame(eid='e', x=110, y=40, players=5):
    return dict(event_uuid=eid,visible_area=[60,0,120,0,120,80,60,80],
                freeze_frame=[dict(location=[x,y],teammate=True,actor=False,keeper=False) for _ in range(players)])


class TeamProfileTests(unittest.TestCase):
    def shared_input(self):
        corners=[corner('1','a','A'),corner('1','b','A'),corner('1','excluded','A'),
                 corner('2','a','B','55'),corner('2','b','B','55'),corner('3','none','C','55')]
        frames={'1':{'a':frame('a'),'b':frame('b',x=105,y=20)},
                '2':{'a':frame('a'),'b':frame('b',x=105,y=20)},'3':{}}
        return corners,frames

    def test_one_pooled_fit_and_shared_ids_across_teams_and_competitions(self):
        corners,frames=self.shared_input()
        with patch.object(profiles,'build_setups',wraps=profiles.build_setups) as fit:
            rows,report,members,*_=profiles.build_profiles(corners,frames)
        fit.assert_called_once_with(corners,frames)
        self.assertEqual(report['clusters_found'],2)
        ids={(r['match_id'],r['corner_event_id']):r['cluster_id'] for r in members}
        self.assertEqual(ids[('1','a')],ids[('2','a')])
        self.assertEqual(ids[('1','b')],ids[('2','b')])
        self.assertNotEqual(ids[('1','a')],ids[('1','b')])

    def test_shares_use_eligible_denominator_and_include_zero_memberships(self):
        corners,frames=self.shared_input()
        # Team A: one cluster occurs twice, the other once, plus one excluded.
        corners.insert(0,corner('1','extra','A'));frames['1']['extra']=frame('extra')
        _,report,_,teams,coverage,_,observed=profiles.build_profiles(corners,frames)
        a=[r for r in teams if r['team_id']=='A']
        self.assertEqual(sorted(r['cluster_count'] for r in a),[1,2])
        self.assertAlmostEqual(sum(r['cluster_share'] for r in a),1)
        self.assertEqual(sorted(r['cluster_share'] for r in a),[1/3,2/3])
        self.assertTrue(all(r['eligible_team_corners']==3 for r in a))
        ca=next(r for r in coverage if r['team_id']=='A')
        self.assertEqual((ca['all_corners'],ca['eligible_frames'],ca['excluded_corners']),(4,3,1))
        self.assertEqual(ca['usable_fraction'],3/4)
        # Team D has eligible corners but none in the second global cluster.
        corners.append(corner('1','d','D'));frames['1']['d']=frame('d')
        team_rows=profiles.build_profiles(corners,frames)[3]
        d=[r for r in team_rows if r['team_id']=='D']
        self.assertEqual(sorted(r['cluster_share'] for r in d),[0,1])

    def test_zero_eligible_team_kept_with_undefined_shares(self):
        corners,frames=self.shared_input()
        _,_,_,teams,coverage,_,_=profiles.build_profiles(corners,frames)
        c=[r for r in teams if r['team_id']=='C']
        self.assertEqual(len(c),2)
        self.assertTrue(all(r['cluster_count']==0 and r['cluster_share'] is None for r in c))
        row=next(r for r in coverage if r['team_id']=='C')
        self.assertEqual(row['eligible_frames'],0)
        self.assertEqual(row['usable_fraction'],0)
        self.assertTrue(row['team_small_sample'] and row['team_exploratory'])

    def test_every_team_zero_eligible_has_no_invented_cluster(self):
        _,report,_,teams,coverage,centers,observed=profiles.build_profiles([corner()],{'1':{}})
        self.assertEqual(report['clusters_found'],0)
        self.assertEqual(centers,[])
        self.assertEqual(teams[0]['cluster_id'],None)
        self.assertIsNone(teams[0]['cluster_share'])
        self.assertEqual(observed['eligible_frames'],0)

    def test_counts_reconcile_and_excluded_corner_has_no_membership(self):
        corners,frames=self.shared_input()
        setups,report,members,teams,coverage,centers,observed=profiles.build_profiles(corners,frames)
        self.assertEqual(observed,dict(corners=6,matching_frames=4,eligible_frames=4,excluded_corners=2))
        self.assertEqual(sum(r['cluster_count'] for r in teams),4)
        self.assertEqual(sum(r['size'] for r in centers),4)
        self.assertEqual(sum(r['all_corners'] for r in coverage),6)
        self.assertEqual(len(setups),6)
        self.assertTrue(all(r['cluster_id'] is None for r in members if not r['setup_eligible']))

    def test_matched_but_ineligible_remains_in_coverage(self):
        corners=[corner('1','good'),corner('1','bad')]
        bad=frame('bad');bad['visible_area']=[0,0,5,0,5,5,0,5]
        _,_,members,teams,coverage,_,observed=profiles.build_profiles(corners,{'1':{'good':frame('good'),'bad':bad}})
        self.assertEqual((observed['matching_frames'],observed['eligible_frames']),(2,1))
        self.assertEqual(coverage[0]['exclusion_counts'],{'low_visibility':1})
        self.assertEqual(coverage[0]['excluded_matched_frames'],1)
        self.assertEqual(sum(r['cluster_share'] for r in teams),1)

    def test_unavailable_corrupt_file_is_not_unmatched(self):
        records=[dict(match_id='1',file_status='invalid_file')]
        _,_,members,_,coverage,_,_=profiles.build_profiles([corner()],{'1':None},records)
        self.assertIsNone(members[0]['frame_matched'])
        self.assertEqual(coverage[0]['unavailable_file_corners'],1)
        self.assertEqual(coverage[0]['unmatched_loaded_corners'],0)
        self.assertEqual(coverage[0]['exclusion_counts'],{'invalid_file':1})

    def test_same_country_id_in_two_competitions_not_merged(self):
        corners=[corner('1','e','A'),corner('2','e','A','55')]
        result=profiles.build_profiles(corners,{'1':{'e':frame()},'2':{'e':frame()}})
        self.assertEqual(len(result[4]),2)
        self.assertTrue(all(r['all_corners']==1 for r in result[4]))

    def test_input_order_does_not_change_profiles_or_membership(self):
        corners,frames=self.shared_input()
        a=profiles.build_profiles(corners,frames)
        b=profiles.build_profiles(list(reversed(corners)),frames)
        self.assertEqual(a[1],b[1]); self.assertEqual(a[3],b[3])
        self.assertEqual({profiles.key(r):r['cluster_id'] for r in a[2]},
                         {profiles.key(r):r['cluster_id'] for r in b[2]})

    def test_fractional_center_record_retains_exact_sums_and_denominators(self):
        corners=[corner('1',f'e{i}') for i in range(5)]
        frames={'1':{f'e{i}':frame(f'e{i}',players=5+i) for i in range(5)}}
        centers=profiles.build_profiles(corners,frames)[5]
        self.assertTrue(any('/' in value for c in centers for value in c['exact_rational_mean']))
        for center in centers:
            for mean,total in zip(center['mean_vector'],center['vector_sum']):
                self.assertEqual(mean,total/center['denominator'])

    def test_duplicate_keys_and_inconsistent_metadata_rejected(self):
        with self.assertRaises(ValueError):profiles.build_profiles([corner(),corner()],{})
        a=corner('1','a');b=corner('1','b');b['team']='different label'
        with self.assertRaisesRegex(ValueError,'Inconsistent team metadata'):
            profiles.build_profiles([a,b],{'1':{}})

    def test_all_products_are_explicitly_retrospective(self):
        corners,frames=self.shared_input()
        result=profiles.build_profiles(corners,frames)
        for collection in (result[2],result[3],result[4]):
            self.assertTrue(all(r['profile_scope']==profiles.SCOPE for r in collection))


class WorkflowTests(unittest.TestCase):
    def test_existing_output_refused_before_input_access(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):profiles.run('unused','unused','unused',temp)

    def test_local_workflow_and_hash_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'corners.csv'
            c=corner()
            with source.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(c));writer.writeheader();writer.writerow(c)
            raw=root/'1.json';raw.write_text(json.dumps([frame()]))
            record=dict(match_id=1,competition_id=43,competition_name='World Cup',season_id=106,season='2022',
                        corner_count=1,corners_with_360=1,frames_sha256=profiles.sha(raw))
            coverage=root/'coverage.json';coverage.write_text(json.dumps(dict(matches=[record],totals=dict(corners=1,corners_with_360=1),source_revision='synthetic')))
            with contextlib.redirect_stdout(io.StringIO()):
                manifest=profiles.run(source,coverage,root,root/'result')
            self.assertFalse(manifest['prematch_safe'])
            self.assertEqual(manifest['pooled_fit_calls'],1)
            self.assertTrue(manifest['reconciliation']['agrees'])
            self.assertEqual(manifest['settings'],profiles.DEFAULTS)
            self.assertEqual(manifest['match_files'][0]['sha256'],profiles.sha(raw))
            for name,expected in manifest['output_sha256'].items():
                self.assertEqual(profiles.sha(root/'result'/name),expected)


if __name__=='__main__':unittest.main()
