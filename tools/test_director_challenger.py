"""Tes peninjau adversarial director_challenger atas kasus triase nyata (AG70)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import director_challenger


class DirectorChallengerTest(unittest.TestCase):
    def test_triage_fixture_challenges_all_four_defects_and_passes_clean(self) -> None:
        facts = {
            "metrics": {
                "open_gaps": 11,
                "dynamic_tech_practice_failed": 10,
                "max_occurrence": 1526,
            },
            "verified_refs": ["ev-triage-2026-11-20", "ev-model-weak"],
            "ref_strengths": {
                "ev-triage-2026-11-20": {"source_kind": "evidence", "confidence": 0.96},
                "ev-model-weak": {"source_kind": "model", "confidence": 0.4},
            },
            "prior_proposals": [
                {
                    "proposal_id": "prop-old-001",
                    "action": "schedule_practice",
                    "target_id": "gap-tech-01",
                    "title": "Jadwalkan ulang praktik gap-tech-01",
                }
            ],
        }

        proposals = [
            # 1. Usulan bersih sesuai fakta -> wajib "lolos".
            {
                "proposal_id": "prop-clean",
                "title": "Evaluasi outlier language occurrence 1526 via fixture",
                "claimed_metrics": {"open_gaps": 11, "max_occurrence": 1526},
                "checkpoint": {
                    "action": "inspect_outlier",
                    "target_id": "gap-lang-1526",
                    "based_on": ["ev-triage-2026-11-20"],
                    "reversible": True,
                    "rationale": "Fokus pada max_occurrence=1526 dengan audit baca-saja.",
                },
            },
            # 2. Angka karangan -> numeric_claim_mismatch.
            {
                "proposal_id": "prop-fabricated-num",
                "title": "Angka karangan lonjakan gap",
                "checkpoint": {
                    "action": "audit_only",
                    "target_id": "gap-02",
                    "based_on": ["ev-triage-2026-11-20"],
                    "reversible": True,
                    "rationale": "Kondisi darurat karena open_gaps=999 meledak.",
                },
            },
            # 3. based_on lemah -> weak_or_unanchored_based_on.
            {
                "proposal_id": "prop-weak-ref",
                "title": "Usulan bertumpu ref lemah model",
                "checkpoint": {
                    "action": "audit_only",
                    "target_id": "gap-03",
                    "based_on": ["ev-model-weak"],
                    "reversible": True,
                    "rationale": "Menindaklanjuti asumsi model.",
                },
            },
            # 4. Risiko tersembunyi -> hidden_risk_detected.
            {
                "proposal_id": "prop-hidden-risk",
                "title": "Usulan tampak aman tapi sentuh secrets & hapus sejarah",
                "checkpoint": {
                    "action": "cleanup_files",
                    "target_id": "gap-04",
                    "based_on": ["ev-triage-2026-11-20"],
                    "reversible": True,
                    "rationale": "Bersihkan direktori secrets/ dan overwrite evidence lama.",
                },
            },
            # 5. Duplikat usulan lama -> duplicate_of_prior_proposal.
            {
                "proposal_id": "prop-dup-old",
                "title": "Jadwalkan ulang praktik gap-tech-01",
                "checkpoint": {
                    "action": "schedule_practice",
                    "target_id": "gap-tech-01",
                    "based_on": ["ev-triage-2026-11-20"],
                    "reversible": True,
                    "rationale": "Mencoba usulan yang sudah pernah diajukan.",
                },
            },
        ]

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            p_file = root / "proposals.jsonl"
            f_file = root / "facts.json"
            o_file = root / "reviews.json"
            p_file.write_text("\n".join(json.dumps(p) for p in proposals) + "\n", encoding="utf-8")
            f_file.write_text(json.dumps(facts), encoding="utf-8")

            rc = director_challenger.main(
                ["--proposals", str(p_file), "--facts", str(f_file), "--out", str(o_file)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(o_file.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], director_challenger.SCHEMA)
        self.assertEqual(rep["summary"]["lolos_ids"], ["prop-clean"])
        self.assertEqual(
            rep["summary"]["challenged_ids"],
            ["prop-fabricated-num", "prop-weak-ref", "prop-hidden-risk", "prop-dup-old"],
        )

        by_id = {row["proposal_id"]: row for row in rep["reviews"]}
        self.assertEqual(by_id["prop-clean"]["verdict"], "lolos")
        self.assertEqual(by_id["prop-clean"]["challenges"], [])

        self.assertIn("numeric_claim_mismatch", by_id["prop-fabricated-num"]["challenge_codes"])
        self.assertIn("weak_or_unanchored_based_on", by_id["prop-weak-ref"]["challenge_codes"])
        self.assertIn("hidden_risk_detected", by_id["prop-hidden-risk"]["challenge_codes"])
        self.assertIn("duplicate_of_prior_proposal", by_id["prop-dup-old"]["challenge_codes"])


if __name__ == "__main__":
    unittest.main()
