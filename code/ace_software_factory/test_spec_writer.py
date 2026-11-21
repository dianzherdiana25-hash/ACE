"""Verifier spesifikasi dari ujaran bersumber dan acceptance terbuka."""
import unittest

from ace_software_factory import spec_writer as model


def utterance(index, statement):
    return {"id":f"line_{index}", "ref":f"fixture/brief/{index}", "text":statement}


def brief(surface="cli"):
    return {"schema":"ace.factory-product-brief.v1","id":"fixture_catalog","name":"Katalog Uji",
            "surface":surface,"objective":"Tampilkan katalog lokal.","objective_ref":"fixture/objective",
            "utterances":[utterance(1,"uji show: Render dua entri."),utterance(2,"perlu show: Daftar entri."),
                          utterance(3,"batas offline: Berkas lokal."),
                          utterance(4,"luar publish: Unggah ke layanan.")]}


class SpecTests(unittest.TestCase):
    def test_acceptance_may_arrive_before_its_requirement_and_keep_provenance(self):
        raw=brief()
        result=model.write(raw,model.identity(raw))
        self.assertEqual(result["status"],"ready")
        self.assertEqual(result["brief_sha256"],model.identity(raw))
        self.assertEqual(result["requirements"],[{"id":"show","statement":"Daftar entri.","source_ref":"fixture/brief/2",
                                                   "acceptance":[{"statement":"Render dua entri.","source_ref":"fixture/brief/1"}]}])
        self.assertEqual(result["constraints"][0]["id"],"offline")
        self.assertEqual(result["non_goals"][0]["id"],"publish")
        self.assertIn("Render dua entri. (fixture/brief/1)",model.markdown(result))

    def test_silent_gaps_are_listed_and_block_scaffold_readiness(self):
        raw=brief()
        raw["utterances"]=[utterance(1,"perlu list: Daftar."),utterance(2,"uji unknown: Belum ada."),
                           utterance(3,"Bisakah dibuat lebih bagus?")]
        result=model.write(raw)
        self.assertEqual(result["status"],"needs_clarification")
        self.assertEqual([row["reason"] for row in result["pending"]],
                         ["unrecognized_statement","acceptance_without_requirement","missing_acceptance"])
        self.assertEqual(result["pending"][0]["quote"],"Bisakah dibuat lebih bagus?")

    def test_contradicting_scope_and_tampered_anchor_are_rejected(self):
        original=brief()
        raw={**original,"utterances":[*original["utterances"],utterance(5,"luar show: Matikan daftar.")]}
        with self.assertRaisesRegex(model.ContractError,"bertentangan"):
            model.write(raw)
        with self.assertRaisesRegex(model.ContractError,"anchor"):
            model.write(raw,model.identity(original))
