from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .data_analyst import analyze


def column(name, kind, nullable=False, normalize="exact", minimum=None, maximum=None):
    return {"name": name, "kind": kind, "nullable": nullable, "normalize": normalize,
            "minimum": minimum, "maximum": maximum}


def table(root, data, columns):
    (root / "source.csv").write_bytes(data)
    return {"path": "source.csv", "sha256": sha256(data).hexdigest()}, {"columns": columns, "max_rows": 50}


class AnalysisTests(unittest.TestCase):
    def test_profiles_use_valid_rows_and_report_pairwise_denominators_and_lines(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pointer, spec = table(root, b"group,a,b\n X ,1,2\ny,2,4\nx,3,6\nx,4,\nx,-8,8\n",
                                  [column("group", "category", normalize="casefold"),
                                   column("a", "integer", minimum="0"), column("b", "decimal", nullable=True)])
            plan = {"schema": "ace.institute.analysis-plan.v1", "data": pointer,
                    "format": spec, "pairs": [{"first": "a", "second": "b"}]}
            report = analyze(plan, identity(plan), root)
            self.assertEqual(report["columns"]["a"]["quantiles"]["p50"], "2.5")
            self.assertEqual(report["columns"]["group"]["most_frequent"][0], {"value": "x", "n": 3})
            self.assertEqual(report["columns"]["b"]["missing"], 1)
            self.assertEqual(report["accepted"], 4)
            self.assertEqual(report["rejected"][0]["line"], 6)
            self.assertEqual(report["correlations"][0], {"first": "a", "second": "b", "pearson_r": "1",
                                                        "pairwise_n": 3, "lines": [2, 3, 4]})
