"""Jaga nama repo dan fixpoint renderer saat lokasi checkout berbeda."""
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools import (
    builder_onboarding_pack,
    handover_decision_extractor,
    handover_index,
    platform_requirements_summary,
    program_glossary,
    repo_cartography,
    repo_index,
)


GENERATORS = (
    (repo_index, "docs/REPO_INDEX.md"),
    (repo_cartography, repo_cartography.DEFAULT_OUTPUT_REL),
    (program_glossary, program_glossary.DEFAULT_OUTPUT_REL),
    (handover_index, handover_index.DEFAULT_OUTPUT_REL),
    (builder_onboarding_pack, builder_onboarding_pack.DEFAULT_OUTPUT_REL),
    (platform_requirements_summary, platform_requirements_summary.DEFAULT_OUTPUT_REL),
    (handover_decision_extractor, handover_decision_extractor.DEFAULT_OUTPUT_REL),
)

JSON_GENERATORS = (
    repo_cartography,
    program_glossary,
    handover_index,
    builder_onboarding_pack,
    platform_requirements_summary,
    handover_decision_extractor,
)


class TwoCheckoutTests(unittest.TestCase):
    def seed(self, root, derived=b"", remote_url="https://example.invalid/research/canonical-fixture.git"):
        root.mkdir()
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin", remote_url],
                       check=True, capture_output=True)
        (root / "docs" / "research").mkdir(parents=True)
        (root / "handover").mkdir()
        (root / "tools").mkdir()
        (root / "README.md").write_text("# Program fixture\n\n**Gate**: aturan periksa bukti.\n", encoding="utf-8")
        (root / "handover" / "GOVERNANCE_RULES_20261115.md").write_text(
            "# Aturan Tata Kelola\n\n- Keputusan Pemilik: batas KBM Rp 100000.\n",
            encoding="utf-8",
        )
        (root / "tools" / "local_task.py").write_text('"""Pemeriksaan fixture."""\n', encoding="utf-8")
        if derived is not None:
            for _, rel in GENERATORS:
                (root / rel).write_bytes(derived)

    def render(self, root):
        for generator, rel in GENERATORS:
            self.assertEqual(generator.main(["--root", str(root), "--output", str(root / rel)]), 0)
        return {rel: (root / rel).read_bytes() for _, rel in GENERATORS}

    def test_two_checkout_outputs_and_second_round_are_identical(self):
        self.assertEqual(len(GENERATORS), 7)
        for remote_url in (
            "https://example.invalid/research/canonical-fixture.git",
            "ssh://git@example.invalid:2222/research/canonical-fixture.git?shallow=1",
        ):
            with self.subTest(remote_url=remote_url):
                temp = Path(self.enterContext(TemporaryDirectory()))
                versions = []
                json_versions = []
                for name in ("checkout-one-unique", "checkout-two-unique"):
                    root = temp / name
                    self.seed(root, remote_url=remote_url)
                    converged, diagnosis = self.converge(root)
                    self.assertEqual(diagnosis["status"], "converged", diagnosis)
                    hashes = {rel: hashlib.sha256(data).hexdigest() for rel, data in converged.items()}
                    second = self.render(root)
                    self.assertEqual(
                        {rel: hashlib.sha256(data).hexdigest() for rel, data in second.items()},
                        hashes,
                    )
                    for rel, data in second.items():
                        self.assertNotIn(name.encode(), data, rel)
                        self.assertNotIn(str(root).encode(), data, rel)
                        self.assertNotIn(b"shallow=1", data, rel)
                    for heading_rel in (
                        "docs/REPO_INDEX.md",
                        repo_cartography.DEFAULT_OUTPUT_REL,
                        program_glossary.DEFAULT_OUTPUT_REL,
                        handover_index.DEFAULT_OUTPUT_REL,
                        builder_onboarding_pack.DEFAULT_OUTPUT_REL,
                    ):
                        self.assertIn(b"canonical-fixture", second[heading_rel], heading_rel)

                    json_map = {}
                    for generator in JSON_GENERATORS:
                        out_json = temp / f"{name}_{generator.__name__.rsplit('.', 1)[-1]}.json"
                        self.assertEqual(
                            generator.main(["--root", str(root), "--format", "json", "--output", str(out_json)]),
                            0,
                        )
                        raw_json = out_json.read_bytes()
                        self.assertNotIn(name.encode(), raw_json)
                        self.assertNotIn(str(root).encode(), raw_json)
                        payload = json.loads(raw_json)
                        self.assertEqual(payload["repo_name"], "canonical-fixture")
                        json_map[generator.__name__] = raw_json

                    versions.append(second)
                    json_versions.append(json_map)
                self.assertEqual(*versions)
                self.assertEqual(*json_versions)

    def snapshot(self, root):
        return {rel: (root / rel).read_bytes() for _, rel in GENERATORS if (root / rel).is_file()}

    def converge(self, root, *, render=None, limit=8):
        render = self.render if render is None else render
        previous = self.snapshot(root)
        rounds = []
        for round_number in range(1, limit + 1):
            current = render(root)
            changed = sorted(rel for rel in previous.keys() | current.keys()
                             if previous.get(rel) != current.get(rel))
            rounds.append({"round": round_number, "changed_files": changed,
                           "sha256_after": {rel: hashlib.sha256(data).hexdigest()
                                            for rel, data in current.items()}})
            previous = current
            if not changed:
                return previous, {"status": "converged", "rounds": rounds}
        return previous, {"status": "not_converged", "rounds": rounds}

    def test_bootstrap_and_stale_checkouts_converge_to_current_bytes(self):
        temp = Path(self.enterContext(TemporaryDirectory()))
        current, bootstrap, stale = (temp / name for name in ("current", "bootstrap", "stale"))
        self.seed(current)
        self.seed(bootstrap, derived=None)
        self.seed(stale, derived=b"# Stale fixture\n")
        self.assertEqual(self.snapshot(bootstrap), {})
        self.assertEqual(set(self.snapshot(stale).values()), {b"# Stale fixture\n"})

        _, seed_diagnosis = self.converge(current)
        self.assertEqual(seed_diagnosis["status"], "converged", seed_diagnosis)
        expected, current_diagnosis = self.converge(current)
        bootstrapped, bootstrap_diagnosis = self.converge(bootstrap)
        refreshed, refresh_diagnosis = self.converge(stale)
        diagnoses = {"bootstrap": bootstrap_diagnosis, "refresh": refresh_diagnosis,
                     "current": current_diagnosis}
        bootstrap_changes = sorted({rel for report in bootstrap_diagnosis["rounds"]
                                    for rel in report["changed_files"]})
        report = {
            **{f"{name}_rounds": len(diagnosis["rounds"]) for name, diagnosis in diagnoses.items()},
            "round_diagnoses": diagnoses,
            "bootstrap_changed_files": bootstrap_changes,
            "cross_checkout_differences": {
                name: sorted(rel for rel, data in expected.items() if actual.get(rel) != data)
                for name, actual in (("bootstrap", bootstrapped), ("stale", refreshed))
            },
        }
        print(json.dumps(report, sort_keys=True))
        for diagnosis in diagnoses.values():
            self.assertEqual(diagnosis["status"], "converged", diagnosis)
            self.assertEqual(diagnosis["rounds"][-1]["changed_files"], [])
        self.assertEqual(report["current_rounds"], 1)
        self.assertGreater(report["bootstrap_rounds"], 1)
        self.assertGreater(report["refresh_rounds"], 1)
        self.assertEqual(bootstrap_changes, sorted(expected))
        self.assertEqual(len(bootstrap_changes), 7)
        self.assertEqual(report["cross_checkout_differences"], {"bootstrap": [], "stale": []})
        self.assertEqual(bootstrapped, expected)
        self.assertEqual(refreshed, expected)

    def test_oscillating_renderer_reports_non_convergence_with_hashes(self):
        root = Path(self.enterContext(TemporaryDirectory())) / "oscillating"
        self.seed(root, derived=None)
        rel = GENERATORS[0][1]
        sequence = iter((b"first", b"second") * 4)

        def alternate(root):
            (root / rel).write_bytes(next(sequence))
            return self.snapshot(root)

        _, diagnosis = self.converge(root, render=alternate)
        print(json.dumps({"oscillating_fixture": diagnosis}, sort_keys=True))
        self.assertEqual(diagnosis["status"], "not_converged")
        self.assertEqual(diagnosis["rounds"], [
            {"round": round_number, "changed_files": [rel],
             "sha256_after": {rel: hashlib.sha256(data).hexdigest()}}
            for round_number, data in enumerate((b"first", b"second") * 4, 1)
        ])
