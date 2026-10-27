import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corners.extract import (
    find_corners,
    find_corner_shots,
    extract_corner_sequence,
    describe_corner,
    build_corner_summaries,
)


def event(kind, second, possession=17, team=1, period=1):
    return {
        "id": f"{kind}-{second}-{team}",
        "type": {"name": kind},
        "timestamp": f"00:00:{second:06.3f}",
        "period": period,
        "possession": possession,
        "team": {"id": team},
    }


def corner():
    item = event("Pass", 0)
    item["pass"] = {"type": {"name": "Corner"}}
    return item


def shot(second=4):
    item = event("Shot", second)
    item["shot"] = {"outcome": {"name": "Saved"}}
    return item


class CornerExtractionTests(unittest.TestCase):
    def test_builds_one_summary_per_corner(self):
        delivery = corner()
        attempt = shot(4)
        attempt["shot"]["statsbomb_xg"] = 0.12
        rows = build_corner_summaries([delivery, attempt], match_id=123)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["match_id"], 123)
        self.assertEqual(row["corner_event_id"], delivery["id"])
        self.assertEqual(row["shot_count"], 1)
        self.assertEqual(row["goal_count"], 0)
        self.assertTrue(row["led_to_shot"])
        self.assertAlmostEqual(row["provider_xg_sum"], 0.12)
        self.assertEqual(row["shot_event_ids"], [attempt["id"]])
        self.assertEqual(
            row["chain_event_ids"], [delivery["id"], attempt["id"]]
        )
        self.assertEqual(row["stop_reason"], "end_of_data")
        self.assertEqual(row["window_seconds"], 15)
        self.assertEqual(row["short_limit"], 15)

    def test_short_corner_distance_and_height(self):
        delivery = corner()
        delivery["location"] = [120, 0]
        delivery["pass"].update({
            "end_location": [108, 9],  # Exactly 15 units away.
            "height": {"name": "Ground Pass"},
        })
        result = describe_corner(delivery)
        self.assertEqual(result["delivery_category"], "short")
        self.assertEqual(result["start_x"], 120)
        self.assertEqual(result["end_y"], 9)
        self.assertEqual(
            describe_corner(delivery, short_limit=10)["delivery_category"],
            "unknown",
        )
        delivery["pass"]["height"]["name"] = "High Pass"
        self.assertEqual(describe_corner(delivery)["delivery_category"], "unknown")
        for technique in ("Inswinging", "Outswinging"):
            with self.subTest(technique=technique):
                delivery["pass"]["technique"] = {"name": technique}
                self.assertEqual(
                    describe_corner(delivery)["delivery_category"], technique.lower()
                )
        for limit in (0, -1, float("inf"), float("nan")):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    describe_corner(delivery, short_limit=limit)

    def test_missing_coordinates_and_direct_shot(self):
        delivery = corner()
        delivery["pass"]["height"] = {"name": "Ground Pass"}
        result = describe_corner(delivery)
        for field in ("start_x", "start_y", "end_x", "end_y"):
            self.assertIsNone(result[field])
        self.assertEqual(result["delivery_category"], "unknown")
        direct = shot()
        direct["shot"]["type"] = {"name": "Corner"}
        self.assertEqual(describe_corner(direct)["delivery_category"], "direct_shot")

    def test_sequence_records_ids_and_possession_boundary(self):
        delivery = corner()
        attempt = shot(4)
        boundary = event("Pass", 6, possession=18)
        result = extract_corner_sequence(
            [delivery, attempt, boundary], delivery
        )
        self.assertEqual(
            result["chain_event_ids"], [delivery["id"], attempt["id"]]
        )
        self.assertEqual(result["stop_reason"], "possession_change")

    def test_sequence_records_terminal_goal(self):
        delivery = corner()
        attempt = shot(4)
        attempt["shot"]["outcome"]["name"] = "Goal"
        result = extract_corner_sequence(
            [delivery, attempt, shot(6)], delivery
        )
        self.assertEqual(result["shots"], [attempt])
        self.assertEqual(result["stop_reason"], "goal")
        self.assertEqual(
            result["chain_event_ids"], [delivery["id"], attempt["id"]]
        )

    def test_identifies_corners_and_deduplicates_ids(self):
        delivery = corner()
        direct = shot()
        direct["shot"]["type"] = {"name": "Corner"}
        events = [event("Pass", 1), delivery, delivery.copy(), shot(2), direct]
        self.assertEqual(find_corners(events), [delivery, direct])

    def test_counts_attacking_shots_despite_opponent_pressure(self):
        delivery = corner()
        first_shot, rebound = shot(4.142), shot(6)
        opponent_shot = shot(3)
        opponent_shot["team"]["id"] = 2
        events = [
            delivery,
            event("Pressure", 2, team=2),
            opponent_shot,
            first_shot,
            rebound,
        ]
        self.assertEqual(find_corner_shots(events, delivery), [first_shot, rebound])

    def test_stops_at_possession_change_and_rejects_missing_possession(self):
        delivery = corner()
        events = [delivery, event("Pass", 2, possession=18), shot(4)]
        self.assertEqual(find_corner_shots(events, delivery), [])
        del delivery["possession"]
        with self.assertRaisesRegex(ValueError, "no possession identifier"):
            find_corner_shots(events, delivery)

    def test_stops_at_period_change(self):
        delivery = corner()
        next_period_shot = shot(4)
        next_period_shot["period"] = 2
        self.assertEqual(find_corner_shots([delivery, next_period_shot], delivery), [])

    def test_time_limit_includes_exact_boundary_and_can_be_configured(self):
        delivery = corner()
        boundary_shot, late_shot = shot(15), shot(15.001)
        events = [delivery, boundary_shot, late_shot]
        self.assertEqual(find_corner_shots(events, delivery), [boundary_shot])
        self.assertEqual(find_corner_shots(events, delivery, max_seconds=10), [])
        self.assertEqual(
            find_corner_shots(events, delivery, max_seconds=None),
            [boundary_shot, late_shot],
        )

    def test_direct_corner_shot_counts_itself_and_follow_up(self):
        direct = shot(0)
        direct["shot"]["type"] = {"name": "Corner"}
        follow_up = shot(4)
        self.assertEqual(
            find_corner_shots([direct, follow_up], direct), [direct, follow_up]
        )
        self.assertEqual(
            find_corner_shots([direct, direct.copy(), follow_up, follow_up.copy()], direct),
            [direct, follow_up],
        )
        direct["shot"]["outcome"]["name"] = "Goal"
        self.assertEqual(find_corner_shots([direct, follow_up], direct), [direct])

    def test_stops_at_restarts_stoppages_and_ball_out(self):
        boundaries = []
        for restart_type in (
            "Corner", "Free Kick", "Goal Kick", "Kick Off", "Throw-in", "Penalty"
        ):
            for kind in ("Pass", "Shot"):
                restart = event(kind, 2)
                restart[kind.lower()] = {"type": {"name": restart_type}}
                boundaries.append(restart)
        ball_out = event("Clearance", 2)
        ball_out["out"] = True
        boundaries.extend([
            event("Foul Committed", 2),
            event("Foul Won", 2),
            event("Half End", 2),
            event("Injury Stoppage", 2),
            event("Offside", 2),
            event("Referee Ball-Drop", 2),
            ball_out,
        ])
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                delivery = corner()
                self.assertEqual(
                    find_corner_shots([delivery, boundary, shot(4)], delivery), []
                )
        for outcome, out in [("Goal", False), ("Wayward", True)]:
            with self.subTest(outcome=outcome, out=out):
                delivery = corner()
                ending_shot = shot(2)
                ending_shot["shot"]["outcome"]["name"] = outcome
                ending_shot["out"] = out
                self.assertEqual(
                    find_corner_shots([delivery, ending_shot, shot(4)], delivery),
                    [ending_shot],
                )

    def test_advantage_does_not_stop_play(self):
        for kind in ("Foul Committed", "Foul Won"):
            with self.subTest(kind=kind):
                delivery = corner()
                foul = event(kind, 2)
                foul[kind.lower().replace(" ", "_")] = {"advantage": True}
                follow_up = shot(4)
                self.assertEqual(
                    find_corner_shots([delivery, foul, follow_up], delivery),
                    [follow_up],
                )


if __name__ == "__main__":
    unittest.main()
