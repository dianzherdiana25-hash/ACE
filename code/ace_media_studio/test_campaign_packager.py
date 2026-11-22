from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, canonical, identity
from ._raster import blank, png
from .campaign_packager import campaign
from .test_video_assembler import make_clip


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class CampaignTests(unittest.TestCase):
    def test_rights_cover_each_asset_and_schedule_has_dependency_order(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)

            def save(name, raw):
                (root / name).write_bytes(raw)
                return {"path": name, "sha256": sha256(raw).hexdigest()}

            assets = {
                "main": save("main.mp4", make_clip(root, [(52, 60, 100)])),
                "teaser": save("teaser.mp4", make_clip(root, [(128, 75, 40)])),
                "cover": save("cover.png", png(blank(32, 22, (84, 180, 90)))),
                "caption": save("caption.txt", b"Keterangan fixture\n")}
            registry = {"schema": "ace.media.rights-registry.v1", "grants": [
                {"id": key, "asset_sha256": ref["sha256"], "license_ref": f"fixture:grant-{key}", "uses": ["campaign"],
                 "territories": ["*"], "effective": "2025-01-01", "expires": "2025-12-31", "credit": None}
                for key, ref in assets.items()]}
            intent = {"schema": "ace.media.rights-intent.v1", "use": "campaign", "date": "2025-01-04",
                      "territories": ["ID"], "assets": [
                          {"id": key, "sha256": ref["sha256"], "credits": []} for key, ref in assets.items()]}
            use_ref = save("intent.json", canonical(intent))
            planned = {"schema": "ace.media.campaign-plan.v1", "id": "winter", "source_ref": "fixture:brief",
                       "rights_registry": save("rights.json", canonical(registry)), "max_total_bytes": 50000,
                       "releases": [{"id": "second", "channel": "show", "at_utc": "2025-01-04T12:00:00Z",
                                     "after": ["first"], "intent": use_ref, "assets": [assets[key] | {"role": key} for key in ("main", "cover", "caption")]},
                                    {"id": "first", "channel": "show", "at_utc": "2025-01-04T08:00:00Z",
                                     "after": [], "intent": use_ref, "assets": [assets[key] | {"role": key} for key in ("teaser", "cover", "caption")]}]}
            files, report = campaign(planned, identity(planned), root)
            self.assertEqual(report["status"], "local_draft")
            self.assertEqual([r["id"] for r in report["schedule"]], ["first", "second"])
            self.assertEqual(report["total_bytes"], sum(map(len, files.values())))
            planned["releases"][0]["at_utc"] = "2025-01-05T07:00:00Z"
            with self.assertRaisesRegex(ContractError, "tanggal rilis"):
                campaign(planned, identity(planned), root)
            planned["releases"][0]["at_utc"] = "2025-01-04T07:00:00Z"
            with self.assertRaisesRegex(ContractError, "mendahului"):
                campaign(planned, identity(planned), root)
            planned["releases"][1]["assets"][2]["sha256"] = "b" * 64
            with self.assertRaisesRegex(ContractError, "tanpa grant"):
                campaign(planned, identity(planned), root)
