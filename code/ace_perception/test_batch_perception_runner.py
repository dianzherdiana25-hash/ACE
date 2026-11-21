"""Verifier budget logis, katalog operasi, dan sumber file tertambat."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import batch_perception_runner as model
from ace_perception.test_ocr_engine import canvas, font, raster


def plan(jobs, byte_budget=100000, attempts=10):
    return model._canonical({"schema": "ace.perception-batch.v1", "plan_ref": "fixture/batch",
                             "maximum_bytes": byte_budget, "maximum_attempts": attempts, "jobs": jobs})


def job(key, sources, name="scene", **policy):
    return {"id": key, "operation": name, "inputs": sources, "parameters": policy}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory()))
        self.image = self.write("page.pgm", raster(canvas(["HAT"])))
        self.font = self.write("font.json", font())

    def write(self, name, payload):
        (self.path/name).write_bytes(payload)
        return {"path": name, "sha256": sha256(payload).hexdigest(), "bytes": len(payload)}

    def test_reported_failures_and_budget_deferrals_keep_roster_order(self):
        changed = {**self.image, "sha256": "f"*64}
        queued = [job("valid", [self.image, self.font], "ocr"), job("tampered", [changed]),
                  job("end", [self.image]), job("later", [self.image])]
        result = model.run(self.path, plan(queued, attempts=3))
        self.assertEqual(result["attempted"], 3)
        self.assertEqual(result["counts"], {"failed": 1, "reported": 2, "skipped_budget": 1})
        before, error, decoded, skipped = result["jobs"]
        self.assertEqual(before["result"]["text"], "HAT")
        self.assertEqual(before["result_sha256"], model._sha(before["result"]))
        self.assertEqual(error["reasons"], ["source_verification_failed"])
        self.assertEqual(decoded["operation"], "scene")
        self.assertEqual(skipped["reasons"], ["attempt_budget"])
        self.assertEqual(result["reserved_bytes"], self.image["bytes"]*3+self.font["bytes"])

    def test_skips_expensive_job_and_continues_if_smaller_one_fits(self):
        one = job("too-large", [self.image, self.font], "ocr")
        two = job("fits", [self.image])
        result = model.run(self.path, plan([one, two], byte_budget=self.image["bytes"]))
        self.assertEqual(result["attempted"], 1)
        self.assertEqual(result["jobs"][0]["reasons"], ["byte_budget"])
        self.assertEqual(result["jobs"][1]["status"], "reported")

    def test_bad_operation_settings_cannot_enable_execution_or_path_escape(self):
        for entry in (job("a", [self.image], "shell"),
                      job("a", [self.image], command="fixture"),
                      job("a", [{**self.image, "path": "../outside.pgm"}])):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                model.run(self.path, plan([entry]))

    def test_symlink_not_followed_but_nested_regular_file_is_verified(self):
        (self.path/"nested").mkdir()
        source = self.write("nested/good.pgm", raster(canvas(["OH"])))
        (self.path/"link").symlink_to(self.path/"nested", target_is_directory=True)
        (self.path/"dangling.pgm").symlink_to("nested/good.pgm")
        queued = [job("regular", [source]), job("directory-link", [{**source, "path": "link/good.pgm"}]),
                  job("file-link", [{**source, "path": "dangling.pgm"}])]
        result = model.run(self.path, plan(queued))
        self.assertEqual([item["status"] for item in result["jobs"]], ["reported", "failed", "failed"])
        self.assertEqual(sha256((self.path/"nested/good.pgm").read_bytes()).hexdigest(), source["sha256"])

    def test_decoder_failure_and_declared_size_smaller_or_larger_are_explicit(self):
        invalid = self.write("broken.pgm", b"not an image")
        jobs = [job("decode-error", [invalid]), job("smaller", [{**self.image, "bytes": self.image["bytes"]-1}]),
                job("larger", [{**self.image, "bytes": self.image["bytes"]+1}])]
        result = model.run(self.path, plan(jobs))
        self.assertEqual([item["reasons"] for item in result["jobs"]], [
            ["decoder_or_settings_failed"], ["source_verification_failed"], ["source_verification_failed"]])
        self.assertEqual(result["attempted"], 3)
