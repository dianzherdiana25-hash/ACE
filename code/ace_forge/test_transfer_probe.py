"""Verifier baseline bersama, matriks transfer, dan bukti yang kurang."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import transfer_probe as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


BASE = "a" * 64
ADAPTERS = {"a": "b" * 64, "b": "c" * 64}


def result(ref, artifact, passed):
    return {"receipt_ref": ref, "artifact_sha256": artifact, "passed": passed}


def fixture():
    sources = [{"domain": domain, "artifact_sha256": artifact, "training_ref": f"fixture/train/{domain}",
                "training_families": [f"train/{domain}"]} for domain, artifact in ADAPTERS.items()]
    cases = [{"id": f"{domain}{i}", "domain": domain, "family_id": f"held/{domain}",
              "case_ref": f"fixture/case/{domain}{i}"} for domain in "ab" for i in range(2)]
    baseline = [{"case_id": q["id"], "result": result(f"fixture/base/{q['id']}", BASE, q["id"].endswith("0"))}
                for q in cases]
    adapted = [{"case_id": key, "source_domain": source,
                "result": result(f"fixture/after/{source}/{key}", ADAPTERS[source], label)}
               for (source, key), label in {
                   ("a", "a0"): True, ("a", "a1"): True, ("a", "b0"): False, ("a", "b1"): False,
                   ("b", "a0"): True, ("b", "a1"): False, ("b", "b0"): True,
               }.items()]
    protocol = {"protocol_ref": "fixture/matrix", "baseline_sha256": BASE, "minimum_per_cell": 2,
                "sources": sources, "target_cases": cases}
    return protocol, {"baseline": baseline, "adapted": adapted}


def run(protocol, evidence):
    return model.measure(protocol, evidence, identity(protocol))


class TransferTests(unittest.TestCase):
    def test_computes_all_ordered_cells_and_does_not_impute_missing_delta(self):
        result_ = run(*fixture())
        found = {(row["source_domain"], row["target_domain"]): row for row in result_["cells"]}
        self.assertEqual(found["a", "a"]["delta"], q(1, 2))
        self.assertEqual(found["a", "b"]["delta"], q(-1, 2))
        self.assertEqual(found["b", "a"]["delta"], q(0))
        self.assertIsNone(found["b", "b"]["delta"])
        self.assertEqual(found["b", "b"]["cases"][-1]["outcome"], "missing")
        self.assertEqual(found["a", "b"]["cases"][0]["before"], found["b", "b"]["cases"][0]["before"])
        self.assertEqual(result_["cross"], {"cells": 2, "measured_cells": 2, "observed_mean_delta": q(-1, 4)})
        self.assertEqual(result_["within"], {"cells": 2, "measured_cells": 1, "observed_mean_delta": q(1, 2)})

    def test_missing_baseline_withholds_every_cell_that_depends_on_case(self):
        protocol, evidence = fixture()
        evidence["baseline"].pop(0)
        report = run(protocol, evidence)
        for row in report["cells"]:
            if row["target_domain"] == "a":
                self.assertIsNone(row["delta"])
                self.assertEqual(row["paired"], 1)
        self.assertEqual(report["within"]["measured_cells"], 0)

    def test_raises_sample_floor_without_dropping_coverage(self):
        protocol, evidence = fixture()
        protocol["minimum_per_cell"] = 3
        result_ = run(protocol, evidence)
        self.assertEqual(result_["cross"]["measured_cells"], 0)
        first = result_["cells"][0]
        self.assertEqual(first["paired"], 2)
        self.assertEqual(first["status"], "insufficient_evidence")
        self.assertIsNone(first["delta"])

    def test_cross_family_leakage_and_protocol_anchor_are_end_to_end(self):
        protocol, evidence = fixture()
        checked = identity(protocol)
        protocol["target_cases"][0]["family_id"] = "train/b"
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.measure(protocol, evidence, checked)
        with self.assertRaisesRegex(model.InputError, "tumpang tindih"):
            run(protocol, evidence)

    def test_unregistered_or_conflicting_evidence_is_refused(self):
        for update in ({"case_id": "unknown"}, {"source_domain": "unknown"},
                       {"result": result("fixture/other", ADAPTERS["b"], True)},
                       {"result": result("fixture/other", ADAPTERS["a"], 0)}):
            protocol, evidence = fixture()
            evidence["adapted"][0].update(update)
            with self.subTest(update=update), self.assertRaises(model.InputError):
                run(protocol, evidence)

    def test_baseline_must_have_one_receipt_per_question_and_be_used_for_each_source(self):
        protocol, evidence = fixture()
        item = evidence["baseline"][0]
        evidence["baseline"].append({**item, "result": result("fixture/new", BASE, False)})
        with self.assertRaisesRegex(model.InputError, "baseline ganda"):
            run(protocol, evidence)

    def test_separate_state_when_all_pairs_unobserved(self):
        protocol, _ = fixture()
        result_ = run(protocol, {"baseline": [], "adapted": []})
        self.assertEqual(len(result_["cells"]), 4)
        self.assertTrue(all(row["counts"] == {"missing": 2} for row in result_["cells"]))
        self.assertIsNone(result_["within"]["observed_mean_delta"])
        self.assertIsNone(result_["cross"]["observed_mean_delta"])

    def test_cli_is_read_only_and_provides_provenance_for_all_arms(self):
        protocol, evidence = fixture()
        folder = Path(self.enterContext(TemporaryDirectory()))
        p, e = folder / "protocol.json", folder / "evidence.json"
        p.write_bytes(canonical(protocol))
        e.write_bytes(canonical(evidence))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(p), str(e), "--expect-protocol-sha256", identity(protocol)]), 0)
        self.assertEqual(json.loads(output.getvalue()), run(protocol, evidence))
        self.assertEqual(e.read_bytes(), canonical(evidence))
        self.assertEqual(run(protocol, evidence)["sources"]["b"]["training_ref"], "fixture/train/b")

    def test_distinct_sources_may_not_point_to_same_artifact_or_original_baseline(self):
        for artifact in (BASE, ADAPTERS["a"]):
            protocol, evidence = fixture()
            protocol["sources"][1]["artifact_sha256"] = artifact
            with self.subTest(artifact=artifact), self.assertRaisesRegex(model.InputError, "ganda"):
                run(protocol, evidence)

    def test_evidence_array_order_changes_binding_but_not_observed_matrix(self):
        protocol, evidence = fixture()
        first = run(protocol, evidence)
        for key in evidence:
            evidence[key].reverse()
        other = run(protocol, evidence)
        self.assertNotEqual(first.pop("evidence_sha256"), other.pop("evidence_sha256"))
        self.assertEqual(first, other)

    def test_only_cell_means_enter_macro_even_with_unequal_domain_sizes(self):
        protocol, evidence = fixture()
        protocol["minimum_per_cell"] = 1
        protocol["target_cases"].pop()
        evidence["baseline"].pop()
        evidence["adapted"] = [row for row in evidence["adapted"] if row["case_id"] != "b1"]
        value = run(protocol, evidence)
        self.assertEqual(value["cross"]["measured_cells"], 2)
        self.assertEqual(value["cross"]["observed_mean_delta"], q(-1, 2))
        self.assertEqual(value["within"]["observed_mean_delta"], q(1, 4))

    def test_receipt_cannot_certify_two_distinct_observations(self):
        protocol, evidence = fixture()
        first = evidence["adapted"][0]["result"]
        evidence["adapted"][1]["result"]["receipt_ref"] = first["receipt_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            run(protocol, evidence)

    def test_missing_observed_limb_preserves_other_source_pointer(self):
        protocol, evidence = fixture()
        evidence["adapted"][0]["result"] = None
        cell = run(protocol, evidence)["cells"][0]
        self.assertEqual(cell["counts"]["missing"], 1)
        self.assertEqual(cell["cases"][0]["before"]["receipt_ref"], "fixture/base/a0")
        self.assertIsNone(cell["cases"][0]["after"])
