"""Self-contained offline ingestion tests."""

import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError, URLError

from src.corners.batch import run_batch
from src.data.pipeline import ingest
from src.data.source import (
    DataError,
    JsonSource,
    json_bytes,
)


REVISION = "e" * 40


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []

        self.config = {
            "source_revision": REVISION,
            "cache_dir": str(self.root / "cache"),
            "output_dir": str(self.root / "run1"),
            "download_360": True,
            "competitions": [
                {
                    "competition_id": 9001,
                    "season_id": 9001,
                }
            ],
        }

        competition = {
            "competition_id": 9001,
            "season_id": 9001,
            "competition_name": "Invented Cup",
            "season_name": "2026",
        }

        match = {
            "match_id": 101,
            "match_date": "2026-01-01",
            "competition": {
                "competition_id": 9001
            },
            "season": {"season_id": 9001},
            "home_team": {
                "home_team_id": 10,
                "home_team_name": "Example A",
            },
            "away_team": {
                "away_team_id": 11,
                "away_team_name": "Example B",
            },
        }

        other = copy.deepcopy(match)
        other.update(
            match_id=201,
            match_date="2026-01-02",
        )

        corner = {
            "id": "invented-corner",
            "index": 2,
            "period": 1,
            "timestamp": "00:01:00.000",
            "minute": 1,
            "second": 0,
            "possession": 5,
            "type": {
                "id": 30,
                "name": "Pass",
            },
            "team": {
                "id": 10,
                "name": "Example A",
            },
            "location": [120, 0],
            "pass": {
                "type": {
                    "id": 61,
                    "name": "Corner",
                },
                "end_location": [110, 40],
                "custom_field": "preserved",
            },
        }

        shot = copy.deepcopy(corner)
        shot.update(
            id="invented-shot",
            index=3,
            timestamp="00:01:04.000",
            second=4,
            type={
                "id": 16,
                "name": "Shot",
            },
            location=[110, 40],
        )
        del shot["pass"]

        shot["shot"] = {
            "type": {
                "id": 87,
                "name": "Open Play",
            },
            "outcome": {
                "id": 100,
                "name": "Saved",
            },
            "statsbomb_xg": 0.2,
        }

        start = {
            "id": "invented-start",
            "index": 1,
            "period": 1,
            "timestamp": "00:00:00.000",
            "type": {
                "id": 35,
                "name": "Starting XI",
            },
        }

        other_start = dict(
            start,
            id="invented-other-start",
        )

        frame = {
            "event_uuid": "invented-corner",
            "visible_area": [],
            "freeze_frame": [
                {
                    "location": [110, -0.5],
                    "teammate": True,
                    "actor": False,
                    "keeper": False,
                }
            ],
        }

        self.documents = {
            "data/competitions.json": [
                competition
            ],
            "data/matches/9001/9001.json": [
                other,
                match,
            ],
            "data/events/101.json": [
                shot,
                start,
                corner,
                copy.deepcopy(corner),
            ],
            "data/events/201.json": [
                other_start
            ],
            "data/three-sixty/101.json": [
                frame
            ],
        }

    def opener(self, request, timeout):
        path = request.full_url.split(
            f"/{REVISION}/",
            1,
        )[1]

        self.calls.append(path)

        if path not in self.documents:
            raise HTTPError(
                request.full_url,
                404,
                "Not found",
                {},
                None,
            )

        value = self.documents[path]

        return io.BytesIO(
            value
            if isinstance(value, bytes)
            else json_bytes(value)
        )

    def source(self, offline=False, opener=None):
        return JsonSource(
            REVISION,
            self.config["cache_dir"],
            offline=offline,
            opener=opener or self.opener,
            sleeper=lambda _: None,
        )

    def run_ingestion(self, **kwargs):
        return ingest(
            self.config,
            source=self.source(),
            **kwargs,
        )

    def test_counts_order_completeness_and_raw_preservation(self):
        report = self.run_ingestion()

        self.assertTrue(report["complete"])
        self.assertEqual(
            report["totals"],
            {
                "selected_matches": 2,
                "usable_matches": 2,
                "events": 4,
                "corners": 1,
                "corners_with_360": 1,
            },
        )

        record = report["matches"][0]

        self.assertEqual(
            record["duplicate_events"],
            1,
        )
        self.assertEqual(
            record["outside_pitch_360_players"],
            1,
        )
        self.assertEqual(
            record["completeness"][
                "corner_pass_technique"
            ]["missing"],
            1,
        )

        raw = (
            self.root
            / "cache"
            / REVISION
            / "data/events/101.json"
        )

        self.assertEqual(
            raw.read_bytes(),
            json_bytes(
                self.documents[
                    "data/events/101.json"
                ]
            ),
        )

        with (
            self.root / "run1/events.csv"
        ).open(newline="") as stream:
            rows = list(
                csv.DictReader(stream)
            )

        self.assertEqual(
            [
                row["event_id"]
                for row in rows[:3]
            ],
            [
                "invented-start",
                "invented-corner",
                "invented-shot",
            ],
        )
        self.assertEqual(
            rows[1]["technique"],
            "",
        )
        self.assertEqual(
            json.loads(
                rows[1]["source_event_json"]
            )["pass"]["custom_field"],
            "preserved",
        )

    def test_unchanged_corner_extractor_accepts_manifest(self):
        self.run_ingestion()

        result = run_batch(
            self.root / "run1/batch_manifest.json",
            self.root / "corners",
        )

        self.assertEqual(
            result["total_corners"],
            1,
        )
        self.assertEqual(
            result["matches"][0]["shots"],
            1,
        )
        self.assertEqual(
            result["matches"][1]["status"],
            "no_corners",
        )

    def test_offline_replay_is_byte_identical(self):
        self.run_ingestion()

        def forbidden(*args, **kwargs):
            self.fail(
                "Offline replay attempted a network request"
            )

        config = dict(
            self.config,
            output_dir=str(self.root / "run2"),
        )

        ingest(
            config,
            source=self.source(
                offline=True,
                opener=forbidden,
            ),
        )

        for filename in (
            "events.csv",
            "coverage_manifest.json",
            "coverage_summary.json",
            "batch_manifest.json",
        ):
            self.assertEqual(
                (
                    self.root
                    / "run1"
                    / filename
                ).read_bytes(),
                (
                    self.root
                    / "run2"
                    / filename
                ).read_bytes(),
            )

    def test_corrupt_cache_is_detected_and_repaired(self):
        source = self.source()
        original = source.get(
            "data/events/101.json"
        )

        original.path.write_text("[]")

        with self.assertRaises(
            DataError
        ) as caught:
            self.source(
                offline=True
            ).get("data/events/101.json")

        self.assertEqual(
            caught.exception.status,
            "corrupt_cache",
        )
        self.assertEqual(
            source.get(
                "data/events/101.json"
            ).sha256,
            original.sha256,
        )

    def test_missing_events_are_reported_and_excluded(self):
        del self.documents[
            "data/events/101.json"
        ]

        report = self.run_ingestion()

        self.assertFalse(
            report["complete"]
        )
        self.assertEqual(
            report["matches"][0]["events_status"],
            "missing",
        )

        batch = json.loads(
            (
                self.root
                / "run1/batch_manifest.json"
            ).read_text()
        )

        self.assertEqual(
            [
                row["match_id"]
                for row in batch["matches"]
            ],
            [201],
        )

    def test_conflicting_duplicate_ids_are_errors(self):
        self.documents[
            "data/events/101.json"
        ][-1]["location"] = [120, 80]

        report = self.run_ingestion()

        self.assertEqual(
            report["matches"][0]["events_status"],
            "invalid_schema",
        )

    def test_invalid_json_is_reported(self):
        self.documents[
            "data/events/101.json"
        ] = b"not JSON"

        report = self.run_ingestion()

        self.assertEqual(
            report["matches"][0]["events_status"],
            "invalid_json",
        )

    def test_invalid_360_does_not_hide_usable_events(self):
        self.documents[
            "data/three-sixty/101.json"
        ] = [{"event_uuid": "broken"}]

        report = self.run_ingestion()

        self.assertFalse(
            report["complete"]
        )
        self.assertEqual(
            report["matches"][0]["frames_status"],
            "invalid_schema",
        )
        self.assertEqual(
            report["totals"]["usable_matches"],
            2,
        )

    def test_disabling_360_skips_downloads(self):
        self.config["download_360"] = False

        report = self.run_ingestion()

        self.assertTrue(
            report["complete"]
        )
        self.assertFalse(
            any(
                "three-sixty" in path
                for path in self.calls
            )
        )

    def test_existing_output_is_preserved(self):
        self.run_ingestion()

        path = (
            self.root / "run1/events.csv"
        )
        before = path.read_bytes()

        with self.assertRaises(
            FileExistsError
        ):
            self.run_ingestion()

        self.assertEqual(
            before,
            path.read_bytes(),
        )

    def test_network_errors_retry_without_becoming_missing(self):
        attempts = []

        def broken(*args, **kwargs):
            attempts.append(1)
            raise URLError(
                "temporary failure"
            )

        with self.assertRaises(
            DataError
        ) as caught:
            self.source(
                opener=broken
            ).get("data/events/101.json")

        self.assertEqual(
            caught.exception.status,
            "network_error",
        )
        self.assertEqual(
            len(attempts),
            3,
        )
        self.assertFalse(
            list(
                (
                    self.root / "cache"
                ).rglob("*.missing.json")
            )
        )

    def test_revision_and_paths_are_validated(self):
        with self.assertRaises(
            ValueError
        ):
            JsonSource(
                "master",
                self.root / "cache",
            )

        with self.assertRaises(
            ValueError
        ):
            self.source().get(
                "data/../../secret"
            )

    def test_parquet_round_trip(self):
        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest(
                "Optional pyarrow is not installed"
            )

        self.run_ingestion(
            parquet=True
        )

        table = pq.read_table(
            self.root
            / "run1/events.parquet"
        )

        self.assertEqual(
            table.num_rows,
            4,
        )
        self.assertEqual(
            str(
                table.schema.field(
                    "match_id"
                ).type
            ),
            "int64",
        )
        self.assertEqual(
            str(
                table.schema.field(
                    "start_x"
                ).type
            ),
            "double",
        )
        self.assertIsNone(
            table.to_pylist()[1][
                "technique"
            ]
        )


if __name__ == "__main__":
    unittest.main()