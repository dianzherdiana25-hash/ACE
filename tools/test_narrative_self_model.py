#!/usr/bin/env python3
"""Unit tests for C1: Narrative Self-Model (read-only, source-grounded)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.narrative_self_model import (
    SCHEMA,
    NarrativeClaim,
    SourcePointer,
    SourcelessClaimError,
    assert_no_sourceless_claims,
    build_narrative_self_model,
    extract_facts,
    read_memory_snapshot_readonly,
    render_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _canonical(val: object) -> str:
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(val: object) -> str:
    if isinstance(val, (bytes, bytearray)):
        return hashlib.sha256(bytes(val)).hexdigest()
    return hashlib.sha256(_canonical(val).encode("utf-8")).hexdigest()


def _write_chained_memory_jsonl(path: Path) -> bytes:
    """Bangun log memory.jsonl berantai hash secara manual di direktori temp tes."""
    ev_bytes = b'{"verdict": "GUARD_ADOPTED"}'
    ev_digest = _digest(ev_bytes)
    events = [
        {"type": "anchor", "digest": ev_digest},
        {
            "type": "record",
            "record": {
                "id": "mem_ev_001",
                "kind": "semantic",
                "content": {"event": "Lineage-Guard adopted", "subject": "guard", "predicate": "status", "object": "adopted"},
                "source": {"kind": "evidence", "ref": ev_digest},
                "confidence": 0.95,
                "status": "active",
                "written_seq": 2,
                "outcomes": {},
            },
        },
        {
            "type": "record",
            "record": {
                "id": "mem_op_002",
                "kind": "procedural",
                "content": {"event": "verify_sources.py must pass offline"},
                "source": {"kind": "operator", "ref": "owner"},
                "confidence": 0.95,
                "status": "active",
                "written_seq": 3,
                "outcomes": {},
            },
        },
        {
            "type": "record",
            "record": {
                "id": "mem_guess_003",
                "kind": "semantic",
                "content": {"event": "Unverified model guess on G5 pass rate"},
                "source": {"kind": "model", "ref": None},
                "confidence": 0.40,
                "status": "active",
                "written_seq": 4,
                "outcomes": {},
            },
        },
    ]
    prev = "GENESIS"
    lines = []
    for seq, event in enumerate(events, start=1):
        entry = {"seq": seq, "prev": prev, "event": event, "hash": _digest({"prev": prev, "event": event})}
        prev = entry["hash"]
        lines.append(_canonical(entry))
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


class NarrativeSelfModelTests(unittest.TestCase):
    def test_repo_live_readonly_and_determinism(self) -> None:
        m1 = build_narrative_self_model(REPO_ROOT, organ_context={"front": "organ-A"})
        m2 = build_narrative_self_model(REPO_ROOT, organ_context={"front": "organ-A"})
        self.assertEqual(m1["schema"], SCHEMA)
        self.assertTrue(m1["read_only"])
        self.assertEqual(_canonical(m1), _canonical(m2))
        self.assertGreaterEqual(len(m1["sections"]["identity"]), 3)
        self.assertGreaterEqual(len(m1["sections"]["proven"]), 3)
        self.assertGreaterEqual(len(m1["sections"]["unproven"]), 3)
        self.assertEqual(m1["rejected_sourceless_claims"], [])

        # Pastikan klaim kunci hadir dan punya pointer sumber sah
        fact_keys = {f["fact_key"]: f["fact_value"] for f in extract_facts(m1)}
        self.assertEqual(fact_keys["gate:G3"], "MEASURED_SPECIALIZATION")
        self.assertEqual(fact_keys["gate:G4"], "MEASURED_INHERITANCE_DEMONSTRATED")
        self.assertEqual(fact_keys["gate:round2-gate-01"], "LIFT_DEMONSTRATED")
        self.assertEqual(fact_keys["gate:G2"], "MEASURED_NOT_DEMONSTRATED")
        self.assertEqual(fact_keys["gate:G5"], "NOT_ASSESSED")
        self.assertEqual(fact_keys["phenomenal_consciousness"], "PHENOMENAL_CONSCIOUSNESS_UNKNOWN")

        md = render_markdown(m1)
        self.assertIn("Model-Diri Naratif ACE", md)
        self.assertIn("[sumber:", md)

    def test_memory_jsonl_strictly_readonly_and_guess_segregation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "workspace"
            (root / "handover").mkdir(parents=True)
            (root / "handover" / "PETA_ARAH_SERIBU_TAHUN.md").write_text(
                "- **Kontinuitas adalah intinya, bukan garis finis.**\n",
                encoding="utf-8",
            )
            mem_dir = Path(td) / "cognitive_memory"
            mem_dir.mkdir()
            mem_log = mem_dir / "memory.jsonl"
            before_bytes = _write_chained_memory_jsonl(mem_log)
            os.chmod(mem_log, 0o444)
            os.chmod(mem_dir, 0o555)
            try:
                model = build_narrative_self_model(root, memory_path=mem_dir)
            finally:
                os.chmod(mem_dir, 0o755)
                os.chmod(mem_log, 0o644)

            self.assertEqual(mem_log.read_bytes(), before_bytes)
            self.assertTrue(model["memory_summary"]["chain_ok"])

            proven_keys = {c["fact_key"] for c in model["sections"]["proven"]}
            unproven_keys = {c["fact_key"] for c in model["sections"]["unproven"]}
            self.assertIn("memory_record:mem_ev_001", proven_keys)
            self.assertIn("memory_record:mem_op_002", proven_keys)
            self.assertNotIn("memory_unverified_guess:mem_guess_003", proven_keys)
            self.assertIn("memory_unverified_guess:mem_guess_003", unproven_keys)

    def test_missing_memory_path_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            missing_dir = Path(td) / "never_created_mem"
            snap = read_memory_snapshot_readonly(missing_dir, REPO_ROOT)
            self.assertFalse(snap["present"])
            self.assertFalse(missing_dir.exists())

    def test_sourceless_claims_are_never_emitted(self) -> None:
        bad_no_source = NarrativeClaim(
            claim_id="clm_bad_1",
            section="proven",
            fact_key="fabricated_win",
            fact_value=True,
            statement="Klaim palsu tanpa sumber",
            sources=(),
        )
        bad_missing_file = NarrativeClaim(
            claim_id="clm_bad_2",
            section="identity",
            fact_key="ghost_source",
            fact_value="x",
            statement="Klaim menunjuk berkas hantu",
            sources=(SourcePointer(path="does_not_exist.md", sha256="0" * 64, line=1),),
        )
        model = build_narrative_self_model(
            REPO_ROOT,
            inject_unverified_claims=[bad_no_source, bad_missing_file],
        )
        all_emitted_keys = {c["fact_key"] for s in model["sections"].values() for c in s}
        self.assertNotIn("fabricated_win", all_emitted_keys)
        self.assertNotIn("ghost_source", all_emitted_keys)
        self.assertEqual(len(model["rejected_sourceless_claims"]), 2)

        with self.assertRaises(SourcelessClaimError):
            assert_no_sourceless_claims(
                {"sections": {"identity": [], "proven": [{"fact_key": "x", "sources": []}], "unproven": []}},
                [REPO_ROOT],
            )

    def test_organ_labels_and_style_preserve_extracted_facts(self) -> None:
        m_a = build_narrative_self_model(REPO_ROOT, organ_context={"front": "Qwen3-30B-A3B"}, narrative_style="standard")
        m_b = build_narrative_self_model(REPO_ROOT, organ_context={"front": "gemini-3-flash-preview"}, narrative_style="concise_en")
        self.assertNotEqual(m_a["sections"]["proven"][0]["statement"], m_b["sections"]["proven"][0]["statement"])
        self.assertEqual(m_a["facts"], m_b["facts"])


if __name__ == "__main__":
    unittest.main()
