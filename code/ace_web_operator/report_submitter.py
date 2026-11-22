"""Siapkan pengisian draft laporan berkala dari fakta yang tertambat.

Agregasi terbatas pada periode dan metrik yang ditentukan. Nilai
hilang mencegah rehearsal form. Langkah browser hanya mengisi data,
dengan receipt untuk telaah sebelum tindak lanjut operator.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

from . import browser_engine,form_filler
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


def prepare(plan,expected,report,form):
    checked(plan,expected)
    schema(plan,"ace.web.period-report-plan.v1",("source_ref","report_sha256","form_sha256","from","until","mapping"))
    checked(report,plan["report_sha256"])
    checked(form,plan["form_sha256"])
    schema(report,"ace.web.period-records.v1",("source_ref","rows"))
    pointer=text(plan["source_ref"],"Sumber pengisian laporan")
    source_ref=text(report["source_ref"],"Sumber catatan")
    lower,upper=(time_value(plan[field]) for field in ("from","until"))
    if not 0<upper-lower<=86400*92:
        raise ContractError("Periode laporan di luar batas.")
    mapping={}
    for row in entries(plan["mapping"],30,1):
        obj(row,("field","metric","source_ref"))
        field=identifier(row["field"],"Field form")
        if field in mapping:
            raise ContractError("Pemetaan field ganda.")
        mapping[field]=(identifier(row["metric"],"Metric"),text(row["source_ref"],"Sumber mapping"))
    observations=defaultdict(list)
    seen=set()
    for row in entries(report["rows"],5000):
        obj(row,("id","metric","at","count","source_ref","evidence_sha256"))
        key=identifier(row["id"],"ID fakta")
        metric=identifier(row["metric"],"Metrik")
        if key in seen:
            raise ContractError("ID fakta ganda.")
        seen.add(key)
        checked_ref=text(row["source_ref"],"Sumber fakta")
        anchor=digest(row["evidence_sha256"])
        at=time_value(row["at"])
        count=integer(row["count"],"Hitungan fakta",0,10**9)
        if lower<=at<upper:
            observations[metric].append((key,count,checked_ref,anchor))
    fields=[]
    values={}
    for name,(metric,ref) in sorted(mapping.items()):
        rows=sorted(observations[metric])
        if rows:
            values[name]=str(sum(row[1] for row in rows))
        fields.append({"field":name,"metric":metric,"source_ref":ref,"status":"grounded" if rows else "missing",
                       "inputs":[{"id":key,"source_ref":source,"evidence_sha256":anchor} for key,_,source,anchor in rows]})
    evidence={"schema":"ace.web.report-draft-receipt.v1","plan_sha256":expected,"source_ref":pointer,"data_ref":source_ref,
              "report_sha256":plan["report_sha256"],"form_sha256":plan["form_sha256"],
              "fields":fields,"period":[plan["from"],plan["until"]],"submitted":False}
    if len(values)!=len(mapping):
        return None,{**evidence,"status":"held","reason":"missing_metric"}
    result={"schema":"ace.web.form-assignment.v1","form_sha256":plan["form_sha256"],"values":values,"source_ref":source_ref}
    form_filler.compile_form(form,result,plan["form_sha256"])
    return result,{**evidence,"status":"ready_for_rehearsal","reason":None,"values_sha256":identity(result)}


def rehearse(plan,expected,report,form,*,browser=browser_engine.run):
    data,verdict=prepare(plan,expected,report,form)
    if data is None:
        return verdict
    result=form_filler.fill(form,data,plan["form_sha256"],browser=browser)
    return {**verdict,"status":"filled_locally" if result["status"]=="filled_locally" else "held",
            "reason":result["reason"],"form_receipt":result}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","records","form"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--rehearse",action="store_true")
    args=parser.parse_args(argv)
    try:
        inputs=decode(read(args.plan)),args.expect_sha256,decode(read(args.records)),decode(read(args.form))
        result=rehearse(*inputs) if args.rehearse else prepare(*inputs)[1]
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="held")


if __name__=="__main__":
    raise SystemExit(main())
