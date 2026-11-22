"""Bangun evaluasi feature flag yang stabil per subjek dan fail-closed.

Kontrak mengikat periode, aturan segmentasi dan rollout basis points.
Override runtime berwenang mematikan flag. Subjek kosong, atribut tak
sah, dan flag tak dikenal menghasilkan penolakan yang dapat diaudit.
"""
import argparse
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text


STAMP=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _stamp(raw):
    if not isinstance(raw,str) or not STAMP.fullmatch(raw):
        raise ContractError("Waktu flag perlu UTC kanonis.")
    datetime.fromisoformat(raw.replace("Z","+00:00"))
    return raw


def compile_policy(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.factory-flag-plan.v1",("product_id","source_ref","attributes","flags"))
    product=identifier(plan["product_id"],"ID produk")
    source=text(plan["source_ref"],"Sumber rollout")
    fields={}
    for raw in entries(plan["attributes"],40):
        obj(raw,("id","values"))
        key=identifier(raw["id"],"Nama atribut segmen")
        allowed=[identifier(item,"Nilai atribut") for item in entries(raw["values"],60,minimum=1)]
        if key in fields or len(set(allowed))!=len(allowed):
            raise ContractError("Atribut atau nilai segmen ganda.")
        fields[key]=set(allowed)
    flags={}
    for row in entries(plan["flags"],150,minimum=1):
        obj(row,("id","start","end","enabled","salt","rollout_bp","segments","source_ref"))
        key=identifier(row["id"],"ID flag")
        start,end=(_stamp(row[field]) if row[field] is not None else None for field in ("start","end"))
        if key in flags or type(row["enabled"]) is not bool or (start and end and start>=end):
            raise ContractError("Flag ganda, periode salah atau enabled tidak sah.")
        salt=identifier(row["salt"],"Salt rollout")
        fraction=integer(row["rollout_bp"],"Rollout basis points",0,10_000)
        segments=[]
        for selection in entries(row["segments"],40):
            if not isinstance(selection,dict) or not selection or selection.keys()-fields.keys():
                raise ContractError("Segmentasi mengacu atribut kosong atau tak dikenal.")
            valid={}
            for field, supplied in selection.items():
                choices={identifier(value,"Pilihan nilai") for value in entries(supplied,60,minimum=1)}
                if len(choices)!=len(supplied) or choices-fields[field]:
                    raise ContractError("Pilihan segmentasi ganda atau tak dikenal.")
                valid[field]=choices
            segments.append(valid)
        flags[key]={"id":key,"enabled":row["enabled"],"salt":salt,"rollout_bp":fraction,"start":start,"end":end,
                    "segments":segments,"source_ref":text(row["source_ref"],"Sumber flag")}
    return product,source,fields,flags


def evaluate(plan,expected,request,*,disabled=()):
    product,source,fields,flags=compile_policy(plan,expected)
    obj(request,("flag","subject","at","attributes"))
    name=identifier(request["flag"],"Nama flag")
    now=_stamp(request["at"])
    selection=flags.get(name)
    result={"schema":"ace.factory-flag-result.v1","product_id":product,"plan_sha256":expected,"flag":name,"at":now,
            "source_ref":selection["source_ref"] if selection else source,"enabled":False,"bucket":None,"reason":"unknown_flag"}
    if selection is None:
        return result
    if not selection["enabled"] or name in disabled:
        return {**result,"reason":"disabled"}
    if (selection["start"] and now<selection["start"]) or (selection["end"] and now>=selection["end"]):
        return {**result,"reason":"inactive_window"}
    supplied=request["attributes"]
    if not isinstance(supplied,dict) or supplied.keys()-fields.keys() or any(
            not isinstance(value,str) or value not in fields[key] for key,value in supplied.items()):
        return {**result,"reason":"invalid_attributes"}
    if selection["segments"] and not any(all(supplied.get(field) in allowed for field,allowed in segment.items())
                                         for segment in selection["segments"]):
        return {**result,"reason":"outside_segment"}
    candidate=request["subject"]
    if not isinstance(candidate,str) or not candidate.strip() or len(candidate)>250 or not candidate.isprintable():
        return {**result,"reason":"missing_subject"}
    commitment=sha256(canonical([product,name,selection["salt"],candidate])).digest()
    bucket=int.from_bytes(commitment[:8],"big")*10_000//2**64
    belongs=bucket<selection["rollout_bp"]
    return {**result,"enabled":belongs,"bucket":bucket,"reason":"inside_rollout" if belongs else "outside_rollout"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("request",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--disable",action="append",default=[])
    args=parser.parse_args(argv)
    try:
        result=evaluate(decode(read(args.plan)),args.expect_sha256,decode(read(args.request)),disabled=args.disable)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
