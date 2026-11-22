"""Baca metrik panel analytics fixture setelah filter tanggal cocok.

Ekstraksi DOM membuktikan baris yang dipakai. Tanggal di luar filter,
ID ganda, atau kolom tak dikenal ditahan. Ringkasan mencatat jumlah,
kelompok serta provenance tanpa mengubah dashboard.
"""
import argparse
from collections import defaultdict
from datetime import date
from pathlib import Path
import sys

from . import browser_engine,page_extractor
from ._artifact import write_new
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,obj,read,schema,text,web_path
from .heavy_js_extractor import _bytes


FIELDS=("id","date","group","value")


def _date(raw):
    value=text(raw,"Tanggal analytics",10)
    observed=date.fromisoformat(value)
    if observed.isoformat()!=value:
        raise ContractError("Tanggal analytics tidak kanonis.")
    return observed


def run(plan,expected,*,browser=browser_engine.run):
    checked(plan,expected)
    schema(plan,"ace.web.analytics-plan.v1",("source_ref","permission_ref","browser","path","filter","date_from","date_until",
                                             "container","row_class","metric","groups"))
    source=text(plan["source_ref"],"Sumber analytics")
    approval=text(plan["permission_ref"],"Izin baca panel")
    settings=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    path=web_path(plan["path"])
    start,end=(_date(plan[name]) for name in ("date_from","date_until"))
    if not 0<(end-start).days<=365:
        raise ContractError("Jendela filter analytics tidak sah.")
    metric=identifier(plan["metric"],"Metrik")
    groups=[identifier(name,"Kelompok") for name in entries(plan["groups"],50,1)]
    if len(set(groups))!=len(groups):
        raise ContractError("Kelompok analytics ganda.")
    selection=obj(plan["filter"],("target","value","ready_target","ready_text"))
    control=identifier(selection["target"],"Selector filter")
    value=text(selection["value"],"Opsi filter",90)
    witness=identifier(selection["ready_target"],"Selector penanda")
    condition=text(selection["ready_text"],"Bukti filter",160)
    container=identifier(plan["container"],"Kontainer data")
    row_class=identifier(plan["row_class"],"Kelas baris data")
    job={"schema":"ace.web.browser-plan.v1","source_ref":source,**settings,
         "steps":[{"id":"open","op":"navigate","path":path},
                  {"id":"select","op":"select","test_id":control,"value":value},
                  {"id":"verify_filter","op":"expect_value","test_id":control,"expected":value},
                  {"id":"ready","op":"wait_text","test_id":witness,"expected":condition},
                  {"id":"capture","op":"capture_dom","test_id":container}]}
    anchor=identity(job)
    browser_engine.compile_plan(job,anchor)
    outcome=browser(job,anchor)
    if outcome.get("plan_sha256")!=anchor:
        raise ContractError("Receipt browser berasal dari query lain.")
    output={"schema":"ace.web.analytics-receipt.v1","plan_sha256":expected,"browser_sha256":anchor,
            "source_ref":source,"permission_ref":approval,"metric":metric,"period":[plan["date_from"],plan["date_until"]],
            "status":"held","reason":outcome["reason"],"groups":[]}
    if outcome["status"]!="completed":
        return {},output
    content,capture=_bytes(outcome["steps"][-1]["evidence"])
    artifact=f"analytics-{capture[:20]}.html"
    extraction={"schema":"ace.web.extract-plan.v1","source_ref":source,"html_ref":artifact,"html_sha256":capture,
                "row_tag":"tr","row_class":row_class,"primary":"id","fields":[
                    {"name":name,"marker":name,"type":"integer" if name=="value" else "text",
                     "from":"text","required":True,"source_ref":f"{source}#{name}"} for name in FIELDS]}
    data=page_extractor.extract(content,extraction,identity(extraction))
    if data["status"]!="complete":
        output.update(reason="source_incomplete",extraction=data)
    else:
        by_group=defaultdict(list)
        for row in data["rows"]:
            values=row["values"]
            key=values["group"]
            if key not in groups or not start<=_date(values["date"])<end or values["value"]<0:
                output.update(reason="row_outside_filter",extraction=data)
                break
            by_group[key].append({"id":values["id"],"value":values["value"],"line":row["line"]})
        else:
            summary=[{"group":key,"total":sum(item["value"] for item in by_group[key]) if by_group[key] else None,
                      "events":by_group[key]} for key in sorted(groups)]
            output.update(status="measured_fixture",reason=None,groups=summary,extraction=data)
    return {artifact:content,"analytics_receipt.json":canonical(output)+b"\n"},output


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,result=run(decode(read(args.plan)),args.expect_sha256)
        if files:
            write_new(args.output,files)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="held")


if __name__=="__main__":
    raise SystemExit(main())
