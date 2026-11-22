"""Verifier identitas byte, file yang ditolak, serta objek symlink."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from zlib import compress, crc32

from ace_software_factory import upload_builder
from ace_software_factory._contracts import ContractError, identity


def png():
    def chunk(tag,data):
        payload=tag+data
        return struct.pack(">I",len(data))+payload+struct.pack(">I",crc32(payload))
    header=struct.pack(">IIBBBBB",1,1,8,2,0,0,0)
    return upload_builder.MAGIC+chunk(b"IHDR",header)+chunk(b"IDAT",compress(b"\0\x12\x34\x56"))+chunk(b"IEND",b"")


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))/"store"
        self.policy={"schema":"ace.factory-upload-policy.v1","source_ref":"fixture/upload","max_bytes":140,
                     "media_types":["application/json","image/png"],"max_png_pixels":8}
        self.anchor=identity(self.policy)
        upload_builder.initialize(self.root,self.policy,self.anchor)

    def send(self,name,kind,data):
        return upload_builder.put(self.root,self.policy,self.anchor,name,kind,BytesIO(data))

    def test_hash_publication_replays_byte_identically(self):
        payload=b'{"item":"q"}'
        one=self.send("source.json","application/json",payload)
        two=self.send("other.json","application/json",payload)
        self.assertEqual(one["object"],two["object"])
        self.assertFalse(one["reused"])
        self.assertTrue(two["reused"])
        self.assertEqual((self.root/one["object"]).read_bytes(),payload)
        self.assertEqual(len(list((self.root/"objects").iterdir())),1)

    def test_rejects_path_bad_json_format_corruption_and_size(self):
        for name,media,data in (("../file.json","application/json",b"{}"),("clear.png","image/png",b"bad"),
                                 ("file.json","application/json",b'{"k":1,"k":2}'),
                                 ("file.json","application/json",b"x"*141),("data.json","text/plain",b"{}")):
            with self.subTest(name=name,data=data[:7]), self.assertRaises((ContractError,ValueError)):
                self.send(name,media,data)
        self.assertEqual(list((self.root/"objects").iterdir()),[])
        self.assertEqual(self.send("pixel.png","image/png",png())["bytes"],len(png()))

    def test_fails_closed_when_existing_object_is_a_symlink(self):
        source=self.root/"independent.json"
        source.write_bytes(b"{}")
        anchor=sha256(b"{}").hexdigest()
        (self.root/"objects"/anchor).symlink_to(source)
        with self.assertRaises(OSError):
            self.send("x.json","application/json",b"{}")
        self.assertEqual(source.read_bytes(),b"{}")
        self.assertEqual(len(list((self.root/"objects").iterdir())),1)
