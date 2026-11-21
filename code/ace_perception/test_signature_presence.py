"""Verifier keberadaan tanda dari tinta baru tanpa inferensi identitas."""
from hashlib import sha256
import unittest

from ace_perception import _vision, signature_presence as model


def sample(*, mark=(), erase=(), extra=()):
    pixels = [255]*80
    for x in range(2, 8):
        pixels[5*10+x] = 0
    for x, y in (*mark, *extra):
        pixels[y*10+x] = 0
    for x, y in erase:
        pixels[y*10+x] = 255
    return _vision.encode(10, 8, pixels)


def inputs(**changes):
    blank = sample()
    spec = {"schema": "ace.perception-signature-layout.v1", "blank_sha256": sha256(blank).hexdigest(),
            "box": [1, 1, 9, 7], "minimum_contrast": 35, "minimum_new_pixels": 4,
            "minimum_component": 3, "maximum_missing_bp": 0, "light_ink": False}
    return blank, model._canonical({**spec, **changes})


class SignTests(unittest.TestCase):
    def test_only_new_ink_inside_box_counts_as_mark(self):
        before, spec = inputs()
        marked = sample(mark=((2, 2), (3, 2), (3, 3), (4, 3)), extra=((0, 7),))
        result = model.inspect(marked, before, spec)
        self.assertEqual(result["status"], "present")
        self.assertEqual(result["observed_new_pixels"], 4)
        self.assertEqual(result["components"], [{"box": [2, 2, 5, 4], "new_pixels": 4}])
        self.assertEqual(result["removed_pixels"], 0)
        self.assertEqual(result["blank_sha256"], sha256(before).hexdigest())
        self.assertEqual(model.inspect(before, before, spec)["status"], "not_detected")

    def test_reference_erasure_holds_presence_even_with_enough_new_ink(self):
        base, spec = inputs()
        moved = sample(mark=((2, 2), (3, 2), (3, 3), (4, 3)), erase=((2, 5),))
        result = model.inspect(moved, base, spec)
        self.assertEqual(result["status"], "registration_uncertain")
        self.assertEqual(result["removed_pixels"], 1)

    def test_wrong_anchor_and_scattered_noise(self):
        src, spec = inputs(blank_sha256="0"*64)
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.inspect(src, src, spec)
        _, spec = inputs()
        result = model.inspect(sample(mark=((2, 2), (4, 2), (6, 2), (8, 2))), src, spec)
        self.assertEqual(result["largest_component"], 1)
        self.assertEqual(result["status"], "not_detected")
