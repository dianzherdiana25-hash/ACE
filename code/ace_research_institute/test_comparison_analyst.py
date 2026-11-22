from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .comparison_analyst import compare


def save(root, name, raw):
    (root / name).write_bytes(raw)
    return {"path": name, "sha256": sha256(raw).hexdigest()}


class ComparisonTests(unittest.TestCase):
    def test_weighted_scores_converted_units_and_required_missing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)

            def alt(key, speed, score):
                metrics = [{"id": "score", "value": score, "unit": "points", "source_ref": "fixture:score"}]
                if speed is not None:
                    metrics.append({"id": "speed", "value": speed, "unit": "ms", "source_ref": "fixture:timer"})
                return {"id": key, **save(root, f"{key}.json", canonical({"schema": "ace.institute.observations.v1", "metrics": metrics}))}

            plan = {"schema": "ace.institute.comparison-plan.v1", "minimum_coverage_bp": 8000,
                    "criteria": [{"id": "speed", "unit": "s", "floor": "0", "ceiling": "4", "prefer": "lower",
                                  "weight": 5000, "required": True},
                                 {"id": "score", "unit": "points", "floor": "0", "ceiling": "10", "prefer": "higher",
                                  "weight": 5000, "required": False}],
                    "alternatives": [alt("fast", 1000, 8), alt("slow", 3000, 10), alt("unknown", None, 10)]}
            result = compare(plan, identity(plan), root)
            self.assertEqual(result["eligible_rank"], ["fast", "slow"])
            scores = {item["id"]: item["score_bp"] for item in result["alternatives"]}
            self.assertEqual(scores, {"fast": 7750, "slow": 6250, "unknown": None})
