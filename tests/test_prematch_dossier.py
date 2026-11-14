"""Synthetic cutoff/leakage checks; no target fixture outcomes are opened."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.dossier import prematch as d
from test_evaluation import make_league,corner,PAIRS,TEAMS,write_rows


def league():
    rows=make_league('same')
    for r in rows:
        pair=PAIRS[(r['match_id']-5000)%len(PAIRS)]
        r.update(home_team=TEAMS[pair[0]],away_team=TEAMS[pair[1]])
    return rows


def fixture(rows,mid=5059):
    row=next(r for r in rows if r['match_id']==mid)
    a,b=PAIRS[(mid-5000)%len(PAIRS)]
    return dict(match_id=mid,match_date=row['match_date'],competition_id=900,
                competition_name='Invented League',season_id=1,season='Invented Season',
                teams=[dict(team_id=a,team=TEAMS[a],role='home'),dict(team_id=b,team=TEAMS[b],role='away')])


class CutoffTests(unittest.TestCase):
    def setUp(self):
        self.rows=league();self.fixture=fixture(self.rows)

    def test_target_and_future_outcomes_do_not_change_any_analytical_quantity(self):
        reference,_=d.build_dossier(self.rows,self.fixture,bootstrap_draws=0)
        changed=[dict(r,delivery_category='invalid future category',shot_count='not a number',
                      led_to_shot=not r['led_to_shot'],provider_xg_sum=float('nan'),window_seconds=999)
                 if r['match_date']>=self.fixture['match_date'] else r for r in self.rows]
        # Appending future teams and many future corners must not change pooling/eligibility.
        changed += [corner(9000+i,0,77,'unknown',True,'2027-01-01') for i in range(40)]
        actual,_=d.build_dossier(changed,self.fixture,bootstrap_draws=0)
        self.assertEqual(reference,actual)
        self.assertEqual(d.render(dict(reference,setup_coverage=d.setup_coverage({},[]))),
                         d.render(dict(actual,setup_coverage=d.setup_coverage({},[]))))

    def test_entire_target_date_excluded_not_only_target_match(self):
        rows=self.rows+[dict(self.rows[0],match_id=99999,corner_event_id='same-date',match_date=self.fixture['match_date'])]
        result,history=d.build_dossier(rows,self.fixture,bootstrap_draws=0)
        self.assertNotIn(99999,result['included_match_ids'])
        self.assertNotIn(self.fixture['match_id'],result['included_match_ids'])
        self.assertTrue(all(r['match_date']<self.fixture['match_date'] for r in history))

    def test_target_id_excluded_even_if_its_row_date_is_wrong(self):
        changed=[dict(r,match_date='2025-01-01') if r['match_id']==self.fixture['match_id'] else r for r in self.rows]
        result,_=d.build_dossier(changed,self.fixture,bootstrap_draws=0)
        self.assertNotIn(self.fixture['match_id'],result['included_match_ids'])

    def test_fitting_selection_and_eligibility_only_see_past_data(self):
        with patch.object(d,'fit_history',wraps=d.fit_history) as fit, \
             patch.object(d,'select_parameter',wraps=d.select_parameter) as select, \
             patch.object(d,'eligible_teams',wraps=d.eligible_teams) as eligible:
            result,_=d.build_dossier(self.rows,self.fixture,bootstrap_draws=0)
        for call in fit.call_args_list:
            self.assertTrue(all(r['match_date']<self.fixture['match_date'] for r in call.args[0]))
        self.assertEqual(len(fit.call_args_list),2)
        for call in select.call_args_list:
            self.assertTrue(all(r['match_date']<self.fixture['match_date'] for r in call.args[1]))
            self.assertEqual(call.args[3],d.ALPHA_GRID)
        training=eligible.call_args.args[0]
        roles={r['match_id']:r['split'] for r in result['history_roles']}
        self.assertTrue(all(roles[r['match_id']]=='train' for r in training))
        self.assertFalse(result['full_season_evaluation_parameters_used'])

    def test_future_history_cannot_promote_sparse_team(self):
        early=fixture(self.rows,5004)
        result,_=d.build_dossier(self.rows,early,bootstrap_draws=0)
        self.assertTrue(all(not r['prediction_eligible'] for r in result['teams']))
        self.assertTrue(all(r['exclusion_reasons'] for r in result['teams']))
        self.assertTrue(all(m['shot_probability'] is None for r in result['teams'] for m in r['estimates']))

    def test_final_fit_uses_all_past_only_not_just_selection_prefix(self):
        with patch.object(d,'fit_history',wraps=d.fit_history) as fit:
            result,history=d.build_dossier(self.rows,self.fixture,bootstrap_draws=0)
        self.assertEqual(fit.call_args_list[-1].args[0],history)
        self.assertGreater(len(history),len(fit.call_args_list[0].args[0]))
        self.assertTrue(any(r['selection_role']=='refit_only' for r in result['history_roles']))

    def test_unknown_validation_does_not_reuse_alpha_or_disable_shots(self):
        before,_=d.build_dossier(self.rows,self.fixture,bootstrap_draws=0)
        val={r['match_id'] for r in before['history_roles'] if r['split']=='validation'}
        changed=[dict(r,delivery_category='unknown') if r['match_id'] in val else r for r in self.rows]
        result,_=d.build_dossier(changed,self.fixture,bootstrap_draws=0)
        self.assertIsNone(result['alpha'])
        self.assertIsNotNone(result['beta'])
        self.assertTrue(all(m['delivery_probabilities'] is None and m['shot_probability'] is not None
                            for r in result['teams'] for m in r['estimates']))

    def test_probability_denominators_and_unknown_observations(self):
        changed=[dict(r,delivery_category='unknown') if i%10==0 else r for i,r in enumerate(self.rows)]
        result,_=d.build_dossier(changed,self.fixture,bootstrap_draws=0)
        for team in result['teams']:
            observed=team['observed']
            self.assertEqual(sum(observed['n_'+c] for c in d.DELIVERY_CATEGORIES),team['history_corners'])
            for model in team['estimates']:
                self.assertAlmostEqual(sum(model['delivery_probabilities'].values()),1)
                self.assertTrue(0<=model['shot_probability']<=1)

    def test_coverage_future_frames_cannot_change_setup_section(self):
        result,history=d.build_dossier(self.rows,self.fixture,bootstrap_draws=0)
        past=[dict(match_id=mid,frames_status='not_requested') for mid in result['included_match_ids']]
        a=d.setup_coverage(dict(matches=past),history)
        b=d.setup_coverage(dict(matches=past+[dict(match_id=self.fixture['match_id'],frames_status='ok'),dict(match_id=999999,frames_status='ok')]),history)
        self.assertEqual(a,b)
        self.assertEqual(a['status'],'unavailable')
        self.assertIsNone(a['usable_fraction'])
        self.assertFalse(a['retrospective_centers_used'])


class InputAndWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.rows=league();self.fixture=fixture(self.rows)

    def test_filter_before_typing_ignores_invalid_future_answers_and_duplicate_ids(self):
        source=self.root/'source.csv'
        mutated=[dict(r,shot_count='bad',delivery_category='future invalid',window_seconds='bad')
                 if r['match_date']>=self.fixture['match_date'] else r for r in self.rows]
        mutated += [mutated[-1]]
        write_rows(source,mutated)
        actual=d.read_history(source,self.fixture)
        self.assertEqual(len(actual),sum(r['match_date']<self.fixture['match_date'] for r in self.rows))

    def test_fixture_selection_uses_only_metadata_and_history_coverage(self):
        original=d.select_fixture(self.rows,900,1)
        changed=[dict(r,delivery_category='arbitrary',shot_count='bad',goal_count=999999,
                      led_to_shot=True,provider_xg_sum='bad') for r in self.rows]
        self.assertEqual(original,d.select_fixture(changed,900,1))
        self.assertTrue(all(t['selection_training_matches']>=10 and t['selection_training_corners']>=30
                            for t in original['teams']))
        self.assertTrue(all(t['selection_validation_corners']>=1 for t in original['teams']))

    def test_full_workflow_selection_is_saved_before_dossier_and_hashes_verified(self):
        source=self.root/'source.csv'
        rows=[dict(r,competition_id=2,competition_name='Premier League',season_id=27,season='2015/2016') for r in self.rows]
        write_rows(source,rows)
        coverage=self.root/'coverage.json'
        coverage.write_text(json.dumps(dict(matches=[dict(match_id=mid,frames_status='not_requested') for mid in {r['match_id'] for r in rows}])))
        plan=self.root/'selection.json';output=self.root/'dossier'
        selected=d.select(source,coverage,plan,output)
        self.assertTrue(plan.exists());self.assertFalse(output.exists())
        result=d.run(plan)
        self.assertEqual(result['cutoff'],selected['cutoff'])
        provenance=json.loads((output/'provenance.json').read_text())
        self.assertEqual(provenance['selection_plan_sha256'],d.sha(plan))
        self.assertNotIn(selected['fixture']['match_id'],provenance['included_match_ids'])
        for name,digest in provenance['output_sha256'].items():self.assertEqual(d.sha(output/name),digest)
        with self.assertRaises(FileExistsError):d.run(plan)

    def test_changed_input_after_selection_refused(self):
        source=self.root/'source.csv';rows=[dict(r,competition_id=2,season_id=27) for r in self.rows]
        write_rows(source,rows)
        coverage=self.root/'coverage.json';coverage.write_text('{"matches": []}')
        plan=self.root/'selection.json';output=self.root/'dossier'
        d.select(source,coverage,plan,output)
        source.write_bytes(source.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'Frozen source hash mismatch'):d.run(plan)
        self.assertFalse(output.exists())

    def test_all_readable_dossier_artifacts_are_past_only(self):
        source=self.root/'source.csv';write_rows(source,self.rows)
        history=d.read_history(source,self.fixture)
        result,_=d.build_dossier(history,self.fixture,bootstrap_draws=0)
        self.assertTrue(all(mid<self.fixture['match_id'] for mid in result['included_match_ids']))
        self.assertEqual(sum(t['history_corners'] for t in result['teams']),
                         sum(r['team_id'] in {t['team_id'] for t in self.fixture['teams']} for r in history))


if __name__=='__main__':unittest.main()
