"""Run from the repository root:
python -m src.setups --corners <corner_summary.csv> --three-sixty-dir <folder> --output <new folder>
"""

import argparse
import csv
import json
from pathlib import Path
import shutil
import tempfile

from .loader import read_corner_table, read_frames
from .pipeline import DEFAULTS, ROW_FIELDS, build_setups


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corners", type=Path, required=True,
                        help="corner_summary.csv from the corner extractor")
    parser.add_argument("--three-sixty-dir", type=Path, required=True,
                        help="folder holding <match_id>.json 360 files")
    parser.add_argument("--output", type=Path, required=True,
                        help="new folder; existing folders are never overwritten")
    parser.add_argument("--k", type=int, default=DEFAULTS["k"], help="clusters wanted")
    parser.add_argument("--min-box-coverage", type=float,
                        default=DEFAULTS["min_box_coverage"],
                        help="minimum share of the penalty box inside the visible area")
    parser.add_argument("--min-visible-players", type=int,
                        default=DEFAULTS["min_visible_players"])
    parser.add_argument("--min-corners-confident", type=int,
                        default=DEFAULTS["min_corners_confident"],
                        help="below this many usable corners results are labelled exploratory")
    parser.add_argument("--min-cluster-size", type=int,
                        default=DEFAULTS["min_cluster_size"],
                        help="clusters smaller than this make the result exploratory")
    args = parser.parse_args()
    if args.output.exists():
        parser.exit(1, "Output exists; choose a new folder\n")
    if args.k < 1 or not 0 <= args.min_box_coverage <= 1:
        parser.exit(1, "--k must be >= 1 and --min-box-coverage between 0 and 1\n")
    try:
        corners = read_corner_table(args.corners)
        frames = read_frames(args.three_sixty_dir, [c["match_id"] for c in corners])
        rows, report = build_setups(
            corners, frames, k=args.k, min_box_coverage=args.min_box_coverage,
            min_visible_players=args.min_visible_players,
            min_corners_confident=args.min_corners_confident,
            min_cluster_size=args.min_cluster_size)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Setup analysis failed: {exc}\n")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".setups-run-", dir=args.output.parent))
    try:
        with (stage / "setup_summary.csv").open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=ROW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        (stage / "setup_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        stage.rename(args.output)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(f"{report['corners_total']} corners; {report['corners_usable']} usable 360; "
          f"{report['corners_excluded']} excluded {report['excluded_by_reason']}; "
          f"{report['clusters_found']} clusters; exploratory={report['exploratory']} "
          f"-> {args.output}")


if __name__ == "__main__":
    main()
