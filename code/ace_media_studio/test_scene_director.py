from copy import deepcopy
import unittest

from ._contracts import ContractError, identity
from .scene_director import direct


def storyboard():
    return {"schema": "ace.media.storyboard.v1", "project": "fixture", "fps": 12,
            "cast": [{"id": "aria", "wardrobe": ["uniform", "coat"]}], "scenes": [{
                "id": "hall", "location": "Aula", "source_ref": "fixture:hall",
                "wardrobe_change": [], "shots": [
                    {"id": "first", "type": "wide", "frames": 24, "axis": "left",
                     "cast": [{"id": "aria", "wardrobe": "uniform"}], "dialogue_words": 0, "notes": "Kenalkan ruang"},
                    {"id": "second", "type": "medium", "frames": 48, "axis": "left",
                     "cast": [{"id": "aria", "wardrobe": "uniform"}], "dialogue_words": 5, "notes": "Mulai dialog"}]}]}


class DirectionTests(unittest.TestCase):
    def test_ready_timeline_has_nonoverlapping_ranges_and_source(self):
        plan = storyboard()
        report = direct(plan, identity(plan))
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["frames"], 72)
        self.assertEqual([0, 24], [shot["first_frame"] for shot in report["shots"]])
        self.assertEqual(["fixture:hall"] * 2, [shot["source_ref"] for shot in report["shots"]])
        self.assertEqual(report, direct(deepcopy(plan), identity(plan)))

    def test_axis_costume_and_dialogue_holds_are_specific(self):
        plan = storyboard()
        last = plan["scenes"][0]["shots"][1]
        last.update(axis="right", dialogue_words=13, cast=[{"id": "aria", "wardrobe": "coat"}])
        report = direct(plan, identity(plan))
        self.assertEqual("hold_for_review", report["status"])
        self.assertEqual({"wardrobe_jump", "axis_flip", "dialogue_time"},
                         {row["rule"] for row in report["continuity_findings"]})
        self.assertEqual({last["id"]}, {row["shot"] for row in report["continuity_findings"]})
        last["cast"][0]["id"] = "unknown"
        with self.assertRaisesRegex(ContractError, "terdaftar"):
            direct(plan, identity(plan))
