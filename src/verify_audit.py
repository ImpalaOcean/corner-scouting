"""Run: python -B src/verify_audit.py --root . --output NEW_DIRECTORY.

Automated verification only; no manual judgments or production extractor calls.

Independent implementation of documented rules, not independent ground truth.
Uses provider labels and the same conceptual boundary priority, so shared rule
errors, provider errors, and off-target missingness can remain undetected.
"""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

LIMITATIONS = (
    "Automated verification, not manual judgments or ground truth. "
    "Independent code implements the same documented rules and trusts provider "
    "possession/timing/technique; shared conceptual errors can escape detection. "
    "Decimal timestamp arithmetic can expose floating-point boundary differences. "
    "No video/physical ball-out inference, no human agreement computed."
)
RESTARTS = {"Corner", "Free Kick", "Goal Kick", "Kick Off", "Throw-in", "Penalty"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def seconds(timestamp):
    h, m, s = timestamp.split(":")
    return Decimal(h)*3600 + Decimal(m)*60 + Decimal(s)


def evidence(event):
    kind = event["type"]["name"]
    details = event.get(kind.lower().replace(" ", "_"), {})
    return dict(id=event["id"], timestamp=event["timestamp"], period=event["period"],
                team=event.get("team"), possession=event.get("possession"),
                out=event.get("out"), out_field_present="out" in event,
                event_type=kind, location=event.get("location"),
                details={k:v for k,v in details.items() if k!="freeze_frame"})


def compute(events, starter, window, short_limit):
    kind = starter["type"]["name"]
    details = starter.get(kind.lower(), {})
    if kind not in ("Pass", "Shot") or details.get("type", {}).get("name") != "Corner":
        raise ValueError("Raw starter is not a corner")
    start, end = starter.get("location", []), details.get("end_location", [])
    usable = (len(start)>=2 and len(end)>=2
              and all(type(x) in (int,float) and math.isfinite(x) for x in start[:2]+end[:2]))
    distance = math.dist(start[:2], end[:2]) if usable else None
    technique = details.get("technique", {}).get("name")
    if kind=="Shot":
        category="direct_shot"
    elif details.get("height",{}).get("name")=="Ground Pass" and distance is not None and distance<=short_limit:
        category="short"
    else:
        category={"Inswinging":"inswinging","Outswinging":"outswinging","Straight":"straight"}.get(technique,"unknown")
    chain=[starter]; shots=[starter] if kind=="Shot" else []
    reason="end_of_data"; boundary=None; flags=[]; seen={starter["id"]}
    if starter.get("possession") is None:
        raise ValueError("Raw corner lacks possession")
    if details.get("outcome",{}).get("name")=="Goal":
        reason="goal"; boundary=starter
    elif starter.get("out"):
        reason="ball_out"; boundary=starter
    else:
        offset=next(i for i,e in enumerate(events) if e["id"]==starter["id"])
        for e in events[offset+1:]:
            if e["id"] in seen:
                flags.append("duplicate source event ID skipped: "+e["id"])
                continue
            ek=e["type"]["name"]; ed=e.get(ek.lower().replace(" ","_"),{})
            elapsed=seconds(e["timestamp"])-seconds(starter["timestamp"])
            tests=[
                ("period_end",e["period"]!=starter["period"]),
                ("time_limit",window is not None and elapsed>window),
                ("new_restart",ek in ("Pass","Shot") and ed.get("type",{}).get("name") in RESTARTS),
                ("possession_change",e.get("possession")!=starter["possession"]),
                ("stoppage",ek in ("Half End","Injury Stoppage","Offside","Referee Ball-Drop")
                 or (ek in ("Foul Committed","Foul Won") and not ed.get("advantage",False))),
            ]
            applicable=[name for name,applies in tests if applies]
            if applicable:
                reason=applicable[0]; boundary=e
                if len(applicable)>1: flags.append("overlapping boundary conditions: "+", ".join(applicable))
                break
            chain.append(e); seen.add(e["id"])
            if ek=="Shot" and e.get("team",{}).get("id")==starter["team"]["id"]: shots.append(e)
            if e.get("shot",{}).get("outcome",{}).get("name")=="Goal":
                reason="goal"; boundary=e; break
            if e.get("out"):
                reason="ball_out"; boundary=e; break
    for e in chain:
        if e.get("shot",{}).get("outcome",{}).get("name") in ("Off T","Wayward") and not e.get("out"):
            flags.append("off-target shot without explicit true out flag: "+e["id"])
    return dict(delivery_category=category, shot_count=len(shots),
                goal_count=sum(e["shot"].get("outcome",{}).get("name")=="Goal" for e in shots),
                stop_reason=reason, shot_event_ids=[e["id"] for e in shots],
                chain_event_ids=[e["id"] for e in chain], boundary_event_id=boundary["id"] if boundary else None,
                raw_distance=distance, raw_delivery=evidence(starter),
                supporting_events=[evidence(e) for e in chain]+([evidence(boundary)] if boundary and boundary["id"] not in seen else []),
                ambiguities=flags)



FIELDS = ('delivery_category', 'shot_count', 'goal_count', 'shot_event_ids', 'stop_reason', 'chain_event_ids')


def ordered(events):
    """Order one match only; callers must never mix match files."""
    return sorted(events, key=lambda e: (e['period'], seconds(e['timestamp']), e['index']))


def locate(matches, match_id, event_id):
    events = ordered(matches[str(match_id)])
    starter = next(e for e in events if e['id'] == event_id)
    return events, starter


def run(root, output, *, expected_size=100):
    import collections
    import subprocess
    import sys
    from datetime import datetime, timezone
    if output.exists():
        raise FileExistsError('Destination already exists; inspect it before changing anything: '+str(output))
    sample_path = root/'outputs/audit-combined-primary-sample/audit_sheet.csv'
    old_path = root/'outputs/audit-combined-primary-sample/automated_crosscheck.csv'
    input_records = {}
    protected = {}

    def record(path):
        key = path.relative_to(root).as_posix()
        try:
            digest = sha(path)
            input_records.setdefault(key, {}).update(status='readable', sha256=digest)
            protected[path] = digest
            return load(path) if path.suffix == '.json' else None
        except OSError as exc:
            input_records.setdefault(key, {}).update(status='unavailable', sha256=None, error=str(exc))
            return None

    record(sample_path); record(old_path)
    provenance_path = sample_path.with_name('sample_provenance.json')
    sample_provenance = record(provenance_path)
    if sample_provenance is None:
        raise ValueError('Frozen-sample provenance is unavailable')
    expected_sheet_hash = sample_provenance['artifacts']['audit_sheet.csv']['sha256']
    if sha(sample_path) != expected_sheet_hash:
        raise ValueError('Frozen sample hash differs from sample_provenance.json')
    if sample_provenance['sample']['size'] != expected_size:
        raise ValueError('Recorded sample size differs from requested validation size')
    if sample_provenance['population']['settings'] != {'window_seconds':15, 'short_limit':15}:
        raise ValueError('Recorded sample settings are not primary 15/15')
    input_records[sample_path.relative_to(root).as_posix()].update(
        expected_sha256=expected_sheet_hash, provenance_status='verified')
    for recorded_input in sample_provenance['inputs']:
        input_path = (root/recorded_input['path']).resolve()
        input_path.relative_to(root)  # Refuse paths outside this repository.
        record(input_path)
        status = input_records[input_path.relative_to(root).as_posix()]
        expected_hash = recorded_input.get('sha256')
        status['expected_sha256'] = expected_hash
        status['provenance_status'] = 'unverified' if (
            status['status'] != 'readable' or not expected_hash
        ) else ('verified' if status['sha256'] == expected_hash else 'mismatch')
        if status['provenance_status'] == 'mismatch':
            raise ValueError('Recorded sampling input hash mismatch: '+str(input_path))
    combined_path = root/'outputs/audit-combined-primary/batch_manifest.json'
    combined = record(combined_path)
    preparation_path = root/'outputs/audit-combined-primary/preparation_manifest.json'
    preparation = record(preparation_path)
    preparation_record = input_records[preparation_path.relative_to(root).as_posix()]
    combined_preparation_verified = (
        preparation is not None
        and preparation_record['status'] == 'readable'
        and bool(preparation_record.get('expected_sha256'))
        and preparation_record['sha256'] == preparation_record['expected_sha256']
    )
    record(root/'docs/corner-extraction-methods.md')
    record(root/'src/corners/extract.py')  # Hash/reference only; never import or execute.
    cases = table(sample_path)
    if len(cases) != expected_size or len({(r['match_id'], r['corner_event_id']) for r in cases}) != expected_size:
        raise ValueError(f'Frozen sample must contain {expected_size} unique keys')
    old = {(r['match_id'], r['corner_event_id']): r for r in table(old_path)} if old_path.exists() else {}
    lookup, summaries = {}, {}
    for run_name, input_name in [('wc2022-euro2024-corners','wc2022-euro2024'), ('leagues-2015-16-corners','leagues-2015-16')]:
        run_path = root/'outputs'/run_name/'run_manifest.json'
        manifest_path = root/'data/ingested'/input_name/'batch_manifest.json'
        report = record(run_path); source_manifest = record(manifest_path)
        if report is None or source_manifest is None:
            raise ValueError('Missing constituent provenance: '+input_name)
        if sha(manifest_path) != report['manifest_sha256']:
            raise ValueError('Constituent manifest hash does not match run: '+input_name)
        if report['settings'] != {'window_seconds':15, 'short_limit':15.0}:
            raise ValueError('Not a primary 15/15 run')
        runs = {str(m['match_id']):m for m in report['matches']}
        for entry in source_manifest['matches']:
            mid = str(entry['match_id'])
            if mid in lookup: raise ValueError('Overlapping match IDs')
            lookup[mid] = (entry, runs[mid], manifest_path, run_path)
        csv_path = root/'outputs'/run_name/'corner_summary.csv'
        record(csv_path)
        for row in table(csv_path):
            key = row['match_id'],row['corner_event_id']
            if key in summaries: raise ValueError('Duplicate summary key')
            summaries[key] = row
    combined_lookup = {str(e['match_id']):e for e in combined['matches']} if combined else None
    results, event_cache, source_records = [], {}, {}
    for case in cases:
        key = case['match_id'], case['corner_event_id']
        result = dict(verification_type='automated verification, not manual review or ground truth',
                      audit_id=int(case['audit_id']), match_id=key[0], corner_event_id=key[1],
                      source_path='', expected_source_sha256='', actual_source_sha256='',
                      provenance_status='unresolved', source_revision='', source_locator_manifest='',
                      source_run_manifest='', window_seconds=15, short_limit=15,
                      provenance_note='', error='', supporting_events=[], ambiguities=[],
                      boundary_event_id=None, raw_distance=None, explanation='', initial_result_status='unresolved')
        for field in FIELDS:
            result['exported_'+field] = None
            result['computed_'+field] = None
            result[field+'_status'] = 'unresolved'
        try:
            row = summaries[key]
            for field in FIELDS:
                value = row[field]
                if field.endswith('_ids'): value = json.loads(value)
                elif field.endswith('_count'): value = int(value)
                result['exported_'+field] = value
            for field in ('delivery_category','shot_count','goal_count','stop_reason','chain_event_ids'):
                left = json.loads(case[field]) if field.endswith('_ids') else case[field]
                right = json.loads(row[field]) if field.endswith('_ids') else row[field]
                if left != right: raise ValueError('Frozen sample differs from original summary: '+field)
            if float(case['window_seconds']) != 15 or float(row['short_limit']) != 15 or float(row['window_seconds']) != 15:
                raise ValueError('Case settings not 15/15')
            entry, recorded, manifest_path, run_path = lookup[key[0]]
            source = (manifest_path.parent/entry['events']).resolve()
            result.update(source_path=str(source), expected_source_sha256=recorded['events_sha256'],
                          source_revision=recorded['source_revision'], source_locator_manifest=str(manifest_path),
                          source_run_manifest=str(run_path))
            if entry.get('source_revision') != recorded['source_revision']:
                raise ValueError('Source revision differs between manifests')
            if combined_lookup is not None:
                resolved = (combined_path.parent/combined_lookup[key[0]]['events']).resolve()
                if resolved != source: raise ValueError('Combined path differs from constituent source')
                result['provenance_note'] = 'Combined and constituent paths agree; source hash verified against constituent run.'
            else:
                result['provenance_note'] = 'Combined manifest inaccessible; original constituent manifest and recorded run hash used. Combined preparation provenance cannot be verified.'
            if key[0] not in event_cache:
                digest = sha(source)
                source_records[str(source)] = {'actual_sha256':digest, 'expected_sha256':recorded['events_sha256'], 'source_revision':recorded['source_revision']}
                result['actual_source_sha256'] = digest
                if digest != recorded['events_sha256']: raise ValueError('Raw source hash mismatch')
                raw = load(source)
                if not isinstance(raw,list): raise ValueError('Raw events must be a JSON list')
                event_cache[key[0]] = raw
            result['actual_source_sha256'] = source_records[str(source)]['actual_sha256']
            result['provenance_status'] = 'verified_original_manifest_fallback' if combined_lookup is None else 'verified'
            events, starter = locate(event_cache, *key)
            computed = compute(events, starter, Decimal(15), 15)
            for field in FIELDS:
                result['computed_'+field] = computed[field]
                result[field+'_status'] = 'match' if result['exported_'+field] == computed[field] else 'mismatch'
            for field in ('supporting_events','ambiguities','boundary_event_id','raw_distance'):
                result[field] = computed[field]
            result['explanation'] = ('Delivery evaluated from raw pass height, finite coordinates and technique (direct shots classified first). '
                f"Distance={computed['raw_distance']}; attacking shot IDs={computed['shot_event_ids']}. "
                f"Sequence ends at {computed['boundary_event_id']} with {computed['stop_reason']}; pre-inclusion priority is period, time >15s, restart, possession, stoppage. Included goals precede ball-out flags.")
            previous = old.get(key)
            if previous:
                checks = [str(previous['computed_'+f]) == str(computed[f]) for f in ('delivery_category','shot_count','goal_count','stop_reason')]
                checks.append(json.loads(previous['computed_shot_event_ids']) == computed['shot_event_ids'])
                result['initial_result_status'] = 'match' if all(checks) else 'mismatch'
        except (OSError, ValueError, KeyError, StopIteration, TypeError) as exc:
            result['error'] = str(exc)
            for field in FIELDS: result[field+'_status'] = 'unresolved'
        statuses = [result[f+'_status'] for f in FIELDS]
        result['overall_status'] = 'unresolved' if 'unresolved' in statuses else ('mismatch' if 'mismatch' in statuses else 'match')
        result['physical_boundary_ambiguity'] = any(a.startswith('off-target') for a in result['ambiguities'])
        results.append(result)

    overlap_ids = [r['audit_id'] for r in results if any(a.startswith('overlapping boundary') for a in r['ambiguities'])]
    off_ids = [r['audit_id'] for r in results if r['physical_boundary_ambiguity']]
    summary = dict(cases=len(results), overall_counts=dict(collections.Counter(r['overall_status'] for r in results)),
        comparison_counts={f:dict(collections.Counter(r[f+'_status'] for r in results)) for f in FIELDS},
        provenance_counts=dict(collections.Counter(r['provenance_status'] for r in results)),
        initial_result_counts=dict(collections.Counter(r['initial_result_status'] for r in results)),
        overlapping_boundary_audit_ids=overlap_ids, off_target_without_true_out_audit_ids=off_ids,
        intersection_audit_ids=sorted(set(overlap_ids)&set(off_ids)), unique_source_files=len(source_records),
        physical_boundary_ambiguity_cases=len(off_ids), human_agreement_computed=False, manual_judgments_written=0)
    summary['initial_flag_counts'] = {
        'overlapping_boundary_cases':sum(any(a.startswith('overlapping boundary') for a in json.loads(r['ambiguities'])) for r in old.values()),
        'off_target_cases':sum(any(a.startswith('off-target') for a in json.loads(r['ambiguities'])) for r in old.values())}
    lines = ['# Frozen sample: automated verification', '',
        'This is automated verification, not manual review or ground truth. No reviewer judgments are inspected or written. Independent implementations can share conceptual errors.', '',
        LIMITATIONS, '',
        '## Reproduction', '',
        'From the repository root, run focused tests first, then use a NEW destination (existing destinations are refused):', '',
        '```powershell',
        '.\\.venv\\Scripts\\python.exe -B -m unittest discover -s tests -p test_audit_crosscheck.py -v',
        '.\\.venv\\Scripts\\python.exe -B src/verify_audit.py --root . --output outputs/audit-combined-primary-automated-review-reproduction',
        '```', '',
        'Frozen sheet SHA-256 agrees with sample_provenance.json. Recorded combined input hashes are checked when readable; inaccessible inputs remain explicitly unverified.', '',
        '## Rules and interpretation', '',
        'Methods reference: docs/corner-extraction-methods.md (hash in review manifest). Events are ordered within each source match by period, Decimal timestamp and provider index. Duplicated included IDs are skipped. The first qualifying raw corner ID is used. No events are joined across matches.', '',
        'Short = ground pass with finite start/end coordinate pairs and Euclidean distance <=15 native units; short precedes technique. Otherwise recognized Inswinging/Outswinging/Straight techniques apply, with unknown fallback; a direct corner Shot is direct_shot. Exported Unknown does not establish that the raw technique field was absent.', '',
        'Pre-inclusion boundary priority: period change > elapsed time strictly greater than 15s > new restart > possession change > stoppage. Boundary records are excluded. Otherwise include the event, count attacking shots, then stop on any recorded Goal before checking out=true. Included terminal shots count. Exactly 15s remains eligible. Advantage fouls do not stop play.', '',
        'Overlapping flags identify simultaneous pre-inclusion conditions; the first condition in the documented priority wins. They are rule-consistent if the exported reason agrees, not automatic extraction errors. The relevant boundary event and winning reason appear in each case below.', '',
        'Off T/Wayward without out=true does not independently terminate the sequence under the documented rules. A later explicit boundary wins. This verifies implementation consistency but leaves the physical instant the ball went out unresolved; source events alone cannot settle that interpretation. Missing out, false out and true out are distinguished in the raw evidence.', '',
        'Neither combined manifest could be assumed accessible. Access results, errors and constituent fallback hashes are recorded in review_manifest.json. Original source hashes establish the bytes used; they do not verify inaccessible combined preparation metadata.', '',
        '## Reconciliation', '', '```json', json.dumps(summary,indent=2), '```', '',
        'The two flag lists above are case IDs (not exclusive groups); their intersection is listed explicitly. Comparison statuses concern documented-rule consistency. Physical-boundary ambiguity is recorded separately from comparison mismatches/unresolved evidence.', '',
        '## Evidence for all cases', '']
    for r in results:
        lines += [f"### Audit {r['audit_id']}: match {r['match_id']}, corner {r['corner_event_id']}", '',
                  f"Source: `{r['source_path']}`", '',
                  f"SHA-256 actual: `{r['actual_source_sha256']}`; expected: `{r['expected_source_sha256']}`. Status: {r['provenance_status']}.", '',
                  r['provenance_note'], '',
                  '| Field | Exported | Independent | Status |', '| --- | --- | --- | --- |']
        for f in FIELDS:
            lines.append(f"| {f} | {json.dumps(r['exported_'+f])} | {json.dumps(r['computed_'+f])} | {r[f+'_status']} |")
        lines += ['', r['explanation'] or r['error'], '', 'Flags: '+('; '.join(r['ambiguities']) or 'None.'), '']
        if r['physical_boundary_ambiguity']:
            lines += ['Interpretation: rule-consistent termination does not resolve physical ball-out timing. No automatic error or manual judgment is assigned.', '']
        lines += ['Raw supporting events below include the corner, included actions, and the first excluded boundary if present. Goal/ball-out terminals are already included. Fields omitted by the provider remain absent in details; out_field_present explicitly distinguishes absence.', '', '```json', json.dumps(r['supporting_events'],ensure_ascii=False,indent=2), '```', '']
    for path, digest in protected.items():
        if sha(path) != digest: raise ValueError('Protected input changed: '+str(path))
    output.mkdir(parents=True, exist_ok=False)
    with (output/'automated_crosscheck.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(results[0])); writer.writeheader()
        for row in results:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    (output/'evidence.md').write_text('\n'.join(lines),encoding='utf-8')
    script = Path(__file__).resolve()
    test_path = root/'tests/test_audit_crosscheck.py'
    manifest = dict(label='automated verification, not manual review or ground truth',
        created_utc=datetime.now(timezone.utc).isoformat(), code_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        python_version=sys.version, settings={'window_seconds':15,'short_limit':15,'timestamp_arithmetic':'Decimal'},
        limitations=LIMITATIONS, combined_preparation_verified=combined_preparation_verified,
        reproducible_code={str(script.relative_to(root)):sha(script), str(test_path.relative_to(root)):sha(test_path)},
        git_status=subprocess.check_output(['git','status','--short'],cwd=root,text=True),
        frozen_sample_provenance_verified=True,
        validation_note='Run tests separately: python -B -m unittest discover -s tests -p test_audit_crosscheck.py -v. The workflow does not recursively invoke tests.',
        inputs=input_records, source_verification=source_records, summary=summary,
        protected_inputs_unchanged=True, rules_reference='docs/corner-extraction-methods.md',
        outputs={p.name:sha(p) for p in output.iterdir() if p.is_file()},
        source_layout_note='Cached raw paths resolve relative to original manifests; reproduction requires the same repository cache layout or regenerated equivalent manifests.')
    (output/'review_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Independent frozen-sample automated verification; never writes reviewer judgments.')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.root.resolve(),args.output.resolve())
