"""Isi grid spreadsheet fixture dari matriks lokal dengan alamat A1.

Posisi dan tipe sel divalidasi sebelum browser dipanggil. Setiap nilai
diperiksa ulang melalui input. Rumus dan submit dikeluarkan dari kontrak
fixture supaya rehearsal berakhir pada isi grid sementara.
"""
import argparse
from pathlib import Path
import re
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,read,schema,text,web_path


A1=re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,3})")
MUTATING={"commit","publish","save","submit","apply"}


def _cell(raw):
    if type(raw) is bool:
        return "true" if raw else "false"
    if type(raw) is int:
        return str(integer(raw,"Integer sel",-2**53+1,2**53-1))
    value=text(raw,"Teks sel",180)
    if value.lstrip().startswith(("=","+","-","@")):
        raise ContractError("Rumus atau sel yang menyerupai rumus tidak didukung.")
    return value


def _column(number):
    values=[]
    while number>0:
        number,position=divmod(number-1,26)
        values.append(chr(65+position))
    return "".join(reversed(values))


def compile_grid(plan,expected,sheet):
    checked(plan,expected)
    schema(plan,"ace.web.sheet-plan.v1",("source_ref","sheet_sha256","browser","path","start","selector_prefix"))
    checked(sheet,plan["sheet_sha256"])
    schema(sheet,"ace.web.sheet-data.v1",("source_ref","rows"))
    pointer=text(plan["source_ref"],"Sumber grid")
    source=text(sheet["source_ref"],"Sumber data sel")
    start=text(plan["start"],"Alamat mula",12)
    matching=A1.fullmatch(start)
    if matching is None:
        raise ContractError("Alamat mula harus A1 kanonis.")
    letters,number=matching.groups()
    index=0
    for letter in letters:
        index=index*26+(ord(letter)-64)
    first_row=int(number)
    prefix=identifier(plan["selector_prefix"],"Prefix selector sel")
    browser=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    path=web_path(plan["path"])
    if any(set(web_path(value).casefold().split("/"))&MUTATING for value in entries(browser["allow_paths"],70,1)):
        raise ContractError("Tidak ada rute mutasi tersimpan pada rehearsal grid.")
    rows=entries(sheet["rows"],18,1)
    size=len(entries(rows[0],18,1))
    if len(rows)*size>18 or index+size-1>702 or first_row+len(rows)-1>1000:
        raise ContractError("Rentang grid melebihi scope fixture.")
    steps=[{"id":"open_grid","op":"navigate","path":path}]
    cells=[]
    for r,row in enumerate(rows,first_row):
        if not isinstance(row,list) or len(row)!=size:
            raise ContractError("Grid harus persegi panjang.")
        for c,value in enumerate(row,index):
            coordinate=f"{_column(c)}{r}"
            label=f"{prefix}_{coordinate.lower()}"
            escaped=_cell(value)
            fill_id=f"fill_{len(cells)+1}"
            check_id=f"check_{len(cells)+1}"
            steps.extend([{"id":fill_id,"op":"fill","test_id":label,"value":escaped},
                          {"id":check_id,"op":"expect_value","test_id":label,"expected":escaped}])
            cells.append({"cell":coordinate,"check":check_id,"value_sha256":identity(escaped)})
    recipe={"schema":"ace.web.browser-plan.v1","source_ref":pointer,**browser,"steps":steps}
    browser_engine.compile_plan(recipe,identity(recipe))
    return recipe,cells,source


def fill(plan,expected,sheet,*,browser=browser_engine.run):
    program,cells,pointer=compile_grid(plan,expected,sheet)
    key=identity(program)
    record=browser(program,key)
    if record.get("plan_sha256")!=key:
        raise ContractError("Receipt browser merujuk grid lain.")
    observed={row["id"]:row["status"] for row in record["steps"]}
    for row in cells:
        row["verified"]=observed.get(row.pop("check"))=="ok"
    return {"schema":"ace.web.sheet-receipt.v1","plan_sha256":expected,"sheet_sha256":plan["sheet_sha256"],
            "source_ref":plan["source_ref"],"sheet_ref":pointer,"browser_sha256":key,"saved_to_service":False,
            "status":"filled_locally" if record["status"]=="completed" else "held","cells":cells,"reason":record["reason"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("sheet",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=fill(decode(read(args.plan)),args.expect_sha256,decode(read(args.sheet)))
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="filled_locally")


if __name__=="__main__":
    raise SystemExit(main())
