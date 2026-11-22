"""Verifier runtime antrean hasil build dengan lease kedaluwarsa dan retry."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import worker_builder
from ace_software_factory._contracts import identity
from ace_software_factory.repo_scaffolder import materialize


class LeaseTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        config = {"schema": "ace.factory-worker-plan.v1", "id": "work", "source_ref": "fixture/queue",
                  "max_jobs": 3, "max_payload_bytes": 100,
                  "queues": [{"id": "stock", "max_attempts": 2, "lease_seconds": 5,
                              "retry_seconds": 3, "source_ref": "fixture/policy"}]}
        files, report = worker_builder.build(config, identity(config))
        materialize(root / "runtime", files)
        spec = spec_from_file_location("generated_queue", root / "runtime" / report["runtime"]["path"])
        self.runtime = module_from_spec(spec)
        spec.loader.exec_module(self.runtime)
        self.db = root / "jobs.sqlite"
        self.runtime.initialize(self.db)

    def test_one_live_lease_and_late_owner_cannot_finish_reclaimed_job(self):
        driver = self.runtime
        driver.enqueue(self.db,"a","stock",{"units":4},0)
        claimed = driver.claim(self.db,"stock",0)
        self.assertIsNone(driver.claim(self.db,"stock",4))
        retried = driver.claim(self.db,"stock",5)
        self.assertEqual(retried["attempt"],2)
        self.assertEqual(driver.finish(self.db,"a",claimed["lease"],5,success=True),{"status":"lease_lost"})
        self.assertEqual(driver.finish(self.db,"a",retried["lease"],5,success=True)["status"],"done")
        self.assertEqual(driver.inspect(self.db,"a")["attempts"],2)

    def test_retries_are_delayed_and_dead_lettered_after_final_attempt(self):
        driver = self.runtime
        driver.enqueue(self.db,"a","stock",{},0)
        early = driver.claim(self.db,"stock",0)
        self.assertEqual(driver.finish(self.db,"a",early["lease"],1,success=False)["available"],4)
        self.assertIsNone(driver.claim(self.db,"stock",3))
        late = driver.claim(self.db,"stock",4)
        self.assertEqual(late["attempt"],2)
        self.assertIsNone(driver.claim(self.db,"stock",10))
        self.assertEqual(driver.inspect(self.db,"a")["outcome"],"lease_exhausted")

    def test_idempotent_insert_guards_payload_and_history(self):
        driver = self.runtime
        driver.enqueue(self.db,"a","stock",{},0)
        self.assertTrue(driver.enqueue(self.db,"a","stock",{},1)["duplicate"])
        with self.assertRaisesRegex(ValueError,"job_id_conflict"):
            driver.enqueue(self.db,"a","stock",{"changed":True},1)
        driver.enqueue(self.db,"b","stock",{},0)
        driver.enqueue(self.db,"c","stock",{},0)
        with self.assertRaisesRegex(ValueError,"history_full"):
            driver.enqueue(self.db,"d","stock",{},0)
