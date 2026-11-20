"""Tes perencana gabung replikasi (lease satu-penulis, urutan salin, daftar konflik) (AG84)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import home_replication_pack


class HomeReplicationMergePlanTest(unittest.TestCase):
    def test_merge_plan_with_one_conflict_copies_nothing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            home_a = root / "home_a"
            home_b = root / "home_b"
            home_a.mkdir()
            home_b.mkdir()

            (home_a / "memory.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"id": "rec-same", "content": "identik"}),
                        json.dumps({"id": "rec-a-only", "content": "dari rumah A"}),
                        json.dumps({"id": "rec-conflict", "content": "versi A"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (home_b / "memory.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"id": "rec-same", "content": "identik"}),
                        json.dumps({"id": "rec-b-only", "content": "dari rumah B"}),
                        json.dumps({"id": "rec-conflict", "content": "versi B"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (home_a / "extra_from_a.json").write_text('{"note": "a"}\n', encoding="utf-8")

            snap_a = {p.name: p.read_bytes() for p in home_a.iterdir()}
            snap_b = {p.name: p.read_bytes() for p in home_b.iterdir()}

            man_a = root / "man_a.json"
            man_b = root / "man_b.json"
            plan_out = root / "merge_plan.json"
            self.assertEqual(
                home_replication_pack.main(["manifest", "--home", str(home_a), "--out", str(man_a)]),
                0,
            )
            self.assertEqual(
                home_replication_pack.main(["manifest", "--home", str(home_b), "--out", str(man_b)]),
                0,
            )
            self.assertEqual(
                home_replication_pack.main(
                    ["merge-plan", "--left", str(man_a), "--right", str(man_b), "--out", str(plan_out)]
                ),
                0,
            )

            # Pastikan tidak ada satu pun berkas disalin ataupun diubah di kedua rumah!
            self.assertEqual({p.name: p.read_bytes() for p in home_a.iterdir()}, snap_a)
            self.assertEqual({p.name: p.read_bytes() for p in home_b.iterdir()}, snap_b)
            self.assertFalse((home_b / "extra_from_a.json").exists())

            plan = json.loads(plan_out.read_text(encoding="utf-8"))

        self.assertEqual(plan["schema"], home_replication_pack.MERGE_PLAN_SCHEMA)
        self.assertTrue(plan["plan_only"])
        self.assertFalse(plan["executed_copy"])
        self.assertFalse(plan["summary"]["clean_auto_merge"])
        self.assertEqual(plan["summary"]["conflict_decision_count"], 1)

        # Tabel lease satu-penulis per record.
        leases = {(r["file"], r["record_id"]): r for r in plan["lease_table"]}
        self.assertEqual(leases[("memory.jsonl", "rec-same")]["writer_lease"], "shared_synced")
        self.assertEqual(leases[("memory.jsonl", "rec-a-only")]["writer_lease"], "home_a")
        self.assertEqual(leases[("memory.jsonl", "rec-b-only")]["writer_lease"], "home_b")
        self.assertEqual(
            leases[("memory.jsonl", "rec-conflict")]["writer_lease"],
            "HELD_PENDING_OPERATOR_DECISION",
        )

        # Urutan salin hanya mencakup file/record non-konflik.
        copy_targets = [(c["kind"], c["file"], c.get("record_id")) for c in plan["copy_sequence"]]
        self.assertEqual(
            copy_targets,
            [
                ("copy_file", "extra_from_a.json", None),
                ("copy_record", "memory.jsonl", "rec-a-only"),
                ("copy_record", "memory.jsonl", "rec-b-only"),
            ],
        )

        # Konflik yang butuh keputusan operator.
        conflict = plan["conflicts_requiring_decision"][0]
        self.assertEqual((conflict["file"], conflict["record_id"]), ("memory.jsonl", "rec-conflict"))
        self.assertTrue(conflict["held"])
        self.assertNotEqual(conflict["left_sha256"], conflict["right_sha256"])


if __name__ == "__main__":
    unittest.main()
