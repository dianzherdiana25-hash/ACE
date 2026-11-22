from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .number_provenance import scan_prose
from .test_comparison_analyst import save
from .unsourced_number_detector import locate_unsourced


class MissingCitationTests(unittest.TestCase):
    def test_missing_unresolvable_and_valid_citations_are_separate(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b"Laporan 4 dari 5, lalu 9 poin.\n"
            offsets = list(dict(scan_prose(raw.decode())))
            plan = {"schema": "ace.institute.unsourced-number-plan.v1", "draft": save(root, "draft.md", raw),
                    "references": [{"id": "observed", "line": 1, **save(root, "source.txt", b"Data tersedia\n")}],
                    "annotations": [{"line": line, "column": column, "ref": ref}
                                    for (line, column), ref in zip(offsets, ("observed", "missing"))]}
            result = locate_unsourced(plan, identity(plan), root)
            self.assertEqual(result["numbers_found"], 3)
            self.assertEqual([row["reason"] for row in result["without_pointer"]],
                             ["no_resolvable_pointer", "missing_annotation"])
