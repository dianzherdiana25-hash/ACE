"""Verifier cabang lisensi, notice hilang, dan provenans terpisah."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import license_guard as model
from ace_forge._forge_io import canonical, identity
from ace_forge.dataset_custody import seal
from ace_forge.dataset_forge import forge
from ace_forge.test_dataset_custody import wire
from ace_forge.test_dataset_forge import proof, source


def policy():
    return {"policy_ref": "fixture/policy", "licenses": [
        {"term": key, "training": status, "obligations": required, "rule_ref": f"fixture/rule/{index}"}
        for index, (key, status, required) in enumerate((
            ("Allowed-A", "allow", ["attribution"]), ("Allowed-B", "allow", ["notice"]),
            ("Denied", "deny", []), ("Allowed-A WITH Exception-1", "allow", []),
        ))
    ]}


def fixture():
    expressions = {"eligible": "Allowed-A", "missing": "Allowed-A AND Allowed-B",
                   "choice": "Allowed-A OR Denied", "deny": "Denied", "unknown": "Unknown",
                   "syntax": "(Allowed-A", "excepted": "Allowed-A WITH Exception-1"}
    records = [source(key) for key in expressions]
    result, _ = forge({"examples": records, "seed": 52, "held_out_basis_points": 0,
                       "allowed_licenses": sorted(set(expressions.values()))},
                      {"index_ref": "fixture/verification", "records": [
                          proof(row, license_id=expressions[row["event_id"]]) for row in records]})
    raw = wire(result)
    manifest = seal(raw, "fixture/dataset")
    rules = policy()
    index = {"index_ref": "fixture/license-sources", "sources": [
        {"evidence_ref": f"fixture/evidence/{key}", "source_ref": f"fixture/source/{key}",
         "notices": {"attribution": f"fixture/author/{key}"} if key != "excepted" else {}}
        for key in expressions
    ]}
    return raw, manifest, manifest["head_sha256"], rules, identity(rules), index


class LicenseTests(unittest.TestCase):
    def test_reports_each_alternative_and_required_notices(self):
        result = model.audit(*fixture())
        self.assertEqual(result["counts"], {"blocked": 1, "eligible": 3, "review": 3})
        by_id = {row["event_id"]: row for row in result["records"]}
        self.assertEqual(by_id["choice"]["status"], "eligible")
        self.assertEqual([row["status"] for row in by_id["choice"]["options"]], ["eligible", "blocked"])
        self.assertEqual(by_id["choice"]["options"][0]["notice_refs"], {"attribution": "fixture/author/choice"})
        self.assertEqual(by_id["choice"]["options"][0]["rule_refs"], {"Allowed-A": "fixture/rule/0"})
        self.assertEqual(by_id["missing"]["options"][0]["missing_notices"], ["notice"])
        self.assertEqual(by_id["missing"]["source_ref"], "fixture/source/missing")
        self.assertEqual(by_id["syntax"]["diagnostic"], "invalid_expression")
        self.assertEqual(by_id["excepted"]["status"], "eligible")

    def test_precedence_distribution_and_parenthesized_license_alternatives(self):
        self.assertEqual(model.alternatives("A OR B AND C"), [("A",), ("B", "C")])
        self.assertEqual(model.alternatives("(A OR B) AND (C OR A)"),
                         [("A",), ("A", "B"), ("A", "C"), ("B", "C")])
        self.assertEqual(model.alternatives("A WITH E OR A WITH E"), [("A WITH E",)])

    def test_vacuous_malformed_or_explosive_expression_fails(self):
        many = " AND ".join(f"(A{i} OR B{i})" for i in range(8))
        for raw in ("", "A and B", "A OR", "(A OR B))", "A WITH AND", "(A) WITH E", many):
            with self.subTest(raw=raw), self.assertRaises(model.InputError):
                model.alternatives(raw)

    def test_known_base_does_not_resolve_unknown_exception(self):
        _, catalog = model._policy(policy())
        result = model._option(("Allowed-A WITH Unknown",), catalog, "fixture/example", {})
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["unresolved_terms"], ["Allowed-A WITH Unknown"])
        self.assertEqual(result["rule_refs"], {})

    def test_missing_mapping_holds_example_even_with_permissive_expression(self):
        data, manifest, head, rules, anchor, mapping = fixture()
        mapping["sources"] = [row for row in mapping["sources"] if not row["evidence_ref"].endswith("/excepted")]
        result = model.audit(data, manifest, head, rules, anchor, mapping)
        row = next(item for item in result["records"] if item["event_id"] == "excepted")
        self.assertEqual(row["status"], "review")
        self.assertEqual(row["diagnostic"], "unmapped_source")

    def test_integrity_failures_and_catalog_validation_are_separate(self):
        data, manifest, head, rules, anchor, mapping = fixture()
        with self.assertRaisesRegex(model.InputError, "kustodi"):
            model.audit(data, manifest, "0" * 64, rules, anchor, mapping)
        rules["licenses"][0]["training"] = "unknown"
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.audit(data, manifest, head, rules, anchor, mapping)
        with self.assertRaisesRegex(model.InputError, "izin"):
            model.audit(data, manifest, head, rules, identity(rules), mapping)

    def test_cli_reads_original_evidence_and_holds_noneligible_rows(self):
        data, manifest, head, rules, anchor, mapping = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        dataset, pol, idx, man = (root / name for name in ("data.jsonl", "policy.json", "index.json", "manifest.json"))
        dataset.write_bytes(data)
        for file, value in ((pol, rules), (idx, mapping), (man, manifest)):
            file.write_bytes(canonical(value))
        with redirect_stdout(StringIO()) as output:
            code = model.main([str(dataset), str(pol), str(idx), "--manifest", str(man), "--expect-head", head,
                               "--expect-policy-sha256", anchor])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue()), model.audit(data, manifest, head, rules, anchor, mapping))
        self.assertEqual(dataset.read_bytes(), data)
