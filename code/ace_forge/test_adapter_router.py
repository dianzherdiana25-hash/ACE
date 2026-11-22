"""Verifier pembatas basis, fallback, dan ranking adaptor yang ditinjau."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import adapter_router as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_adapter_zoo import ALT, BASE, artifact, fixture as zoo_fixture, row


def query(key, **extra):
    return {"id": key, "query_ref": f"fixture/query/{key}", "domain": "code", "base_sha256": BASE,
            "layer": "fixture/dense", "features": 2, "outputs": 1,
            "capabilities": ["rank"], "maximum_rank": 2, "allow_general": False, **extra}


def fixture():
    catalog, payloads = zoo_fixture()
    additions = [
        ("general", artifact(4), {"domain": "*", "caps": ["rank", "translate"]}),
        ("small", artifact(5), {"caps": ["rank"]}),
        ("larger", artifact(6, rank=2), {"caps": ["rank"]}),
        ("tune", artifact(7, base=ALT), {"caps": ["rank"]}),
        ("different_shape", artifact(8, width=3), {"caps": ["rank"]}),
    ]
    for name, payload, kwargs in additions:
        catalog["entries"].append(row(name, 1, payload, **kwargs))
        payloads.append(payload)
    queries = [query("exact"), query("general", allow_general=True, capabilities=["translate"]),
               query("not-allowed", domain="other"), query("missing", capabilities=["ocr"]),
               query("different", base_sha256="f"*64)]
    request = {"request_ref": "fixture/routing", "catalog_sha256": identity(catalog), "queries": queries}
    return request, catalog, payloads


def route(request, catalog, payloads):
    return model.route(request, catalog, payloads, identity(request))


def by_name(result):
    return {row["id"]: row for row in result["routes"]}


class AdapterRouterTests(unittest.TestCase):
    def test_domain_then_surplus_then_rank_determine_selection(self):
        bundle = fixture()
        results = route(*bundle)
        first = by_name(results)["exact"]
        self.assertEqual(first["status"], "exact_domain")
        self.assertEqual(first["selection"]["name"], "small")
        self.assertEqual(first["selection"]["rank"], 1)
        self.assertEqual(first["selection"]["surplus_capabilities"], 0)
        self.assertEqual(first["compatible_artifacts"], 6)
        self.assertEqual(first["eligible_artifacts"], 3)
        self.assertEqual(first["rejection_counts"], {"domain_mismatch": 2, "not_qualified": 1})
        self.assertEqual(first["selection"]["review_ref"], "fixture/review/small/1")
        self.assertEqual(first["selection"]["artifact_sha256"], identity(bundle[2][4]))

    def test_explicit_general_fallback_and_unrouted_reason(self):
        results = by_name(route(*fixture()))
        general = results["general"]
        self.assertEqual(general["status"], "general_fallback")
        self.assertEqual(general["selection"]["name"], "general")
        for key in ("missing", "not-allowed"):
            self.assertEqual(results[key]["reason"], "no_eligible_adapter")
            self.assertIsNone(results[key]["selection"])
        self.assertEqual(results["different"]["reason"], "no_compatible_layout")
        self.assertEqual(results["different"]["compatible_artifacts"], 0)

    def test_fallback_happens_only_when_same_domain_unavailable(self):
        request, catalog, payloads = fixture()
        request["queries"] = [query("explicit", allow_general=True), query("other", allow_general=True, domain="other")]
        routes = by_name(route(request, catalog, payloads))
        self.assertEqual(routes["explicit"]["status"], "exact_domain")
        self.assertEqual(routes["other"]["status"], "general_fallback")

    def test_no_cross_base_layer_or_tensor_dimensions(self):
        request, catalog, payloads = fixture()
        request["queries"] = [query("alt", base_sha256=ALT), query("width", features=3),
                              query("layer", layer="other"), query("output", outputs=3)]
        routes = by_name(route(request, catalog, payloads))
        self.assertEqual(routes["alt"]["selection"]["name"], "tune")
        self.assertEqual(routes["width"]["selection"]["name"], "different_shape")
        self.assertIsNone(routes["layer"]["selection"])
        self.assertIsNone(routes["output"]["selection"])

    def test_qualified_preference_for_higher_version_after_same_name_and_rank(self):
        request, catalog, payloads = fixture()
        latest = catalog["entries"][1]
        latest["review"] = {"status": "qualified", "review_ref": "test/review/latest", "held_out_sha256": "d"*64}
        request["catalog_sha256"] = identity(catalog)
        request["queries"] = [query("versions", capabilities=["rank", "review"])]
        candidate = route(request, catalog, payloads)["routes"][0]["selection"]
        self.assertEqual((candidate["name"], candidate["version"]), ("alpha", 2))

    def test_rank_bound_inclusive(self):
        request, catalog, payloads = fixture()
        catalog["entries"][5]["capabilities"].append("special")
        request["catalog_sha256"] = identity(catalog)
        request["queries"] = [query("fit", capabilities=["special"], maximum_rank=2),
                              query("limit", capabilities=["special"], maximum_rank=1)]
        results = by_name(route(request, catalog, payloads))
        self.assertEqual(results["fit"]["selection"]["name"], "larger")
        self.assertEqual(results["limit"]["rejection_counts"]["rank_limit"], 1)
        self.assertIsNone(results["limit"]["selection"])

    def test_request_anchor_and_joined_catalog_anchor(self):
        request, catalog, payloads = fixture()
        original = identity(request)
        request["queries"][0]["capabilities"] = ["new"]
        with self.assertRaisesRegex(model.InputError, "routing.*anchor"):
            model.route(request, catalog, payloads, original)
        catalog["catalog_ref"] = "fixture/moved"
        with self.assertRaisesRegex(model.InputError, "Katalog.*anchor"):
            route(request, catalog, payloads)

    def test_explicit_review_requirement_and_retired_version(self):
        request, catalog, payloads = fixture()
        retired = catalog["entries"][4]["review"]
        retired["status"] = "retired"
        request["catalog_sha256"] = identity(catalog)
        outcome = by_name(route(request, catalog, payloads))["exact"]
        self.assertEqual(outcome["selection"]["name"], "larger")
        self.assertEqual(outcome["rejection_counts"]["not_qualified"], 2)

    def test_duplicate_query_refs_and_malformed_contracts_rejected(self):
        request, catalog, payloads = fixture()
        for changed in ({"query_ref": request["queries"][0]["query_ref"]}, {"id": "exact"},
                        {"allow_general": 1}, {"maximum_rank": True}, {"features": 0}):
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                route({**request, "queries": [request["queries"][0], query("invalid", **changed)]}, catalog, payloads)

    def test_coverage_distinguishes_failures_from_fallbacks(self):
        request, catalog, payloads = fixture()
        report = route(request, catalog, payloads)
        self.assertEqual(report["coverage"], [
            {"domain": "code", "queries": 4, "exact_domain": 1, "general_fallback": 1, "unrouted": 2},
            {"domain": "other", "queries": 1, "exact_domain": 0, "general_fallback": 0, "unrouted": 1},
        ])
        request["queries"].reverse()
        self.assertEqual(route(request, catalog, payloads)["routes"], report["routes"])

    def test_cli_deterministic_and_no_mutation_of_inputs(self):
        request, catalog, payloads = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        paths = [root / name for name in ("request", "catalog", "payloads")]
        expected = [canonical(item) for item in (request, catalog, payloads)]
        for path, data in zip(paths, expected, strict=True):
            path.write_bytes(data)
        args = [*map(str, paths), "--expect-request-sha256", identity(request)]
        with redirect_stdout(StringIO()) as out, redirect_stdout(StringIO()) as second:
            self.assertEqual(model.main(args), 0)
        with redirect_stdout(out):
            self.assertEqual(model.main(args), 0)
        self.assertEqual(out.getvalue(), second.getvalue())
        self.assertEqual(json.loads(out.getvalue()), route(request, catalog, payloads))
        self.assertEqual([path.read_bytes() for path in paths], expected)

    def test_canonical_tie_after_rank_uses_name_before_version(self):
        request, catalog, payloads = fixture()
        payload = artifact(17)
        payloads.append(payload)
        catalog["entries"].append(row("aardvark", 1, payload, caps=["rank"]))
        request["catalog_sha256"] = identity(catalog)
        exact = by_name(route(request, catalog, payloads))["exact"]
        self.assertEqual(exact["selection"]["name"], "aardvark")
        self.assertEqual(exact["eligible_artifacts"], 4)

    def test_empty_queries_or_catalog_report_observed_coverage(self):
        request, catalog, payloads = fixture()
        empty = {**catalog, "entries": []}
        request["catalog_sha256"] = identity(empty)
        result = route(request, empty, [])
        self.assertEqual(len(result["routes"]), len(request["queries"]))
        self.assertTrue(all(row["status"] == "unrouted" for row in result["routes"]))
        request["queries"] = []
        self.assertEqual(route(request, empty, [])["coverage"], [])
