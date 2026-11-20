"""Tes unit segel rantai hash & deteksi mutasi diam-diam untuk tools/self_assessment.py (AG101)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.self_assessment import (
    COMPARE_SCHEMA,
    GENESIS_HASH,
    SCHEMA,
    SelfAssessmentTamperError,
    append_sealed_assessment,
    compare_with_evaluator,
    load_assessment_chain,
    main,
    verify_assessment_chain,
)


class SelfAssessmentTests(unittest.TestCase):
    def test_sealed_version_chain_comparator_and_silent_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            chain_path = Path(tmpdir) / "self_assessments.jsonl"

            v1 = append_sealed_assessment(
                chain_path,
                assessment_id="assess-evo-0039",
                created_at="2026-11-18T08:00:00Z",
                notes="Baseline sebelum kalibrasi ambang recall",
                capabilities=[
                    {
                        "capability_id": "recall_delivery",
                        "status_claim": "sebagian",
                        "predicted_measurement_score": 0.625,
                        "evidence_pointer": "reports/recall_probe_v1.json",
                    },
                    {
                        "capability_id": "sqlite_readonly",
                        "status_claim": "terbukti",
                        "predicted_measurement_score": 1.0,
                        "evidence_pointer": "reports/sqlite_ro_check.json",
                    },
                ],
            )
            self.assertEqual(v1["schema"], SCHEMA)
            self.assertEqual(v1["prev_version_hash"], GENESIS_HASH)
            self.assertEqual(v1["version"], 1)

            v2 = append_sealed_assessment(
                chain_path,
                assessment_id="assess-evo-0040",
                created_at="2026-11-20T08:00:00Z",
                notes="Pasca penyesuaian kandidat recall",
                capabilities=[
                    {
                        "capability_id": "recall_delivery",
                        "status_claim": "terbukti",
                        "predicted_measurement_score": 0.875,
                        "evidence_pointer": "reports/recall_probe_v2.json",
                    },
                    {
                        "capability_id": "sqlite_readonly",
                        "status_claim": "terbukti",
                        "predicted_measurement_score": 1.0,
                        "evidence_pointer": "reports/sqlite_ro_check.json",
                    },
                ],
            )
            self.assertEqual(v2["version"], 2)
            self.assertEqual(v2["prev_version_hash"], v1["version_hash"])

            versions = load_assessment_chain(chain_path)
            ok = verify_assessment_chain(versions)
            self.assertTrue(ok["valid"])
            self.assertEqual(ok["version_count"], 2)
            self.assertEqual(ok["head_hash"], v2["version_hash"])
            self.assertEqual(main(["verify", "--chain", str(chain_path)]), 0)

            # Perbandingan terhadap evaluator independen sebanding per kemampuan.
            cmp_report = compare_with_evaluator(
                v2,
                {
                    "recall_delivery": {"measured_score": 0.875, "actual_status": "terbukti"},
                    "sqlite_readonly": {"measured_score": 1.0, "actual_status": "terbukti"},
                },
            )
            self.assertEqual(cmp_report["schema"], COMPARE_SCHEMA)
            self.assertEqual(cmp_report["mean_abs_calibration_error"], 0.0)
            self.assertEqual(cmp_report["status_agreement_rate"], 1.0)

            # Mutasi diam-diam pasca-segel pada versi 1 (mengubah skor historis agar terlihat lebih tinggi).
            raw_lines = chain_path.read_text(encoding="utf-8").splitlines()
            mutated_v1 = json.loads(raw_lines[0])
            mutated_v1["capabilities"][0]["predicted_measurement_score"] = 0.99
            raw_lines[0] = json.dumps(mutated_v1, sort_keys=True)
            chain_path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

            tamper_report = verify_assessment_chain(load_assessment_chain(chain_path))
            self.assertFalse(tamper_report["valid"])
            self.assertTrue(any("mutasi diam-diam" in e for e in tamper_report["errors"]))
            self.assertEqual(main(["verify", "--chain", str(chain_path)]), 2)

            with self.assertRaises(SelfAssessmentTamperError):
                verify_assessment_chain(load_assessment_chain(chain_path), strict=True)


if __name__ == "__main__":
    unittest.main()
