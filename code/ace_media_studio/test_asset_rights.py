import unittest

from ._contracts import identity
from .asset_rights import check_rights


class RightsTests(unittest.TestCase):
    def test_usage_date_country_credit_and_hash_are_all_required(self):
        row = {"id": "original", "asset_sha256": "a" * 64, "license_ref": "fixture:grant",
               "uses": ["trailer"], "territories": ["ID"], "effective": "2025-01-01",
               "expires": "2025-05-01", "credit": "Creative Studio"}
        policy = {"schema": "ace.media.rights-registry.v1", "grants": [row]}
        usage = {"schema": "ace.media.rights-intent.v1", "use": "trailer", "date": "2025-05-01", "territories": ["ID"],
                 "assets": [{"id": "poster", "sha256": "a" * 64, "credits": ["Creative Studio"]}]}
        case = check_rights(policy, identity(policy), usage, identity(usage))
        self.assertEqual(case["status"], "recorded_grants_cover_intent")
        usage.update(date="2025-05-02", use="ad", territories=["SG"])
        usage["assets"][0]["credits"].clear()
        case = check_rights(policy, identity(policy), usage, identity(usage))
        self.assertEqual(case["assets"][0]["denials"][0]["reasons"], ["use", "territory", "date", "credit"])
        usage["assets"][0]["sha256"] = "b" * 64
        case = check_rights(policy, identity(policy), usage, identity(usage))
        self.assertEqual(case["assets"][0]["status"], "unlisted")
