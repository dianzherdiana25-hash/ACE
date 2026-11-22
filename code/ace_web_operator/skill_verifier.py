"""Nilai jawaban atas suite held-out yang dibekukan sebelum kurikulum.

Verifier memeriksa hash paket, suite, jawaban, serta tumpang tindih
prompt latihan. Hasil dilaporkan per tujuan dan jenis pengukuran.
Receipt fixture hanya menyatakan lulus fixture.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .skill_absorber import OPS,normalized,prompt_identity
from .web_scheduler import time_value


def _rubric(op,expected,actual):
    if op=="equals":
        return identity(expected)==identity(actual)
    if op=="text_fold":
        return type(expected) is str and type(actual) is str and normalized(expected)==normalized(actual)
    if op=="int_exact":
        return type(actual) is int and type(expected) is int and actual==expected
    if op=="contains_all":
        return isinstance(actual,list) and {identity(item) for item in expected}<={identity(item) for item in actual}
    raise ContractError("Rubrik mekanis belum dikenal.")


def _cases(suite,package,targets):
    training_names={row["id"] for row in package["practice"]}
    training_prompts={row["prompt_sha256"] for row in package["practice"]}
    excerpts=[normalized(row["excerpt"]) for row in package["lessons"]]
    records={}
    used=set()
    for row in entries(suite["cases"],250,1):
        obj(row,("id","objective","prompt","op","expected","source_ref"))
        key=identifier(row["id"],"ID held-out")
        objective=identifier(row["objective"],"Tujuan held-out")
        question=text(row["prompt"],"Pertanyaan held-out",1000)
        fingerprint=prompt_identity(question)
        op=row["op"]
        expected=row["expected"]
        if key in training_names or fingerprint in training_prompts or (
            len(normalized(question).split())>=4 and any(normalized(question) in source for source in excerpts)
        ):
            raise ContractError("Kasus held-out tumpang tindih dengan latihan/pelajaran.")
        if (key in records or fingerprint in used or objective not in targets or not isinstance(op,str) or op not in OPS
                or len(canonical(expected))>8000):
            raise ContractError("Kasus held-out tidak sah.")
        if ((op=="text_fold" and not isinstance(expected,str)) or (op=="int_exact" and type(expected) is not int) or
                (op=="contains_all" and (not isinstance(expected,list) or not expected))):
            raise ContractError("Jawaban patokan tidak sesuai rubrik.")
        used.add(fingerprint)
        records[key]=(objective,op,expected,text(row["source_ref"],"Sumber kasus"))
    return records


def evaluate(package,package_anchor,suite,answers,answer_anchor):
    checked(package,package_anchor)
    schema(package,"ace.web.skill-package.v1",("id","cluster","version","source_ref","plan_sha256","heldout_sha256",
                                                "sources","objectives","lessons","practice"))
    suite_hash=digest(package["heldout_sha256"])
    checked(suite,suite_hash)
    checked(answers,answer_anchor)
    schema(suite,"ace.web.heldout-suite.v1",("skill","scope","source_ref","evaluator_ref","min_cases_per_objective",
                                              "target_bp","cases"))
    schema(answers,"ace.web.heldout-answers.v1",("package_sha256","suite_sha256","source_ref","solver_ref",
                                                  "at","answers"))
    key=identifier(package["id"],"Skill")
    scope=suite["scope"]
    if (suite["skill"]!=key or scope not in ("fixture","controlled") or answers["package_sha256"]!=package_anchor
            or answers["suite_sha256"]!=suite_hash):
        raise ContractError("Suite, jawaban dan paket tidak tertambat pada skill yang sama.")
    suite_ref=text(suite["source_ref"],"Sumber suite")
    evaluator=text(suite["evaluator_ref"],"Evaluator independen")
    solver=text(answers["solver_ref"],"Rujukan solver")
    source=text(answers["source_ref"],"Sumber jawaban")
    at=answers["at"]
    time_value(at)
    if evaluator==solver:
        raise ContractError("Evaluator perlu rujukan berbeda dari solver.")
    target=integer(suite["target_bp"],"Ambang basis points",1,10_000)
    minimum=integer(suite["min_cases_per_objective"],"Kasus minimum per tujuan",1,100)
    targets=[identifier(row["id"],"Tujuan skill") for row in entries(package["objectives"],50,1)]
    if len(set(targets))!=len(targets):
        raise ContractError("Tujuan skill ganda.")
    records=_cases(suite,package,set(targets))
    supplied={}
    for row in entries(answers["answers"],250):
        obj(row,("id","value","source_ref"))
        name=identifier(row["id"],"ID jawaban")
        if name in supplied or name not in records or len(canonical(row["value"]))>8000:
            raise ContractError("Jawaban ganda, tak dikenal, atau terlalu panjang.")
        supplied[name]=(row["value"],text(row["source_ref"],"Sumber jawaban kasus"))
    outcomes=[]
    totals={name:{"tested":0,"passed":0,"missing":0} for name in sorted(targets)}
    for name,(objective,op,expect,ref) in sorted(records.items()):
        stats=totals[objective]
        stats["tested"]+=1
        if name not in supplied:
            verdict="missing"
            actual_ref=None
            observed_hash=None
            stats["missing"]+=1
        else:
            actual,actual_ref=supplied[name]
            ok=_rubric(op,expect,actual)
            verdict="passed" if ok else "failed"
            observed_hash=identity(actual)
            stats["passed"]+=ok
        outcomes.append({"id":name,"objective":objective,"criterion_ref":ref,"answer_ref":actual_ref,
                         "answer_sha256":observed_hash,"expected_sha256":identity(expect),"status":verdict})
    for scores in totals.values():
        trials=scores["tested"]
        scores["score_bp"]=scores["passed"]*10_000//trials if trials else None
        scores["qualified"]=trials>=minimum and scores["missing"]==0 and scores["score_bp"]>=target
    score=sum(row["status"]=="passed" for row in outcomes)*10_000//len(outcomes)
    passed=all(row["qualified"] for row in totals.values())
    return {"schema":"ace.web.skill-verification-receipt.v1","skill":key,"cluster":package["cluster"],"version":package["version"],
            "package_sha256":package_anchor,"suite_sha256":suite_hash,"answer_sha256":answer_anchor,"scope":scope,"at":at,
            "source_ref":source,"suite_ref":suite_ref,"solver_ref":solver,"evaluator_ref":evaluator,"score_bp":score,
            "objectives":totals,"cases":outcomes,"passed":passed,"status":("fixture_passed" if scope=="fixture" else
                "heldout_passed") if passed else "below_criteria"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("package","suite","answers"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--package-sha256",required=True)
    parser.add_argument("--answers-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=evaluate(decode(read(args.package)),args.package_sha256,decode(read(args.suite)),
                        decode(read(args.answers)),args.answers_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,KeyError,TypeError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(not result["passed"])


if __name__=="__main__":
    raise SystemExit(main())
