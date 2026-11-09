"""Run from the repository root with python -m src.data."""

import argparse
import json
from pathlib import Path

from .pipeline import ingest


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/data/sample.json"),
    )
    parser.add_argument(
        "--output",
        help="Override output_dir; must be a new directory",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use verified cache only; no HTTP",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Use a pinned local open-data checkout/export",
    )
    parser.add_argument(
        "--parquet",
        action="store_true",
        help="Write typed Parquet alongside CSV",
    )

    args = parser.parse_args()

    try:
        config = json.loads(
            args.config.read_text(
                encoding="utf-8"
            )
        )

        if args.output:
            config["output_dir"] = args.output

        report = ingest(
            config,
            offline=args.offline,
            source_dir=args.source_dir,
            parquet=args.parquet,
        )

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        parser.exit(
            1,
            f"Ingestion failed: {exc}\n",
        )

    totals = report["totals"]

    print(
        f"{totals['usable_matches']}/"
        f"{totals['selected_matches']} matches usable; "
        f"{totals['events']} events; "
        f"{totals['corners']} corners; "
        f"{totals['corners_with_360']} corners with 360 "
        f"-> {config['output_dir']}"
    )

    if not report["complete"]:
        parser.exit(
            2,
            "Incomplete coverage: inspect "
            "coverage_manifest.json before extraction.\n",
        )


if __name__ == "__main__":
    main()