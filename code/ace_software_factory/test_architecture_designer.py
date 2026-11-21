"""Verifier keputusan arsitektur, lapisan, dan jejak acceptance."""
import unittest

from ace_software_factory import architecture_designer as model, spec_writer
from ace_software_factory.test_spec_writer import brief, utterance


def decisions(spec,retention="none",persist=False):
    return {"spec_sha256":model.identity(spec),"data_retention":retention,"storage_ref":"fixture/retention",
            "interfaces":[{"id":"list_items","requirement":"show","input_shape":"Unit","output_shape":"ItemList",
                           "persist":persist,"source_ref":"fixture/interactions/list"}]}


class ArchitectureTests(unittest.TestCase):
    def test_all_three_supported_surfaces_map_to_natural_boundary(self):
        for surface,entry in (("web","http_adapter"),("cli","command_adapter"),("service","worker_adapter")):
            fixture=spec_writer.write(brief(surface))
            with self.subTest(surface=surface):
                product=model.design(fixture,decisions(fixture))
                self.assertEqual(product["status"],"ready")
                self.assertEqual(product["components"][0]["id"],entry)
                self.assertEqual(product["interfaces"][0]["use_case"],"show")
                self.assertEqual(product["trace"][0]["acceptance_refs"],["fixture/brief/1"])
                self.assertFalse(product["trace"][0]["uses_repository"])

    def test_selected_repository_is_traced_and_missing_paths_remain_open(self):
        fixture=brief()
        fixture["utterances"]+= [utterance(5,"perlu detail: Tampilkan isi."),utterance(6,"uji detail: Buka satu item.")]
        spec=spec_writer.write(fixture)
        product=model.design(spec,decisions(spec,"durable",True))
        self.assertEqual(product["unmapped_requirements"],["detail"])
        self.assertEqual(product["status"],"missing_interfaces")
        self.assertEqual(product["components"][-1],{"id":"sqlite_repository","layer":"adapter","depends_on":["repository"]})
        self.assertEqual(product["interfaces"][0]["data_boundary"],"repository")
        with self.assertRaisesRegex(model.ContractError,"persistence"):
            model.design(spec,decisions(spec,persist=True))
