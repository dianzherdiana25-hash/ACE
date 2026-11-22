"""Bandingkan hasil held-out bertanggal untuk mengukur retensi skill.

Baseline dan follow-up harus tercatat, berasal dari scope controlled,
memakai paket yang sama, dan memakai suite yang berbeda serta
setara menurut rujukan desain. Delta dilaporkan per tujuan.
"""
import argparse
from collections import Counter,defaultdict
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,integer,obj,read,schema,text
from .web_scheduler import time_value


def _receipt(record,anchor,key,pkg):
    checked(record,anchor)
    schema(record,"ace.web.skill-verification-receipt.v1",("skill","cluster","version","package_sha256","suite_sha256","answer_sha256",
             "scope","at","source_ref","suite_ref","solver_ref","evaluator_ref","score_bp","objectives","cases","passed","status"))
    if record["skill"]!=key or record["package_sha256"]!=pkg:
        raise ContractError("Receipt tidak menilai paket skill yang sama.")
    digest(record["suite_sha256"])
    digest(record["answer_sha256"])
    text(record["source_ref"],"Sumber jawaban")
    time_value(record["at"])
    integer(record["score_bp"],"Skor",0,10_000)
    data=record["objectives"]
    if not isinstance(data,dict) or not 1<=len(data)<=80:
        raise ContractError("Daftar tujuan pada receipt tidak sah.")
    cases=defaultdict(Counter)
    names=set()
    for row in entries(record["cases"],250,1):
        obj(row,("id","objective","criterion_ref","answer_ref","answer_sha256","expected_sha256","status"))
        name=identifier(row["id"],"Kasus")
        key=identifier(row["objective"],"Tujuan kasus")
        state=row["status"]
        if name in names or key not in data or state not in ("passed","failed","missing"):
            raise ContractError("Kasus receipt ganda atau tidak sah.")
        names.add(name)
        digest(row["expected_sha256"])
        text(row["criterion_ref"],"Rujukan criterion")
        if state=="missing":
            if row["answer_ref"] is not None or row["answer_sha256"] is not None:
                raise ContractError("Kasus tanpa jawaban memiliki bukti yang kontradiktif.")
        else:
            digest(row["answer_sha256"])
            text(row["answer_ref"],"Rujukan jawaban")
        cases[key][state]+=1
    if record["score_bp"]!=sum(row["passed"] for row in cases.values())*10_000//len(names):
        raise ContractError("Skor total berbeda dari kasus receipt.")
    for name,row in data.items():
        identifier(name,"Tujuan")
        obj(row,("tested","passed","missing","score_bp","qualified"))
        total=integer(row["tested"],"Kasus",0,250)
        good=integer(row["passed"],"Kasus lulus",0,total)
        integer(row["missing"],"Kasus tanpa jawaban",0,total-good)
        summary=cases[name]
        if ((total,good,row["missing"])!=(sum(summary.values()),summary["passed"],summary["missing"])
                or row["score_bp"]!=(good*10_000//total if total else None) or type(row["qualified"]) is not bool):
            raise ContractError("Census tujuan tidak cocok dengan skor.")
    return record


def compare(probe,expected,reference,followup):
    checked(probe,expected)
    schema(probe,"ace.web.skill-retention-plan.v1",("source_ref","skill","package_sha256","baseline_sha256","followup_sha256",
            "comparability_ref","minimum_days","maximum_drop_bp","minimum_cases"))
    key=identifier(probe["skill"],"Skill")
    package=digest(probe["package_sha256"])
    source=text(probe["source_ref"],"Sumber retensi")
    equivalence=text(probe["comparability_ref"],"Bukti kesetaraan suite")
    delay=integer(probe["minimum_days"],"Umur minimum",1,365)*86400
    tolerance=integer(probe["maximum_drop_bp"],"Penurunan maksimum",0,10_000)
    floor=integer(probe["minimum_cases"],"Kasus minimum per tujuan",1,100)
    baseline=_receipt(reference,probe["baseline_sha256"],key,package)
    current=_receipt(followup,probe["followup_sha256"],key,package)
    elapsed=time_value(current["at"])-time_value(baseline["at"])
    report={"schema":"ace.web.skill-retention-report.v1","plan_sha256":expected,"skill":key,"package_sha256":package,
            "source_ref":source,"comparability_ref":equivalence,"baseline_sha256":probe["baseline_sha256"],
            "followup_sha256":probe["followup_sha256"],"elapsed_seconds":elapsed,"status":"unmeasured",
            "reason":None,"objectives":[],"delta_bp":None}
    a,b=baseline["objectives"],current["objectives"]
    if baseline["scope"]!="controlled" or current["scope"]!="controlled":
        return {**report,"reason":"fixture_scope"}
    if baseline["suite_sha256"]==current["suite_sha256"]:
        return {**report,"reason":"reused_suite"}
    if not baseline["passed"] or elapsed<delay:
        return {**report,"reason":"baseline_or_interval_unqualified"}
    if a.keys()!=b.keys() or any(value["tested"]<floor or value["missing"] for data in (a,b) for value in data.values()):
        return {**report,"reason":"insufficient_objective_evidence"}
    scores=[{"id":name,"delta_bp":b[name]["score_bp"]-a[name]["score_bp"],"before_bp":a[name]["score_bp"],
             "after_bp":b[name]["score_bp"],"before_cases":a[name]["tested"],"after_cases":b[name]["tested"]}
            for name in sorted(a)]
    drift=any(item["delta_bp"]<-tolerance for item in scores)
    return {**report,"status":"fragile" if drift else "retained","reason":None,
            "delta_bp":current["score_bp"]-baseline["score_bp"],"objectives":scores}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","baseline","followup"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=compare(decode(read(args.plan)),args.expect_sha256,decode(read(args.baseline)),decode(read(args.followup)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="unmeasured")


if __name__=="__main__":
    raise SystemExit(main())
