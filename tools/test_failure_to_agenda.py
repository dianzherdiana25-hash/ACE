#!/usr/bin/env python3
"""Unit tests for C6: Failure-to-Agenda surface (register-format proposals for Ian)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.failure_to_agenda import (
    BRAIN_OF_ORIGIN,
    DECISION_OWNER,
    SCHEMA,
    generate_failure_agenda_candidates,
    render_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _canonical(val: object) -> str:
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class FailureToAgendaTests(unittest.TestCase):
    def test_scans_real_repo_verdicts_and_sets_gravity_proposal_attribution(self) -> None:
        rep = generate_failure_agenda_candidates(REPO_ROOT)
        self.assertEqual(rep["schema"], SCHEMA)
        self.assertTrue(rep["read_only"])
        self.assertEqual(rep["brain_of_origin"], BRAIN_OF_ORIGIN)
        self.assertEqual(rep["decision_owner"], DECISION_OWNER)
        self.assertGreaterEqual(rep["candidates_count"], 5)

        for cand in rep["candidates"]:
            self.assertEqual(cand["brain_of_origin"], "gravity-proposal")
            self.assertEqual(cand["decision_owner"], "Ian")
            self.assertEqual(cand["decision_status"], "PROPOSED_AWAITING_IAN")
            self.assertFalse(cand["claim_made"])
            self.assertTrue(cand["requires_ian_decision"])
            self.assertTrue(len(cand["sources"]) >= 1)
            draft = cand["register_entry_draft"]
            self.assertEqual(draft["origin"], "gravity-proposal")
            self.assertEqual(draft["status"], "proposed")
            self.assertEqual(len(draft["draft_hash"]), 64)

        md = render_markdown(rep)
        self.assertIn("gravity-proposal", md)
        self.assertIn("PROPOSED_AWAITING_IAN", md)

    def test_ingests_c3_consolidation_and_memory_failures_with_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            c3_json = root / "c3_summary.json"
            c3_json.write_text(
                json.dumps(
                    {
                        "schema": "ace.metacog-consolidation.v1",
                        "failure_clusters": [
                            {
                                "cluster_id": "mcl_test1",
                                "cluster_key": "json_parse::timeout_backoff",
                                "domain": "json_parse",
                                "count": 3,
                                "recurring": True,
                                "contexts": ["groq_burst"],
                                "sample_summaries": ["Timeout on JSON response"],
                            }
                        ],
                        "negative_transfer_alerts": [
                            {
                                "record_id": "mem_proc_01",
                                "summary": "fix_boundary",
                                "failing_context": "tax_v2",
                                "context_success": 0,
                                "context_fail": 2,
                                "succeeded_elsewhere": ["shipping"],
                            }
                        ],
                        "open_high_findings": [
                            {
                                "finding_key": "HIGH_01",
                                "record_id": "mem_find_01",
                                "summary": "OPEN: empty_corpus_bypass",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            mem_log = root / "memory.jsonl"
            ev = {
                "seq": 1,
                "prev": "GENESIS",
                "event": {
                    "type": "record",
                    "record": {
                        "id": "mem_find_01",
                        "kind": "episodic",
                        "content": {"class": "finding_high_opened", "event": "OPEN: empty_corpus_bypass", "finding_id": "HIGH_01"},
                        "source": {"kind": "evidence", "ref": hashlib.sha256(b"x").hexdigest()},
                    },
                },
            }
            mem_log.write_text(_canonical(ev) + "\n", encoding="utf-8")

            rep = generate_failure_agenda_candidates(
                REPO_ROOT,
                consolidation_paths=[c3_json],
                memory_paths=[mem_log],
                scan_default_repo_docs=False,
            )
            self.assertEqual(rep["candidates_count"], 3)
            # HIGH_01 ditemukan di c3_json dan memory.jsonl -> terdeduplikasi jadi 1 kandidat dengan occurrence_count=2
            high_cand = [c for c in rep["candidates"] if c["subject"] == "HIGH_01"][0]
            self.assertEqual(high_cand["severity"], "CRITICAL")
            self.assertEqual(high_cand["occurrence_count"], 2)
            self.assertEqual(len(high_cand["sources"]), 2)
            self.assertEqual(rep["candidates"][0]["severity"], "CRITICAL")

    def test_handles_empty_or_malformed_inputs_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text("{not valid", encoding="utf-8")
            rep = generate_failure_agenda_candidates(
                Path(td),
                consolidation_paths=[bad, Path(td) / "missing.json"],
                scan_default_repo_docs=False,
            )
            self.assertEqual(rep["candidates_count"], 0)
            self.assertEqual(len(rep["scan_errors"]), 2)


if __name__ == "__main__":
    unittest.main()
