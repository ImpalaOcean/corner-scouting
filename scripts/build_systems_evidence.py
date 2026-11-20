"""Verify completed Nov27 experiments, build compact tables and an evidence ZIP."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def table(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build(root, runs, clean, output):
    root, runs, clean, output = [p.resolve() for p in (root, runs, clean, output)]
    output.mkdir(parents=True, exist_ok=False)
    comparisons, timings, raw_timings = [], [], []
    reports = {}
    for corpus in ('tournament', 'league'):
        report = read(runs/f'{corpus}-comparisons/report.json')
        require(report['status']=='complete', f'{corpus} comparison incomplete')
        for row in report['comparisons']:
            require(row['status']=='match' and not any(row[k] for k in ('missing_keys','extra_keys','field_mismatches','provenance_errors')), 'Corpus mismatch')
            comparisons.append(dict(corpus=corpus, **row))
        report = read(runs/f'{corpus}-benchmark/report.json')
        require(report['status']=='complete' and report['repetitions']==5, 'Benchmark incomplete')
        reports[corpus] = report
        for implementation, values in report['summaries'].items():
            require(values['repetitions']==5, 'Missing timing repetition')
            timings.append(dict(corpus=corpus, implementation=implementation, **values))
        with (runs/f'{corpus}-benchmark/timings.csv').open(newline='',encoding='utf-8') as stream:
            raw_timings.extend(dict(corpus=corpus, **r) for r in csv.DictReader(stream))
    dossier = read(runs/'dossier-benchmark/report.json')
    require(dossier['status']=='complete' and dossier['repetitions']==5, 'Dossier benchmark incomplete')
    proof = read(runs/'reproduction-proof/report.json')
    require(proof['status']=='complete' and proof['clean_execution']['final_status']=='', 'Checkout reproduction incomplete')
    for row in proof['corpora']:
        require(row['comparison_status']=='match' and row['python_byte_identical'] and row['sql_byte_identical'] and row['per_match_source_metadata_counts_equal'], 'Reproduction mismatch')
    require(digest(clean/'outputs/nov27/dossier/dossier.json')==dossier['dossier_json_sha256'], 'Clean dossier differs')
    # Verify the measured source-content hashes still match the working files.
    for report in [*reports.values(), dossier]:
        for name, expected in report['environment']['code_sha256'].items():
            require(digest(root/name)==expected, f'Measured source changed: {name}')
    table(output/'comparisons.csv', comparisons)
    table(output/'extraction-benchmarks.csv', timings)
    table(output/'extraction-repetitions.csv', raw_timings)
    table(output/'dossier-benchmarks.csv', [dict(stage=k,**v) for k,v in dossier['summaries'].items()])
    (output/'dossier-repetitions.csv').write_bytes((runs/'dossier-benchmark/timings.csv').read_bytes())
    table(output/'clean-reproduction.csv', proof['corpora'])
    reconciliation = read(runs/'serialization-check/published-hash-proof.json')
    require(reconciliation['reconstructed_exact_published_bytes'], 'Published-hash proof unavailable')
    table(output/'xg-rounding.csv', read(runs/'serialization-check/fsum-investigation.json')['changes'])
    material = dict(comparisons=comparisons, extraction=reports, dossier=dossier,
                    reproduction=proof, archived_hash_reconciliation=reconciliation)
    (output/'report-data.json').write_text(json.dumps(material,indent=2),encoding='utf-8')
    entries = {}
    def include(path, name):
        require(name not in entries or entries[name]==path, f'Duplicate archive path: {name}')
        entries[name] = path
    for path in runs.rglob('*'):
        if not path.is_file() or output in path.parents:
            continue
        parts = path.relative_to(runs).parts
        allowed = path.suffix in ('.json','.log') or path.name in ('summary.csv','timings.csv','differences.csv')
        allowed |= path.name=='corner_summary.csv' and parts[0] in ('tournament-comparisons','league-comparisons')
        allowed |= path.name=='fsum-short-15.0-window-15.csv'
        if allowed:
            include(path, path.relative_to(runs).as_posix())
    for path in (clean/'outputs/nov27').rglob('*'):
        if path.is_file() and (path.suffix in ('.json','.log','.md') or ('analysis' in path.parts and path.suffix=='.csv') or 'dossier' in path.parts):
            include(path, 'clean-checkout/'+path.relative_to(clean/'outputs/nov27').as_posix())
    for name in ('wc2022-euro2024','leagues-2015-16'):
        for filename in ('batch_manifest.json','coverage_manifest.json'):
            include(root/f'data/ingested/nov27-{name}'/filename, f'ingestion/{name}/{filename}')
        include(root/f'configs/data/{name}.json',f'configs/{name}.json')
    for path in output.iterdir():
        if path.suffix in ('.csv','.json'):
            include(path,'tables/'+path.name)
    include(root/'src/systems/requirements.txt','software/requirements.txt')
    include(root/'src/systems/experiments.py','software/experiments.py')
    include(Path(__file__).resolve(),'software/build_systems_evidence.py')
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    inventory = {name:dict(sha256=digest(path),bytes=path.stat().st_size) for name,path in sorted(entries.items())}
    archive = output/'systems-evidence-2026-11-20.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for name,path in sorted(entries.items()):
            bundle.write(path,name)
        bundle.writestr('CONTENTS.json',json.dumps(dict(packaging_commit=commit,files=inventory),indent=2))
        bundle.writestr('README.txt','Systems evidence, November 20, 2026. Full comparison CSVs, reports, recorded code/input hashes, timing repetitions, dossier outputs and clean-checkout evidence. Raw provider events, flattened ingestion tables, duplicate benchmark tables and Parquet files remain outside this compact bundle. Manifests retain historical execution paths; use the repository reproduction instructions to regenerate data locally. CONTENTS.json hashes every included source file.\n')
    receipt = dict(archive=str(archive),sha256=digest(archive),bytes=archive.stat().st_size,files=len(entries),
                   packaging_commit=commit,clean_dossier_json_equal=True,measured_source_hashes_verified=True)
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--runs',type=Path,default=Path('outputs/nov27'))
    parser.add_argument('--clean-checkout',type=Path,default=Path('../corner-scouting-clean-nov27'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build(args.root,args.runs,args.clean_checkout,args.output)


if __name__=='__main__':
    main()
