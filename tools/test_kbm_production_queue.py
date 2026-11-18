from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools.kbm_production_queue import STATUS, enqueue, export_review, list_items
from tools.test_cover_check import _make_png


class ProductionQueueTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.source = root / "source.md"
        self.source.write_text(
            "# Bab 1: Awal\nBeberapa kata untuk contoh pertama.\n\n"
            "# Bab 2: Akhir\nBeberapa kata untuk contoh berikutnya.\n",
            encoding="utf-8",
        )
        self.cover = root / "cover.png"
        self.cover.write_bytes(_make_png(800, 1200))
        self.db = root / "queue.sqlite3"

    def put(self, **overrides):
        thresholds = {"min_words": 3, "min_bytes": 12} | overrides
        return enqueue(self.source, self.cover, self.db, **thresholds)

    def test_end_to_end_snapshot_and_idempotent_retry(self):
        self.assertEqual(list_items(self.db), [])
        self.assertFalse(self.db.exists())
        first = self.put()
        repeated = self.put()
        self.assertTrue(first["inserted"])
        self.assertFalse(repeated["inserted"])
        self.assertEqual(first["id"], repeated["id"])
        self.assertIs(first["upload_authorized"], False)
        self.assertEqual(self.db.stat().st_mode & 0o077, 0)
        item, = list_items(self.db)
        self.assertEqual(item["status"], STATUS)
        manifest = item["manifest"]
        self.assertEqual(len(manifest["chapters"]), 2)
        self.assertNotIn("source_manuscript", manifest)
        with closing(sqlite3.connect(self.db)) as connection:
            blobs = dict(connection.execute("SELECT name, payload FROM kbm_review_blob"))
        cover = manifest["cover"]
        self.assertEqual(blobs[cover["file"]], self.cover.read_bytes())
        for chapter in manifest["chapters"]:
            self.assertEqual(hashlib.sha256(blobs[chapter["bundle_file"]]).hexdigest(), chapter["sha256"])

    def test_bad_cover_and_short_chapter_leave_queue_uncreated(self):
        self.cover.write_bytes(_make_png(100, 200))
        result = self.put()
        self.assertFalse(result["queued"])
        self.assertIn("cover_rules_failed", result["errors"])
        self.cover.write_bytes(_make_png(800, 1200))
        result = self.put(min_words=100)
        self.assertFalse(result["queued"])
        self.assertFalse(self.db.exists())

    def test_changed_content_creates_distinct_review_item(self):
        first = self.put()
        with self.source.open("a", encoding="utf-8") as stream:
            stream.write("Satu kalimat tambahan.\n")
        second = self.put()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(list_items(self.db)), 2)

    def test_parallel_retry_creates_a_single_complete_item(self):
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: self.put(), range(2)))
        self.assertEqual(sum(result["inserted"] for result in results), 1)
        self.assertEqual(len(list_items(self.db)), 1)
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM kbm_review_blob").fetchone(), (3,))

    def test_existing_corrupt_item_is_not_reported_as_valid_retry(self):
        item = self.put()
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("UPDATE kbm_review_blob SET payload = ?", (b"altered",))
        with self.assertRaisesRegex(ValueError, "existing queue item"):
            self.put()
        preview = self.db.with_name("review")
        with self.assertRaisesRegex(ValueError, "payload failed integrity"):
            export_review(self.db, item["id"], preview)
        self.assertFalse(preview.exists())

    def test_review_exports_snapshot_into_fresh_local_directory(self):
        item = self.put()
        self.source.unlink()
        self.cover.unlink()
        preview = self.db.with_name("review")
        self.assertIs(export_review(self.db, item["id"], preview)["upload_authorized"], False)
        self.assertEqual(len(list(preview.iterdir())), 4)
        with self.assertRaises(FileExistsError):
            export_review(self.db, item["id"], preview)

    def test_public_permission_queue_rejected(self):
        self.db.touch(mode=0o644)
        self.db.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private regular file"):
            self.put()
