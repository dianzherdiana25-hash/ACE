"""Verifier sambungan, provenance dan penahanan overlap yang tidak terbukti."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _raster, _vision, page_stitcher as model


def pix(rows):
    return _vision.encode(len(rows[0]), len(rows), bytes(value for line in rows for value in line))


A = [[32, 12, 92], [63, 90, 240], [150, 140, 130], [90, 25, 9]]
B = [[150, 140, 130], [90, 25, 9], [9, 100, 19], [22, 18, 190]]
C = [[9, 100, 19], [22, 18, 190], [24, 1, 33]]


class StitchTests(unittest.TestCase):
    def test_auto_overlap_detects_two_seams_and_preserves_known_source_rows(self):
        files = [pix(A), pix(B), pix(C)]
        image, report = model.stitch(files, auto_overlap=(1, 2), maximum_mean_difference=0)
        self.assertEqual(report["status"], "stitched")
        self.assertEqual([row["overlap"] for row in report["seams"]], [2, 2])
        self.assertEqual(report["size"], [3, 7])
        self.assertEqual(image, pix(A+B[2:]+C[2:]))
        self.assertEqual(report["output_sha256"], sha256(image).hexdigest())
        self.assertEqual(report["source_sha256"], [sha256(data).hexdigest() for data in files])
        self.assertEqual([row["box"] for row in report["placements"]], [[0, 0, 3, 4], [0, 2, 3, 6], [0, 4, 3, 7]])
        self.assertEqual(report["seams"][0]["candidates"][1]["difference_sum"], 0)

    def test_horizontal_explicit_overlap_blends_rounded_average(self):
        one = pix([[30, 10], [90, 20]])
        two = pix([[12, 50], [21, 100]])
        image, result = model.stitch([one, two], direction="horizontal", overlap_px=1,
                                     maximum_mean_difference=2)
        self.assertEqual(image, pix([[30, 11, 50], [90, 21, 100]]))
        self.assertEqual(result["placements"][1]["box"], [1, 0, 3, 2])
        self.assertEqual(result["seams"][0]["candidates"][0]["difference_sum"], 3)

    def test_gap_mode_is_explicit_and_allows_different_page_sizes(self):
        result, report = model.stitch([pix([[10, 20], [30, 40]]), pix([[90]])], gap=2)
        self.assertEqual(result, pix([[10, 20], [30, 40], [255, 255], [255, 255], [90, 255]]))
        self.assertEqual(report["seams"][0]["status"], "gap")
        self.assertEqual(report["placements"][-1]["box"], [0, 4, 1, 5])

    def test_tied_scores_for_repeated_stripes_are_held(self):
        stripe = pix([[20, 200]]*4)
        result, report = model.stitch([stripe, stripe], auto_overlap=[1, 3])
        self.assertIsNone(result)
        self.assertEqual(report["seams"][0]["status"], "ambiguous")
        self.assertIsNone(report["output_sha256"])
        self.assertEqual(report["placements"], [])

    def test_flat_blank_overlaps_and_mismatch_have_distinct_reasons(self):
        blank = pix([[240, 240]]*3)
        artifact, report = model.stitch([blank, blank], overlap_px=1)
        self.assertIsNone(artifact)
        self.assertEqual(report["seams"][0]["status"], "insufficient_texture")
        output, different = model.stitch([pix(A), pix(B)], overlap_px=1, maximum_mean_difference=0)
        self.assertIsNone(output)
        self.assertEqual(different["seams"][0]["status"], "mismatch")

    def test_invalid_mode_cross_bounds_or_cost_refused(self):
        pages = [pix(A), pix(B)]
        for options in ({"auto_overlap": [1]}, {"overlap_px": 4}, {"overlap_px": True},
                        {"auto_overlap": [1, 2], "gap": 1}, {"direction": "diagonal"},
                        {"overlap_px": 1, "auto_overlap": [1, 2]}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                model.stitch(pages, **options)
        with self.assertRaisesRegex(ValueError, "dimensi silang"):
            model.stitch([pix(A), pix([[1, 3], [20, 99]])], overlap_px=1)
        with patch.object(model, "MAX_WORK", 4), self.assertRaisesRegex(ValueError, "Pencarian"):
            model.stitch(pages, auto_overlap=[1, 2])

    def test_cli_held_overlap_has_no_raster_and_does_not_modify_inputs(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        first, second, artifact = [folder/name for name in ("a.pgm", "b.pgm", "merged.pgm")]
        first.write_bytes(pix(A))
        second.write_bytes(pix(B))
        args = [sys.executable, "-m", "ace_perception.page_stitcher", str(first), str(second),
                "--output", str(artifact), "--maximum-mean-difference", "0"]
        held = subprocess.run([*args, "--overlap-px", "1"], capture_output=True)
        self.assertEqual(held.returncode, 1)
        self.assertEqual(json.loads(held.stdout)["status"], "held")
        self.assertFalse(artifact.exists())
        run = subprocess.run([*args, "--overlap-px", "2"], capture_output=True, check=True)
        self.assertEqual(json.loads(run.stdout)["status"], "stitched")
        self.assertEqual(_raster.decode(artifact.read_bytes()).height, 6)
        self.assertEqual(first.read_bytes(), pix(A))
