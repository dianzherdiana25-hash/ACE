"""Bentuk catatan suara dari potongan receipt yang memiliki penanda.

Aturan prefiks memberi jenis catatan, dan nilai setelah prefiks
dikutip dengan boks waktu. Tanggal ISO, jam, dan angka diperiksa
sebagai tipe terpisah. Prefiks yang tidak ditemukan dan nilai
salah tetap tampak bersama rujukan segmen.
"""
import argparse
from datetime import date, time
from hashlib import sha256
from pathlib import Path
import re
import sys
import unicodedata

from . import _audio, _raster, _vision, audio_pipeline, document_extractor
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token


KIND = {"action", "decision", "due_date", "clock_time", "decimal", "memo"}


def _normalized(text):
    return unicodedata.normalize("NFC", text.strip(".,:;!?").casefold())


def _markers(raw):
    if not isinstance(raw,list) or not 1 <= len(raw) <= 100:
        raise ValueError("Jumlah aturan catatan di luar batas.")
    result, keys, phrases = [], set(), set()
    for row in raw:
        if not isinstance(row,dict) or set(row) != {"id","kind","prefix","source_ref"}:
            raise ValueError("Bentuk aturan catatan tidak sah.")
        key, kind, ref = (_token(row[field],field) for field in ("id","kind","source_ref"))
        phrase = tuple(map(_normalized,_token(row["prefix"],"Penanda catatan").split()))
        if key in keys or kind not in KIND or not 1 <= len(phrase) <= 8 or not all(phrase) or phrase in phrases:
            raise ValueError("Aturan catatan ganda atau jenis/prefiks tidak sah.")
        keys.add(key)
        phrases.add(phrase)
        result.append((phrase,key,kind,ref))
    return sorted(result,key=lambda row:(-len(row[0]),row[1]))


def _typed(kind,text):
    if not text:
        return None
    if kind == "due_date":
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",text):
            return None
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return None
    if kind == "clock_time":
        if not re.fullmatch(r"[0-9]{2}:[0-9]{2}",text):
            return None
        try:
            return time.fromisoformat(text).isoformat(timespec="minutes")
        except ValueError:
            return None
    if kind == "decimal":
        return document_extractor._value("decimal",text)
    return text


def structure(wav,transcript,policy,**segment_policy):
    raw = _vision.spec(policy,"ace.perception-voice-note-rules.v1",("rules","maximum_value_words"))
    marker = _markers(raw["rules"])
    cap = _integer(raw["maximum_value_words"],1,100,"Kata nilai maksimum")
    notes = audio_pipeline.align(wav,transcript,**segment_policy)
    output = []
    for segment in notes["segments"]:
        base = {"segment":segment["id"],"receipt_ref":segment["receipt_ref"],
                "start_us":segment["start_us"],"end_us":segment["end_us"]}
        tokens = segment["words"]
        observed = [_normalized(row["word"]) for row in tokens]
        matching = next((row for row in marker if tuple(observed[:len(row[0])]) == row[0]),None)
        if matching is None:
            output.append({**base,"status":"unstructured" if segment["status"] == "read" else segment["status"],
                           "kind":None,"value":None,"rule_ref":None})
            continue
        phrase,key,kind,pointer = matching
        suffix = tokens[len(phrase):]
        payload = " ".join(row["word"] for row in suffix)
        value = _typed(kind,payload) if len(suffix)<=cap else None
        output.append({**base,"status":"structured" if value is not None else "invalid_value","kind":kind,
                       "value":value,"rule_id":key,"rule_ref":pointer,
                       "value_words":len(suffix),"value_start_us":suffix[0]["start_us"] if suffix else None,
                       "value_end_us":suffix[-1]["end_us"] if suffix else None})
    return {"schema":"ace.perception-voice-note.v1","audio_sha256":notes["audio_sha256"],
            "transcript_sha256":notes["receipt_sha256"],"rules_sha256":sha256(policy).hexdigest(),
            "status":notes["status"],"items":output}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("wav","transcript","policy"):
        parser.add_argument(arg,type=Path)
    args = parser.parse_args(argv)
    try:
        result = structure(_raster.read(args.wav,_audio.MAX_BYTES),
                           _raster.read(args.transcript,audio_pipeline.MAX_RECEIPT_BYTES),
                           _raster.read(args.policy,_vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError,OverflowError,RecursionError,ValueError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"] == "incomplete" or any(row["status"] != "structured" for row in result["items"]))


if __name__ == "__main__":
    raise SystemExit(main())
