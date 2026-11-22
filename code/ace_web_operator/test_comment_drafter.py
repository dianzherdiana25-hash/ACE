"""Verifier template berkategori dan draf tertahan tanpa bukti fakta."""
import unittest

from ace_web_operator import comment_drafter
from ace_web_operator._contracts import ContractError,identity


class CommentsTests(unittest.TestCase):
    def setUp(self):
        self.inbox={"schema":"ace.web.comment-inbox.v1","comments":[{"id":"first","category":"question","locale":"id",
                  "source_ref":"fixture/question","comment_sha256":"a"*64}]}
        self.facts={"schema":"ace.web.comment-facts.v1","entries":[{"id":"schedule","value":"Kamis",
                    "status":"verified","source_ref":"fixture/calendar","evidence_sha256":"b"*64}]}
        self.policy={"schema":"ace.web.comment-draft-policy.v1","source_ref":"fixture/template",
                     "inbox_sha256":identity(self.inbox),"templates":[{"category":"question","locale":"id",
                         "body":"Jadwal yang tercatat {schedule}.","facts":["schedule"],"source_ref":"fixture/reply"}]}

    def say(self):
        self.policy["facts_sha256"]=identity(self.facts)
        return comment_drafter.draft(self.policy,identity(self.policy),self.inbox,self.facts)

    def test_verified_fact_is_linked_in_draft_for_review(self):
        result=self.say()
        self.assertFalse(result["sent"])
        first=result["drafts"][0]
        self.assertEqual(first["draft"],"Jadwal yang tercatat Kamis.")
        self.assertEqual(first["fact_refs"][0]["source_ref"],"fixture/calendar")

    def test_unknown_fact_or_object_access_will_not_render(self):
        self.facts["entries"][0]["status"]="unverified"
        self.assertEqual(self.say()["drafts"][0]["missing_facts"],["schedule"])
        self.assertIsNone(self.say()["drafts"][0]["draft"])
        self.policy["templates"][0]["body"]="{schedule.__class__}"
        with self.assertRaisesRegex(ContractError,"Placeholder"):
            self.say()
