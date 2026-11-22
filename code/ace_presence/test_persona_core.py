from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import PresenceError, canonical, identity
from .persona_core import revise
from .test_rolling_summary import save


class PersonaTests(unittest.TestCase):
    def test_two_version_history_requires_evidence_only_for_actual_changes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = {"tone": "Ringkas", "identifier": "ace", "languages": ["id", "en"],
                    "boundaries": ["Rujuk bukti yang tersedia."]}
            initial = {"schema": "ace.presence.persona-plan.v1", "version": 1, "effective": "2025-04-30",
                       "profile": data, "parent": None,
                       "evidence": [{"field": key, "source_ref": "fixture:charter"} for key in data]}
            first = revise(initial, identity(initial), root)
            prior = save(root, "first.json", canonical(first["revision"]))
            second = initial | {"version": 2, "effective": "2025-05-01", "profile": data | {"tone": "Teknis"},
                                "parent": prior, "evidence": [{"field": "tone", "source_ref": "fixture:revision"}]}
            outcome = revise(second, identity(second), root)
            self.assertEqual(outcome["changed_fields"], ["tone"])
            self.assertEqual(outcome["revision"]["parent_sha256"], prior["sha256"])
            second["profile"]["identifier"] = "different"
            with self.assertRaisesRegex(PresenceError, "identitas"):
                revise(second, identity(second), root)
