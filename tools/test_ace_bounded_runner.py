import tempfile
import unittest
import sys
from pathlib import Path
from ace_bounded_runner import run


class BoundedRunnerTests(unittest.TestCase):
    def test_success(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "ok.log"
            result = run([sys.executable, "-c", "print('ok')"],
                         timeout=5, heartbeat=0.05, log_file=p)
            self.assertEqual(result["status"], "OK")
            self.assertIn(b"ok", p.read_bytes())

    def test_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as root:
            result = run([sys.executable, "-c", "raise SystemExit(7)"],
                         timeout=5, heartbeat=0.05, log_file=Path(root)/"fail.log")
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["exit_code"], 7)

    def test_timeout_terminates_worker(self):
        with tempfile.TemporaryDirectory() as root:
            result = run([sys.executable, "-c", "import time; time.sleep(30)"],
                         timeout=0.2, heartbeat=0.05, log_file=Path(root)/"timeout.log")
            self.assertEqual(result["status"], "TIMEOUT")
            self.assertLess(result["elapsed_s"], 3)


if __name__ == "__main__":
    unittest.main()
