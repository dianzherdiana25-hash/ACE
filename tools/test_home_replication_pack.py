"""Tes regresi fixture-only untuk tools.home_replication_pack (AG50)."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools import home_replication_pack


def _write_sqlite_store(db_path: Path, rows: list[tuple[str, str]]) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE gaps (id TEXT PRIMARY KEY, status TEXT NOT NULL)"
        )
        conn.executemany("INSERT INTO gaps (id, status) VALUES (?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


class HomeReplicationPackTest(unittest.TestCase):
    def test_separates_missing_files_from_per_record_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home_a = root / "home_a"
            home_b = root / "home_b"
            home_a.mkdir()
            home_b.mkdir()

            # memory.jsonl bersama: rec-ok identik, rec-conflict beda isi, rec-only-a hilang di home_b.
            rec_ok_a = {"seq": 1, "event": {"type": "record", "record": {"id": "rec-ok", "content": "sama"}}}
            rec_cf_a = {"seq": 2, "event": {"type": "record", "record": {"id": "rec-conflict", "content": "versi A"}}}
            rec_only_a = {"seq": 3, "event": {"type": "record", "record": {"id": "rec-only-a", "content": "hanya A"}}}

            rec_ok_b = {"seq": 1, "event": {"type": "record", "record": {"id": "rec-ok", "content": "sama"}}}
            rec_cf_b = {"seq": 2, "event": {"type": "record", "record": {"id": "rec-conflict", "content": "versi B"}}}

            (home_a / "memory.jsonl").write_text(
                "\n".join(json.dumps(x) for x in (rec_ok_a, rec_cf_a, rec_only_a)) + "\n",
                encoding="utf-8",
            )
            (home_b / "memory.jsonl").write_text(
                "\n".join(json.dumps(x) for x in (rec_ok_b, rec_cf_b)) + "\n",
                encoding="utf-8",
            )

            # SQLite store bersama: g1 sama, g2 konflik status.
            _write_sqlite_store(home_a / "store.sqlite", [("g1", "OPEN"), ("g2", "OPEN")])
            _write_sqlite_store(home_b / "store.sqlite", [("g1", "OPEN"), ("g2", "RESOLVED")])

            # Berkas yang hanya ada di rumah A (missing file) dan hanya di rumah B (extra file).
            (home_a / "snapshot_only_a.json").write_text('{"only": "a"}\n', encoding="utf-8")
            (home_b / "snapshot_only_b.json").write_text('{"only": "b"}\n', encoding="utf-8")

            manifest_a = root / "manifest_a.json"
            compare_out = root / "compare.json"

            self.assertEqual(
                home_replication_pack.main(
                    ["manifest", "--home", str(home_a), "--out", str(manifest_a)]
                ),
                0,
            )
            self.assertEqual(
                home_replication_pack.main(
                    [
                        "compare",
                        "--source",
                        str(manifest_a),
                        "--target",
                        str(home_b),
                        "--out",
                        str(compare_out),
                    ]
                ),
                0,
            )
            rep = json.loads(compare_out.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], home_replication_pack.SCHEMA)
        self.assertFalse(rep["sync_clean"])

        # Berkas hilang dipisahkan bersih dari konflik rekaman.
        self.assertEqual(rep["files"]["missing_on_target"], ["snapshot_only_a.json"])
        self.assertEqual(rep["files"]["extra_on_target"], ["snapshot_only_b.json"])
        self.assertEqual(rep["summary"]["missing_file_count"], 1)
        self.assertEqual(rep["summary"]["extra_file_count"], 1)

        # Konflik dilaporkan per record (memory rec-conflict + sqlite gaps:g2), bukan berkas hilang.
        conflicts = rep["records"]["conflicts"]
        self.assertEqual(rep["summary"]["record_conflict_count"], 2)
        conflict_pairs = {(c["file"], c["record_id"]) for c in conflicts}
        self.assertEqual(
            conflict_pairs,
            {("memory.jsonl", "rec-conflict"), ("store.sqlite", "gaps:g2")},
        )
        for item in conflicts:
            self.assertNotEqual(item["source_sha256"], item["target_sha256"])

        self.assertEqual(
            rep["records"]["missing_on_target"],
            [{"file": "memory.jsonl", "record_id": "rec-only-a"}],
        )
        matching_pairs = {(m["file"], m["record_id"]) for m in rep["records"]["matching"]}
        self.assertEqual(
            matching_pairs,
            {("memory.jsonl", "rec-ok"), ("store.sqlite", "gaps:g1")},
        )


if __name__ == "__main__":
    unittest.main()
