import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.setups.cluster import adjusted_rand_index, kmeans
from src.setups.features import frame_features, vector
from src.setups.geometry import corner_side, coverage, mirror_y, zone_of
from src.setups.loader import read_corner_table, read_frames
from src.setups.pipeline import ROW_FIELDS, build_setups

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "setups"
FULL = [60, 0, 120, 0, 120, 80, 60, 80]


def player(x, y, teammate=True, actor=False, keeper=False):
    return dict(teammate=teammate, actor=actor, keeper=keeper, location=[x, y])


def frame(players, area=FULL):
    return dict(event_uuid="e", visible_area=area, freeze_frame=players)


class GeometryTests(unittest.TestCase):
    def test_zones_cover_exactly_the_penalty_box(self):
        self.assertEqual(zone_of(102, 18), 1)
        self.assertEqual(zone_of(120, 62), 9)
        self.assertEqual(zone_of(110, 40), 5)
        for x, y in [(101.9, 40), (110, 17.9), (110, 62.1), (121, 40), (60, 40), (-1, 5)]:
            with self.subTest(x=x, y=y):
                self.assertIsNone(zone_of(x, y))

    def test_corner_side_and_mirroring(self):
        self.assertEqual(corner_side(80), "top")
        self.assertEqual(corner_side(0.1), "bottom")
        self.assertIsNone(corner_side(39.9))      # mid-pitch is not a corner
        self.assertIsNone(corner_side(None))
        for x, y in [(120, 40), (60, 80), (120, 500), (120, -5), (0, 0),
                     (120, float("nan")), (float("inf"), 80), (120, True)]:
            self.assertIsNone(corner_side(y, x), (x, y))
        self.assertEqual(mirror_y(20), 60)

    def test_coverage_fraction(self):
        box = (102, 18, 120, 62)
        self.assertAlmostEqual(coverage(FULL_POLY, box), 1.0)
        half = [(60, 40), (130, 40), (130, 90), (60, 90)]   # top half of the box
        self.assertAlmostEqual(coverage(half, box), (62 - 40) / 44)
        self.assertEqual(coverage([(0, 0), (5, 0), (5, 5)], box), 0.0)
        self.assertEqual(coverage([], box), 0.0)


FULL_POLY = [(60, 0), (120, 0), (120, 80), (60, 80)]


class FeatureTests(unittest.TestCase):
    def test_outside_box_players_are_not_in_zones(self):
        f = frame([player(120, 80, actor=True), player(95, 40), player(110, 10, False),
                   player(110, 40)])
        out = frame_features(f, 80)
        self.assertEqual(out["att_in_box"], 1)      # only (110, 40)
        self.assertEqual(out["def_in_box"], 0)
        self.assertEqual(out["visible_players"], 4)
        self.assertEqual(out["visible_attackers"], 2)

    def test_actor_and_keepers_are_not_counted_as_outfield(self):
        f = frame([player(120, 80, actor=True), player(119, 40, False, keeper=True),
                   player(110, 40, False)])
        out = frame_features(f, 80)
        self.assertEqual(out["visible_keepers"], 1)
        self.assertEqual(out["def_in_box"], 1)
        self.assertEqual(out["visible_defenders"], 1)
        self.assertEqual(out["att_in_box"], 0)
        self.assertEqual(out["keeper_zone"], 6)

    def test_bottom_corner_is_mirrored_onto_top_corner(self):
        top = frame([player(120, 80, actor=True), player(110, 30), player(105, 55, False)])
        bottom = frame([player(120, 0, actor=True), player(110, 50), player(105, 25, False)])
        self.assertEqual(vector(frame_features(top, 80)), vector(frame_features(bottom, 0)))
        self.assertEqual(frame_features(bottom, 0)["corner_side"], "bottom")

    def test_visibility_coverage_follows_visible_area(self):
        far = frame([player(110, 40)], area=[60, 0, 70, 0, 70, 10, 60, 10])
        self.assertEqual(frame_features(far, 80)["box_coverage"], 0.0)
        self.assertEqual(frame_features(frame([player(110, 40)]), 80)["box_coverage"], 1.0)

    def test_unknown_side_gives_none(self):
        self.assertIsNone(frame_features(frame([player(110, 40)]), None))


class ClusterTests(unittest.TestCase):
    def test_identical_vectors_share_a_cluster_and_different_ones_split(self):
        a, b = [5] + [0] * 17, [0] * 8 + [5] + [0] * 9
        for order in ([a, b, a, b, a], [b, a, a, b, a], [a, a, a, b, b]):
            with self.subTest(order=order):
                labels, _ = kmeans(order, 2)
                self.assertEqual({labels[i] for i, v in enumerate(order) if v == a},
                                 {labels[order.index(a)]})
                self.assertNotEqual(labels[order.index(a)], labels[order.index(b)])

    def test_labels_follow_their_own_vectors_whatever_the_order(self):
        # Regression: labels must stay attached to the right item.
        a, b, c = [9] + [0] * 17, [0] * 17 + [9], [0] * 9 + [9] + [0] * 8
        vectors = [b, a, c, a, b]
        labels, centers = kmeans(vectors, 3)
        self.assertEqual(labels[1], labels[3])
        self.assertEqual(labels[0], labels[4])
        self.assertEqual(len({labels[0], labels[1], labels[2]}), 3)

    def test_k_is_capped_at_distinct_vectors(self):
        labels, centers = kmeans([[1, 1], [1, 1], [1, 1]], 4)
        self.assertEqual(labels, [0, 0, 0])
        self.assertEqual(len(centers), 1)

    def test_deterministic(self):
        data = [[i % 3, (i * 7) % 5] for i in range(30)]
        self.assertEqual(kmeans(data, 3), kmeans(list(data), 3))

    def test_stability_needs_enough_data(self):
        from src.setups.cluster import stability
        small = [[i % 2, 0] for i in range(8)]
        labels, _ = kmeans(small, 2)
        self.assertIsNone(stability(small, labels, 2))
        big = [[i % 2, 0] for i in range(60)]
        labels, _ = kmeans(big, 2)
        self.assertEqual(stability(big, labels, 2), 1.0)

    def test_adjusted_rand_index(self):
        self.assertEqual(adjusted_rand_index([0, 0, 1, 1], [1, 1, 0, 0]), 1.0)
        self.assertLess(adjusted_rand_index([0, 0, 1, 1], [0, 1, 0, 1]), 0.1)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.corners = read_corner_table(FIXTURES / "corners.csv")
        self.frames = read_frames(FIXTURES, [c["match_id"] for c in self.corners])
        self.rows, self.report = build_setups(self.corners, self.frames, k=2)
        self.by_id = {r["corner_event_id"]: r for r in self.rows}

    def test_every_corner_gets_one_row_with_a_status(self):
        self.assertEqual(len(self.rows), 8)
        self.assertEqual(set(self.rows[0]), set(ROW_FIELDS))

    def test_exclusions_are_recorded_not_crashes(self):
        reasons = {c: r["exclusion_reason"] for c, r in self.by_id.items()}
        self.assertEqual(reasons["c5"], "no_360_frame")
        self.assertEqual(reasons["c7"], "no_360_file")
        self.assertEqual(reasons["c6"], "low_visibility")
        self.assertEqual(self.report["corners_usable"], 5)
        self.assertEqual(self.report["excluded_by_reason"]["no_360_frame"], 1)
        for c in ("c5", "c6", "c7"):
            self.assertEqual(self.by_id[c]["cluster_id"], "")

    def test_side_normalisation_gives_identical_setups(self):
        keys = [f"att_z{z}" for z in range(1, 10)] + [f"def_z{z}" for z in range(1, 10)]
        self.assertEqual([self.by_id["c1"][k] for k in keys], [self.by_id["c2"][k] for k in keys])
        self.assertEqual(self.by_id["c2"]["corner_side"], "bottom")
        # c8 has no corner location in the table: side comes from the taker in the frame.
        self.assertEqual(self.by_id["c8"]["status"], "ok")
        self.assertEqual(self.by_id["c8"]["corner_side"], "top")

    def test_clusters_group_same_setups(self):
        ids = {c: self.by_id[c]["cluster_id"] for c in ("c1", "c2", "c3", "c4", "c8")}
        self.assertEqual(ids["c1"], ids["c2"])
        self.assertEqual(ids["c1"], ids["c4"])
        self.assertNotEqual(ids["c1"], ids["c3"])

    def test_small_sample_is_labelled_exploratory(self):
        self.assertTrue(self.report["exploratory"])
        self.assertTrue(any("only 5" in c for c in self.report["caveats"]))

    def test_input_order_does_not_change_results(self):
        rows, _ = build_setups(list(reversed(self.corners)), self.frames, k=2)
        again = {r["corner_event_id"]: r["cluster_id"] for r in rows}
        self.assertEqual(again, {c: r["cluster_id"] for c, r in self.by_id.items()})

    def test_thresholds_are_configurable(self):
        rows, report = build_setups(self.corners, self.frames, k=2, min_box_coverage=0.0)
        self.assertEqual(report["corners_usable"], 6)   # c6 now accepted

    def test_all_excluded_run_does_not_fail(self):
        rows, report = build_setups(self.corners, {"9001": None, "9002": None})
        self.assertEqual(report["corners_usable"], 0)
        self.assertEqual(report["clusters_found"], 0)
        self.assertTrue(report["exploratory"])

    def test_malformed_frame_is_excluded(self):
        frames = {"9001": {"c1": {"event_uuid": "c1", "visible_area": [1, 2, 3],
                                  "freeze_frame": []}}}
        rows, _ = build_setups([self.corners[0]], frames)
        self.assertEqual(rows[0]["exclusion_reason"], "invalid_frame")

    def test_duplicate_corner_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.csv"
            path.write_text("match_id,corner_event_id,start_x,start_y\n1,a,120,0\n1,a,120,0\n")
            with self.assertRaises(ValueError):
                read_corner_table(path)
            path.write_text("match_id,corner_event_id\n1,a\n")
            with self.assertRaises(ValueError):
                read_corner_table(path)
                
    def _corners(self, n):
        return [dict(match_id="1", corner_event_id=f"c{i}", team_id="1", team="A",
                     start_x=120.0, start_y=80.0) for i in range(n)]

    def _frame(self, uuid, players=None, area=FULL):
        players = players or [player(120, 80, actor=True)] + [
            player(105 + i % 10, 25 + i, i % 2 == 0) for i in range(10)]
        return dict(event_uuid=uuid, visible_area=area, freeze_frame=players)

    def test_identical_setups_are_exploratory_without_stability(self):
        corners = self._corners(100)
        frames = {"1": {c["corner_event_id"]: self._frame(c["corner_event_id"])
                        for c in corners}}
        _, report = build_setups(corners, frames, k=2)
        self.assertIsNone(report["stability_ari"])
        self.assertEqual(report["clusters_found"], 1)
        self.assertTrue(report["exploratory"])
        self.assertTrue(any("stability" in c for c in report["caveats"]))

    def test_tiny_cluster_makes_result_exploratory(self):
        corners = self._corners(30)
        odd = [player(120, 80, actor=True)] + [player(103, 60)] * 9 + [player(104, 20, False)]
        frames = {"1": {c["corner_event_id"]: self._frame(
            c["corner_event_id"], odd if c["corner_event_id"] == "c0" else None)
            for c in corners}}
        _, report = build_setups(corners, frames, k=2, min_corners_confident=30)
        self.assertEqual([c["size"] for c in report["clusters"]], [29, 1])
        self.assertEqual([c["meets_min_size"] for c in report["clusters"]], [True, False])
        self.assertTrue(report["exploratory"])
        self.assertTrue(any("fewer than" in c for c in report["caveats"]))

    def test_healthy_large_run_is_not_exploratory(self):
        corners = self._corners(120)
        other = ([player(120, 80, actor=True)] + [player(104, 60)] * 5
                 + [player(112, 40, False)] * 5)
        frames = {"1": {c["corner_event_id"]: self._frame(
            c["corner_event_id"], other if i % 2 else None)
            for i, c in enumerate(corners)}}
        _, report = build_setups(corners, frames, k=2)
        self.assertFalse(report["exploratory"], report["caveats"])
        self.assertEqual(report["stability_ari"], 1.0)

    def test_degenerate_visible_areas_are_invalid_even_with_zero_threshold(self):
        for name, area in [("empty", []), ("two points", [60, 0, 120, 80]),
                           ("zero area", [0, 0, 50, 50, 100, 100])]:
            with self.subTest(name):
                frames = {"1": {"c0": self._frame("c0", area=area)}}
                rows, _ = build_setups(self._corners(1), frames,
                                       min_box_coverage=0.0, min_visible_players=1)
                self.assertEqual(rows[0]["status"], "excluded")
                self.assertEqual(rows[0]["exclusion_reason"], "invalid_frame")

    def test_invalid_corner_coordinates_are_excluded(self):
        for x, y in [(120, 40), (60, 80), (120, 500), (120, -5), (0, 0),
                     (120, float("nan"))]:
            with self.subTest(x=x, y=y):
                corners = self._corners(1)
                corners[0].update(start_x=x, start_y=y)
                rows, _ = build_setups(corners, {"1": {"c0": self._frame("c0")}})
                self.assertEqual(rows[0]["status"], "excluded")
                self.assertEqual(rows[0]["exclusion_reason"], "invalid_corner_location")

    def test_unparseable_table_coordinates_are_invalid_not_blank(self):
        from src.setups.loader import number
        self.assertIsNone(number(""))
        self.assertNotEqual(number("abc"), number("abc"))       # nan
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.csv"
            path.write_text("match_id,corner_event_id,start_x,start_y\n1,c0,120,abc\n")
            corners = read_corner_table(path)
        rows, _ = build_setups(corners, {"1": {"c0": self._frame("c0")}})
        self.assertEqual(rows[0]["exclusion_reason"], "invalid_corner_location")

if __name__ == "__main__":
    unittest.main()
