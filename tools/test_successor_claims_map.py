"""Uji peta klaim sekaligus batas root bukti."""
from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools.successor_inventory import main


class ClaimsMapTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.repo, self.snapshot = root / "repo", root / "snapshot"
        self.repo.mkdir()
        self.snapshot.mkdir()
        self.out, self.claims = root / "out", root / "claims.json"
        self.git("init", "-q")
        self.evidence = self.repo / "s0006-evidence.md"
        self.evidence.write_text("fixture\n")
        self.git("add", self.evidence.name)
        self.args = ["--repo", str(self.repo), "--snapshot", str(self.snapshot),
                     "--output-dir", str(self.out), "--claims", str(self.claims)]

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def test_map_missing_and_untested_with_inventory_pointer(self):
        claims = [
            {"id": "missing", "evidence": "absent.md", "status": "teruji"},
            {"id": "untested", "evidence": self.evidence.name, "status": "belum"},
            {"id": "tested", "evidence": self.evidence.name, "status": "teruji"},
        ]
        self.claims.write_text(json.dumps(claims))
        self.assertEqual(main(self.args), 0)
        report = json.loads((self.out / "inventory.json").read_bytes())["claims"]
        self.assertEqual(report["missing_evidence"], [{**claims[0], "in_successor_inventory": False}])
        self.assertEqual(report["untested_with_evidence"], [{**claims[1], "in_successor_inventory": True}])
        self.assertIn("Klaim dengan bukti hilang (1)", (self.out / "inventory.md").read_text())

    def test_outside_root_and_symlink_escape_refused_without_output(self):
        outside = self.repo.parent / "outside.md"
        outside.write_text("fixture\n")
        (self.repo / "escape.md").symlink_to(outside)
        for path in ("../outside.md", str(outside), "escape.md"):
            with self.subTest(path=path), redirect_stderr(StringIO()) as errors:
                self.claims.write_text(json.dumps([{"id": "outside", "evidence": path, "status": "belum"}]))
                with self.assertRaises(SystemExit) as failed:
                    main(self.args)
                self.assertEqual(failed.exception.code, 2)
                self.assertIn("di luar", errors.getvalue())
                self.assertFalse(self.out.exists())

    def test_legacy_manifest_preserves_cli_bytes(self):
        self.claims.write_text(json.dumps([
            {"id": "missing", "evidence": "absent.md", "status": "teruji"},
            {"id": "untested", "evidence": self.evidence.name, "status": "belum"},
        ]))
        self.assertEqual(main(self.args), 0)
        for name, digest in {
            "inventory.json": "ce3aa18b30b920ec9e7fffe7e596b3ab40ade25f3543b733af67a681a2c3de40",
            "inventory.md": "cfccce631d683a07e629f06ac1ad289b83e6c3485104dc662150f18a8fdb5b30",
        }.items():
            self.assertEqual(hashlib.sha256((self.out / name).read_bytes()).hexdigest(), digest)

    def test_missing_original_requires_verified_relocation_bytes(self):
        digest = hashlib.sha256(self.evidence.read_bytes()).hexdigest()
        moved = self.evidence.rename(self.repo / "moved.md")
        (self.repo / "different.md").write_text("changed\n")
        self.claims.write_text(json.dumps([
            {"id": "moved", "evidence": self.evidence.name, "status": "belum",
             "relocated_to": moved.name, "sha256": digest},
            {"id": "different", "evidence": self.evidence.name, "status": "teruji",
             "relocated_to": "different.md", "sha256": digest},
        ]))
        self.assertEqual(main(self.args), 0)
        report = json.loads((self.out / "inventory.json").read_bytes())["claims"]
        self.assertEqual([row["id"] for row in report["missing_evidence"]], ["different"])
        self.assertEqual(report["relocation_unverified"][0]["reason"], "sha256_mismatch")
        self.assertEqual(report["relocated_verified"][0]["relocated_to"], moved.name)
        self.assertEqual(report["untested_with_evidence"][0]["evidence"], moved.name)
        self.assertIn("terverifikasi di lokasi baru (1)", (self.out / "inventory.md").read_text())

    def test_relocation_checks_path_before_digest_and_output(self):
        outside = self.repo.parent / "outside.md"
        outside.write_text("fixture\n")
        (self.repo / "escape.md").symlink_to(outside)
        for pointer in ("../outside.md", str(outside), "escape.md"):
            with self.subTest(pointer=pointer), redirect_stderr(StringIO()) as errors:
                self.claims.write_text(json.dumps([
                    {"id": "escape", "evidence": self.evidence.name, "status": "teruji",
                     "relocated_to": pointer},
                ]))
                with self.assertRaises(SystemExit) as failed:
                    main(self.args)
                self.assertEqual(failed.exception.code, 2)
                self.assertIn("di luar", errors.getvalue())
                self.assertFalse(self.out.exists())

    def test_chain_verifies_against_git_blob_and_reports_failed_paths(self):
        self.git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "seed")
        original = self.evidence.read_bytes()
        self.evidence.unlink()
        digest = hashlib.sha256(original).hexdigest()

        def point(source, target):
            (self.repo / source).write_text(json.dumps({
                "schema": "ace.successor-relocation.v1", "relocated_to": target,
            }))

        (self.repo / "valid.md").write_bytes(original)
        (self.repo / "changed.md").write_bytes(b"changed\n")
        point("hop.json", "valid.md")
        point("changed.json", "changed.md")
        point("cycle.json", "cycle-2.json")
        point("cycle-2.json", "cycle.json")
        point("long.json", "long-2.json")
        point("long-2.json", "long-3.json")
        point("long-3.json", "valid.md")
        claims = [("ok", "hop.json", digest), ("changed", "changed.json", digest),
                  ("cycle", "cycle.json", digest), ("long", "long.json", digest),
                  ("untrusted", "changed.json", hashlib.sha256(b"changed\n").hexdigest())]
        self.claims.write_text(json.dumps([
            {"id": identifier, "evidence": self.evidence.name, "status": "teruji",
             "relocated_to": target, "sha256": expected} for identifier, target, expected in claims
        ]))
        self.assertEqual(main(self.args), 0)
        report = json.loads((self.out / "inventory.json").read_bytes())["claims"]
        verified, = report["relocated_verified"]
        self.assertEqual(verified["relocation_chain"], [self.evidence.name, "hop.json", "valid.md"])
        self.assertEqual(verified["git_origin"]["state"], "match")
        self.assertEqual(verified["git_origin"]["sha256"], digest)
        faults = {item["id"]: item for item in report["relocation_unverified"]}
        self.assertEqual([item["id"] for item in report["missing_evidence"]],
                         ["changed", "cycle", "long", "untrusted"])
        self.assertEqual({key: item["reason"] for key, item in faults.items()}, {
            "changed": "sha256_mismatch", "cycle": "relocation_cycle",
            "long": "relocation_hop_limit", "untrusted": "origin_blob_mismatch",
        })
        self.assertEqual(faults["cycle"]["relocation_chain"],
                         [self.evidence.name, "cycle.json", "cycle-2.json", "cycle.json"])
        self.assertEqual(faults["untrusted"]["git_origin"]["state"], "mismatch")

    def test_intermediate_pointer_obeys_root_guard(self):
        (self.repo / "hop.json").write_text(json.dumps({
            "schema": "ace.successor-relocation.v1", "relocated_to": "../outside.md",
        }))
        self.claims.write_text(json.dumps([{
            "id": "outside", "evidence": self.evidence.name, "status": "teruji",
            "relocated_to": "hop.json", "sha256": "a" * 64,
        }]))
        with redirect_stderr(StringIO()) as errors, self.assertRaises(SystemExit) as stopped:
            main(self.args)
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn("di luar", errors.getvalue())
        self.assertFalse(self.out.exists())
