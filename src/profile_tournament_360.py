"""Profile delivery-specific 360 matching and setup eligibility; never download."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from math import isfinite
from pathlib import Path
import subprocess
import tempfile

from src.data.source import DataError
from src.data.validation import validate_frames
from src.setups.loader import read_corner_table, read_frames
from src.setups.pipeline import DEFAULTS, build_setups

CATEGORIES = ("short", "inswinging", "outswinging", "straight", "unknown", "direct_shot")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def load_match(record, manifest_dir, frames_dir):
    mid = str(record["match_id"])
    path = Path(record["frames"]) if record.get("frames") else Path(frames_dir) / f"{mid}.json"
    if not path.is_absolute():
        path = Path(manifest_dir) / path
    path = path.resolve()
    info = dict(match_id=mid, path=str(path), recorded_status=record.get("frames_status"),
                file_status="missing_file", sha256=None, error="")
    if not path.is_file():
        return None, info
    try:
        info["sha256"] = sha(path)
        if record.get("frames_sha256") and info["sha256"] != record["frames_sha256"]:
            info.update(file_status="hash_mismatch", error="File differs from coverage manifest")
            return None, info
        with path.open(encoding="utf-8-sig") as stream:
            validate_frames(json.load(stream))
        # Reuse setup loader's exact event UUID indexing and match isolation.
        frames = read_frames(path.parent, [mid])[mid]
        if path.name != f"{mid}.json":
            raise ValueError("Expected pinned cache filename <match_id>.json")
        info["file_status"] = "loaded"
        return frames, info
    except (DataError, ValueError, UnicodeError) as exc:
        info.update(file_status="invalid_file", error=str(exc))
    except OSError as exc:
        info.update(file_status="read_error", error=str(exc))
    return None, info


def summarize(rows):
    total = len(rows)
    available = sum(r["file_loaded"] for r in rows)
    matched = sum(r["frame_matched"] is True for r in rows)
    usable = sum(r["setup_eligible"] is True for r in rows)
    return dict(corners=total, corners_in_loaded_matches=available, matched=matched,
                usable=usable, unavailable_file_corners=total - available,
                unmatched_loaded_corners=available - matched,
                excluded_matched_corners=matched - usable,
                matching_pct_all=percent(matched, total),
                usable_pct_all=percent(usable, total),
                matching_pct_loaded=percent(matched, available),
                usable_pct_matched=percent(usable, matched))


def profile(corners, coverage, manifest_dir, frames_dir, **thresholds):
    records = {}
    for record in coverage["matches"]:
        mid = str(record["match_id"])
        if mid in records:
            raise ValueError("Duplicate coverage match")
        records[mid] = record
    keys = [(r["match_id"], r["corner_event_id"]) for r in corners]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate corner keys")
    for row in corners:
        if row["match_id"] not in records or row["delivery_category"] not in CATEGORIES:
            raise ValueError("Missing coverage match or unknown delivery category")
        for name in ("competition_id", "competition_name", "season_id", "season"):
            if str(row[name]) != str(records[row["match_id"]][name]):
                raise ValueError("Competition/season disagrees with coverage manifest")
    output, files = [], []
    for mid, record in sorted(records.items()):
        group = [r for r in corners if r["match_id"] == mid]
        frames, info = load_match(record, manifest_dir, frames_dir)
        files.append(info)
        setup_rows, _ = build_setups(group, {mid: frames}, **thresholds)
        for corner, setup in zip(group, setup_rows):
            loaded = info["file_status"] == "loaded"
            matched = corner["corner_event_id"] in frames if loaded else None
            eligible = setup["status"] == "ok" if matched else (False if loaded else None)
            reason = ("" if eligible else setup["exclusion_reason"]) if loaded else info["file_status"]
            output.append(dict(corner, file_loaded=loaded, file_status=info["file_status"],
                               frame_matched=matched, setup_eligible=eligible,
                               coverage_status=("usable" if eligible else "excluded_frame" if matched
                                                else "unmatched_frame" if loaded else "file_unavailable"),
                               setup_exclusion_reason=setup["exclusion_reason"],
                               coverage_exclusion_reason=reason,
                               box_coverage=setup["box_coverage"],
                               visible_players=setup["visible_players"]))
    summaries, comparisons = [], []
    competitions = sorted({(r["competition_id"], r["competition_name"], r["season_id"], r["season"])
                           for r in corners})
    for cid, name, sid, season in competitions:
        group = [r for r in output if r["competition_id"] == cid and r["season_id"] == sid]
        identity = dict(competition_id=cid, competition_name=name, season_id=sid, season=season)
        for category in CATEGORIES:
            summaries.append(dict(identity, delivery_category=category,
                                  **summarize([r for r in group if r["delivery_category"] == category])))
        for label in ("short", "non_short"):
            selected = [r for r in group if (r["delivery_category"] == "short") == (label == "short")]
            comparisons.append(dict(identity, comparison_group=label, **summarize(selected)))
    exclusions = Counter((r["competition_name"], r["coverage_exclusion_reason"])
                         for r in output if not r["setup_eligible"])
    discrepancies = []
    for mid, record in records.items():
        group = [r for r in output if r["match_id"] == mid]
        actual = sum(r["frame_matched"] is True for r in group)
        if len(group) != record["corner_count"] or actual != record["corners_with_360"]:
            discrepancies.append(dict(match_id=mid, observed_corners=len(group),
                                      recorded_corners=record["corner_count"],
                                      observed_matches=actual, recorded_matches=record["corners_with_360"]))
    if len(output) != len(corners) or sum(r["corners"] for r in summaries) != len(corners):
        raise ValueError("Count reconciliation failed")
    return output, files, summaries, comparisons, exclusions, discrepancies


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["competition_name", "reason", "corners"])
        writer.writeheader()
        writer.writerows(rows)


def run(corners_path, coverage_path, frames_dir, destination, **thresholds):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Output exists; choose a new destination")
    cfg = dict(DEFAULTS, **thresholds)
    if not isfinite(cfg["min_box_coverage"]) or not 0 <= cfg["min_box_coverage"] <= 1:
        raise ValueError("Invalid minimum box coverage")
    if type(cfg["min_visible_players"]) is not int or cfg["min_visible_players"] < 1:
        raise ValueError("Minimum visible players must be positive")
    coverage_path = Path(coverage_path).resolve()
    coverage = json.loads(coverage_path.read_text(encoding="utf-8-sig"))
    corners = read_corner_table(corners_path)
    hashes = dict(corners=sha(corners_path), coverage_manifest=sha(coverage_path))
    rows, files, summary, comparisons, exclusions, differences = profile(
        corners, coverage, coverage_path.parent, Path(frames_dir).resolve(), **thresholds)
    totals = summarize(rows)
    expected = coverage["totals"]
    reconciliation = dict(observed=totals, recorded_corners=expected["corners"],
                          recorded_matching=expected["corners_with_360"],
                          per_match_discrepancies=differences)
    reconciliation["agrees"] = (len(rows) == expected["corners"]
                                and totals["matched"] == expected["corners_with_360"] and not differences)
    root = Path(__file__).resolve().parents[1]
    code_paths = [Path(__file__), root / "src/data/validation.py", root / "src/setups/loader.py",
                  root / "src/setups/pipeline.py", root / "src/setups/features.py",
                  root / "src/setups/geometry.py", root / "src/setups/cluster.py"]
    provenance = dict(schema="delivery_360_coverage_v1", inputs=dict(corners=str(Path(corners_path).resolve()),
                      coverage_manifest=str(coverage_path), frames_dir=str(Path(frames_dir).resolve())),
                      input_sha256=hashes, source_revision=coverage["source_revision"],
                      code_revision=subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
                      code_sha256={str(p.relative_to(root)):sha(p) for p in code_paths},
                      setup_settings=cfg, reconciliation=reconciliation, match_files=files,
                      note="Uncommitted profiler identified by code hashes. Null frame matching means file unavailable, not unmatched.")
    if hashes != dict(corners=sha(corners_path), coverage_manifest=sha(coverage_path)):
        raise ValueError("Inputs changed during profiling")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".profile-360-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        write_csv(stage / "per_corner.csv", rows)
        write_csv(stage / "by_delivery.csv", summary)
        write_csv(stage / "short_comparison.csv", comparisons)
        write_csv(stage / "match_files.csv", files)
        write_csv(stage / "exclusions.csv", [dict(competition_name=c, reason=r, corners=n)
                  for (c,r), n in sorted(exclusions.items())])
        provenance["output_sha256"] = {p.name:sha(p) for p in stage.glob("*.csv")}
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        stage.rename(destination)
    print(json.dumps(reconciliation, indent=2))
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corners", type=Path, required=True)
    parser.add_argument("--coverage-manifest", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-box-coverage", type=float, default=DEFAULTS["min_box_coverage"])
    parser.add_argument("--min-visible-players", type=int, default=DEFAULTS["min_visible_players"])
    args = parser.parse_args()
    try:
        run(args.corners, args.coverage_manifest, args.frames_dir, args.output,
            min_box_coverage=args.min_box_coverage, min_visible_players=args.min_visible_players)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Profiling failed: {exc}\n")


if __name__ == "__main__":
    main()
