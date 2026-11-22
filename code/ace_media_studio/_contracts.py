"""Kontrak lokal dan hash artefak untuk studio media."""
from hashlib import sha256
import json
import re


HEX=re.compile(r"[a-f0-9]{64}")
ID=re.compile(r"[a-z][a-z0-9_]{0,63}")


class ContractError(ValueError):
    """Masukan tidak sesuai kontrak studio."""


def canonical(raw):
    return json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def identity(raw):
    return sha256(canonical(raw)).hexdigest()


def digest(raw):
    if not isinstance(raw,str) or not HEX.fullmatch(raw):
        raise ContractError("SHA-256 harus kanonis.")
    return raw


def checked(raw,expected):
    if identity(raw)!=digest(expected):
        raise ContractError("Masukan berbeda dari anchor kontrak.")


def obj(raw,fields):
    if not isinstance(raw,dict) or set(raw)!=set(fields):
        raise ContractError("Kolom kontrak studio tidak sesuai.")
    return raw


def schema(raw,name,fields):
    obj(raw,("schema",*fields))
    if raw["schema"]!=name:
        raise ContractError("Schema studio belum didukung.")
    return raw


def identifier(raw,label):
    if not isinstance(raw,str) or not ID.fullmatch(raw):
        raise ContractError(f"{label} perlu identifier.")
    return raw


def text(raw,label,cap=350):
    if not isinstance(raw,str) or not raw.strip() or not raw.isprintable() or len(raw)>cap:
        raise ContractError(f"{label} perlu teks cetak dalam batas.")
    return raw


def integer(raw,label,minimum,maximum):
    if type(raw) is not int or not minimum<=raw<=maximum:
        raise ContractError(f"{label} di luar batas.")
    return raw


def entries(raw,cap,minimum=0):
    if not isinstance(raw,list) or not minimum<=len(raw)<=cap:
        raise ContractError("Panjang daftar studio melampaui kontrak.")
    return raw


def _unique(pairs):
    data={}
    for key,value in pairs:
        if key in data:
            raise ContractError("Kunci JSON ganda.")
        data[key]=value
    return data


def _reject(value):
    raise ContractError("Angka nonfinite tidak didukung.")


def decode(data):
    return json.loads(data.decode("utf-8"),object_pairs_hook=_unique,parse_constant=_reject)


def read(path,cap=2_000_000):
    with path.open("rb") as stream:
        data=stream.read(cap+1)
    if len(data)>cap:
        raise ContractError("Artefak melampaui anggaran byte.")
    return data
