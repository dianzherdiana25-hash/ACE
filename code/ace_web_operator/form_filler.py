"""Isi kontrol form dari data yang diikat kontrak dan batas situs lokal.

Field divalidasi seluruhnya sebelum browser dibuka. Builder
menghasilkan instruksi fill/select/check tanpa menjalankan submit.
Receipt merujuk field dan status saja, tanpa menyalin nilai form.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,read,schema,text


def compile_form(plan,values,expected):
    checked(plan,expected)
    schema(plan,"ace.web.form-plan.v1",("source_ref","browser","path","fields"))
    source=text(plan["source_ref"],"Rujukan form")
    settings=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    schema(values,"ace.web.form-assignment.v1",("form_sha256","values","source_ref"))
    if values["form_sha256"]!=expected:
        raise ContractError("Nilai form merujuk form yang berbeda.")
    value_ref=text(values["source_ref"],"Sumber nilai form")
    data=values["values"]
    if not isinstance(data,dict):
        raise ContractError("Nilai form harus berbentuk objek.")
    fields=set()
    controls=set()
    records=[]
    operations=[{"id":"open_form","op":"navigate","path":plan["path"]}]
    for row in entries(plan["fields"],30,1):
        obj(row,("id","kind","test_id","required","max_chars","choices","source_ref"))
        key=identifier(row["id"],"ID field")
        locator=identifier(row["test_id"],"Selector fixture")
        kind=row["kind"]
        source_ref=text(row["source_ref"],"Sumber field")
        if (key in fields or locator in controls or kind not in ("text","choice","checkbox") or
                type(row["required"]) is not bool):
            raise ContractError("Field, selector, atau tipe form tidak sah.")
        fields.add(key)
        controls.add(locator)
        allowed=entries(row["choices"],30,1 if kind=="choice" else 0)
        if kind=="choice":
            options=[text(value,"Pilihan",150) for value in allowed]
            if len(set(options))!=len(options) or row["max_chars"] is not None:
                raise ContractError("Kontrak pilihan tidak sah.")
        elif allowed or (kind=="checkbox" and row["max_chars"] is not None):
            raise ContractError("Kontrak kontrol memiliki opsi yang keliru.")
        max_chars=integer(row["max_chars"],"Batas field",1,500) if kind=="text" else None
        supplied=data.get(key)
        if key not in data:
            if row["required"]:
                raise ContractError(f"Field wajib belum terisi pada {key}.")
            records.append({"id":key,"source_ref":source_ref,"status":"omitted"})
            continue
        if kind=="text":
            if (not isinstance(supplied,str) or len(supplied)>max_chars or supplied!="" and not supplied.isprintable()
                    or row["required"] and not supplied.strip()):
                raise ContractError(f"Nilai teks di luar kontrak pada {key}.")
            op={"op":"fill","value":supplied}
        elif kind=="choice":
            if supplied not in options:
                raise ContractError(f"Pilihan tidak diizinkan pada {key}.")
            op={"op":"select","value":supplied}
        else:
            if type(supplied) is not bool or row["required"] and not supplied:
                raise ContractError(f"Checkbox wajib memiliki state yang sah pada {key}.")
            op={"op":"check","state":supplied}
        operations.append({"id":f"field_{len(operations)}","test_id":locator,**op})
        records.append({"id":key,"source_ref":source_ref,"step":operations[-1]["id"],"status":"planned"})
    if data.keys()-fields:
        raise ContractError("Payload form memuat field yang tidak terdaftar.")
    browser={"schema":"ace.web.browser-plan.v1","source_ref":source,**settings,"steps":operations}
    browser_engine.compile_plan(browser,identity(browser))
    return browser,records,value_ref


def fill(plan,values,expected,*,browser=browser_engine.run):
    program,fields,pointer=compile_form(plan,values,expected)
    anchor=identity(program)
    receipt=browser(program,anchor)
    if receipt.get("plan_sha256")!=anchor:
        raise ContractError("Receipt browser menunjuk kontrak lain.")
    outcomes={row["id"]:row["status"] for row in receipt["steps"]}
    for field in fields:
        if field["status"]=="planned":
            state=outcomes.get(field.pop("step"))
            field["status"]="filled" if state=="ok" else "failed" if state=="failed" else "not_started"
    return {"schema":"ace.web.form-receipt.v1","form_sha256":expected,"values_sha256":identity(values),
            "values_ref":pointer,"browser_sha256":anchor,"source_ref":plan["source_ref"],
            "status":"filled_locally" if receipt["status"]=="completed" else "held","reason":receipt["reason"],
            "submitted":False,"fields":fields}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("values",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=fill(decode(read(args.plan)),decode(read(args.values)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="filled_locally")


if __name__=="__main__":
    raise SystemExit(main())
