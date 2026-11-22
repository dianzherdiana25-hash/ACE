"""Verifier shift, tepi yang tak terukur dan ukuran komponen perubahan."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _vision, change_detector as model


WIDTH, HEIGHT = 12, 10


def sample(points=(), width=WIDTH, height=HEIGHT, max_gray=255, background=None):
    data = bytearray([max_gray if background is None else background]*(width*height))
    for x, y, v in points:
        data[y*width+x] = v
    return _vision.encode(width, height, data, max_gray)


def paired(dx, dy, additions=()):
    signs = [(3, 2, 9), (5, 3, 34), (4, 7, 21), (6, 4, 5), (8, 5, 63)]
    return sample(signs), sample([*( (x+dx, y+dy, shade) for x, y, shade in signs), *additions])


class ChangeTests(unittest.TestCase):
    def test_fixed_comparison_uses_threshold_and_separates_small_components(self):
        before = sample()
        after = sample([(2, 4, 170), (3, 4, 160), (8, 6, 176), (1, 0, 246)])
        report = model.detect(before, after, threshold=10, minimum_region=2)
        self.assertEqual(report["before_sha256"], sha256(before).hexdigest())
        self.assertEqual(report["after_sha256"], sha256(after).hexdigest())
        self.assertEqual(report["alignment"]["status"], "fixed")
        self.assertEqual(report["changed_pixels"], 3)
        self.assertEqual(report["raw_difference_sum"], 268)
        self.assertEqual(report["maximum_difference"], 95)
        self.assertEqual(report["below_region_minimum_pixels"], 1)
        self.assertEqual(report["regions"], [{"before_box": [2, 4, 4, 5], "after_box": [2, 4, 4, 5], "pixels": 2}])

    def test_known_shift_detected_with_closed_overlap_and_coordinate_direction(self):
        before, after = paired(dx=2, dy=-1)
        result = model.detect(before, after, max_shift=2)
        self.assertEqual(result["alignment"]["status"], "aligned")
        self.assertEqual(result["alignment"]["shift"], [2, -1])
        self.assertEqual(result["alignment"]["sample_pixels"], 48)
        self.assertGreater(result["alignment"]["base_sad"], 0)
        self.assertEqual(result["alignment"]["best_sad"], 0)
        self.assertEqual(result["before_overlap_box"], [0, 1, WIDTH-2, HEIGHT])
        self.assertEqual(result["compared_pixels"], 90)
        self.assertEqual(result["uncompared_pixels"], 30)
        self.assertEqual(result["changed_pixels"], 0)

    def test_shift_and_actual_edit_are_both_preserved(self):
        before, after = paired(dx=-1, dy=2, additions=[(4, 4, 55), (5, 4, 55)])
        report = model.detect(before, after, max_shift=2, threshold=20)
        self.assertEqual(report["alignment"]["shift"], [-1, 2])
        self.assertEqual(report["changed_pixels"], 2)
        self.assertEqual(report["regions"], [{"before_box": [5, 2, 7, 3], "after_box": [4, 4, 6, 5], "pixels": 2}])

    def test_uniform_ties_keep_offset_zero_and_never_choose_lexically(self):
        src = sample(background=50)
        result = model.detect(src, src, max_shift=1)
        self.assertEqual(result["alignment"]["status"], "ambiguous")
        self.assertIsNone(result["alignment"]["best_shift"])
        self.assertEqual(result["alignment"]["shift"], [0, 0])
        self.assertEqual(result["changed_pixels"], 0)
        self.assertEqual(result["uncompared_pixels"], 0)

    def test_moderate_gain_never_meets_threshold_selecting_shift(self):
        before, after = paired(dx=1, dy=0)
        result = model.detect(before, after, max_shift=1, minimum_alignment_gain=255)
        self.assertEqual(result["alignment"]["status"], "below_alignment_gain")
        self.assertEqual(result["alignment"]["best_shift"], [1, 0])
        self.assertEqual(result["alignment"]["shift"], [0, 0])
        self.assertGreater(result["changed_pixels"], 0)

    def test_depth_scaling_matches_white_and_black_as_same_image(self):
        first = sample([(0, 0, 0)], max_gray=255)
        second = sample([(0, 0, 0)], max_gray=31)
        result = model.detect(first, second)
        self.assertEqual(result["raw_difference_sum"], 0)
        self.assertNotEqual(result["before_sha256"], result["after_sha256"])

    def test_size_invalid_parameters_and_work_rejected(self):
        with self.assertRaisesRegex(ValueError, "ukuran"):
            model.detect(sample(width=4), sample())
        src = sample(width=2, height=2)
        with self.assertRaisesRegex(ValueError, "registrasi"):
            model.detect(src, src, max_shift=1)
        for opts in ({"threshold": 0}, {"max_shift": True}, {"minimum_region": 0}, {"minimum_alignment_gain": 256}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                model.detect(src, src, **opts)
        with patch.object(model, "MAX_WORK", 2), self.assertRaisesRegex(ValueError, "registrasi"):
            model.detect(sample(), sample(), max_shift=1)

    def test_region_cap_reports_truncation_without_changing_counts(self):
        with patch.object(model, "MAX_REGIONS", 1):
            result = model.detect(sample(), sample([(1, 1, 0), (4, 5, 10)]))
        self.assertEqual(result["changed_pixels"], 2)
        self.assertEqual(len(result["regions"]), 1)
        self.assertEqual(result["regions_omitted_by_cap"], 1)

    def test_command_line_and_deterministic_json(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        left, right = root/"left.pgm", root/"right.pgm"
        before, after = paired(dx=1, dy=0)
        left.write_bytes(before)
        right.write_bytes(after)
        cmd = [sys.executable, "-m", "ace_perception.change_detector", str(left), str(right), "--max-shift", "1"]
        report = subprocess.run(cmd, capture_output=True, check=True)
        self.assertEqual(json.loads(report.stdout), model.detect(before, after, max_shift=1))
        self.assertEqual(subprocess.run(cmd, capture_output=True, check=True).stdout, report.stdout)
        self.assertEqual(right.read_bytes(), after)
