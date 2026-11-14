"""Past-only prematch dossier construction; never imports season-fit estimates."""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from src.analysis.evaluation import (
    ALPHA_GRID, METHODS, SCORED_CATEGORIES, delivery_probabilities, eligible_teams,
    fit_history, select_parameter, shot_probability,
)
from src.analysis.summary import (
    DELIVERY_CATEGORIES, MIN_MATCHES, MIN_CORNERS, chronological_splits,
    load_corners, team_summaries, check_corners,
)
from src.analysis.publication import new_output_directory

METADATA = ['match_id','match_date','competition_id','competition_name','season_id','season',
            'home_team','away_team','team_id','team']
RULE = ('Earliest Premier League 2015/2016 fixture by ISO date then numeric match ID '
        'whose two teams each have >=10 observed matches and >=30 corners in the '
        'earliest 60% of strictly earlier competition-season matches, plus >=1 '
        'validation corner each. Selection reads dates, identities and corner '
        'coverage only; no delivery labels or match outcomes.')
POLICY = dict(window_seconds=15,short_limit=15,bootstrap_draws=1000,seed=5118,
              selection_fractions=[0.6,0.2,0.2],selection_grid=ALPHA_GRID,
              eligibility=dict(training_matches_at_least=MIN_MATCHES,training_corners_at_least=MIN_CORNERS),
              fitting='Select on first-60%-train/next-20%-validation within past-only history. '
                      'Do not score the remaining past 20%; after selection refit on ALL strictly past matches.',
              full_season_parameters_reused=False,exclude_entire_cutoff_date=True,
              cutoff_safe_360_fit=False)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def iso(value):
    if not value:
        return None
    value=str(value)
    if date.fromisoformat(value).isoformat()!=value:
        raise ValueError('Dates must use YYYY-MM-DD')
    return value


def in_history(row,fixture):
    # Exclude target and future rows before outcome typing, validation or aggregation.
    if str(row['match_id'])==str(fixture['match_id']):
        return False
    day=iso(row.get('match_date'))
    return bool(day and day < fixture['match_date']
                and str(row['competition_id'])==str(fixture['competition_id'])
                and str(row['season_id'])==str(fixture['season_id']))


def select_fixture(metadata,competition_id=2,season_id=27):
    """Use projected metadata only, never delivery/outcome values."""
    scoped=[{k:r.get(k) for k in METADATA} for r in metadata
            if str(r['competition_id'])==str(competition_id) and str(r['season_id'])==str(season_id)]
    fixtures={}
    for row in scoped:
        day=iso(row['match_date'])
        if not day:
            continue
        info={k:row[k] for k in METADATA[:8]}
        if not all(info.get(k) for k in METADATA[:8]):
            raise ValueError('Fixture identity metadata is incomplete')
        if fixtures.setdefault(str(row['match_id']),info)!=info:
            raise ValueError('Inconsistent fixture metadata')
    for candidate in sorted(fixtures.values(),key=lambda r:(r['match_date'],int(r['match_id']))):
        history=[r for r in scoped if in_history(r,candidate)]
        matches=sorted({(r['match_date'],int(r['match_id'])) for r in history})
        if len(matches)<5:
            continue
        train_ids={str(mid) for _,mid in matches[:int(len(matches)*.6)]}
        val_ids={str(mid) for _,mid in matches[int(len(matches)*.6):int(len(matches)*.8)]}
        names=defaultdict(set)
        for r in history:
            names[r['team']].add(str(r['team_id']))
        teams=[]
        for role in ('home_team','away_team'):
            ids=names.get(candidate[role],set())
            if len(ids)!=1:
                break
            tid=next(iter(ids))
            training=[r for r in history if str(r['match_id']) in train_ids and str(r['team_id'])==tid]
            validation=[r for r in history if str(r['match_id']) in val_ids and str(r['team_id'])==tid]
            observed_matches=len({r['match_id'] for r in training})
            if observed_matches<MIN_MATCHES or len(training)<MIN_CORNERS or not validation:
                break
            teams.append(dict(team_id=int(tid),team=candidate[role],role=role.removesuffix('_team'),
                              selection_training_matches=observed_matches,selection_training_corners=len(training),
                              selection_validation_corners=len(validation)))
        if len(teams)==2:
            return dict(match_id=int(candidate['match_id']),match_date=candidate['match_date'],
                        competition_id=int(candidate['competition_id']),competition_name=candidate['competition_name'],
                        season_id=int(candidate['season_id']),season=candidate['season'],teams=teams,
                        selection_rule=RULE,selection_history_matches=len(matches))
    raise ValueError('No fixture satisfies the predeclared date/coverage rule')


def read_metadata(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if not set(METADATA)<=set(reader.fieldnames or []):
            raise ValueError('Corner table lacks fixture-selection metadata')
        return [{k:row[k] for k in METADATA} for row in reader]


def read_history(path,fixture):
    """Filter CSV rows before reusing the existing typed loader unchanged."""
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        fields=reader.fieldnames or []
        past=[r for r in reader if in_history(r,fixture)]
    with tempfile.TemporaryDirectory(prefix='prematch-history-') as temp:
        filtered=Path(temp)/'past.csv'
        with filtered.open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields)
            writer.writeheader();writer.writerows(past)
        return load_corners(filtered)


def build_dossier(rows,fixture,bootstrap_draws=1000,seed=5118):
    fixture=dict(fixture)
    fixture['match_date']=iso(fixture['match_date'])
    history=[r for r in rows if in_history(r,fixture)]
    check_corners(history)
    history.sort(key=lambda r:(r['match_date'],r['match_id'],r['corner_event_id']))
    if history and {(r['window_seconds'],r['short_limit']) for r in history}!={(15.,15.)}:
        raise ValueError('Past-only history must use primary 15/15 settings')
    splits=chronological_splits(history)
    split_of={s['match_id']:s['split'] for s in splits}
    train=[r for r in history if split_of[r['match_id']]=='train']
    validation=[r for r in history if split_of[r['match_id']]=='validation']
    eligible=eligible_teams(train)
    selection_fit=fit_history(train)
    alpha,alpha_table=select_parameter(selection_fit,validation,eligible,ALPHA_GRID,'alpha')
    beta,beta_table=select_parameter(selection_fit,validation,eligible,ALPHA_GRID,'beta')
    final_fit=fit_history(history)
    target_ids={t['team_id'] for t in fixture['teams']}
    observed=team_summaries([r for r in history if r['team_id'] in target_ids],
                            bootstrap_draws=bootstrap_draws,seed=seed,cutoff=fixture['match_date'])
    summary_by_id={s['team_id']:s for s in observed}
    teams=[]
    for target in fixture['teams']:
        tid=target['team_id']; key=((fixture['competition_id'],fixture['season_id']),tid)
        training=[r for r in train if r['team_id']==tid]
        training_matches=len({r['match_id'] for r in training})
        reasons=[]
        if training_matches<MIN_MATCHES:reasons.append('fewer_than_10_selection_training_corner_observed_matches')
        if len(training)<MIN_CORNERS:reasons.append('fewer_than_30_selection_training_corners')
        estimates=[]
        for method in METHODS:
            p=delivery_probabilities(final_fit,key[0],tid,method,alpha) if key in eligible and alpha is not None else None
            q=shot_probability(final_fit,key[0],tid,method,beta) if key in eligible and beta is not None else None
            estimates.append(dict(method=method,delivery_probabilities=p,shot_probability=q,
                                  delivery_status='available' if p is not None else 'unavailable',
                                  shot_status='available' if q is not None else 'unavailable',
                                  delivery_reason=None if p is not None else '; '.join(reasons) or 'no_scorable_past_validation_delivery_labels',
                                  shot_reason=None if q is not None else '; '.join(reasons) or 'no_eligible_past_validation_corners'))
        own=[r for r in history if r['team_id']==tid]
        teams.append(dict(team_id=tid,team=target['team'],role=target['role'],observed=summary_by_id.get(tid),
                          history_matches=len({r['match_id'] for r in own}),history_corners=len(own),
                          selection_training_matches=training_matches,selection_training_corners=len(training),
                          prediction_eligible=key in eligible,exclusion_reasons=reasons,estimates=estimates,
                          historical_corner_ids=[r['corner_event_id'] for r in own]))
    result=dict(scope='cutoff_safe_prematch',fixture=fixture,cutoff=fixture['match_date'],
                cutoff_rule='Strictly earlier ISO dates; target match and entire target date excluded',
                included_match_ids=sorted({r['match_id'] for r in history}),
                included_corner_keys=[[r['match_id'],r['corner_event_id']] for r in history],
                pool_matches=len({r['match_id'] for r in history}),pool_corners=len(history),
                selection_split_counts=dict(Counter(s['split'] for s in splits)),
                alpha=alpha,beta=beta,selection_grid=ALPHA_GRID,methods=METHODS,
                full_season_evaluation_parameters_used=False,
                fit_history_rule=POLICY['fitting'],bootstrap_draws=bootstrap_draws,seed=seed,
                teams=teams,selection_scores=alpha_table+beta_table,
                history_roles=[dict(s,selection_role='refit_only' if s['split']=='test' else s['split']) for s in splits])
    return result,history


def setup_coverage(coverage,history):
    included={str(r['match_id']) for r in history}
    records=[m for m in coverage.get('matches',[]) if str(m.get('match_id')) in included]
    statuses=dict(sorted(Counter(m.get('frames_status','not_recorded') for m in records).items()))
    return dict(status='unavailable',cutoff_safe_fit_available=False,retrospective_centers_used=False,
                historical_matches=len(included),coverage_records=len(records),recorded_360_statuses=statuses,
                usable_fraction=None,
                reason='No suitable verified pre-cutoff 360 input supplied for this league dossier; a cutoff-safe setup fit is not implemented here. Downloads disabled/not-requested is not a measured 0% provider-availability rate. No PR #23 centers or shares are loaded.')


def code_evidence():
    root=Path(__file__).resolve().parents[2]
    paths=[*sorted((root/'src/dossier').glob('*.py')),root/'src/analysis/summary.py',
           root/'src/analysis/evaluation.py',root/'src/analysis/publication.py',root/'tests/test_prematch_dossier.py']
    return dict(code_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                code_sha256={p.relative_to(root).as_posix():sha(p) for p in paths},
                git_status=subprocess.check_output(['git','status','--short'],cwd=root,text=True))


def select(corners_path,coverage_path,selection_path,output):
    selection_path=Path(selection_path)
    if selection_path.exists() or Path(output).exists():
        raise FileExistsError('Refusing existing selection plan or dossier destination')
    corners_path,coverage_path=Path(corners_path).resolve(),Path(coverage_path).resolve()
    fixture=select_fixture(read_metadata(corners_path))
    plan=dict(label='Fixture selected using dates/identity/corner coverage only; saved before dossier generation',
              selected_utc=datetime.now(timezone.utc).isoformat(),fixture=fixture,cutoff=fixture['match_date'],
              selection_rule=RULE,corners=str(corners_path),coverage_manifest=str(coverage_path),
              corners_sha256=sha(corners_path),coverage_manifest_sha256=sha(coverage_path),
              output=str(Path(output).resolve()),settings=POLICY,**code_evidence())
    selection_path.parent.mkdir(parents=True,exist_ok=True)
    with selection_path.open('x',encoding='utf-8') as stream:json.dump(plan,stream,indent=2)
    return plan


def pct(value):return 'Unavailable' if value is None else f'{100*value:.1f}%'
def interval(row,key):
    low,high=row.get(key+'_ci_low'),row.get(key+'_ci_high')
    return 'not estimated' if low is None else f'{100*low:.1f}–{100*high:.1f}%'


def render(result):
    f=result['fixture'];a,b=f['teams']
    lines=[f"# Prematch corner dossier: {a['team']} vs {b['team']}",'',
           f"**{f['competition_name']} {f['season']} · {f['match_date']} · fixture {f['match_id']}**",'',
           f"Cutoff: strictly before **{result['cutoff']}**. The entire target date is excluded because reliable kickoff times are not supplied. No target-match outcomes appear in this dossier.",'',
           f"Competition history used for pooled fitting: **{result['pool_matches']} matches / {result['pool_corners']} corners**. Smoothing selection uses only the earliest 60% training and next 20% validation of this past history. The remaining past 20% is not scored or used to select parameters; after selection, all strictly past history is used for final fitting.",'',
           f"Past-only validation selected alpha={result['alpha'] if result['alpha'] is not None else 'unavailable'}, beta={result['beta'] if result['beta'] is not None else 'unavailable'}. Full-season evaluation parameters were not loaded.",'']
    for team in result['teams']:
        obs=team['observed']
        lines += [f"## {team['team']} ({team['role']})",'',
                  f"Observed history: **{team['history_matches']} matches / {team['history_corners']} corners**. Selection-training history: **{team['selection_training_matches']} matches / {team['selection_training_corners']} corners**. Prediction eligibility: **{team['prediction_eligible']}** (10 training matches and 30 training corners).",'']
        if obs:
            lines += [f"History dates: {obs['first_match_date']} to {obs['last_match_date']}.",
                      f"Corners producing a shot: **{obs['corners_with_shot']}/{obs['corners']} = {pct(obs['shot_rate'])}**, 95% match-bootstrap interval {interval(obs,'shot_rate')}. Total attributed historical shots: {obs['shots']}.",'',
                      '| Observed delivery | Corners | Share of all team corners | 95% interval |',
                      '| --- | ---: | ---: | --- |']
            for category in DELIVERY_CATEGORIES:
                lines.append(f"| {category} | {obs['n_'+category]} | {pct(obs['freq_'+category])} | {interval(obs,'freq_'+category)} |")
            lines += ['',f"Unknown deliveries: **{obs['n_unknown']}**. They remain in descriptive denominators and shot modeling; delivery-model estimates below condition on the five known categories.",'']
        else:
            lines += ['No observed prior corners; frequencies and models are unavailable.','']
        lines += ['| Method | Short | Inswinging | Outswinging | Straight | Direct shot | Shot probability |',
                  '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for model in team['estimates']:
            p=model['delivery_probabilities']
            values=[pct(p[c]) if p is not None else 'Unavailable' for c in SCORED_CATEGORIES]
            lines.append('| '+' | '.join([model['method'],*values,pct(model['shot_probability'])])+' |')
        for model in team['estimates']:
            for target in ('delivery','shot'):
                if model[target+'_status']=='unavailable':
                    lines.append(f"- {model['method']} {target} unavailable: {model[target+'_reason']}.")
        lines += ['',f"Traceability: {len(team['historical_corner_ids'])} supporting corner IDs in `historical_corners.csv` (filter team_id={team['team_id']}). Example IDs: "+', '.join(f'`{x}`' for x in team['historical_corner_ids'][:3])+'.','']
    setup=result['setup_coverage']
    lines += ['## 360 setup profiles — unavailable','',setup['reason'],'',
              f"Historical coverage records: {setup['coverage_records']}/{setup['historical_matches']}; recorded statuses: `{json.dumps(setup['recorded_360_statuses'],sort_keys=True)}`. Usable fraction is undefined, not reported as zero.",'',
              '## Reading this dossier','',
              '- These are earlier-corner descriptions and model expectations, not target-match results, tactical guarantees or causal effects.',
              '- Match counts are corner-observed appearances; matches where a team took no corners are not represented in its eligibility count.',
              '- Samples and validation periods are limited. Match-bootstrap intervals describe observed history with the documented 1,000 draws/seed 5118; fitted-probability uncertainty is not quantified.',
              '- Delivery percentages can be rounded; machine-readable values preserve the full probabilities. Unknown-label exclusions may be non-random.',
              '- Provider possession/sequence rules and the 15-second attribution window limit the meaning of historical shot frequency. The independent human audit remains pending.',
              '- Cutoff safety refers to match dates in a pinned provider snapshot; publication times and later historical-data revisions are not independently established.',
              '- Full-tournament retrospective cluster centers/shares from PR #23 are prohibited here. A setup section would require a separate fit using exclusively pre-cutoff frames.',
              '', 'All included historical match IDs, source hashes, selection scores, eligibility and code hashes are in `provenance.json` and `dossier.json`. `history_roles.csv` records selection roles; `historical_corners.csv` lists every pooled historical corner.','']
    return '\n'.join(lines)


def run(selection_path):
    selection_path=Path(selection_path).resolve()
    plan=json.loads(selection_path.read_text(encoding='utf-8'))
    output=Path(plan['output'])
    if output.exists():raise FileExistsError('Refusing existing dossier destination')
    current=code_evidence()
    if current['code_sha']!=plan['code_sha'] or current['code_sha256']!=plan['code_sha256']:
        raise ValueError('Dossier code differs from frozen fixture-selection plan')
    if plan['settings']!=POLICY or plan['cutoff']!=plan['fixture']['match_date']:
        raise ValueError('Selection plan policy/cutoff differs from frozen policy')
    for field,hash_field in [('corners','corners_sha256'),('coverage_manifest','coverage_manifest_sha256')]:
        if sha(plan[field])!=plan[hash_field]:raise ValueError('Frozen source hash mismatch: '+field)
    history=read_history(plan['corners'],plan['fixture'])
    result,history=build_dossier(history,plan['fixture'],POLICY['bootstrap_draws'],POLICY['seed'])
    coverage=json.loads(Path(plan['coverage_manifest']).read_text(encoding='utf-8-sig'))
    result['setup_coverage']=setup_coverage(coverage,history)
    assert all(r['match_date']<plan['cutoff'] and r['match_id']!=plan['fixture']['match_id'] for r in history)
    with new_output_directory(output) as stage:
        (stage/'dossier.md').write_text(render(result),encoding='utf-8')
        (stage/'dossier.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        trace_fields=['match_id','corner_event_id','match_date','competition_id','season_id','team_id','team','delivery_category','shot_count','led_to_shot']
        with (stage/'historical_corners.csv').open('x',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=trace_fields);writer.writeheader()
            writer.writerows({k:r[k] for k in trace_fields} for r in history)
        with (stage/'history_roles.csv').open('x',encoding='utf-8-sig',newline='') as stream:
            fields=list(result['history_roles'][0]) if result['history_roles'] else ['match_id','match_date','selection_role']
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(result['history_roles'])
        provenance=dict(scope=result['scope'],selection_plan=str(selection_path),selection_plan_sha256=sha(selection_path),
                        fixture=result['fixture'],cutoff=result['cutoff'],included_match_ids=result['included_match_ids'],
                        included_corner_keys=result['included_corner_keys'],settings=POLICY,
                        source_input_sha256=dict(corners=plan['corners_sha256'],coverage_manifest=plan['coverage_manifest_sha256']),
                        input_scope_note='Full source-file hashes include future bytes for identity only; all analytical quantities and coverage summaries use strictly past rows. Changing future bytes changes provenance hashes, not the dossier analyses.',
                        history_fingerprint=hashlib.sha256(json.dumps(history,sort_keys=True).encode()).hexdigest(),
                        setup_coverage=result['setup_coverage'],**current,
                        output_sha256={p.name:sha(p) for p in stage.iterdir()})
        (stage/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
        for field,hash_field in [('corners','corners_sha256'),('coverage_manifest','coverage_manifest_sha256')]:
            if sha(plan[field])!=plan[hash_field]:raise ValueError('Source changed during dossier generation')
    return result
