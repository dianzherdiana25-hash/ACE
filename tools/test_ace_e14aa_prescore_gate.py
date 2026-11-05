import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.ace_e14aa_prescore_gate import verify, PrescoreGateError


class PrescoreGateTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        (self.root/'code').mkdir()
        (self.root/'code'/'worker.py').write_bytes(b'print("hello")\n')
        self.source = 'code/worker.py'
        self.lock = self.root/'locked.json'
        self.data = {'status': 'PRESCORE_LOCK', 'version': 1,
                     'base_sha': '0'*40, 'files': {self.source: hashlib.sha256(
                         (self.root/self.source).read_bytes()).hexdigest()}}
        self.write_lock()

    def write_lock(self):
        self.lock.write_text(json.dumps(self.data))

    def test_valid_lock_does_not_execute_source(self):
        r = verify(self.root, self.lock)
        self.assertEqual(r['status'], 'PRESCORE_LOCAL_HASHES_MATCH')
        self.assertEqual(r['files_checked'], 1)
        self.assertFalse(r['scoring_performed'])
        self.assertFalse(r['independent_custody'])

    def test_byte_drift_fails_closed(self):
        (self.root/self.source).write_bytes(b'print("bye")\n')
        with self.assertRaisesRegex(PrescoreGateError,'mismatch'):
            verify(self.root, self.lock)

    def test_path_traversal_rejected_even_with_matching_digest(self):
        self.data['files'] = {'../locked.json': '0'*64}
        self.write_lock()
        with self.assertRaises(PrescoreGateError):
            verify(self.root, self.lock)

    def test_symlinked_source_rejected(self):
        (self.root/self.source).unlink()
        (self.root/self.source).symlink_to(self.lock)
        with self.assertRaisesRegex(PrescoreGateError,'symlink'):
            verify(self.root, self.lock)

    def test_invalid_type_aliases_rejected(self):
        for version in (True, 1.0, None):
            with self.subTest(version=version):
                self.data['version'] = version
                self.write_lock()
                with self.assertRaises(PrescoreGateError):
                    verify(self.root, self.lock)

    def test_missing_file_and_wrong_status_rejected(self):
        self.data['files'] = {'code/missing.py': '0'*64}
        self.write_lock()
        with self.assertRaises(PrescoreGateError):
            verify(self.root, self.lock)
        self.data['status'] = 'SCORED'
        self.write_lock()
        with self.assertRaises(PrescoreGateError):
            verify(self.root, self.lock)

    def test_lock_symlink_rejected(self):
        original = self.root/'original.json'
        self.lock.rename(original)
        self.lock.symlink_to(original)
        with self.assertRaises(PrescoreGateError):
            verify(self.root, self.lock)


if __name__ == '__main__':
    unittest.main()
