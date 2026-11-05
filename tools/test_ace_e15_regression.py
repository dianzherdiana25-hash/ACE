import tempfile,unittest,json
from pathlib import Path
from .ace_e15_regression import TESTS, PATTERN, collect, sha

class RegressionReceiptTests(unittest.TestCase):
    def test_groups_frozen(self):
        self.assertEqual(len(TESTS),9)
        self.assertEqual(sum(len(v) for v in TESTS.values()),25)
    def test_parser_requires_ok_footer(self):
        self.assertIsNone(PATTERN.search('Ran 34 tests in 1.02s\nFAILED'))
        self.assertIsNotNone(PATTERN.search('Ran 32 tests in 3.75s\n\nOK'))
    def test_partial_set_halts(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'missing group'):
                collect(Path(root))
    def test_tamper_requires_full_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            for group,modules in TESTS.items():
                blob=b'Ran 1 test in 0.001s\n\nOK\n'
                (out/(group+'.log')).write_bytes(blob)
                record={'group':group,'modules':modules,'exit_code':0,'tests_passed':1,
                        'status':'PASS','log_sha256':sha(blob),'log_bytes':len(blob),
                        'wall_seconds':1.0,'python':'3.13.5'}
                (out/(group+'.json')).write_text(json.dumps(record))
            self.assertEqual(collect(out)['groups'],9)
            (out/'u.log').write_bytes(b'TAMPERED')
            with self.assertRaisesRegex(ValueError,'mismatch'):
                collect(out)

if __name__=='__main__':unittest.main()
