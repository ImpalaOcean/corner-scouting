"""Compare all typed corner fields; exit 2 for mismatches, 1 for invalid input."""
import argparse
from collections import Counter
import csv
import json
import math
import os
from pathlib import Path
import re

from src.corners.batch import FIELDS, FLOAT_FIELDS, INT_FIELDS, LIST_FIELDS
from .common import environment, new_directory, sha, write_json


def load_table(path):
    result = {}
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if len(reader.fieldnames or []) != len(FIELDS) or set(reader.fieldnames or []) != set(FIELDS):
            raise ValueError(f'{path}: expected the complete {len(FIELDS)}-column batch schema')
        for number, raw in enumerate(reader, 2):
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError(f'{path}:{number}: malformed CSV row')
            row = {}
            for field, value in raw.items():
                if value == '':
                    row[field] = None
                elif field in LIST_FIELDS:
                    row[field] = json.loads(value)
                    if not isinstance(row[field], list) or any(not isinstance(v, str) for v in row[field]):
                        raise ValueError(f'{path}:{number}: {field} must be a JSON list of strings')
                elif field in INT_FIELDS:
                    row[field] = int(value)
                elif field in FLOAT_FIELDS:
                    row[field] = float(value)
                    if not math.isfinite(row[field]):
                        raise ValueError(f'{path}:{number}: nonfinite {field}')
                elif field == 'led_to_shot':
                    if value not in ('True', 'False', 'true', 'false'):
                        raise ValueError(f'{path}:{number}: invalid boolean')
                    row[field] = value.lower() == 'true'
                else:
                    row[field] = value
            key = (row['match_id'], row['corner_event_id'])
            if key[0] is None or not key[1] or key in result:
                raise ValueError(f'{path}:{number}: blank or duplicate corner key {key}')
            if any(row[f] is None for f in LIST_FIELDS):
                raise ValueError(f'{path}:{number}: event ID lists cannot be null')
            result[key] = row
    return result


def manifest_evidence(path):
    manifest = Path(path).with_name('run_manifest.json')
    if not manifest.is_file():
        return None
    before = sha(manifest)
    content = json.loads(manifest.read_text(encoding='utf-8'))
    fields = ('match_id', 'events_sha256', 'metadata', 'source_revision', 'corners', 'shots', 'goals')
    records = content.get('matches', [])
    if (content.get('schema') != 'corner_summary_batch_v1' or not records
        or not re.fullmatch('[0-9a-f]{64}', content.get('manifest_sha256', ''))
        or not isinstance(content.get('settings'), dict)
        or set(content['settings']) != {'window_seconds', 'short_limit'}):
        raise ValueError(f'{manifest}: incomplete extraction provenance')
    for record in records:
        if (any(k not in record for k in fields)
            or not re.fullmatch('[0-9a-f]{64}', record.get('events_sha256', ''))
            or not isinstance(record['metadata'], dict)):
            raise ValueError(f'{manifest}: incomplete match provenance')
    ids = [r.get('match_id') for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f'{manifest}: duplicate match IDs')
    if before != sha(manifest):
        raise ValueError(f'{manifest}: manifest changed during comparison')
    return dict(sha256=before, manifest_sha256=content.get('manifest_sha256'),
                settings=content.get('settings'), total_corners=content.get('total_corners'),
                matches=sorted([{k: r.get(k) for k in fields} for r in records], key=lambda r: r['match_id']),
                recorded_output_hash=content.get('outputs_sha256', {}).get(Path(path).name))


def compare_tables(reference, candidate, output, xg_abs_tolerance=1e-12):
    if not math.isfinite(xg_abs_tolerance) or xg_abs_tolerance < 0:
        raise ValueError('xG absolute tolerance must be finite and nonnegative')
    before = {str(Path(p).resolve()): sha(p) for p in (reference, candidate)}
    left, right = load_table(reference), load_table(candidate)
    missing, extra = sorted(left.keys() - right.keys()), sorted(right.keys() - left.keys())
    differences = []
    for key in sorted(left.keys() & right.keys()):
        for field in FIELDS:
            a, b = left[key][field], right[key][field]
            equal = a == b
            if field == 'provider_xg_sum' and a is not None and b is not None:
                equal = math.isclose(a, b, rel_tol=0, abs_tol=xg_abs_tolerance)
            if not equal:
                differences.append(dict(match_id=key[0], corner_event_id=key[1], field=field,
                                        reference=a, candidate=b))
    for key in missing:
        differences.append(dict(match_id=key[0], corner_event_id=key[1], field='__missing_corner__', reference=True, candidate=False))
    for key in extra:
        differences.append(dict(match_id=key[0], corner_event_id=key[1], field='__extra_corner__', reference=False, candidate=True))

    a_manifest, b_manifest = manifest_evidence(reference), manifest_evidence(candidate)
    provenance_errors = []
    for path, evidence in ((reference, a_manifest), (candidate, b_manifest)):
        if evidence is not None:
            if evidence['recorded_output_hash'] is not None and evidence['recorded_output_hash'] != sha(path):
                provenance_errors.append(f'{Path(path).parent.name}: recorded output hash mismatch')
            if evidence['total_corners'] != len(left if path == reference else right):
                provenance_errors.append(f'{Path(path).parent.name}: manifest row count mismatch')
    if a_manifest is not None and b_manifest is not None:
        for field in ('manifest_sha256', 'settings', 'total_corners', 'matches'):
            if a_manifest[field] != b_manifest[field]:
                provenance_errors.append(f'Extraction manifest {field} differs')
    warnings = [] if a_manifest is not None and b_manifest is not None else [
        'At least one extraction manifest is absent; source provenance agreement is unverified.']
    for path, digest in before.items():
        if sha(path) != digest:
            raise ValueError(f'Input changed during comparison: {path}')
    with new_directory(output) as stage:
        with (stage / 'differences.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['match_id', 'corner_event_id', 'field', 'reference', 'candidate'])
            writer.writeheader()
            for difference in differences:
                writer.writerow({k: json.dumps(v, allow_nan=False) if k in ('reference', 'candidate') else v
                                 for k, v in difference.items()})
        report = dict(schema='corner_comparison_v1', status='match' if not differences and not provenance_errors else 'mismatch',
                      reference_rows=len(left), candidate_rows=len(right), shared_keys=len(left.keys() & right.keys()),
                      missing_keys=len(missing), extra_keys=len(extra), field_mismatches=sum(d['field'] in FIELDS for d in differences),
                      mismatches_by_field=dict(Counter(d['field'] for d in differences)),
                      examples=differences[:20], xg_absolute_tolerance=xg_abs_tolerance,
                      inputs={name: dict(path=os.path.relpath(Path(path).resolve(), stage), sha256=before[str(Path(path).resolve())])
                              for name, path in (('reference', reference), ('candidate', candidate))},
                      extraction_manifests=dict(reference=a_manifest, candidate=b_manifest),
                      provenance_errors=provenance_errors, warnings=warnings, environment=environment(),
                      differences_sha256=sha(stage / 'differences.csv'))
        write_json(stage / 'comparison.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--xg-abs-tolerance', type=float, default=1e-12)
    args = parser.parse_args()
    try:
        report = compare_tables(args.reference, args.candidate, args.output, args.xg_abs_tolerance)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Comparison failed: {exc}\n')
    print(f"{report['status']}: {report['shared_keys']} shared corners, {report['field_mismatches']} field mismatches -> {args.output}")
    if report['status'] != 'match':
        parser.exit(2)


if __name__ == '__main__':
    main()
