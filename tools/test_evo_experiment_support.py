"""Fixture untuk generator draf, bundel run, dan pembacaan konsolidasi A4."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.evo_prereg_draft import render_draft
from tools.evo_results import compare_metrics, tabulate_verdicts, verdict_markdown
from tools.seal_run import seal_run, verify_run


TOOLS = Path(__file__).resolve().parent


class ExperimentSupportTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(TOOLS / script), *map(str, args)],
                              capture_output=True, text=True)

    def test_prereg_quotes_sections_and_marks_unresolved_fields(self):
        design = self.write("RANCANGAN.md", """# RANCANGAN EVO 9991 — contoh
## 1. Hipotesis
Pemilihan fitur menambah cakupan.
### Ukuran tambahan
Hitung fitur yang teramati.
## 2. Sketsa lengan
Referensi dan pembanding.
```
## 3. Prasyarat
Ini contoh sintaks.
```
## 5. Yang belum diputuskan
Batas jumlah percobaan.
""")
        original = design.read_bytes()
        draft = render_draft(design)
        self.assertIn("# PREREGISTRASI EVO 9991 — DRAF", draft)
        self.assertIn(f"`{hashlib.sha256(original).hexdigest()}`", draft)
        self.assertIn("    Pemilihan fitur menambah cakupan.", draft)
        self.assertIn("    ### Ukuran tambahan", draft)
        self.assertIn("    Batas jumlah percobaan.", draft)
        self.assertEqual(draft.count("Kutipan rancangan, baris "), 3)
        self.assertEqual(draft.count("[Isi keputusan dan bukti pendukung.]"), 6)
        self.assertNotIn("0.75", draft)
        result = self.cli("evo_prereg_draft.py", design)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, draft)
        self.assertEqual(design.read_bytes(), original)
        self.assertEqual(list(self.root.iterdir()), [design])

    def test_prereg_requires_single_explicit_evo_title(self):
        path = self.write("design.md", "# Judul\n")
        self.assertEqual(self.cli("evo_prereg_draft.py", path).returncode, 2)
        path.write_text("# RANCANGAN EVO 0001\n# RANCANGAN EVO 0002\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "satu judul"):
            render_draft(path)

    def test_pinned_seal_round_trip_and_source_unchanged(self):
        source_file = self.write("source/sub/trace.log", "fixture\n")
        bundle = self.root / "bundle"
        packed = self.cli("seal_run.py", "pack", source_file.parents[1], bundle)
        self.assertEqual(packed.returncode, 0, packed.stderr)
        digest = json.loads(packed.stdout)["manifest_sha256"]
        manifest = bundle / "manifest.json"
        self.assertEqual(digest, hashlib.sha256(manifest.read_bytes()).hexdigest())
        verified = self.cli("seal_run.py", "verify", bundle, "--manifest-sha256", digest)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(json.loads(verified.stdout)["manifest_pinned"])
        self.assertEqual(source_file.read_text(encoding="utf-8"), "fixture\n")
        self.assertFalse((source_file.parents[1] / "manifest.json").exists())
        with self.assertRaises(FileExistsError):
            seal_run(source_file.parents[1], bundle)
        self.assertTrue(verify_run(bundle)["valid"])

    def test_verify_detects_modified_missing_extra_and_changed_manifest(self):
        self.write("source/a.txt", "123")
        source, bundle = self.root / "source", self.root / "bundle"
        pin = seal_run(source, bundle)["manifest_sha256"]
        self.write("bundle/a.txt", "456")
        self.write("bundle/other.txt", "new")
        result = verify_run(bundle, manifest_sha256=pin)
        self.assertFalse(result["valid"])
        self.assertEqual(result["modified"][0]["path"], "a.txt")
        self.assertEqual(result["extra_files"], ["other.txt"])
        (bundle / "a.txt").unlink()
        self.assertEqual(verify_run(bundle)["missing"], ["a.txt"])
        manifest = bundle / "manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        self.assertEqual(verify_run(bundle, manifest_sha256=pin)["reason"], "manifest_sha256_mismatch")

    def test_verify_rejects_noncanonical_and_duplicate_paths(self):
        self.write("source/a.txt", "123")
        bundle = self.root / "bundle"
        seal_run(self.root / "source", bundle)
        manifest = bundle / "manifest.json"
        original = json.loads(manifest.read_bytes())
        for bad_path in ("../a.txt", "./a.txt", "/absolute", "manifest.json", "a.txt"):
            with self.subTest(path=bad_path):
                bad = {**original, "file_count": 2, "total_bytes": 6,
                       "files": original["files"] + [{**original["files"][0], "path": bad_path}]}
                manifest.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Path manifest"):
                    verify_run(bundle)

    def test_seal_rejects_overlapping_destinations_and_symlinks(self):
        self.write("source/a.txt", "ok")
        source = self.root / "source"
        with self.assertRaisesRegex(ValueError, "terpisah"):
            seal_run(source, source / "out")
        outside = self.write("outside/file", "no")
        (source / "linked").symlink_to(outside.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink direktori"):
            seal_run(source, self.root / "bundle")
        self.assertFalse((self.root / "bundle").exists())

    def test_seal_rejects_special_files(self):
        self.write("source/a.txt", "ok")
        os.mkfifo(self.root / "source" / "pipe")
        with self.assertRaisesRegex(ValueError, "berkas reguler"):
            seal_run(self.root / "source", self.root / "bundle")

    def test_verdict_tabulation_preserves_named_scope_and_pointers(self):
        early = self.write("early.md", """# KONSOLIDASI EVO 9991 — contoh
## Vonis: NOL
## Gate G2 — Vonis: TIDAK TERDUKUNG
```md
## Gate G3 — Vonis: PASS
```
""")
        later = self.write("later.md", """# EVO 9992 — Konsolidasi
## Blok B — cek (PASS, tersedia)
## Blok A — uji (VONIS: TERDUKUNG)
## T1 — uji — TIDAK TERDUKUNG
### B4 — audit: ERROR (probe)
### B1 — Hanya konteks
""")
        unknown = self.write("unknown.md", "# EVO 9993 — Konsolidasi\n## Catatan hipotesis\n")
        report = tabulate_verdicts([later, unknown, early])
        rows = [(row["gate"], row["verdict"], row["source"]["line"]) for row in report["rows"]]
        self.assertEqual(rows, [("B4", "ERROR", 5), ("BLOK A", "TERDUKUNG", 3),
                                ("BLOK B", "PASS", 2), ("G2", "TIDAK TERDUKUNG", 3),
                                ("PAKET", "NOL", 2), ("T1", "TIDAK TERDUKUNG", 4)])
        markdown = verdict_markdown(report)
        self.assertIn("| PAKET | EVO 9993 | TIDAK TAHU", markdown)
        self.assertIn("| B1 | EVO 9992 | TIDAK TAHU", markdown)
        self.assertEqual(tabulate_verdicts([early, later, unknown]), report)

    def test_duplicate_gate_verdict_is_ambiguous(self):
        duplicate = self.write("duplicate.md", "# EVO 9993 — Konsolidasi\n"
                               "## Gate G2 — Vonis: PASS\n## Gate G2 — Vonis: NOL\n")
        with self.assertRaisesRegex(ValueError, "vonis ganda"):
            tabulate_verdicts([duplicate])

    def test_compare_exact_decimal_and_explicit_unknown(self):
        old = self.write("v1.md", "# EVO 9991 — Konsolidasi\n| rasio | 3/8 = 0.375 |\n| detik | 7,25 |\n")
        new = self.write("v2.md", "# EVO 9992 — Konsolidasi\n| rasio | 5/8 = 0.625 |\n| detik | 4,05 |\n")
        selectors = [{"name": "rasio", "unit": "proporsi", "before":
                      {"line": 2, "column": 2, "format": "equals_decimal"}, "after":
                      {"line": 2, "column": 2, "format": "equals_decimal"}},
                     {"name": "durasi", "unit": "detik", "before":
                      {"line": 3, "column": 2, "format": "decimal_comma"}, "after":
                      {"line": 3, "column": 2, "format": "decimal_comma"}},
                     {"name": "hilang", "unit": "detik", "before": None, "after":
                      {"line": 3, "column": 2, "format": "decimal_comma"}}]
        mapping = self.write("metrics.json", json.dumps(selectors))
        result = self.cli("evo_results.py", "compare", old, new, "--metrics", mapping)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual([(row["name"], row["delta"]) for row in output["metrics"]],
                         [("durasi", "-3.20"), ("hilang", None), ("rasio", "0.250")])
        self.assertEqual(output["metrics"][2]["before"]["source"]["column"], 2)

    def test_compare_rejects_drift_or_wrong_numeric_format(self):
        before = self.write("v1.md", "# EVO 9991 — Konsolidasi\n| jumlah | 9 |\n")
        after = self.write("v2.md", "# EVO 9992 — Konsolidasi\n| jumlah | 10 sementara |\n")
        entry = {"name": "jumlah", "unit": "kasus", "before":
                 {"line": 2, "column": 2, "line_sha256": "0" * 64},
                 "after": {"line": 2, "column": 2}}
        with self.assertRaisesRegex(ValueError, "SHA-256 baris berubah"):
            compare_metrics(before, after, [entry])
        del entry["before"]["line_sha256"]
        with self.assertRaisesRegex(ValueError, "angka desimal"):
            compare_metrics(before, after, [entry])


if __name__ == "__main__":
    unittest.main()
