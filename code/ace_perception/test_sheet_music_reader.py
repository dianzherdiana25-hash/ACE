"""Verifier staf dan notehead sintetis pada geometri yang diketahui."""
import unittest

from ace_perception import _vision, sheet_music_reader as model


W, H = 68, 42


def sheet(lines=(10, 16, 22, 28, 34), glyphs=((8, 34), (27, 31), (42, 28))):
    values = bytearray([255]*W*H)
    for y in lines:
        values[y*W:(y+1)*W] = b"\x00"*W
    for x, center in glyphs:
        for y in range(center-2, center+3):
            values[y*W+x:y*W+x+5] = b"\x00"*5
        for y in range(center-10, center-2):
            values[y*W+x+4] = 0
    return _vision.encode(W, H, values)


def layout(**changes):
    return model._canonical({"schema": "ace.perception-sheet-layout.v1", "box": [0, 1, W, H],
                             "clef": "treble", "light_ink": False, "line_coverage_bp": 9000,
                             "min_head_width_px": 3, "max_head_width_px": 8, "min_head_pixels": 8,
                             "pitch_tolerance_bp": 1500, **changes})


class SheetTests(unittest.TestCase):
    def test_staff_crossing_and_thin_stems_keep_actual_note_positions(self):
        report = model.read_staff(sheet(), layout())
        self.assertEqual(report["status"], "read")
        self.assertEqual(report["staff_bands"], [[10, 11], [16, 17], [22, 23], [28, 29], [34, 35]])
        self.assertEqual([row["pitch"] for row in report["notes"]], ["E4", "F4", "G4"])
        self.assertEqual([row["step_from_bottom"] for row in report["notes"]], [0, 1, 2])
        self.assertEqual(report["notes"][0]["box"], [8, 32, 13, 37])
        self.assertEqual(model.read_staff(sheet(), layout(clef="bass"))["notes"][0]["pitch"], "G2")

    def test_unreadable_staff_does_not_produce_pitch(self):
        report = model.read_staff(sheet(lines=(10, 22, 28, 34)), layout())
        self.assertEqual(report["status"], "unresolved_staff")
        self.assertEqual(report["notes"], [])
        self.assertEqual(len(report["staff_bands"]), 4)

    def test_unsnapped_note_center_remains_unresolved(self):
        report = model.read_staff(sheet(glyphs=((8, 33),)), layout())
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["notes"][0]["status"], "unresolved_pitch")
        self.assertIsNone(report["notes"][0]["pitch"])
