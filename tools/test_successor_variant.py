"""Tes unit round-trip & deteksi tampering untuk tools/successor_variant.py (AG99)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.successor_variant import (
    MANIFEST_FILENAME,
    SCHEMA,
    VariantCustodyError,
    build_variant_archive,
    main,
    verify_variant_archive,
)


_SINGLE_DIFF = """--- a/code/ace_operational/recall_reranker.py
+++ b/code/ace_operational/recall_reranker.py
@@ -10,1 +10,1 @@
-THRESHOLD = 0.85
+THRESHOLD = 0.65
"""

_MULTI_DIFF = """--- a/code/ace_operational/recall_reranker.py
+++ b/code/ace_operational/recall_reranker.py
@@ -10,1 +10,1 @@
-THRESHOLD = 0.85
+THRESHOLD = 0.65
--- a/code/ace_operational/brain_bridge.py
+++ b/code/ace_operational/brain_bridge.py
@@ -1,1 +1,1 @@
-CAP = 10
+CAP = 20
"""


class SuccessorVariantTests(unittest.TestCase):
    def test_roundtrip_archive_build_verify_and_tamper_multidiff_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            archive = tmp / "variant-01"
            manifest = build_variant_archive(
                archive,
                variant_id="var-recall-threshold-01",
                origin_commit="8a0c071",
                target_file="code/ace_operational/recall_reranker.py",
                diff_text=_SINGLE_DIFF,
                prediction={
                    "expected_advantage": "Menghilangkan kasus 0-record recall bertetangga tanpa menambah latensi",
                    "success_metric": "recall_delivery_probe flag == 0 pada 8 tugas heldout",
                    "stop_condition": "Batalkan bila presisi turun > 5%",
                },
                extra_files={"notes/baseline_snapshot.json": '{"0_record_flags": 3}\n'},
            )
            self.assertEqual(manifest["schema"], SCHEMA)

            ok_report = verify_variant_archive(archive)
            self.assertTrue(ok_report["valid"])
            self.assertEqual(ok_report["verified_files"], 3)
            self.assertEqual(ok_report["errors"], [])
            self.assertEqual(main(["verify", "--archive", str(archive)]), 0)

            # 1. Pembangun langsung menolak kelahiran multi-diff (>1 berkas tersentuh).
            with self.assertRaises(VariantCustodyError):
                build_variant_archive(
                    tmp / "variant-multi",
                    variant_id="var-multi-illegal",
                    origin_commit="8a0c071",
                    target_file="code/ace_operational/recall_reranker.py",
                    diff_text=_MULTI_DIFF,
                    prediction={
                        "expected_advantage": "Dua perubahan sekaligus",
                        "success_metric": "skor",
                    },
                )

            # 2. Tampering pada diff di disk ke multi-diff atau ubah byte terdeteksi oleh verifier.
            (archive / "payload/notes/baseline_snapshot.json").write_text(
                '{"0_record_flags": 0}\n', encoding="utf-8"
            )
            tamper_report = verify_variant_archive(archive)
            self.assertFalse(tamper_report["valid"])
            self.assertTrue(any("tampering" in err for err in tamper_report["errors"]))
            self.assertEqual(main(["verify", "--archive", str(archive)]), 2)

            # 3. Mutasi manifes juga terdeteksi lewat manifest_hash.
            mutated = json.loads((archive / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            mutated["single_diff"]["diff_count"] = 2
            (archive / MANIFEST_FILENAME).write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaises(VariantCustodyError):
                verify_variant_archive(archive, strict=True)


if __name__ == "__main__":
    unittest.main()
