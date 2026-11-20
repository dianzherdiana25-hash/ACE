"""Pastikan rollover log mempertahankan pasangan kirim dan yatim yang terbuka."""
from contextlib import redirect_stdout
from io import StringIO
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.self_send_rehearsal import rehearse_batch
from tools.self_send_standing_audit import main, standing_audit


class StandingAuditTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))

    def test_three_utc_days_match_transitions_across_files(self):
        first, second, third = rehearse_batch(4)["log"][::2]
        rows = {
            "z-first.jsonl": [
                {**first, "ts": "2026-11-20T23:59:00Z"},
                {**second, "ts": "2026-11-20T23:59:30Z", "task_id": "unclosed"},
            ],
            "a-second.jsonl": [
                {**first, "ts": "2026-11-20T19:01:00-05:00", "outcome": "sent"},
                {**third, "ts": "2026-11-21T09:00:00Z"},
            ],
            "m-third.jsonl": [
                {**third, "ts": "2026-11-22T10:00:00Z", "outcome": "sent"},
                {**first, "ts": "2026-11-22T10:01:00Z", "outcome": "refused:fixture", "branch": "main"},
                {**third, "ts": "2026-11-22T11:00:00Z"},
            ],
        }
        for name, events in rows.items():
            (self.root / name).write_text("".join(json.dumps(event) + "\n" for event in events))
        originals = {path.name: path.read_bytes() for path in self.root.iterdir()}
        report = standing_audit(self.root)
        self.assertEqual(report, standing_audit(self.root))
        self.assertEqual(report["days"], [
            {"day_utc": day, "prepared": prepared, "sent": sent, "orphans": orphans,
             "sent_without_prepared": 0, "envelope_violations": violations}
            for day, prepared, sent, orphans, violations in (
                ("2026-11-20", 2, 0, 2, 0),
                ("2026-11-21", 1, 1, 2, 0),
                ("2026-11-22", 1, 1, 2, 1),
            )
        ])
        self.assertEqual(report["open_orphan_task_ids"],
                         sorted(["unclosed", f"{third['branch']}@{third['content_digest']}"]))
        self.assertEqual(report["undated_violations"], 0)
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([str(self.root), "--format", "text"]), 1)
            self.assertIn("3 hari, 4 prepared, 2 sent, 2 yatim terbuka", output.getvalue())
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()}, originals)

    def test_empty_directory_reports_no_events(self):
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([str(self.root)]), 0)
        self.assertEqual(json.loads(output.getvalue()), {
            "schema": "ace.self-send-standing-audit.v1", "days": [],
            "open_orphan_task_ids": [], "undated_violations": 0,
        })

    def test_invalid_timestamp_and_unpaired_sent_do_not_create_open_tasks(self):
        (self.root / "events.jsonl").write_text(
            '{"ts":"bad","outcome":"prepared"}\n'
            '{"ts":"2026-11-20T10:00:00Z","outcome":"sent",'
            '"branch":"ace-auto/20261120-only","content_digest":"synthetic"}\n'
        )
        report = standing_audit(self.root)
        self.assertEqual(report["undated_violations"], 1)
        self.assertEqual(report["days"][0]["sent_without_prepared"], 1)
        self.assertEqual(report["open_orphan_task_ids"], [])

    def test_distinct_task_ids_with_same_envelope_do_not_close_each_other(self):
        base = {"ts": "2026-11-20T10:00:00Z", "branch": "ace-auto/20261120-only",
                "content_digest": "synthetic"}
        rows = [{**base, "task_id": task_id, "outcome": outcome} for task_id, outcome in (
            ("first", "prepared"), ("second", "prepared"), ("second", "sent"),
        )]
        (self.root / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assertEqual(standing_audit(self.root)["open_orphan_task_ids"], ["first"])

    def test_mixed_gzip_directory_matches_uncompressed_and_marks_corrupt_gzip(self):
        first, second, third = rehearse_batch(4)["log"][::2]
        plain = self.root / "plain"
        mixed = self.root / "mixed"
        plain.mkdir()
        mixed.mkdir()
        shards = {
            "01.jsonl": [
                {**first, "ts": "2026-11-20T23:59:00Z"},
                {**second, "ts": "2026-11-20T23:59:30Z", "task_id": "unclosed"},
            ],
            "02.jsonl": [
                {**first, "ts": "2026-11-21T01:00:00Z", "outcome": "sent"},
                {**third, "ts": "2026-11-21T09:00:00Z"},
            ],
        }
        for name, events in shards.items():
            raw = "".join(json.dumps(event) + "\n" for event in events)
            (plain / name).write_text(raw, encoding="utf-8")
            if name == "02.jsonl":
                (mixed / f"{name}.gz").write_bytes(gzip.compress(raw.encode("utf-8")))
            else:
                (mixed / name).write_text(raw, encoding="utf-8")

        self.assertEqual(standing_audit(mixed), standing_audit(plain))

        corrupt = mixed / "03-corrupt.jsonl.gz"
        corrupt.write_bytes(b"corrupt-gz-bytes")
        report = standing_audit(mixed)
        self.assertEqual(report["undated_violations"], 1)
        self.assertEqual(len(report["corrupt_shards"]), 1)
        self.assertEqual(report["corrupt_shards"][0]["reason"], "corrupt_gzip_shard")
        self.assertEqual(report["corrupt_shards"][0]["source"], str(corrupt))
        with redirect_stdout(StringIO()):
            self.assertEqual(main([str(mixed)]), 1)
