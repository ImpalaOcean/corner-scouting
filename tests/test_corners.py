import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corners.extract import (
    find_corners,
    find_corner_shots,
    extract_corner_sequence,
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
