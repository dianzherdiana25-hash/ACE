from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, identity
from .label_builder import create_labels
from .test_tabular_engine import save


class LabelsTests(unittest.TestCase):
    def test_items_group_by_compatible_address_and_packing_list_omits_private_fields(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            blob = b"parcel,receiver,destination,item,count\np1,Fixture A,Zone X,book,2\np1,Fixture A,Zone X,note,1\n"
            plan = {"schema": "ace.production.label-plan.v1", "table": save(root, "pack.csv", blob), "title": "Kirim",
                    "max_packages": 4, "formats": ["docx"]}
            files, result = create_labels(plan, identity(plan), root)
            self.assertEqual(files["packing_list.csv"], b"parcel,item,count,source_line\np1,book,2,2\np1,note,1,3\n")
            self.assertEqual(result["parcels"][0]["source_lines"], [2, 3])
            plan["table"] = save(root, "pack.csv", blob + b"p1,Fixture B,Zone Y,marker,1\n")
            with self.assertRaisesRegex(ProductionError, "alamat berkonflik"):
                create_labels(plan, identity(plan), root)
