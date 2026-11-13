import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ace_operational.distractor_inoculation import (
    DistractorRegistryError, inject, load_registry,
    run_battery)

GOOD = {
    "schema": "ace.distractor_registry.v1",
    "distractors": [{
        "id": "d1",
        "key": "('name_swap', (5, 2, 3, 0, 1, 4), 'nc')",
        "mechanism": "search-path diversion",
        "witness_tasks": ["t-020", "t-021"],
        "witness_universe": "band X control split",
        "catalog_context": "60 keys",
        "evidence": {"stage1": "LOO restores"},
        "registered": "2026-11-13"}]}


def write_reg(tmp, obj):
    p = Path(tmp) / "reg.json"
    p.write_text(json.dumps(obj))
    return p


class RegistryTests(unittest.TestCase):
    def test_load_good(self):
        with tempfile.TemporaryDirectory() as tmp:
            recs = load_registry(write_reg(tmp, GOOD))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["_key_tuple"],
                         ("name_swap", (5, 2, 3, 0, 1, 4), "nc"))

    def test_schema_mismatch_fails_closed(self):
        bad = dict(GOOD, schema="ace.other.v9")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DistractorRegistryError):
                load_registry(write_reg(tmp, bad))

    def test_missing_evidence_fails_closed(self):
        bad = json.loads(json.dumps(GOOD))
        bad["distractors"][0]["evidence"] = {}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DistractorRegistryError):
                load_registry(write_reg(tmp, bad))

    def test_unparseable_key_fails_closed(self):
        bad = json.loads(json.dumps(GOOD))
        bad["distractors"][0]["key"] = "not a (tuple"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DistractorRegistryError):
                load_registry(write_reg(tmp, bad))

    def test_seed_registry_loads(self):
        path = Path(__file__).resolve().parent / \
            "distractor_registry.json"
        recs = load_registry(path)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["witness_tasks"],
                         ["catalog_control-020",
                          "catalog_control-021"])


class BatteryTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.registry = load_registry(write_reg(tmp, GOOD))
        self.key = ("name_swap", (5, 2, 3, 0, 1, 4), "nc")

    def test_inject_appends_iff_absent(self):
        self.assertEqual(inject(["a"], self.key),
                         ["a", self.key])
        self.assertEqual(inject([self.key], self.key),
                         [self.key])

    def test_susceptible_flag(self):
        def solve(task_id, keys):
            return self.key not in keys
        rep = run_battery(catalog_keys=["a", "b"],
                          solve=solve, registry=self.registry)
        self.assertEqual(rep["overall"], "SUSCEPTIBLE")
        w = rep["distractors"][0]["witnesses"]
        self.assertTrue(all(x["diverted"] for x in w))

    def test_not_susceptible(self):
        rep = run_battery(catalog_keys=["a"],
                          solve=lambda t, k: True,
                          registry=self.registry)
        self.assertEqual(rep["overall"], "NOT_SUSCEPTIBLE")

    def test_clean_failure_is_not_diversion(self):
        rep = run_battery(catalog_keys=["a"],
                          solve=lambda t, k: False,
                          registry=self.registry)
        self.assertEqual(rep["overall"], "NOT_SUSCEPTIBLE")
        w = rep["distractors"][0]["witnesses"][0]
        self.assertFalse(w["diverted"])


if __name__ == "__main__":
    unittest.main()
