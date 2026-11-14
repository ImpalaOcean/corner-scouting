"""Retrospective shared tournament setup profiles; reuse the existing pipeline.

Run from the repository root: python -m src.profile_tournament_setups --help
Never downloads data, fits per-team clusters, or provides a prematch profile.
"""
import argparse
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import inspect
import json
from math import isclose
from pathlib import Path
import subprocess

from src.profile_tournament_360 import load_match, sha
from src.setups.cluster import kmeans, stability
from src.setups.loader import read_corner_table
from src.setups.pipeline import DEFAULTS, ROW_FIELDS, build_setups
from src.analysis.publication import new_output_directory

SCOPE = 'retrospective_full_tournaments_not_prematch'
IDENTITY = ('competition_id', 'competition_name', 'season_id', 'season', 'team_id', 'team')
FEATURES = [f'{side}_z{z}' for side in ('att', 'def') for z in range(1, 10)]


def key(row):
    return str(row['match_id']), row['corner_event_id']


def load_inputs(corners, coverage, manifest_dir, frames_dir):
    records = {}
    for record in coverage['matches']:
        mid = str(record['match_id'])
        if mid in records:
            raise ValueError('Duplicate coverage match')
        records[mid] = record
    wanted = defaultdict(set)
    for corner in corners:
        mid, eid = key(corner)
        if mid not in records:
            raise ValueError(f'Match {mid} missing from coverage manifest')
        for field in ('competition_id', 'competition_name', 'season_id', 'season'):
            if str(corner[field]) != str(records[mid][field]):
                raise ValueError(f'Coverage metadata mismatch: {mid}, {field}')
        wanted[mid].add(eid)
    frames_by_match, files = {}, []
    for mid, record in sorted(records.items()):
        frames, info = load_match(record, manifest_dir, frames_dir)
        # Retain only corner frames; don't hold every match event in memory.
        frames_by_match[mid] = None if frames is None else {
            eid: frame for eid, frame in frames.items() if eid in wanted[mid]}
        files.append(info)
    return frames_by_match, files


def build_profiles(corners, frames_by_match, file_records=None):
    if len({key(c) for c in corners}) != len(corners):
        raise ValueError('Duplicate corner keys')
    for corner in corners:
        if any(corner.get(f) in (None, '') for f in IDENTITY):
            raise ValueError('Missing competition/season/team identity')
    # Exactly one pooled call: both competitions and every team share this fit.
    setups, report = build_setups(corners, frames_by_match)
    by_setup = {key(r): r for r in setups}
    files = {str(r['match_id']): r for r in (file_records or [])}
    members, grouped = [], defaultdict(list)
    identities = {}
    for corner in corners:
        mid, eid = key(corner)
        setup = by_setup[(mid, eid)]
        team_key = tuple(str(corner[f]) for f in ('competition_id', 'season_id', 'team_id'))
        identity = {f: corner[f] for f in IDENTITY}
        if team_key in identities and identity != identities[team_key]:
            raise ValueError('Inconsistent team metadata')
        identities[team_key] = identity
        frames = frames_by_match.get(mid)
        file_status = files.get(mid, {}).get('file_status', 'loaded' if frames is not None else 'missing_file')
        loaded = frames is not None
        matched = eid in frames if loaded else None
        eligible = setup['status'] == 'ok'
        if eligible and not matched:
            raise ValueError('Eligible setup lacks a matched frame')
        reason = '' if eligible else setup['exclusion_reason'] if loaded else file_status
        row = dict(identity, match_id=mid, corner_event_id=eid, profile_scope=SCOPE,
                   file_status=file_status, file_loaded=loaded, frame_matched=matched,
                   setup_eligible=eligible, setup_status=setup['status'],
                   setup_exclusion_reason=setup['exclusion_reason'], coverage_exclusion_reason=reason,
                   cluster_id=setup['cluster_id'] if eligible else None)
        members.append(row)
        grouped[team_key].append(row)

    cluster_ids = [c['cluster_id'] for c in report['clusters']]
    profiles, coverage_rows = [], []
    for team_key, group in sorted(grouped.items()):
        identity = identities[team_key]
        eligible = sum(r['setup_eligible'] for r in group)
        matched = sum(r['frame_matched'] is True for r in group)
        loaded = sum(r['file_loaded'] for r in group)
        exclusions = dict(sorted(Counter(r['coverage_exclusion_reason'] for r in group if not r['setup_eligible']).items()))
        setup_exclusions = dict(sorted(Counter(r['setup_exclusion_reason'] for r in group if not r['setup_eligible']).items()))
        small = eligible < DEFAULTS['min_corners_confident']
        caveats = list(report['caveats'])
        if small:
            caveats.append(f"team has {eligible} eligible corners (< {DEFAULTS['min_corners_confident']}); descriptive small sample, not a team eligibility filter")
        if not eligible:
            caveats.append('no eligible corners; all cluster shares undefined')
        base = dict(identity, profile_scope=SCOPE, all_corners=len(group),
                    matches=len({r['match_id'] for r in group}), loaded_file_corners=loaded,
                    matched_frames=matched, eligible_frames=eligible, excluded_corners=len(group)-eligible,
                    unmatched_loaded_corners=loaded-matched, unavailable_file_corners=len(group)-loaded,
                    excluded_matched_frames=matched-eligible, exclusion_counts=exclusions,
                    setup_exclusion_counts=setup_exclusions, usable_fraction=eligible/len(group),
                    matching_fraction=matched/len(group), team_small_sample=small,
                    pooled_exploratory=report['exploratory'], team_exploratory=report['exploratory'] or small,
                    caveats=caveats)
        coverage_rows.append(base)
        counts = Counter(r['cluster_id'] for r in group if r['setup_eligible'])
        for cluster_id in cluster_ids or [None]:
            count = counts[cluster_id] if cluster_id is not None else 0
            profiles.append(dict(identity, profile_scope=SCOPE, cluster_id=cluster_id,
                                 cluster_count=count, eligible_team_corners=eligible,
                                 cluster_share=count/eligible if eligible else None,
                                 small_team_cluster=count < DEFAULTS['min_cluster_size'],
                                 team_small_sample=small, pooled_exploratory=report['exploratory'],
                                 team_exploratory=report['exploratory'] or small, caveats=caveats))
        shares = [r['cluster_share'] for r in profiles if tuple(str(r[f]) for f in ('competition_id','season_id','team_id')) == team_key]
        if eligible and not isclose(sum(shares), 1, abs_tol=1e-12):
            raise ValueError('Team cluster shares do not sum to one')

    centers = []
    for native in report['clusters']:
        selected = [r for r in setups if r['status'] == 'ok' and r['cluster_id'] == native['cluster_id']]
        n = len(selected)
        if n != native['size'] or not n:
            raise ValueError('Cluster membership count mismatch')
        sums = [sum(int(r[f]) for r in selected) for f in FEATURES]
        mean = [v/n for v in sums]
        native_mean = [native['mean_attackers_by_zone'][z] for z in range(1,10)] + [native['mean_defenders_by_zone'][z] for z in range(1,10)]
        if [round(v,3) for v in mean] != native_mean:
            raise ValueError('Membership-derived means disagree with pooled pipeline centers')
        centers.append(dict(cluster_id=native['cluster_id'], size=n, feature_fields=FEATURES,
                            vector_sum=sums, denominator=n, mean_vector=mean,
                            exact_rational_mean=[str(Fraction(v,n)) for v in sums]))
    observed = dict(corners=len(corners), matching_frames=sum(r['frame_matched'] is True for r in members),
                    eligible_frames=sum(r['setup_eligible'] for r in members),
                    excluded_corners=sum(not r['setup_eligible'] for r in members))
    if (sum(c['cluster_count'] for c in profiles) != observed['eligible_frames']
            or sum(c['all_corners'] for c in coverage_rows) != observed['corners']
            or observed['eligible_frames'] != report['corners_usable']):
        raise ValueError('Pooled/team count reconciliation failed')
    return setups, report, members, profiles, coverage_rows, centers, observed


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with Path(path).open('x',encoding='utf-8-sig',newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def run(corners_path, coverage_path, frames_dir, destination, coverage_profile=None):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('Refusing existing destination')
    corners_path, coverage_path, frames_dir = [Path(p).resolve() for p in (corners_path,coverage_path,frames_dir)]
    coverage = json.loads(coverage_path.read_text(encoding='utf-8-sig'))
    corners = read_corner_table(corners_path)
    if not corners or {(float(r['window_seconds']),float(r['short_limit'])) for r in corners} != {(15.,15.)}:
        raise ValueError('Expected nonempty primary 15-second / short-limit 15 input')
    inputs = {str(p):sha(p) for p in (corners_path, coverage_path)}
    frames, files = load_inputs(corners, coverage, coverage_path.parent, frames_dir)
    setups, report, members, profiles, team_coverage, centers, observed = build_profiles(corners, frames, files)
    discrepancies = []
    for record in coverage['matches']:
        group = [r for r in members if r['match_id'] == str(record['match_id'])]
        actual = (len(group),sum(r['frame_matched'] is True for r in group))
        expected = (record['corner_count'], record['corners_with_360'])
        if actual != expected:
            discrepancies.append(dict(match_id=record['match_id'], observed=actual, recorded=expected))
    expected = dict(corners=coverage['totals']['corners'],matching_frames=coverage['totals']['corners_with_360'])
    reference = None
    if coverage_profile is not None:
        profile_path = Path(coverage_profile).resolve()
        inputs[str(profile_path)] = sha(profile_path)
        previous = json.loads(profile_path.read_text(encoding='utf-8-sig'))
        if previous['input_sha256'] != dict(corners=inputs[str(corners_path)],coverage_manifest=inputs[str(coverage_path)]):
            raise ValueError('Coverage reference uses different inputs')
        expected['eligible_frames'] = previous['reconciliation']['observed']['usable']
        prior = profile_path.parent/'per_corner.csv'
        if sha(prior) != previous['output_sha256']['per_corner.csv']:
            raise ValueError('Reference per-corner coverage hash mismatch')
        inputs[str(prior)] = sha(prior)
        with prior.open(encoding='utf-8-sig',newline='') as stream:
            historical = {key(r):r for r in csv.DictReader(stream)}
        if set(historical) != {key(r) for r in members}:
            raise ValueError('Reference coverage population differs')
        changes = []
        for r in members:
            for field in ('frame_matched','setup_eligible'):
                actual = '' if r[field] is None else str(r[field])
                if historical[key(r)][field] != actual:
                    changes.append(dict(match_id=r['match_id'],corner_event_id=r['corner_event_id'],field=field,previous=historical[key(r)][field],current=actual))
        discrepancies.extend(changes)
        reference = dict(path=str(profile_path),sha256=inputs[str(profile_path)],per_corner_changes=changes)
    agrees = all(observed[k] == v for k,v in expected.items()) and not discrepancies
    repository = Path(__file__).resolve().parents[1]
    code_paths = [Path(__file__), repository/'src/profile_tournament_360.py',repository/'src/data/validation.py',repository/'src/data/source.py',repository/'src/analysis/publication.py',*sorted((repository/'src/setups').glob('*.py')),repository/'tests/test_tournament_setup_profiles.py']
    provenance = dict(schema='tournament_shared_setup_profiles_v1',profile_scope=SCOPE,prematch_safe=False,
                      prematch_rule='Exclude data on/after cutoff BEFORE pooled fit and all feature/cluster fitting. Full-tournament centers and shares must never be used in a prematch dossier.',
                      input_sha256=inputs,inputs=dict(corners=str(corners_path),coverage_manifest=str(coverage_path),frames_dir=str(frames_dir)),
                      code_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip(),
                      git_status=subprocess.check_output(['git','status','--short'],cwd=repository,text=True),
                      code_sha256={p.relative_to(repository).as_posix():sha(p) for p in code_paths},
                      source_revision=coverage['source_revision'],settings=dict(DEFAULTS),
                      stability_settings={n:inspect.signature(stability).parameters[n].default for n in ('runs','fraction','seed')},
                      kmeans_max_iter=inspect.signature(kmeans).parameters['max_iter'].default,
                      pooled_fit_calls=1,stability_note='The existing pipeline additionally refits pooled 80% subsamples for stability; never per-team fitting.',
                      centers_note='Unrounded empirical means of final 18-dimensional memberships, with exact rational values; checked against native report centers at its three-decimal precision.',
                      match_files=files,reference_coverage=reference,
                      reconciliation=dict(observed=observed,expected=expected,agrees=agrees,discrepancies=discrepancies),
                      teams=len(team_coverage),teams_with_eligible=sum(r['eligible_frames']>0 for r in team_coverage),
                      teams_without_eligible=sum(r['eligible_frames']==0 for r in team_coverage),
                      team_small_sample_threshold_note='The existing pooled min_corners_confident threshold (100) is also shown conservatively per team; this is a reporting flag, never a new eligibility filter.')
    for path,expected_sha in inputs.items():
        if sha(path) != expected_sha:
            raise ValueError('Input changed during setup profiling')
    for record in files:
        if record['sha256'] and sha(record['path']) != record['sha256']:
            raise ValueError('Cached 360 file changed during setup profiling')
    with new_output_directory(destination) as stage:
        write_csv(stage/'setup_summary.csv',setups,ROW_FIELDS)
        (stage/'setup_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        write_csv(stage/'cluster_membership.csv',members)
        write_csv(stage/'team_cluster_profiles.csv',profiles)
        write_csv(stage/'team_coverage.csv',team_coverage)
        write_csv(stage/'match_files.csv',files)
        (stage/'pooled_cluster_centers.json').write_text(json.dumps(centers,indent=2)+'\n',encoding='utf-8')
        (stage/'RETROSPECTIVE_ONLY.md').write_text('Full-tournament retrospective profiles only. Do not use in a prematch dossier. Refit pooled clusters using exclusively data strictly before the dossier cutoff; future frames must not influence any fitting.\n',encoding='utf-8')
        provenance['output_sha256']={p.name:sha(p) for p in stage.iterdir() if p.is_file()}
        (stage/'run_manifest.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(reconciliation=provenance['reconciliation'],clusters=report['clusters'],stability_ari=report['stability_ari'],exploratory=report['exploratory'],caveats=report['caveats'],teams=provenance['teams'],teams_without_eligible=provenance['teams_without_eligible']),indent=2))
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corners',type=Path,required=True)
    parser.add_argument('--coverage-manifest',type=Path,required=True)
    parser.add_argument('--frames-dir',type=Path,required=True)
    parser.add_argument('--coverage-profile',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    try:
        run(args.corners,args.coverage_manifest,args.frames_dir,args.output,args.coverage_profile)
    except (OSError,ValueError,KeyError) as exc:
        parser.exit(1,f'Shared setup profiling failed: {exc}\n')


if __name__ == '__main__':
    main()
