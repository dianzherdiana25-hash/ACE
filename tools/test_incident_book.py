"""Tes buku insiden append-only: tiga insiden, ringkasan periode, dan tolak tulis ulang (AG79)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import incident_book


class IncidentBookTest(unittest.TestCase):
    def test_append_only_three_incidents_summary_and_reject_rewrites(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            book = root / "incidents.jsonl"

            incident_book.record_incident(
                book,
                incident_id="inc-001",
                ts="2026-11-18T03:40:00Z",
                kind="budget_exhausted",
                cause="kuota coder harian habis terlalu cepat",
                remediation="prioritaskan langkah berat sebelum kuota tipis",
                recovery_evidence="evidence/recovery_inc001.json",
            )
            prefix_after_one = book.read_bytes()

            incident_book.record_incident(
                book,
                incident_id="inc-002",
                ts="2026-11-19T11:00:00Z",
                kind="spool_corruption",
                cause="berkas req robek di tengah antrean",
                remediation="tulis lewat .tmp + os.replace & karantina korup",
                recovery_evidence="evidence/recovery_inc002.json",
            )
            # Pastikan prefix lama tetap utuh byte-demi-byte saat append!
            self.assertTrue(book.read_bytes().startswith(prefix_after_one))

            incident_book.record_incident(
                book,
                incident_id="inc-003",
                ts="2026-11-20T09:15:00Z",
                kind="budget_exhausted",
                cause="lonjakan permintaan peran front",
                remediation="aktifkan rotasi fallback non-kritis",
                recovery_evidence="evidence/recovery_inc003.json",
            )

            # 1. Tolak penulisan ulang entri lama berdasarkan ID duplikat.
            with self.assertRaises(incident_book.IncidentBookError):
                incident_book.record_incident(
                    book,
                    incident_id="inc-001",
                    ts="2026-11-20T12:00:00Z",
                    kind="rewritten",
                    cause="coba menimpa inc-001",
                    remediation="nihil",
                    recovery_evidence="nihil",
                )

            # 2. Ringkasan periode menyaring akurat & cocok dengan jumlah insiden.
            out_json = root / "summary.json"
            out_md = root / "summary.md"
            self.assertEqual(
                incident_book.main(
                    [
                        "summary",
                        "--book",
                        str(book),
                        "--start-date",
                        "2026-11-18",
                        "--end-date",
                        "2026-11-20",
                        "--out",
                        str(out_json),
                    ]
                ),
                0,
            )
            self.assertEqual(
                incident_book.main(
                    [
                        "summary",
                        "--book",
                        str(book),
                        "--start-date",
                        "2026-11-19",
                        "--end-date",
                        "2026-11-20",
                        "--format",
                        "markdown",
                        "--out",
                        str(out_md),
                    ]
                ),
                0,
            )
            rep = json.loads(out_json.read_text(encoding="utf-8"))
            md = out_md.read_text(encoding="utf-8")

            self.assertEqual(rep["summary"]["incident_count"], 3)
            self.assertEqual(
                rep["summary"]["by_kind"],
                {"budget_exhausted": 2, "spool_corruption": 1},
            )
            self.assertNotIn("inc-001", md)
            self.assertIn("inc-002", md)
            self.assertIn("inc-003", md)

            # 3. Modifikasi 1 byte pada entri terdahulu langsung ditolak saat dibaca maupun ditulis lagi.
            tampered = book.read_text(encoding="utf-8").replace("inc-001", "inc-999")
            book.write_text(tampered, encoding="utf-8")
            with self.assertRaises(incident_book.IncidentBookError):
                incident_book.summarize_period(book)
            self.assertEqual(
                incident_book.main(["summary", "--book", str(book)]),
                2,
            )


if __name__ == "__main__":
    unittest.main()
