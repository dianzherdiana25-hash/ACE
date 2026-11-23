"""Solver runner: jawaban tertambat, pisah peran, dan kegagalan bridge yang jujur."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from ace_web_operator import skill_solver,skill_verifier
from ace_web_operator._contracts import ContractError,canonical,decode,identity
from ace_web_operator.test_skill_verifier import evidence


def _write(root,name,doc):
    payload=canonical(doc)+b"\n"
    (root/name).write_bytes(payload)
    return {"path":name,"sha256":sha256(payload).hexdigest()}


def solve_plan(root,package,suite,solver="fixture/solver",bridge="http://127.0.0.1:8931"):
    return {"schema":"ace.web.skill-solve-plan.v1","source_ref":"fixture/solve","solver_ref":solver,
            "bridge":bridge,"role":"front","max_tokens":1024,
            "package":_write(root,"package.json",package),"suite":_write(root,"suite.json",suite)}


class SolverTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.package,self.suite,_answers=evidence(self.root)

    def plan(self,**kwargs):
        return solve_plan(self.root,self.package,self.suite,**kwargs)

    def test_completed_run_writes_answers_that_verify(self):
        plan=self.plan()
        answers,receipt=skill_solver.solve(self.root,plan,identity(plan),
                                           transport=lambda *args: json.dumps({"first_test":10,"second_test":7}),
                                           now=1767225600)
        self.assertEqual(receipt["status"],"completed")
        self.assertEqual(receipt["answers_sha256"],identity(answers))
        self.assertEqual(receipt["cases_answered"],2)
        proof=skill_verifier.evaluate(self.package,identity(self.package),self.suite,answers,identity(answers))
        self.assertTrue(proof["passed"])

    def test_solver_never_sees_expected_values(self):
        suite=dict(self.suite)
        suite["cases"]=[{"id":"secret_case","objective":"sum","prompt":"Sebutkan kata sandi tim.",
                         "op":"text_fold","expected":"kunci-rahasia-tak-tertebak","source_ref":"fixture/secret"}]
        package=dict(self.package)
        package["heldout_sha256"]=identity(suite)
        seen=[]
        def transport(origin_value,role,prompt,tokens):
            seen.append(prompt)
            return json.dumps({"secret_case":"kunci-rahasia-tak-tertebak"})
        plan=solve_plan(self.root,package,suite)
        answers,receipt=skill_solver.solve(self.root,plan,identity(plan),transport=transport,now=1767225600)
        self.assertEqual(receipt["status"],"completed")
        self.assertIn("Sebutkan kata sandi tim.",seen[0])
        self.assertNotIn("kunci-rahasia-tak-tertebak",seen[0])
        self.assertEqual(answers["answers"][0]["value"],"kunci-rahasia-tak-tertebak")

    def test_bridge_down_records_failed_receipt_without_answers(self):
        plan=self.plan()
        def down(*args):
            raise skill_solver.SolverUnavailable("bridge_unreachable")
        answers,receipt=skill_solver.solve(self.root,plan,identity(plan),transport=down,now=1767225600)
        self.assertIsNone(answers)
        self.assertEqual(receipt["status"],"failed")
        self.assertEqual(receipt["reason"],"bridge_unreachable")
        self.assertIsNone(receipt["answers_sha256"])
        self.assertEqual(receipt["cases_answered"],0)

    def test_unreachable_bridge_via_real_transport_fails_honestly(self):
        plan=self.plan(bridge="http://127.0.0.1:59999")
        answers,receipt=skill_solver.solve(self.root,plan,identity(plan),now=1767225600)
        self.assertIsNone(answers)
        self.assertEqual(receipt["status"],"failed")
        self.assertEqual(receipt["reason"],"bridge_unreachable")

    def test_bad_solver_output_records_failure(self):
        plan=self.plan()
        answers,receipt=skill_solver.solve(self.root,plan,identity(plan),
                                           transport=lambda *args: "bukan json sama sekali",now=1767225600)
        self.assertIsNone(answers)
        self.assertEqual(receipt["status"],"failed")
        self.assertEqual(receipt["reason"],"bad_solver_output")

    def test_evaluator_must_differ_from_solver_before_any_call(self):
        plan=self.plan(solver="fixture/verifier")
        def forbidden(*args):
            raise AssertionError("transport tidak boleh dipanggil")
        with self.assertRaisesRegex(ContractError,"berbeda dari solver"):
            skill_solver.solve(self.root,plan,identity(plan),transport=forbidden,now=1767225600)

    def test_main_writes_answers_and_receipt_create_only(self):
        plan=self.plan()
        plan_file=self.root/"solve_plan.json"
        plan_file.write_bytes(canonical(plan)+b"\n")
        output=self.root/"run1"
        fake=lambda *args: json.dumps({"first_test":10,"second_test":7})
        with mock.patch.object(skill_solver,"_bridge_transport",fake):
            self.assertEqual(skill_solver.main([str(self.root),str(plan_file),str(output),
                                                "--expect-sha256",identity(plan)]),0)
        answers=decode((output/"heldout_answers.json").read_bytes())
        receipt=decode((output/"solve_receipt.json").read_bytes())
        self.assertEqual(receipt["answers_sha256"],identity(answers))
        with mock.patch.object(skill_solver,"_bridge_transport",fake):
            with self.assertRaises(SystemExit) as caught:
                skill_solver.main([str(self.root),str(plan_file),str(output),
                                   "--expect-sha256",identity(plan)])
        self.assertEqual(caught.exception.code,2)

    def test_main_bridge_down_writes_only_receipt_and_returns_1(self):
        plan=self.plan()
        plan_file=self.root/"solve_plan.json"
        plan_file.write_bytes(canonical(plan)+b"\n")
        output=self.root/"run_down"
        def down(*args):
            raise skill_solver.SolverUnavailable("bridge_unreachable")
        with mock.patch.object(skill_solver,"_bridge_transport",down):
            self.assertEqual(skill_solver.main([str(self.root),str(plan_file),str(output),
                                                "--expect-sha256",identity(plan)]),1)
        self.assertTrue((output/"solve_receipt.json").exists())
        self.assertFalse((output/"heldout_answers.json").exists())
        self.assertEqual(decode((output/"solve_receipt.json").read_bytes())["status"],"failed")


if __name__=="__main__":
    unittest.main()
