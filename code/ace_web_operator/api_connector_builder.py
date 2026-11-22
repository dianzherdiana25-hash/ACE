"""Turunkan konektor GET dari dokumentasi OpenAPI lokal yang tertambat.

Subset dukungan mengikuti path parameter, kontrak JSON sederhana, dan
respons 200. Konektor JSON dapat diaudit dan dijalankan terhadap origin
loopback eksplisit. URL dari dokumen tidak pernah dipakai sebagai target.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import (ContractError,canonical,checked,decode,digest,entries,identifier,identity,
                         integer,obj,origin,read,schema,text,web_path)
from ._http import fetch


PARAM=re.compile(r"\{([a-z][a-z0-9_]{0,63})\}")
SEGMENT=re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,59}")
TYPES={"object","array","boolean","integer","number","string","null"}


def _shape(raw, depth=0):
    if depth>5 or not isinstance(raw,dict) or not isinstance(raw.get("type"),str) or raw["type"] not in TYPES:
        raise ContractError("Kontrak respons OpenAPI di luar subset.")
    flavor=raw["type"]
    if flavor=="object":
        if set(raw)-{"type","properties","required","additionalProperties","description","title"} or raw.get("additionalProperties") is not False:
            raise ContractError("Objek OpenAPI perlu additionalProperties false.")
        names=raw.get("properties",{})
        if not isinstance(names,dict) or len(names)>40:
            raise ContractError("Properti respons melampaui batas.")
        fields={identifier(key,"Properti respons"):_shape(value,depth+1) for key,value in sorted(names.items())}
        required=[identifier(key,"Properti wajib") for key in entries(raw.get("required",[]),40)]
        if len(required)!=len(set(required)) or set(required)-fields.keys():
            raise ContractError("Properti required tidak cocok.")
        return {"type":flavor,"properties":fields,"required":sorted(required)}
    if flavor=="array":
        if set(raw)-{"type","items","maxItems","description","title"}:
            raise ContractError("Array OpenAPI memakai fitur yang belum didukung.")
        return {"type":flavor,"items":_shape(raw.get("items"),depth+1),
                "maximum":integer(raw.get("maxItems",100),"Batas array",0,300)}
    if set(raw)-{"type","description","title"}:
        raise ContractError("Constraint primitif belum didukung.")
    return {"type":flavor}


def _params(template, rows):
    segments=template.split("/")[1:]
    placeholders=[]
    for segment in [part for part in segments if part]:
        match=PARAM.fullmatch(segment)
        if match:
            placeholders.append(match.group(1))
        else:
            web_path("/"+segment)
    if len(set(placeholders))!=len(placeholders):
        raise ContractError("Placeholder rute ganda.")
    types={}
    for raw in entries(rows,30):
        if not isinstance(raw,dict) or raw.get("in")!="path" or raw.get("required") is not True:
            raise ContractError("Parameter di luar path wajib belum didukung.")
        field=identifier(raw.get("name"),"Parameter path")
        contents=raw.get("schema",{})
        kind=contents.get("type")
        if field in types or field not in placeholders or kind not in ("integer","string") or contents.keys()!={"type"}:
            raise ContractError("Parameter path ambigu atau tipe belum didukung.")
        types[field]=kind
    if set(placeholders)!=types.keys():
        raise ContractError("Placeholder rute tanpa deklarasi parameter.")
    web_path(PARAM.sub("placeholder",template))
    return dict(sorted(types.items()))


def compile_connector(document,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.connector-plan.v1",("id","source_ref","document_sha256","origin","operations","max_response"))
    checked(document,plan["document_sha256"])
    base,_=origin(plan["origin"])
    product=identifier(plan["id"],"ID konektor")
    pointer=text(plan["source_ref"],"Rujukan dokumentasi")
    cap=integer(plan["max_response"],"Batas response",50,500_000)
    if not isinstance(document,dict) or not str(document.get("openapi","")).startswith(("3.0.","3.1.")):
        raise ContractError("Diperlukan OpenAPI 3.0 atau 3.1.")
    paths=document.get("paths",{})
    if not isinstance(paths,dict) or len(paths)>300:
        raise ContractError("Dokumen paths di luar batas.")
    ops={}
    for raw in entries(plan["operations"],50,1):
        obj(raw,("id","path","ref"))
        key=identifier(raw["id"],"Alias operasi")
        path=text(raw["path"],"Path OpenAPI",200)
        record=paths.get(path)
        if key in ops or not isinstance(record,dict) or not isinstance(record.get("get"),dict):
            raise ContractError("Alias ganda atau operasi GET tidak ditemukan.")
        get=record["get"]
        if "security" in get and get["security"]!=[] or get.get("requestBody") is not None or (
                document.get("security") and get.get("security") != []
        ):
            raise ContractError("Konektor fixture tidak menerima autentikasi atau body outbound.")
        result=get.get("responses",{}).get("200",{}).get("content",{}).get("application/json",{})
        params=_params(path,[*record.get("parameters",[]),*get.get("parameters",[])])
        ops[key]={"template":path,"params":params,"shape":_shape(result.get("schema")),
                  "source_ref":text(raw["ref"],"Rujukan operasi")}
    return {"schema":"ace.web.connector.v1","plan_sha256":expected,"document_sha256":plan["document_sha256"],
            "id":product,"origin":base,"source_ref":pointer,"max_response":cap,"operations":dict(sorted(ops.items()))}


def conforms(value,shape):
    kind=shape["type"]
    if kind=="object":
        fields=shape["properties"]
        return (isinstance(value,dict) and set(shape["required"])<=value.keys()<=fields.keys()
                and all(conforms(contents,fields[name]) for name,contents in value.items()))
    if kind=="array":
        return isinstance(value,list) and len(value)<=shape["maximum"] and all(conforms(item,shape["items"]) for item in value)
    match={"integer":(int,),"number":(int,float),"boolean":(bool,),"string":(str,),"null":(type(None),)}
    return kind in match and type(value) in match[kind]


def invoke(connector,expected,operation,params,*,transport=fetch):
    checked(connector,expected)
    schema(connector,"ace.web.connector.v1",("plan_sha256","document_sha256","id","origin","source_ref",
                                            "max_response","operations"))
    name=identifier(operation,"Alias request")
    operations=connector["operations"]
    if name not in operations:
        raise ContractError("Operasi tidak tercatat pada konektor.")
    row=operations[name]
    obj(row,("template","params","shape","source_ref"))
    values=obj(params,row["params"])
    path=row["template"]
    for key,kind in row["params"].items():
        value=values[key]
        if kind=="integer":
            value=str(integer(value,key,0,2**53-1))
        if not isinstance(value,str) or kind not in ("string","integer") or not SEGMENT.fullmatch(value):
            raise ContractError("Parameter tidak dapat menjadi satu segmen path.")
        path=path.replace("{"+key+"}",value)
    address=web_path(path)
    cap=integer(connector["max_response"],"Batas connector",50,500_000)
    base,_=origin(connector["origin"])
    response=transport(base,address,cap=cap)
    outcome={"schema":"ace.web.connector-receipt.v1","connector_sha256":expected,"operation":name,
             "source_ref":row["source_ref"],"path":address,"http_status":response.status,"body_sha256":None,
             "status":"held","reason":response.error}
    if response.error:
        return None,outcome
    outcome["body_sha256"]=sha256(response.body).hexdigest()
    if response.status!=200 or response.media_type!="application/json":
        return None,{**outcome,"reason":"unexpected_status_or_type"}
    try:
        body=decode(response.body)
        if not conforms(body,row["shape"]):
            return None,{**outcome,"reason":"schema_mismatch"}
    except (ValueError,RecursionError):
        return None,{**outcome,"reason":"json_invalid"}
    return body,{**outcome,"status":"verified","reason":None}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=compile_connector(decode(read(args.document)),decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,TypeError,KeyError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
