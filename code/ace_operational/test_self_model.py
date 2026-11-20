"""Tes unit untuk code/ace_operational/self_model.py (AG91)."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.self_model import (
    SCHEMA,
    SelfModelBuilder,
    SelfModelValidationError,
    validate_self_model_payload,
)


class SelfModelBuilderTests(unittest.TestCase):
    def test_no_engine_imports(self) -> None:
        src_path = Path(__file__).with_name("self_model.py")
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any("autonomous_engine" in name for name in imported))

    def test_builds_from_three_custody_sources_and_rejects_sourceless_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            receipts_path = tmp / "receipts.jsonl"
            memory_path = tmp / "memory.jsonl"
            ledger_path = tmp / "decisions.json"

            receipts_path.write_text(
                json.dumps(
                    {
                        "receipt_id": "rcpt-01",
                        "action": "verify_backup",
                        "status": "applied",
                        "class": "A",
                        "timestamp": "2026-11-18T10:00:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            memory_path.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "prev": "GENESIS",
                        "event": {"kind": "record", "topic": "bridge_restart_rule", "recorded_at": "2026-11-18T10:05:00Z"},
                        "hash": "abc123",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            ledger_path.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "decision_id": "dec-01",
                                "decision": "Tunda deploy sampai verifikasi sumber lolos",
                                "reason": "Hash sumber berbeda satu berkas",
                                "outcome": "lulus_setelah_perbaikan",
                                "decided_at": "2026-11-18T11:00:00Z",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            builder = SelfModelBuilder()
            self.assertEqual(builder.ingest_receipts_jsonl(receipts_path), 1)
            self.assertEqual(builder.ingest_memory_chain_jsonl(memory_path), 1)
            self.assertEqual(builder.ingest_decision_ledger(ledger_path), 1)

            # Paksa klaim tanpa sumber kustodi -> wajib ditolak.
            with self.assertRaises(SelfModelValidationError):
                builder.add_claim(
                    entry_id="claim-orphan",
                    category="identity",
                    claim="Saya selalu benar",
                    value=True,
                    custody=None,
                )

            # Paksa penunjuk kustodi dengan record_id kosong atau source_kind palsu -> ditolak.
            with self.assertRaises(SelfModelValidationError):
                builder.add_claim(
                    entry_id="claim-bad-kind",
                    category="identity",
                    claim="Klaim mengarang",
                    value=True,
                    custody={"source_kind": "imagination", "source_ref": "x", "record_id": "1"},
                )
            with self.assertRaises(SelfModelValidationError):
                builder.add_claim(
                    entry_id="claim-empty-record",
                    category="identity",
                    claim="Klaim tanpa id",
                    value=True,
                    custody={"source_kind": "receipt", "source_ref": "receipts.jsonl", "record_id": ""},
                )

            built = builder.build()
            self.assertEqual(built["schema"], SCHEMA)
            self.assertEqual(built["entry_count"], 3)
            self.assertEqual(
                built["by_source_kind"],
                {"decision_ledger": 1, "memory_chain": 1, "receipt": 1},
            )

            # Mutasi model hasil build dengan entri tanpa kustodi -> validator dokumen juga menolak.
            tampered = dict(built)
            tampered["entries"] = list(built["entries"]) + [
                {"entry_id": "inject", "category": "x", "claim": "Klaim tanpa sumber", "value": 1}
            ]
            with self.assertRaises(SelfModelValidationError):
                validate_self_model_payload(tampered)


if __name__ == "__main__":
    unittest.main()
