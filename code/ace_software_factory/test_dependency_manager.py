"""Verifier katalog, interval kebijakan, dan advisori offline."""
import unittest

from ace_software_factory import dependency_manager
from ace_software_factory._contracts import ContractError, identity


def span(low, high):
    return {"min_inclusive": low, "max_exclusive": high}


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"schema": "ace.factory-package-catalog.v1", "ref": "fixture/catalog", "packages": [
            {"name": "Sample_Tool", "releases": [
                {"version": version, "sha256": anchor * 64, "yanked": yanked}
                for version, anchor, yanked in (("1.4.0", "a", False), ("1.5.0", "b", False),
                                                  ("1.6.0", "c", True), ("1.7.0", "d", False), ("2.0.0", "e", False))]}]}
        self.advisories = {"schema": "ace.factory-package-advisories.v1", "ref": "fixture/advisories", "advisories": [
            {"id": "fixture-a", "package": "Sample.Tool", "affected": span("1.4.0", "1.7.0"),
             "source_ref": "fixture/advisories/0"}]}
        self.plan = {"schema": "ace.factory-dependency-plan.v1", "source_ref": "fixture/lock",
                     "catalog_sha256": identity(self.catalog), "advisories_sha256": identity(self.advisories),
                     "pins": [{"name": "sample-tool", "version": "1.4.0", "sha256": "a" * 64,
                               "allowed": span("1.0.0", "2.0.0"), "source_ref": "fixture/lock/2"}]}

    def inspect(self):
        return dependency_manager.inspect(self.plan, self.catalog, self.advisories, identity(self.plan))

    def test_respects_half_open_range_yanked_and_minimal_update_policy(self):
        row = self.inspect()["pins"][0]
        self.assertEqual(row["issues"], ["advisory_match"])
        self.assertEqual(row["advisories"][0]["id"], "fixture-a")
        self.assertEqual(row["next_allowed_pin"]["version"], "1.7.0")

    def test_unknown_or_mismatched_hash_is_not_reported_as_clean(self):
        self.plan["pins"][0]["sha256"] = "f" * 64
        self.assertIn("pin_hash_mismatch", self.inspect()["pins"][0]["issues"])
        self.plan["pins"][0]["version"] = "1.1.0"
        self.assertIn("pin_not_in_catalog", self.inspect()["pins"][0]["issues"])

    def test_refuses_duplicate_normalized_pin_and_unanchored_catalog(self):
        original = self.plan["pins"][0]
        self.plan["pins"].append({**original, "name": "SAMPLE.tool"})
        with self.assertRaisesRegex(ContractError, "ganda"):
            self.inspect()
        self.plan["pins"].pop()
        self.catalog["ref"] = "changed"
        with self.assertRaisesRegex(ContractError, "anchor"):
            self.inspect()
