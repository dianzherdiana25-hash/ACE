from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, canonical, identity
from ._raster import blank, png
from .brand_safety_qa import audit
from .release_packager_media import pack_release
from .test_video_assembler import make_clip
from .upload_metadata_writer import prepare_metadata


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class ReleaseTests(unittest.TestCase):
    def test_local_packages_only_pass_after_audit_and_metadata_match_artifact(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)

            def save(name, data):
                (root / name).write_bytes(data)
                return {"path": name, "sha256": sha256(data).hexdigest()}

            video = save("source.mp4", make_clip(root, [(60, 100, 145)], audio=True))
            cover = save("cover.png", png(blank(32, 18, (60, 120, 210))))
            meta = {"schema": "ace.media.metadata-plan.v1", "platform": "local", "media_sha256": video["sha256"],
                    "title": "Sorot", "source_ref": "fixture:brief", "limits": {"title": 80, "description": 100, "tags": 2},
                    "facts": [{"id": "scene", "text": "Satu frame", "source_ref": "fixture:timeline", "approved": True}],
                    "tags": [], "credits": []}
            policy = {"schema": "ace.media.brand-policy.v1", "required_channels": ["visual"],
                      "blocked_categories": [], "phrase_rules": []}
            annotations = {"schema": "ace.media.brand-annotations.v1", "asset_sha256": video["sha256"], "duration_ms": 250,
                           "items": [{"id": "scene", "channel": "visual", "start_ms": 0, "end_ms": 250,
                                      "text": "Warna acuan", "categories": [], "source_ref": "fixture:scene"}]}
            brand = audit(policy, identity(policy), annotations, identity(annotations))
            record = {"id": "local", "video": video, "cover": cover,
                      "metadata": save("meta.json", canonical(prepare_metadata(meta, identity(meta)))),
                      "brand_audit": save("brand.json", canonical(brand)),
                      "limits": {"max_bytes": 60000, "max_width": 32, "max_height": 24, "requires_audio": True}}
            plan = {"schema": "ace.media.release-plan.v1", "project": "fixture", "max_total_bytes": 60000,
                    "targets": [record]}
            files, report = pack_release(plan, identity(plan), root)
            self.assertEqual(report["state"], "local_draft")
            self.assertEqual(report["targets"][0]["dimensions"], [32, 24])
            self.assertEqual(report["targets"][0]["assets"]["video.mp4"]["sha256"], video["sha256"])
            self.assertEqual(set(files["local"]), {"video.mp4", "cover.png", "metadata.json", "brand_audit.json"})
            brand["asset_sha256"] = "f" * 64
            record["brand_audit"] = save("other.json", canonical(brand))
            with self.assertRaisesRegex(ContractError, "Audit merek"):
                pack_release(plan, identity(plan), root)
