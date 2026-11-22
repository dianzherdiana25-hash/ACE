from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .learner_model import posterior
from .test_tabular_engine import save


def profile(root):
    rows = [{"id": f"attempt_{index}", "learner": person, "topic": topic, "date": day, "earned": earned,
             "possible": 4, "source_ref": f"fixture:item:{index}"} for index, (person, topic, day, earned) in enumerate((
                 ("student", "base", "2025-04-09", 0), ("student", "base", "2025-04-10", 2),
                 ("student", "target", "2025-04-12", 4), ("other", "base", "2025-04-08", 4)), 1)]
    ref = save(root, "attempts.jsonl", b"\n".join(map(canonical, rows)))
    return {"schema": "ace.teaching.learner-plan.v1", "learner": "student", "as_of": "2025-04-11",
            "topics": ["base", "target"], "attempts": ref, "minimum_attempts": 2,
            "prior": {"alpha": 1, "beta": 1}}


class LearnerTests(unittest.TestCase):
    def test_fractional_credit_and_missing_evidence_are_visible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = profile(root)
            found = posterior(plan, identity(plan), root)
            self.assertEqual(found["disregarded_lines"], [3, 4])
            base, target = [found["topic_posteriors"][key] for key in ("base", "target")]
            self.assertEqual((base["posterior_mean_bp"], base["alpha_exact"], base["beta_exact"]), (3750, [3, 2], [5, 2]))
            self.assertEqual(base["evidence_status"], "observed")
            self.assertEqual(target["evidence_status"], "insufficient_attempts")
            self.assertIsNone(target["latest"])
