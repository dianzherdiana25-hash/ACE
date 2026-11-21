"""Verifier pemeriksaan mekanis dan keluaran yang menyembunyikan kutipan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import safety_data_filter as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_dataset_forge import inputs, source


def policy():
    return {"policy_ref": "fixture/screen", "rules": [
        {"id": "prompt-policy", "scope": "prompt", "phrases": ["bendera kuning"]},
        {"id": "target-policy", "scope": "target", "phrases": ["terlalu jelas", "straße"]},
        {"id": "shared-policy", "scope": "both", "phrases": ["label panjang"]},
    ], "builtin_checks": sorted(model.BUILTINS)}


def fixture():
    request, _ = inputs(
        source("ready", prompt="Prompt baik.", target="Jawaban baik."),
        source("prompt", prompt="Gunakan BENDERA, kuning sekarang.", target="Netral."),
        source("target", prompt="Pertanyaan biasa.", target="Mulai terlalu jelas."),
        source("both", prompt="Contoh label panjang dan biasa.", target="LABEL PANJANG."),
        source("email", prompt="Satu alamat me@example.invalid", target="Netral."),
        source("key", prompt="Satu placeholder.", target="-----BEGIN FIXTURE PRIVATE KEY-----"),
        source("assignment", prompt="Contoh nama API_KEY=FAKE-FIXTURE-VALUE", target="Netral."),
    )
    return request, policy()


def apply(source, rules):
    return model.filter_candidates(source, rules, identity(rules))


class FilterTests(unittest.TestCase):
    def test_flagged_text_never_reaches_candidate_output_or_report(self):
        data, rules = fixture()
        filtered, report = apply(data, rules)
        self.assertEqual((report["examples"], report["passed"], report["held"]), (7, 1, 6))
        self.assertEqual([row["event_id"] for row in filtered["examples"]], ["ready"])
        self.assertEqual(report["rule_field_hits"], {
            "credential_assignment": 1, "email_marker": 1, "private_key_marker": 1,
            "prompt-policy": 1, "shared-policy": 2, "target-policy": 1,
        })
        self.assertEqual(report["findings"][1]["findings"], [
            {"rule_id": "shared-policy", "field": "prompt"}, {"rule_id": "shared-policy", "field": "target"},
        ])
        for sample in ("me@example.invalid", "FAKE-FIXTURE-VALUE", "BEGIN FIXTURE", "terlalu jelas", "BENDERA"):
            with self.subTest(sample=sample):
                self.assertNotIn(sample.encode(), canonical(report))
                self.assertNotIn(sample.encode(), canonical(filtered))

    def test_phrase_respects_token_boundary_and_configured_field(self):
        data, rules = fixture()
        data["examples"] = [source("a", prompt="terlalu jelas", target="bendera kuning"),
                            source("b", prompt="bendera kuningan", target="netral")]
        selected, report = apply(data, rules)
        self.assertEqual([row["event_id"] for row in selected["examples"]], ["a", "b"])
        self.assertEqual(report["findings"], [])

    def test_automaton_matches_overlapping_and_suffix_rules_at_same_offset(self):
        data, rules = fixture()
        rules["rules"] = [{"id": name, "scope": "both", "phrases": [term]}
                          for name, term in (("one", "utama bagian"), ("two", "bagian"), ("three", "bagian baru"))]
        data["examples"] = [source("hit", prompt="utama BAGIAN baru", target="lain")]
        findings = apply(data, rules)[1]["findings"][0]["findings"]
        self.assertEqual([row["rule_id"] for row in findings], ["one", "three", "two"])

    def test_nfkc_casefold_handles_wide_and_multichar_unicode(self):
        data, rules = fixture()
        data["examples"] = [source("converted", prompt="Biasa", target="ＳＴＲＡＳＳＥ")]
        filtered, report = apply(data, rules)
        self.assertEqual(filtered["examples"], [])
        self.assertEqual(report["findings"][0]["findings"], [{"rule_id": "target-policy", "field": "target"}])

    def test_optional_builtin_is_only_active_when_declared(self):
        data, rules = fixture()
        data["examples"] = [source("alias", target="test@example.invalid")]
        rules["builtin_checks"] = []
        self.assertEqual(apply(data, rules)[1]["passed"], 1)
        rules["builtin_checks"] = ["email_marker"]
        self.assertEqual(apply(data, rules)[1]["held"], 1)

    def test_invalid_or_empty_policy_never_passes_all_rows_by_default(self):
        data, rules = fixture()
        for change in ({"rules": [], "builtin_checks": []}, {"builtin_checks": ["secret"]},
                       {"rules": [{"id": "email_marker", "scope": "both", "phrases": ["test"]}]},
                       {"rules": [{"id": "blank", "scope": "both", "phrases": [" -- "]}]},
                       {"rules": [{"id": "dups", "scope": "target", "phrases": ["A B", "a b"]}]},
                       {"rules": [{"id": "other", "scope": "name", "phrases": ["safe"]}]}):
            with self.subTest(change=change), self.assertRaises(model.InputError):
                apply(data, {**rules, **change})

    def test_edited_rule_is_rejected_when_anchor_remains_fixed(self):
        data, rules = fixture()
        checksum = identity(rules)
        rules["rules"].pop()
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.filter_candidates(data, rules, checksum)

    def test_cli_defaults_to_text_free_report_and_explicit_filtered_option(self):
        data, rules = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        candidates, policy_path = root / "candidates.json", root / "policy.json"
        candidates.write_bytes(canonical(data))
        policy_path.write_bytes(canonical(rules))
        args = [str(candidates), str(policy_path), "--expect-policy-sha256", identity(rules)]
        expected, report = apply(data, rules)
        for flags, result in (([], report), (["--filtered"], expected)):
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main([*args, *flags]), 0)
            self.assertEqual(json.loads(out.getvalue()), result)
        self.assertEqual(candidates.read_bytes(), canonical(data))

    def test_repeated_candidate_id_or_unlicensed_request_is_malformed(self):
        data, rules = fixture()
        for changed in ({"examples": data["examples"] * 2}, {"allowed_licenses": []}, {"seed": True}):
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                apply({**data, **changed}, rules)

    def test_order_invariant_results_preserve_original_text_for_available_candidates(self):
        data, rules = fixture()
        before = apply(data, rules)
        data["examples"].reverse()
        self.assertEqual(before, apply(data, rules))
        self.assertEqual(before[0]["examples"][0]["prompt"], "Prompt baik.")

    def test_filtered_candidate_keeps_payload_identity_for_independent_verification(self):
        from ace_forge.dataset_forge import forge

        candidates, rules = fixture()
        original, index = inputs(*candidates["examples"])
        before = {row["event_id"]: identity(row) for row in original["examples"]}
        filtered, _ = apply(candidates, rules)
        accepted, _ = forge(filtered, index)
        self.assertEqual([item["provenance"]["payload_sha256"] for item in accepted], [before["ready"]])
