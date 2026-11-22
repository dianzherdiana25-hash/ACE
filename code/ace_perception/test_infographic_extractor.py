"""Verifier layout infografik multiwilayah dan hubungan caption."""
from hashlib import sha256
import unittest

from ace_perception import infographic_extractor as model
from ace_perception.test_document_extractor import FULL
from ace_perception.test_ocr_engine import font, raster
from ace_perception.test_screen_understanding import board, label, rectangle


def zone(key,kind,box,**options):
    return {"id":key,"kind":kind,"box":box,"source_ref":f"fixture/zone/{key}","options":options}


def contents():
    page=board(72,48)
    label(page,"HA",2,2)
    rectangle(page,(14,17,32,30),filled=True)
    rectangle(page,(36,20,49,30),filled=True)
    label(page,"HOT",13,35)
    label(page,"H 24",36,2,FULL)
    return raster(page)


class InfographicTests(unittest.TestCase):
    def test_extracts_typed_metric_and_caption_to_single_target(self):
        img=contents()
        spec={"schema":"ace.perception-infographic-layout.v1","image_sha256":sha256(img).hexdigest(),
              "light_ink":False,"word_gap":4,"maximum_caption_gap_px":10,"zones":[
            zone("title","heading",[0,0,30,14]),
            zone("amount","metric",[34,0,67,14],prefix="H ",type="integer",unit="unit"),
            zone("figure","figure",[11,15,33,31]),
            zone("caption","caption",[13,34,35,45]),
        ]}
        output=model.extract(img,font(FULL),model._canonical(spec))
        by_id={row["id"]:row for row in output["regions"]}
        self.assertEqual(by_id["amount"]["data"]["value"],24)
        self.assertEqual(by_id["title"]["data"]["text"],"HA")
        self.assertEqual(by_id["figure"]["data"]["regions"][0]["box"],[14,17,32,30])
        self.assertEqual(output["caption_links"],[{"caption_id":"caption","status":"matched","target_ids":["figure"],"gap_px":3}])

    def test_ambiguous_captions_never_pick_by_name(self):
        records=[{"id":"one","role":"figure","box":[0,0,10,10],"status":"read"},
                 {"id":"two","role":"table","box":[11,0,20,10],"status":"read"},
                 {"id":"cap","role":"caption","box":[0,11,20,13],"status":"read"}]
        self.assertEqual(model._captions(records,3),[
            {"caption_id":"cap","status":"ambiguous","target_ids":["one","two"],"gap_px":1}])
