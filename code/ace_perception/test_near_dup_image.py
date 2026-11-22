"""Verifier scale/rotation, cache-free comparison, and grayscale guard."""
import unittest

from ace_perception import _vision, near_dup_image as model


def square(rows, scale=1):
    return _vision.encode(len(rows[0])*scale, len(rows)*scale,
                          [item for row in rows for _ in range(scale) for value in row for item in [value]*scale])


def sketch():
    return [[x*12+y*3+x*y*2 for x in range(9)] for y in range(9)]


class DuplicateImageTests(unittest.TestCase):
    def test_identical_bytes_scaled_and_rotated_are_distinguished(self):
        grid = sketch()
        a, b, c = square(grid), square(grid, scale=2), square(model._rotate(grid))
        report = model.compare([a, a, b, c], maximum_hamming=0, maximum_gray_mean=0)
        matches = {(row["left"], row["right"]): row for row in report["pairs"]}
        self.assertEqual(matches[1, 2]["status"], "identical_bytes")
        self.assertEqual(matches[1, 3]["status"], "near_candidate")
        self.assertEqual(matches[1, 4]["rotation_clockwise"], 270)
        self.assertEqual(matches[1, 4]["gray_difference_sum"], 0)
        fixed = model.compare([a, c], maximum_hamming=0, maximum_gray_mean=0, rotations=False)
        self.assertEqual(fixed["pairs"], [])

    def test_gradients_alone_do_not_match_flat_images_with_strong_gray_difference(self):
        one = square([[0]*9]*9)
        two = square([[255]*9]*9)
        self.assertEqual(model.compare([one, two], maximum_hamming=0, maximum_gray_mean=18)["rejected_pairs"], 1)
        self.assertEqual(model.compare([one, two], maximum_hamming=0, maximum_gray_mean=255)["pairs"][0]["hamming"], 0)
