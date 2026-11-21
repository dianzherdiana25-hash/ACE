"""Jalankan reviewer pada sumber bernama, termasuk byte yang berubah."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import self_reviewer
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


def fixture(test, files):
    root = Path(test.enterContext(TemporaryDirectory())) / "sources"
    materialize(root, files)
    manifest = {"schema": self_reviewer.SOURCE_SCHEMA, "source_ref": "fixture/sources",
                "files": [{"path": path, "sha256": sha256(payload).hexdigest()} for path, payload in files.items()]}
    return root, manifest


class ReviewerTests(unittest.TestCase):
    def test_finds_only_supported_patterns_with_line_and_file_hash(self):
        source = b"""def f(options=[], *, rules=dict()):
    try:
        assert (1, 0)
        return 5 is options
        unused = 2
    except (ValueError, Exception):
        pass
def g():
    try:
        return None
    except:
        raise
"""
        root, manifest = fixture(self, {"app.py": source, "clean.py": b"def clean(a=None):\n    return a is None\n"})
        result = self_reviewer.review(root, manifest, identity(manifest))
        self.assertEqual(result["status"], "review_required")
        rows = result["findings"]
        self.assertEqual([(row["line"], row["rule"]) for row in rows], [
            (1, "mutable_default"), (1, "mutable_default"), (3, "assertion_uses_nonempty_tuple"),
            (4, "identity_compares_value_literal"), (5, "unreachable_statement"),
            (6, "broad_exception_suppressed"), (11, "bare_except")])
        self.assertEqual({row["path"] for row in rows}, {"app.py"})
        self.assertEqual({row["sha256"] for row in rows}, {sha256(source).hexdigest()})

    def test_non_python_syntax_is_reported_without_running_import_side_effects(self):
        root, manifest = fixture(self, {"broken.py": b"def missing(\n", "app.py": b"raise RuntimeError()\n"})
        result = self_reviewer.review(root, manifest, identity(manifest))
        self.assertEqual([(row["path"], row["rule"], row["line"]) for row in result["findings"]],
                         [("broken.py", "syntax_error", 1)])
        self.assertEqual([row["parse_ok"] for row in result["sources"]], [True, False])

    def test_wrong_anchor_refuses_to_review_different_source(self):
        root, manifest = fixture(self, {"app.py": b"pass\n"})
        (root / "app.py").write_bytes(b"raise RuntimeError()\n")
        with self.assertRaisesRegex(ContractError, "SHA-256"):
            self_reviewer.review(root, manifest, identity(manifest))
