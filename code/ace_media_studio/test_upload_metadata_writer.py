import unittest

from ._contracts import identity
from .upload_metadata_writer import prepare_metadata


class MetadataTests(unittest.TestCase):
    def test_approval_platform_limits_credits_and_sources(self):
        plan = {"schema": "ace.media.metadata-plan.v1", "platform": "fixture", "media_sha256": "a" * 64,
                "title": "Klip Sore", "source_ref": "fixture:brief", "limits": {"title": 18, "description": 120, "tags": 2},
                "facts": [{"id": "scene", "text": "Ada empat panel.", "source_ref": "fixture:script", "approved": True}],
                "tags": ["Sore", "Visual", "sore"], "credits": [
                    {"asset": "cover", "credit": "Studio", "license_ref": "fixture:original"}]}
        report = prepare_metadata(plan, identity(plan))
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["upload_fields"]["tags"], ["sore", "visual"])
        self.assertEqual(report["upload_fields"]["description"].splitlines(),
                         ["Ada empat panel.", "Kredit cover: Studio (fixture:original)"])
        self.assertEqual([line["source_ref"] for line in report["line_sources"]],
                         ["fixture:script", "fixture:original"])
        plan["facts"][0]["approved"] = False
        plan["limits"]["title"] = 3
        blocked = prepare_metadata(plan, identity(plan))
        self.assertIsNone(blocked["upload_fields"])
        self.assertEqual([row["rule"] for row in blocked["blocking"]],
                         ["unapproved_fact", "no_approved_description", "platform_limit"])
        self.assertNotIn("Ada empat panel", str(blocked))
