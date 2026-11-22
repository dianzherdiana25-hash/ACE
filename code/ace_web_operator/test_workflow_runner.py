"""Verifier alur graf, stop pada assertion dan urutan receipt."""
import unittest

from ace_web_operator import workflow_runner
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import browser_available,fixture,plan


def workflow(port):
    base=plan(port)
    settings={key:base[key] for key in ("origin","allow_paths","timeout_ms","request_limit")}
    return {"schema":"ace.web.workflow-plan.v1","source_ref":"fixture/workflow","browser":settings,
            "stages":[{"id":"confirm","requires":["prepare"],"steps":base["steps"][4:],"source_ref":"fixture/end"},
                      {"id":"open","requires":[],"steps":base["steps"][:2],"source_ref":"fixture/open"},
                      {"id":"prepare","requires":["open"],"steps":base["steps"][2:4],"source_ref":"fixture/prep"}]}


class WorkflowTests(unittest.TestCase):
    def test_stage_plan_is_deterministic_and_cycles_refused(self):
        raw=workflow(9010)
        first,stages=workflow_runner.compile_workflow(raw,identity(raw))
        raw["stages"].reverse()
        self.assertEqual(workflow_runner.compile_workflow(raw,identity(raw))[0],first)
        self.assertEqual([item["id"] for item in stages],["open","prepare","confirm"])
        next(item for item in raw["stages"] if item["id"]=="open")["requires"]=["confirm"]
        with self.assertRaisesRegex(ContractError,"siklus"):
            workflow_runner.compile_workflow(raw,identity(raw))

    def test_real_one_session_workflow_stops_after_assertion_failure(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        http=fixture(self)
        raw=workflow(http.server_port)
        result=workflow_runner.execute(raw,identity(raw))
        self.assertEqual([stage["status"] for stage in result["stages"]],["completed"]*3)
        next(item for item in raw["stages"] if item["id"]=="open")["steps"][1]["expected"]="Judul yang salah"
        result=workflow_runner.execute(raw,identity(raw))
        self.assertEqual(result["status"],"held")
        self.assertEqual([stage["status"] for stage in result["stages"]],["failed","not_started","not_started"])
