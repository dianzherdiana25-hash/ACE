"""Simpan unggahan produk melalui deposit lokal yang dibatasi isi.

Tipe harus diizinkan oleh policy, dan nama pemakai hanya metadata.
Objek diterbitkan dengan SHA-256 ke direktori yang dibuka tanpa
symlink. Operasi gagal atau replay tidak menimpa objek lama.
"""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import re
from secrets import token_hex
import stat
import struct
import sys
from unicodedata import normalize
from zlib import crc32, decompressobj, error as ZlibError

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, entries, integer, read, schema, text
from .repo_scaffolder import materialize


TYPES = {"text/plain": {".txt"}, "application/json": {".json"}, "image/png": {".png"}}
RESERVED = re.compile(r"(?i)(?:aux|con|nul|prn|com[1-9]|lpt[1-9])(?:\..*)?")
MAGIC = b"\x89PNG\r\n\x1a\n"
DIR_FLAGS = os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW


def _policy(raw, expected):
    checked(raw, expected)
    schema(raw, "ace.factory-upload-policy.v1", ("source_ref","max_bytes","media_types","max_png_pixels"))
    text(raw["source_ref"],"Rujukan policy")
    cap=integer(raw["max_bytes"],"Anggaran byte",1,4_000_000)
    pixels=integer(raw["max_png_pixels"],"Anggaran piksel",1,4_000_000)
    media=entries(raw["media_types"],len(TYPES),minimum=1)
    if any(not isinstance(kind,str) or kind not in TYPES for kind in media) or len(set(media)) != len(media):
        raise ContractError("Media tidak dikenal atau ganda.")
    return cap,pixels,set(media)


def _name(raw, media):
    candidate=normalize("NFKC",text(raw,"Nama unggahan",180))
    if (not candidate or candidate[0] in ". " or candidate[-1] in ". " or RESERVED.fullmatch(candidate)
            or any(char in candidate for char in '/\\:*?"<>|') or Path(candidate).suffix.lower() not in TYPES[media]):
        raise ContractError("Nama berkas tidak cocok dengan jenis atau aturan portabilitas.")
    return candidate


def _png(data, pixels):
    if not data.startswith(MAGIC):
        raise ContractError("Signature PNG tidak sah.")
    start=8
    seen_header=False
    raster=[]
    for _ in range(800):
        if start+12>len(data):
            break
        length,kind=struct.unpack_from(">I4s",data,start)
        stop=start+8+length
        if stop+4>len(data) or crc32(data[start+4:stop])!=struct.unpack_from(">I",data,stop)[0]:
            raise ContractError("Panjang atau CRC chunk PNG tidak sah.")
        if not seen_header:
            if kind!=b"IHDR" or length!=13:
                raise ContractError("PNG perlu IHDR awal.")
            width,height,depth,color,compression,filtering,interlace=struct.unpack_from(">IIBBBBB",data,start+8)
            if not 1<=width<=4096 or not 1<=height<=4096 or width*height>pixels or not (
                    depth==8 and color in (0,2,6) and compression==filtering==interlace==0):
                raise ContractError("Dimensi atau format PNG di luar cakupan.")
            seen_header=True
        elif kind==b"IDAT":
            raster.append(data[start+8:stop])
        elif kind==b"IEND" and length==0 and stop+4==len(data) and raster:
            stride=1+width*{0:1,2:3,6:4}[color]
            inflater=decompressobj()
            try:
                decoded=inflater.decompress(b"".join(raster),stride*height+1)
            except ZlibError as error:
                raise ContractError("Deflate raster PNG tidak sah.") from error
            if (len(decoded)!=stride*height or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail
                    or any(decoded[offset]>4 for offset in range(0,len(decoded),stride))):
                raise ContractError("Raster PNG berbeda dari header.")
            return
        elif kind not in {b"sRGB",b"pHYs",b"gAMA"} or raster:
            raise ContractError("Chunk PNG di luar profil upload.")
        start=stop+4
    raise ContractError("PNG tidak memiliki penutup kanonis.")


def _content(data, media, pixels):
    if media=="image/png":
        _png(data,pixels)
    elif media=="application/json":
        decode(data)
    else:
        decoded=data.decode("utf-8")
        if any(not char.isprintable() and char not in "\t\r\n" for char in decoded):
            raise ContractError("Unggahan teks berisi karakter kontrol.")


def initialize(root, policy, expected):
    _policy(policy,expected)
    anchor=canonical({"schema":"ace.factory-upload-vault.v1","policy_sha256":expected})+b"\n"
    materialize(root,{"vault.json":anchor})
    (root/"objects").mkdir(mode=0o700)


@contextmanager
def _objects(root):
    directory=os.open(root,DIR_FLAGS)
    try:
        objects=os.open("objects",DIR_FLAGS,dir_fd=directory)
        try:
            yield objects
        finally:
            os.close(objects)
    finally:
        os.close(directory)


def _verify(path, folder, payload, expected):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=folder)
    with os.fdopen(fd,"rb") as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size!=len(payload) or sha256(stream.read(len(payload)+1)).hexdigest()!=expected:
            raise ContractError("Objek di vault tidak cocok dengan identitasnya.")


def put(root, policy, expected, filename, media, incoming):
    cap,pixels,allowed=_policy(policy,expected)
    if not isinstance(media,str) or media not in allowed:
        raise ContractError("Jenis upload tidak diizinkan.")
    name=_name(filename,media)
    stamp=decode(read_relative(root,"vault.json",500))
    if stamp != {"schema":"ace.factory-upload-vault.v1","policy_sha256":expected}:
        raise ContractError("Policy tidak cocok dengan vault.")
    payload=incoming.read(cap+1)
    if not isinstance(payload,bytes) or not 1<=len(payload)<=cap:
        raise ContractError("Unggahan kosong atau melampaui anggaran.")
    _content(payload,media,pixels)
    anchor=sha256(payload).hexdigest()
    reused=False
    with _objects(root) as folder:
        pending=".candidate-"+token_hex(16)
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW
        fd=os.open(pending,flags,0o600,dir_fd=folder)
        try:
            with os.fdopen(fd,"wb") as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())
            try:
                os.link(pending,anchor,src_dir_fd=folder,dst_dir_fd=folder,follow_symlinks=False)
            except FileExistsError:
                _verify(anchor,folder,payload,anchor)
                reused=True
            os.fsync(folder)
        finally:
            os.unlink(pending,dir_fd=folder)
    return {"schema":"ace.factory-upload-receipt.v1","policy_sha256":expected,"media_type":media,
            "name":name,"bytes":len(payload),"object_sha256":anchor,"object":f"objects/{anchor}","reused":reused}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("init","put"))
    parser.add_argument("root",type=Path)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--filename")
    parser.add_argument("--media")
    args=parser.parse_args(argv)
    try:
        rule=decode(read(args.policy))
        if args.action=="init":
            initialize(args.root,rule,args.expect_sha256)
        else:
            receipt=put(args.root,rule,args.expect_sha256,args.filename,args.media,sys.stdin.buffer)
            sys.stdout.buffer.write(canonical(receipt)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
