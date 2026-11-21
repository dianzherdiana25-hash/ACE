"""Verifier cache, permintaan terikat, durabilitas dan penyimpanan paralel."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import perception_cache as model


DATA = b"fixture perceptual content"
STAMP = "2026-11-21T00:00:00Z"
VALUE = {"tiles": [1, 2]}


def request(**changes):
    return model._canonical({"schema": "ace.perception-cache-request.v1", "media_sha256": sha256(DATA).hexdigest(),
                             "operation": "fixture-feature", "algorithm_revision": "1",
                             "settings": {"width": 1, "height": 2}, **changes})


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))/"cache"

    def test_store_hit_missing_and_policy_revision_separated(self):
        self.assertEqual(model.lookup(self.root, DATA, request())["status"], "miss")
        self.assertFalse(self.root.exists())
        stored = model.store(self.root, DATA, request(), VALUE, STAMP)
        self.assertEqual(stored["status"], "stored")
        self.assertEqual(model.lookup(self.root, DATA, request())["entry"], stored["entry"])
        self.assertEqual(model.lookup(self.root, DATA, request(algorithm_revision="2"))["status"], "miss")
        self.assertEqual(model.lookup(self.root, DATA, request(settings={"width": 4}))["status"], "miss")
        self.assertEqual(model.lookup(self.root, DATA, request(settings={"height": 2, "width": 1}))["status"], "hit")

    def test_stale_age_boundary_future_and_age_without_clock(self):
        model.store(self.root, DATA, request(), VALUE, STAMP)
        self.assertEqual(model.lookup(self.root, DATA, request(), as_of="2026-11-21T07:00:03+07:00",
                         max_age_seconds=3)["status"], "hit")
        self.assertEqual(model.lookup(self.root, DATA, request(), as_of="2026-11-21T00:00:03.000001Z",
                         max_age_seconds=3)["status"], "stale")
        with self.assertRaisesRegex(ValueError, "masa depan"):
            model.lookup(self.root, DATA, request(), as_of="2026-11-20T23:59:59Z")
        with self.assertRaisesRegex(ValueError, "cap waktu"):
            model.lookup(self.root, DATA, request(), max_age_seconds=1)

    def test_two_concurrent_identical_stores_produce_same_committed_entry(self):
        def put():
            return model.store(self.root, DATA, request(), VALUE, STAMP)
        with ThreadPoolExecutor(2) as pool:
            first, second = [future.result() for future in (pool.submit(put), pool.submit(put))]
        self.assertEqual({first["status"], second["status"]}, {"stored", "reused"})
        self.assertEqual(first["entry"], second["entry"])
        self.assertEqual(len(list(self.root.iterdir())), 1)
        with self.assertRaisesRegex(ValueError, "berisi hasil berbeda"):
            model.store(self.root, DATA, request(), {"tiles": []}, STAMP)
        self.assertEqual(model.lookup(self.root, DATA, request())["entry"]["result"], VALUE)

    def test_source_digest_and_byte_tamper_detected(self):
        with self.assertRaisesRegex(ValueError, "Media berbeda"):
            model.key_for(DATA+b"!", request())
        result = model.store(self.root, DATA, request(), VALUE, STAMP)
        path = self.root/(result["key"]+".json")
        payload = json.loads(path.read_bytes())
        payload.update(stored_at="2026-11-21T00:00:01Z")
        path.write_bytes(model._canonical(payload)+b"\n")
        with self.assertRaisesRegex(ValueError, "Checksum entry"):
            model.lookup(self.root, DATA, request())

    def test_cache_entry_symlinks_are_not_followed(self):
        self.root.mkdir()
        outside = self.root.parent/"outside"
        outside.write_bytes(b"only fixture")
        key, _ = model.key_for(DATA, request())
        (self.root/(key+".json")).symlink_to(outside)
        with self.assertRaises(OSError):
            model.lookup(self.root, DATA, request())
        with self.assertRaises(OSError):
            model.store(self.root, DATA, request(), VALUE, STAMP)
        self.assertEqual(outside.read_bytes(), b"only fixture")
