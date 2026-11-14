"""Select using metadata, then build from the frozen prematch selection plan."""
import argparse
import json
from pathlib import Path
from .prematch import select,run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    selection=sub.add_parser('select')
    selection.add_argument('--corners',type=Path,required=True)
    selection.add_argument('--coverage-manifest',type=Path,required=True)
    selection.add_argument('--selection',type=Path,required=True)
    selection.add_argument('--output',type=Path,required=True)
    build=sub.add_parser('build')
    build.add_argument('--selection',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=select(args.corners,args.coverage_manifest,args.selection,args.output) if args.command=='select' else run(args.selection)
    except (OSError,ValueError,KeyError) as exc:
        parser.exit(1,f'Dossier failed: {exc}\n')
    print(json.dumps({k:result[k] for k in ('fixture','cutoff')}|{'status':'selection_saved' if args.command=='select' else 'dossier_published'},indent=2))


if __name__=='__main__':main()
