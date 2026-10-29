"""Ingestion, coverage audit, and corner-extractor handoff."""

from collections import defaultdict
import csv
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from .source import (
    DataError,
    JsonSource,
    atomic_write,
    json_bytes,
)
from .validation import (
    EVENT_FIELDS,
    competitions,
    completeness,
    event_row,
    integer,
    is_corner,
    matches,
    on_pitch,
    validate_events,
    validate_frames,
)


def config_settings(config):
    if not isinstance(config, dict):
        raise ValueError("Config must be a JSON object")

    allowed = {
        "source_revision",
        "cache_dir",
        "output_dir",
        "competitions",
        "download_360",
    }

    if set(config) - allowed:
        raise ValueError(
            f"Unknown config keys: "
            f"{sorted(set(config) - allowed)}"
        )

    for key in ("cache_dir", "output_dir"):
        if (
            not isinstance(config.get(key), str)
            or not config[key]
        ):
            raise ValueError(f"Config requires {key}")

    selections = config.get("competitions", [])

    if not isinstance(selections, list):
        raise ValueError(
            "competitions must be an array; "
            "empty means all available seasons"
        )

    seen = set()

    for selection in selections:
        selection_keys = {
            "competition_id",
            "season_id",
            "max_matches",
            "match_ids",
        }

        if (
            not isinstance(selection, dict)
            or set(selection) - selection_keys
        ):
            raise ValueError(
                "Invalid competition selection"
            )

        key = (
            integer(
                selection.get("competition_id"),
                "competition_id",
            ),
            integer(
                selection.get("season_id"),
                "season_id",
            ),
        )

        if key in seen:
            raise ValueError(
                "Duplicate competition-season selection"
            )
        seen.add(key)

        if selection.get("max_matches") is not None:
            integer(
                selection["max_matches"],
                "max_matches",
            )

        if "match_ids" in selection:
            ids = selection["match_ids"]

            if not isinstance(ids, list) or not ids:
                raise ValueError(
                    "match_ids must be a nonempty array"
                )

            for mid in ids:
                integer(mid, "match_id")

            if len(ids) != len(set(ids)):
                raise ValueError(
                    "Duplicate selected match ID"
                )

    if type(config.get("download_360", True)) is not bool:
        raise ValueError(
            "download_360 must be true or false"
        )

    return selections


def metadata(match, competition):
    return {
        "match_id": match["match_id"],
        "competition_id": competition["competition_id"],
        "competition_name": competition["competition_name"],
        "season_id": competition["season_id"],
        "season": competition["season_name"],
        "match_date": match["match_date"],
        "home_team": match["home_team"]["home_team_name"],
        "away_team": match["away_team"]["away_team_name"],
    }


def parquet_schema(pa):
    integers = {
        "match_id",
        "competition_id",
        "season_id",
        "index",
        "period",
        "minute",
        "second",
        "possession_id",
        "team_id",
        "player_id",
        "recipient_id",
    }

    floats = {
        "start_x",
        "start_y",
        "end_x",
        "end_y",
        "provider_xg",
    }

    fields = []

    for key in EVENT_FIELDS:
        if key in integers:
            kind = pa.int64()
        elif key in floats:
            kind = pa.float64()
        else:
            kind = pa.string()

        fields.append((key, kind))

    return pa.schema(fields)


def ingest(
    config,
    *,
    offline=False,
    source_dir=None,
    parquet=False,
    source=None,
):
    selections = config_settings(config)
    output = Path(config["output_dir"]).resolve()
    cache = Path(config["cache_dir"]).resolve()

    if (
        output == cache
        or cache in output.parents
        or output in cache.parents
    ):
        raise ValueError(
            "Output and cache directories must be separate"
        )

    if output.exists():
        raise FileExistsError(
            "Output exists; choose a new output_dir "
            "or --output"
        )

    source = source or JsonSource(
        config["source_revision"],
        cache,
        offline=offline,
        source_dir=source_dir,
    )

    if source.revision != config["source_revision"]:
        raise ValueError(
            "Source revision does not match configuration"
        )

    pa = pq = schema = None

    if parquet:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ValueError(
                "Parquet requires: python -m pip install "
                "-r src/data/requirements.txt"
            ) from exc

        schema = parquet_schema(pa)

    catalogue = source.get("data/competitions.json")
    catalogue_rows = competitions(catalogue.value)

    available = {
        (row["competition_id"], row["season_id"]): row
        for row in catalogue_rows
    }

    if not selections:
        selections = [
            {
                "competition_id": cid,
                "season_id": sid,
            }
            for cid, sid in sorted(available)
        ]

    for selection in selections:
        key = (
            selection["competition_id"],
            selection["season_id"],
        )

        if key not in available:
            raise ValueError(
                "Selected competition-season is not "
                "in the pinned catalogue"
            )

    settings = {
        "source_revision": source.revision,
        "competitions": selections,
        "download_360": config.get(
            "download_360", True
        ),
    }

    report = {
        "schema": "data_coverage_v1",
        "source_repository": (
            "https://github.com/hudl/open-data"
        ),
        "source_revision": source.revision,
        "revision_verification": source.verification,
        "settings": settings,
        "settings_sha256": hashlib.sha256(
            json_bytes(settings)
        ).hexdigest(),
        "competitions_sha256": catalogue.sha256,
        "seasons": [],
        "matches": [],
    }

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    stage = Path(
        tempfile.mkdtemp(
            prefix=".data-run-",
            dir=output.parent,
        )
    )

    batch = []
    global_matches = set()

    team_totals = defaultdict(
        lambda: {
            "matches": 0,
            "events": 0,
            "corners": 0,
            "corners_with_360": 0,
        }
    )

    writer = None

    try:
        if parquet:
            writer = pq.ParquetWriter(
                stage / "events.parquet",
                schema,
                compression="snappy",
            )

        with (stage / "events.csv").open(
            "w",
            newline="",
            encoding="utf-8",
        ) as stream:
            csv_writer = csv.DictWriter(
                stream,
                fieldnames=EVENT_FIELDS,
            )
            csv_writer.writeheader()

            ordered_selections = sorted(
                selections,
                key=lambda row: (
                    row["competition_id"],
                    row["season_id"],
                ),
            )

            for selection in ordered_selections:
                cid = selection["competition_id"]
                sid = selection["season_id"]
                competition = available[cid, sid]

                season_report = {
                    "competition_id": cid,
                    "competition_name": (
                        competition["competition_name"]
                    ),
                    "season_id": sid,
                    "season": competition["season_name"],
                }

                report["seasons"].append(
                    season_report
                )

                try:
                    match_file = source.get(
                        f"data/matches/{cid}/{sid}.json"
                    )

                    season_matches = matches(
                        match_file.value,
                        competition,
                    )

                    season_report.update(
                        status="ok",
                        matches_sha256=match_file.sha256,
                        available_matches=len(
                            season_matches
                        ),
                    )

                    wanted = set(
                        selection.get("match_ids", [])
                    )
                    missing_ids = wanted - {
                        match["match_id"]
                        for match in season_matches
                    }

                    if missing_ids:
                        raise DataError(
                            "missing_match_ids",
                            "IDs not listed in this season: "
                            f"{sorted(missing_ids)}",
                        )

                    if wanted:
                        season_matches = [
                            match
                            for match in season_matches
                            if match["match_id"] in wanted
                        ]

                    if selection.get("max_matches"):
                        season_matches = season_matches[
                            :selection["max_matches"]
                        ]

                    season_report["selected_matches"] = (
                        len(season_matches)
                    )

                except DataError as exc:
                    season_report.update(
                        status=exc.status,
                        error=str(exc),
                    )
                    continue

                for match in season_matches:
                    mid = match["match_id"]

                    if mid in global_matches:
                        raise ValueError(
                            "Match ID occurs in multiple "
                            f"selected seasons: {mid}"
                        )

                    global_matches.add(mid)
                    meta = metadata(
                        match,
                        competition,
                    )

                    record = dict(
                        meta,
                        events_status="not_attempted",
                        frames_status="not_requested",
                    )
                    report["matches"].append(record)

                    events = None
                    frames = None
                    event_doc = None
                    frame_doc = None

                    try:
                        event_doc = source.get(
                            f"data/events/{mid}.json"
                        )

                        record["events_sha256"] = (
                            event_doc.sha256
                        )

                        events, duplicates = validate_events(
                            event_doc.value
                        )

                        if not events:
                            raise DataError(
                                "empty_events",
                                f"Match {mid}: empty event array",
                            )

                        record.update(
                            events_status="ok",
                            input_events=len(
                                event_doc.value
                            ),
                            unique_events=len(events),
                            duplicate_events=duplicates,
                            completeness=completeness(
                                events
                            ),
                        )

                    except DataError as exc:
                        record.update(
                            events_status=exc.status,
                            events_error=str(exc),
                        )
                        events = None

                    if config.get(
                        "download_360", True
                    ):
                        try:
                            frame_doc = source.get(
                                f"data/three-sixty/{mid}.json"
                            )

                            record["frames_sha256"] = (
                                frame_doc.sha256
                            )

                            frames = validate_frames(
                                frame_doc.value
                            )

                            outside_players = sum(
                                not on_pitch(
                                    player["location"]
                                )
                                for frame in frames
                                for player in frame[
                                    "freeze_frame"
                                ]
                            )

                            record.update(
                                frames_status=(
                                    "ok"
                                    if frames
                                    else "empty_frames"
                                ),
                                frame_count=len(frames),
                                outside_pitch_360_players=(
                                    outside_players
                                ),
                            )

                            record["frames"] = (
                                os.path.relpath(
                                    frame_doc.path,
                                    output,
                                )
                            )

                        except DataError as exc:
                            record.update(
                                frames_status=exc.status,
                                frames_error=str(exc),
                            )

                    if events is None:
                        continue

                    event_ids = {
                        event["id"]
                        for event in events
                    }
                    frame_ids = {
                        frame["event_uuid"]
                        for frame in frames or []
                    }
                    corners = [
                        event
                        for event in events
                        if is_corner(event)
                    ]

                    record.update(
                        corner_count=len(corners),
                        corners_with_360=sum(
                            event["id"] in frame_ids
                            for event in corners
                        ),
                        orphan_360_frames=(
                            len(frame_ids - event_ids)
                            if frames is not None
                            else None
                        ),
                        events=os.path.relpath(
                            event_doc.path,
                            output,
                        ),
                    )

                    rows = (
                        []
                        if writer is not None
                        else None
                    )

                    for event in events:
                        row = event_row(
                            event,
                            meta,
                            source.revision,
                        )

                        csv_writer.writerow(row)

                        if rows is not None:
                            rows.append(row)

                    if writer is not None:
                        writer.write_table(
                            pa.Table.from_pylist(
                                rows,
                                schema=schema,
                            )
                        )

                    batch.append(
                        {
                            "match_id": mid,
                            "events": record["events"],
                            "metadata": meta,
                            "source_revision": (
                                source.revision
                            ),
                        }
                    )

                    for side in (
                        "home_team",
                        "away_team",
                    ):
                        tid = match[side][
                            side + "_id"
                        ]
                        name = match[side][
                            side + "_name"
                        ]
                        key = (cid, sid, tid, name)

                        totals = team_totals[key]
                        totals["matches"] += 1
                        totals["events"] += sum(
                            event.get(
                                "team", {}
                            ).get("id") == tid
                            for event in events
                        )

                        team_corners = [
                            event
                            for event in corners
                            if event.get(
                                "team", {}
                            ).get("id") == tid
                        ]

                        totals["corners"] += len(
                            team_corners
                        )
                        totals["corners_with_360"] += sum(
                            event["id"] in frame_ids
                            for event in team_corners
                        )

        if writer is not None:
            writer.close()
            writer = None

        event_ok = sum(
            record["events_status"] == "ok"
            for record in report["matches"]
        )

        optional_ok = {
            "ok",
            "missing",
            "empty_frames",
            "not_requested",
        }

        report["complete"] = (
            all(
                row["status"] == "ok"
                for row in report["seasons"]
            )
            and event_ok == len(
                report["matches"]
            )
            and all(
                row["frames_status"] in optional_ok
                for row in report["matches"]
            )
        )

        report["totals"] = {
            "selected_matches": len(
                report["matches"]
            ),
            "usable_matches": event_ok,
            "events": sum(
                row.get("unique_events", 0)
                for row in report["matches"]
            ),
            "corners": sum(
                row.get("corner_count", 0)
                for row in report["matches"]
            ),
            "corners_with_360": sum(
                row.get("corners_with_360", 0)
                for row in report["matches"]
            ),
        }

        summary = {
            "schema": "data_coverage_summary_v1",
            "source_revision": source.revision,
            "totals": report["totals"],
            "teams": [
                dict(
                    competition_id=key[0],
                    season_id=key[1],
                    team_id=key[2],
                    team=key[3],
                    **value,
                )
                for key, value in sorted(
                    team_totals.items()
                )
            ],
        }

        outputs = (
            ("coverage_manifest.json", report),
            ("coverage_summary.json", summary),
            (
                "batch_manifest.json",
                {"matches": batch},
            ),
        )

        for name, value in outputs:
            atomic_write(
                stage / name,
                json_bytes(value),
            )

        stage.rename(output)
        return report

    except BaseException:
        if writer is not None:
            writer.close()

        shutil.rmtree(
            stage,
            ignore_errors=True,
        )
        raise