import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.profile_tournament_360 import load_match, percent, profile, run, CATEGORIES


def frame(eid="e", players=5):
    return dict(event_uuid=eid, visible_area=[60,0,120,0,120,80,60,80],
                freeze_frame=[dict(location=[110,40], teammate=True, actor=False, keeper=False)
                              for _ in range(players)])


def corner(mid="1", eid="e", category="short"):
    return dict(match_id=mid, corner_event_id=eid, start_x=120., start_y=80.,
                competition_id="43", competition_name="Cup", season_id="106",
                season="2022", delivery_category=category)


def record(mid="1", count=1, matched=1):
    return dict(match_id=int(mid), corner_count=count, corners_with_360=matched,
                competition_id=43, competition_name="Cup", season_id=106, season="2022")


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def save(self, mid, frames):
        (self.base / f"{mid}.json").write_text(json.dumps(frames), encoding="utf-8")

    def calculate(self, corners, records):
        return profile(corners, dict(matches=records), self.base, self.base)

    def test_exact_match_isolation(self):
        self.save("1", [frame()])
        self.save("2", [frame("other")])
        rows, _, _, _, _, _ = self.calculate([corner(), corner("2")], [record(), record("2",matched=0)])
        self.assertTrue(rows[0]["frame_matched"])
        self.assertFalse(rows[1]["frame_matched"])
        self.assertTrue(rows[0]["setup_eligible"])

    def test_missing_and_unmatched_are_different(self):
        self.save("2", [])
        rows, _, _, _, _, _ = self.calculate([corner(),corner("2")], [record(matched=0),record("2",matched=0)])
        self.assertIsNone(rows[0]["frame_matched"])
        self.assertEqual(rows[0]["file_status"], "missing_file")
        self.assertTrue(rows[1]["file_loaded"])
        self.assertFalse(rows[1]["frame_matched"])
        self.assertEqual(rows[1]["setup_exclusion_reason"], "no_360_frame")

    def test_corrupt_file_and_duplicate_uuid_are_unavailable(self):
        (self.base / "1.json").write_text("{bad",encoding="utf-8")
        frames, info = load_match(record(), self.base, self.base)
        self.assertIsNone(frames)
        self.assertEqual(info["file_status"], "invalid_file")
        self.save("1",[frame(),frame()])
        self.assertEqual(load_match(record(),self.base,self.base)[1]["file_status"],"invalid_file")

    def test_hash_mismatch_not_unmatched(self):
        self.save("1",[frame()])
        entry=record(); entry["frames_sha256"]="0"*64
        self.assertEqual(load_match(entry,self.base,self.base)[1]["file_status"],"hash_mismatch")

    def test_eligibility_reasons_reuse_pipeline(self):
        for reason, item, change in [
            ("too_few_visible_players",frame(players=4),{}),
            ("low_visibility",dict(frame(),visible_area=[0,0,5,0,5,5,0,5]),{}),
            ("invalid_frame",dict(frame(),visible_area=[]),{}),
            ("invalid_corner_location",frame(),{"start_x":60.}),
            ("no_corner_location",frame(),{"start_x":None,"start_y":None}),
        ]:
            with self.subTest(reason=reason):
                self.save("1",[item])
                c=corner(); c.update(change)
                rows,*_=self.calculate([c],[record()])
                self.assertTrue(rows[0]["frame_matched"])
                self.assertFalse(rows[0]["setup_eligible"])
                self.assertEqual(rows[0]["setup_exclusion_reason"],reason)

    def test_zero_denominators_and_six_categories(self):
        self.assertIsNone(percent(0,0))
        self.save("1",[])
        _,_,summary,comparisons,_,_=self.calculate([corner()],[record(matched=0)])
        self.assertEqual({r["delivery_category"] for r in summary},set(CATEGORIES))
        empty=next(r for r in summary if r["delivery_category"]=="direct_shot")
        self.assertEqual(empty["corners"],0)
        self.assertIsNone(empty["matching_pct_all"])
        nonshort=next(r for r in comparisons if r["comparison_group"]=="non_short")
        self.assertIsNone(nonshort["usable_pct_all"])

    def test_reconciliation_reports_disagreement(self):
        self.save("1",[frame()])
        rows,_,summary,_,_,differences=self.calculate([corner()],[record(count=2,matched=0)])
        self.assertEqual(len(rows),1)
        self.assertEqual(sum(r["corners"] for r in summary),1)
        self.assertEqual(differences[0]["observed_matches"],1)
        self.assertEqual(differences[0]["recorded_matches"],0)

    def test_duplicates_and_existing_destination_refused(self):
        with self.assertRaises(ValueError):
            self.calculate([corner(),corner()],[record()])
        with self.assertRaises(FileExistsError):
            run("unused","unused","unused",self.base)


if __name__=="__main__":
    unittest.main()
