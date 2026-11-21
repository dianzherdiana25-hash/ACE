"""Verifier seluruh piksel wilayah sensitif dan kegagalan anotasi wajib."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import _raster, _vision, media_redactor as model


def data():
    return _vision.encode(6, 5, list(range(30)), 31)


def plan(*, marks=None, needed=None, **options):
    rows = [{"id": "plate", "class": "plate", "source_ref": "fixture/annotations/2", "box": [4, 3, 6, 5]},
            {"id": "label", "class": "text", "source_ref": "fixture/annotations/1", "box": [1, 1, 4, 3]}]
    request = {"schema": "ace.perception-redactions.v1", "source_sha256": sha256(data()).hexdigest(),
               "mask_level": 31, "padding_px": 1, "annotations": rows if marks is None else marks,
               "required_ids": ["label", "plate"] if needed is None else needed}
    return model._canonical({**request, **options})


class RedactorTests(unittest.TestCase):
    def test_overlap_padding_and_untouched_pixels_verified_from_export(self):
        artifact, result = model.redact(data(), plan())
        out = _raster.decode(artifact)
        boxes = [[0, 0, 5, 4], [3, 2, 6, 5]]
        self.assertEqual([row["box"] for row in result["areas"]], boxes)
        self.assertEqual(out.maximum, 31)
        marked = set()
        for index, level in enumerate(out.pixels):
            x, y = index%6, index//6
            inside = any(a<=x<c and b<=y<d for a,b,c,d in boxes)
            if inside:
                marked.add(index)
            self.assertEqual(level, 31 if inside else index)
        self.assertEqual(result["covered_pixels"], len(marked))
        self.assertEqual(result["status"], "redacted")
        self.assertEqual(result["output_sha256"], sha256(artifact).hexdigest())
        self.assertTrue(model.verify(data(), plan(), artifact)["verified"])
        self.assertFalse(model.verify(data(), plan(), data())["verified"])

    def test_missing_or_empty_roster_holds_artifact_and_verification(self):
        artifact, result = model.redact(data(), plan(marks=[]))
        self.assertIsNone(artifact)
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["missing_ids"], ["label", "plate"])
        self.assertEqual(result["reason"], "required_annotations_missing")
        with self.assertRaisesRegex(ValueError, "Tidak ada"):
            model.verify(data(), plan(marks=[]), data())
        _, report = model.redact(data(), plan(marks=[], needed=[]))
        self.assertEqual(report["reason"], "no_annotations")

    def test_wrong_hash_bad_geometry_and_wrong_mask_depth_rejected(self):
        for changes in ({"source_sha256": "0"*64}, {"mask_level": 32}, {"padding_px": True},
                        {"required_ids": ["same", "same"]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.redact(data(), plan(**changes))
        row = {"id": "x", "class": "face", "source_ref": "fixture/face", "box": [0, 0, 99, 100]}
        with self.assertRaisesRegex(ValueError, "di luar"):
            model.redact(data(), plan(marks=[row], needed=[]))

    def test_cli_output_cannot_overwrite_input_and_hash_matches(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        image, spec, out = [root/name for name in ("before.pgm", "plan.json", "after.pgm")]
        image.write_bytes(data())
        spec.write_bytes(plan())
        args = [sys.executable, "-m", "ace_perception.media_redactor", str(image), str(spec)]
        run = subprocess.run([*args, "--output", str(out)], capture_output=True, check=True)
        report = json.loads(run.stdout)
        self.assertEqual(sha256(out.read_bytes()).hexdigest(), report["output_sha256"])
        verify = subprocess.run([*args, "--verify", str(out)], capture_output=True, check=True)
        self.assertTrue(json.loads(verify.stdout)["verified"])
        self.assertEqual(subprocess.run([*args, "--output", str(image)], capture_output=True).returncode, 2)
        self.assertEqual(image.read_bytes(), data())
