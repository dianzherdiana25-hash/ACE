"""Uji arsip deterministik, jejak preseden, dan pagar anggota."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZipInfo

from ace_deliberation import debate_archiver as archive, debate_protocol
from ace_deliberation.test_debate_protocol import fixture as debate_fixture


def fixture():
    return {"case_ref": "fixture/precedent", "tags": ["sampling", "audit"],
            "transcript": debate_protocol.replay(debate_fixture())}


def replace(payload, name, data):
    output = BytesIO()
    with ZipFile(BytesIO(payload)) as source, ZipFile(output, "w") as target:
        for item in source.infolist():
            target.writestr(item, data if item.filename == name else source.read(item))
    return output.getvalue()


class DebateArchiveTests(unittest.TestCase):
    def test_archive_is_byte_identical_and_keeps_basis_and_dissent(self):
        raw = fixture()
        first = archive.build_archive(raw)
        second = archive.build_archive({**raw, "tags": raw["tags"][::-1]})
        self.assertEqual(first, second)
        digest = hashlib.sha256(first).hexdigest()
        result = archive.verify_archive(first, expected_sha256=digest)
        self.assertTrue(result["external_digest_checked"])
        self.assertEqual(result["lesson"]["dissent"][0]["turn_id"], "b1")
        self.assertEqual(result["lesson"]["decision_basis"][0]["turn_id"], "c1")
        self.assertEqual(result["lesson"]["case_ref"], "fixture/precedent")
        self.assertEqual(result["manifest"]["debate_sha256"], raw["transcript"]["sha256"])

    def test_tampering_with_lesson_fails_replay_even_with_valid_zip_crc(self):
        raw = archive.build_archive(fixture())
        changed = replace(raw, "lesson.json", b'{"synthetic":"changed"}\n')
        with self.assertRaisesRegex(archive.ArchiveError, "tidak cocok"):
            archive.verify_archive(changed)
        with self.assertRaisesRegex(archive.ArchiveError, "hash eksternal"):
            archive.verify_archive(changed, expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_unknown_archive_members_and_symlinks_never_extract(self):
        data = archive.build_archive(fixture())
        broken = BytesIO(data)
        with ZipFile(broken, "a") as target:
            target.writestr("../escape", b"fixture")
        with self.assertRaisesRegex(archive.ArchiveError, "anggota arsip asing".capitalize()):
            archive.verify_archive(broken.getvalue())

        rebuilt = BytesIO()
        with ZipFile(BytesIO(data)) as source, ZipFile(rebuilt, "w") as target:
            for info in source.infolist():
                content = source.read(info)
                if info.filename == "transcript.json":
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                target.writestr(info, content)
        with self.assertRaisesRegex(archive.ArchiveError, "blob reguler"):
            archive.verify_archive(rebuilt.getvalue())

    def test_unverified_or_incomplete_debate_cannot_be_archived(self):
        raw = fixture()
        raw["transcript"]["decision"]["rationale"] = "berubah"
        with self.assertRaises(archive.ArchiveError):
            archive.build_archive(raw)
        draft = debate_fixture()
        draft.pop("decision")
        raw["transcript"] = debate_protocol.replay(draft)
        with self.assertRaises(archive.ArchiveError):
            archive.build_archive(raw)

    def test_cli_build_is_atomic_no_overwrite_and_verify_reads_same_hash(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        source, target = root / "request.json", root / "debate.zip"
        source.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(archive.main(["build", str(source), str(target)]), 0)
        saved = target.read_bytes()
        expected = json.loads(output.getvalue())["archive_sha256"]
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            archive.main(["build", str(source), str(target)])
        self.assertEqual(target.read_bytes(), saved)
        self.assertEqual({file.name for file in root.iterdir()}, {"request.json", "debate.zip"})
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(archive.main(["verify", str(target), "--expected-sha256", expected]), 0)
        self.assertTrue(json.loads(output.getvalue())["external_digest_checked"])

    def test_rejects_repackaging_from_same_data_with_different_metadata(self):
        raw = archive.build_archive(fixture())
        output = BytesIO()
        with ZipFile(BytesIO(raw)) as source, ZipFile(output, "w") as target:
            for item in source.infolist():
                copy = ZipInfo(item.filename, date_time=(1981, 1, 1, 0, 0, 0))
                copy.external_attr = item.external_attr
                target.writestr(copy, source.read(item))
        with self.assertRaisesRegex(archive.ArchiveError, "serialisasi"):
            archive.verify_archive(output.getvalue())

    def test_tags_cannot_be_deduplicated_silently(self):
        raw = fixture()
        raw["tags"] = ["logic", " logic "]
        with self.assertRaisesRegex(archive.ArchiveError, "ganda"):
            archive.build_archive(raw)

    def test_manifest_binds_every_nonmanifest_member_to_exact_bytes(self):
        blob = archive.build_archive(fixture())
        manifest = archive.verify_archive(blob)["manifest"]
        with ZipFile(BytesIO(blob)) as source:
            for member in manifest["members"]:
                data = source.read(member["name"])
                self.assertEqual(member["size"], len(data))
                self.assertEqual(member["sha256"], hashlib.sha256(data).hexdigest())
