"""Tests for catalog_artifact (G4 prerequisite P-G4-2;
dossier design: bench Task 08, gap G-1).

The shipped-artifact tests pin the materialised v4
catalog to the ratified candidate description in
Task 08 §2 (per-class admitted counts and exact string
forms). The materialiser tests use synthetic evidence in
temp dirs — deterministic, seconds.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ace_operational import catalog_artifact
from ace_operational.catalog_artifact import (
    classes_digest, load_catalog, materialize, verify_catalog)

EXPECTED_COUNTS = {"bounds_off_by_one": (3, 1),
                   "dist_step_2": (1, 0),
                   "returns_start_distance": (1, 1),
                   "wall_char_x": (1, 0)}


class ShippedCatalogTests(unittest.TestCase):

    def test_shipped_artifact_verifies(self):
        report = verify_catalog()
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["artifact_digest"],
                         report["recomputed_digest"])

    def test_shipped_artifact_matches_task08_candidate(self):
        artifact = load_catalog()
        self.assertEqual(artifact["artifact_name"],
                         "operator_catalog_v4")
        counts = {cls: (len(rec["operators"]), len(rec["chains"]))
                  for cls, rec in artifact["classes"].items()}
        self.assertEqual(counts, EXPECTED_COUNTS)
        total_ops = sum(c[0] for c in counts.values())
        total_chains = sum(c[1] for c in counts.values())
        self.assertEqual((total_ops, total_chains), (6, 2))

    def test_exact_string_forms_preserved(self):
        artifact = load_catalog()
        bounds = artifact["classes"]["bounds_off_by_one"]
        self.assertIn("('binop_swap', (5, 2, 3, 0, 1, 4), 'Mult')",
                      bounds["operators"])
        self.assertIn(
            "(('return_indices', (6,), ('gr', 'gc')), "
            "('binop_swap', (5, 2, 3, 0, 1, 4), 'Mult'))",
            bounds["chains"])
        returns = artifact["classes"]["returns_start_distance"]
        self.assertEqual(returns["operators"],
                         ["('return_indices', (6,), ('gr', 'gc'))"])

    def test_digest_is_sha256_over_canonical_payload(self):
        # Independent re-derivation (P-G4-2 reproducibility
        # discipline): rebuild the canonical payload from
        # the artifact's classes and compare digests.
        artifact = load_catalog()
        payload = json.dumps(
            {"artifact_name": "operator_catalog_v4",
             "classes": artifact["classes"]},
            sort_keys=True, separators=(",", ":"),
            ensure_ascii=False).encode("utf-8")
        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                         artifact["artifact_digest"])
        self.assertEqual(classes_digest(artifact["classes"]),
                         artifact["artifact_digest"])


class MaterialiserTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _evidence(self):
        return {"by_class": {
            "zeta_class": {
                "admitted_operators": ["('op_b', (1,), 2)",
                                       "('op_a', (1,), 1)"],
                "admitted_chains": []},
            "alpha_class": {
                "admitted_operators": [],
                "admitted_chains": ["(('op_a', (1,), 1),)"]}}}

    def _write_evidence(self):
        path = self.dir / "evidence.json"
        path.write_text(json.dumps(self._evidence()))
        return path

    def test_materialize_is_deterministic_and_sorted(self):
        evidence = self._write_evidence()
        one = self.dir / "one.json"
        two = self.dir / "two.json"
        materialize(evidence, one)
        materialize(evidence, two)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        artifact = json.loads(one.read_text())
        self.assertEqual(
            artifact["classes"]["zeta_class"]["operators"],
            ["('op_a', (1,), 1)", "('op_b', (1,), 2)"])
        self.assertEqual(
            artifact["source_evidence_sha256"],
            hashlib.sha256(evidence.read_bytes()).hexdigest())
        self.assertTrue(verify_catalog(one)["valid"])

    def test_tampered_artifact_fails_verification(self):
        evidence = self._write_evidence()
        out = self.dir / "catalog.json"
        materialize(evidence, out)
        artifact = json.loads(out.read_text())
        artifact["classes"]["zeta_class"]["operators"][0] = \
            "('op_forged', (9,), 9)"
        out.write_text(json.dumps(artifact))
        report = verify_catalog(out)
        self.assertFalse(report["valid"])
        self.assertTrue(any("digest" in p
                            for p in report["problems"]))
        with self.assertRaises(ValueError):
            load_catalog(out)

    def test_missing_evidence_structure_raises(self):
        bad = self.dir / "bad.json"
        bad.write_text(json.dumps({"no_by_class": {}}))
        with self.assertRaises(ValueError):
            materialize(bad, self.dir / "out.json")


if __name__ == "__main__":
    unittest.main()
