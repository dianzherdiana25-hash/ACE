"""Tes deduplikasi rotasi log tumpang-tindih dan deteksi konflik antar-shard (AG8)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.self_send_standing_audit import main, standing_audit


class SelfSendAuditShardDedupeTests(unittest.TestCase):
    def test_overlapping_rotation_dedupes_identical_and_flags_conflict(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared_prep = {
                "task_id": "task-overlap-1",
                "ts": "2026-11-20T09:00:00Z",
                "outcome": "prepared",
                "branch": "ace-auto/20261120-a1",
                "content_digest": "sha-overlap-1",
                "source": "spool/req/1.json",
            }
            shared_sent = {
                "task_id": "task-overlap-1",
                "ts": "2026-11-20T09:01:00Z",
                "outcome": "sent",
                "branch": "ace-auto/20261120-a1",
                "content_digest": "sha-overlap-1",
                "source": "spool/resp/1.json",
            }
            unique_prep = {
                "task_id": "task-unique-2",
                "ts": "2026-11-20T10:00:00Z",
                "outcome": "prepared",
                "branch": "ace-auto/20261120-b2",
                "content_digest": "sha-unique-2",
                "source": "spool/req/2.json",
            }
            # Konflik antar-shard: task_id + ts + source sama, tetapi outcome berbeda!
            conflict_shard1 = {
                "task_id": "task-conflict-3",
                "ts": "2026-11-20T11:00:00Z",
                "outcome": "sent",
                "branch": "ace-auto/20261120-c3",
                "content_digest": "sha-conflict-3",
                "source": "spool/resp/3.json",
            }
            conflict_shard2 = {
                "task_id": "task-conflict-3",
                "ts": "2026-11-20T11:00:00Z",
                "outcome": "refused:fixture_mismatch",
                "branch": "ace-auto/20261120-c3",
                "content_digest": "sha-conflict-3",
                "source": "spool/resp/3.json",
            }

            (root / "01-rot.jsonl").write_text(
                "\n".join(json.dumps(x) for x in (shared_prep, shared_sent, conflict_shard1)) + "\n",
                encoding="utf-8",
            )
            (root / "02-rot.jsonl").write_text(
                "\n".join(json.dumps(x) for x in (shared_prep, shared_sent, unique_prep, conflict_shard2)) + "\n",
                encoding="utf-8",
            )

            report = standing_audit(root)
            self.assertEqual(main([str(root)]), 1)

        # Identik antar-shard (shared_prep + shared_sent) tepat 2 kali ter-dedupe;
        # hanya terhitung 1x prepared (shared_prep) + 1x prepared (unique_prep) = 2 prepared,
        # 1x sent (shared_sent), 1 yatim terbuka (task-unique-2); task-conflict-3 tidak diam-diam dipilih.
        self.assertEqual(report["deduped_events"], 2)
        self.assertEqual(len(report["days"]), 1)
        self.assertEqual(report["days"][0]["prepared"], 2)
        self.assertEqual(report["days"][0]["sent"], 1)
        self.assertEqual(report["days"][0]["orphans"], 1)
        self.assertEqual(report["open_orphan_task_ids"], ["task-unique-2"])

        conflicts = report["shard_conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["task_id"], "task-conflict-3")
        self.assertEqual(conflicts[0]["reason"], "cross_shard_conflicting_event")
        self.assertEqual(
            [(e["shard"], e["status"]) for e in conflicts[0]["entries"]],
            [("01-rot.jsonl", "sent"), ("02-rot.jsonl", "refused:fixture_mismatch")],
        )


if __name__ == "__main__":
    unittest.main()
