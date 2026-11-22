"""Nilai mutu materi aktual sebelum kurikulum dapat diserap.

Kebijakan menentukan kebaruan, jumlah kata, penanda topik, dan
duplikasi. Gate membaca berkas, membandingkan hash, dan memberi
alasan terukur per sumber. Mutu sumber bukan hasil belajar.
"""
import argparse
from collections import Counter
from pathlib import Path
import re
import sys

from . import skill_absorber
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


WORD=re.compile(r"[^\W_]+",re.UNICODE)


def _tokens(content):
    return WORD.findall(skill_absorber.normalized(content))


def evaluate(root,policy,expected,curriculum):
    checked(policy,expected)
    schema(policy,"ace.web.source-quality-policy.v1",("source_ref","curriculum_sha256","as_of","rules"))
    checked(curriculum,policy["curriculum_sha256"])
    schema(curriculum,"ace.web.skill-absorb-plan.v1",("id","cluster","version","source_ref","heldout_sha256","sources",
                                                      "objectives","lessons","practice"))
    now=time_value(policy["as_of"])
    source=text(policy["source_ref"],"Sumber kriteria mutu")
    criteria={}
    for raw in entries(policy["rules"],40,1):
        obj(raw,("source","source_ref","observed_at","max_age_days","min_words","max_duplicate_bp","topics"))
        key=identifier(raw["source"],"ID sumber")
        if key in criteria:
            raise ContractError("Kriteria sumber ganda.")
        timestamp=time_value(raw["observed_at"])
        if timestamp>now:
            raise ContractError("Waktu pengamatan sumber di masa depan.")
        topics=[]
        used=set()
        for marker in entries(raw["topics"],30,1):
            obj(marker,("id","phrase","source_ref"))
            name=identifier(marker["id"],"ID topik")
            tokens=_tokens(text(marker["phrase"],"Frasa topik",100))
            if not tokens or name in used or len(tokens)>12:
                raise ContractError("Frasa topik kosong/ganda atau melebihi batas.")
            used.add(name)
            topics.append((name,tokens,text(marker["source_ref"],"Sumber topik")))
        criteria[key]=(timestamp,integer(raw["max_age_days"],"Usia sumber",1,1825),
                       integer(raw["min_words"],"Jumlah kata minimum",1,80_000),
                       integer(raw["max_duplicate_bp"],"Toleransi duplikat",0,10_000),
                       sorted(topics),text(raw["source_ref"],"Rujukan aturan"))
    pages=skill_absorber._sources(root,curriculum["sources"])
    if pages.keys()!=criteria.keys():
        raise ContractError("Setiap sumber harus memiliki kriteria mutu.")
    observations=[]
    for key,(meta,lines) in sorted(pages.items()):
        when,limit,min_words,max_duplicates,topics,pointer=criteria[key]
        age=now-when
        words=_tokens(" ".join(lines))
        occupied=set(zip(words,words[1:],strict=False))
        signatures=Counter(skill_absorber.normalized(line) for line in lines if line.strip())
        total=sum(signatures.values())
        duplicate_bp=(total-len(signatures))*10_000//total if total else 0
        topics_found=[]
        for name,pattern,ref in topics:
            plausible=len(pattern)!=2 or tuple(pattern) in occupied
            length=len(pattern)
            hit=plausible and any(words[index:index+length]==pattern for index in range(len(words)-length+1))
            topics_found.append({"id":name,"found":hit,"source_ref":ref})
        problems=[]
        if age>limit*86400:
            problems.append("source_stale")
        if len(words)<min_words:
            problems.append("too_few_words")
        if duplicate_bp>max_duplicates:
            problems.append("duplicate_lines")
        if any(not item["found"] for item in topics_found):
            problems.append("topic_not_observed")
        observations.append({"id":key,"material_ref":meta["source_ref"],"material_sha256":meta["sha256"],
                             "rule_ref":pointer,"age_seconds":age,"word_count":len(words),"duplicate_bp":duplicate_bp,
                             "topics":topics_found,"findings":problems,"status":"accepted" if not problems else "held"})
    ready=all(item["status"]=="accepted" for item in observations)
    return {"schema":"ace.web.source-quality-receipt.v1","policy_sha256":expected,
            "curriculum_sha256":policy["curriculum_sha256"],"source_ref":source,"sources":observations,
            "status":"eligible" if ready else "held"}


def sift_and_absorb(root,policy,expected,curriculum):
    report=evaluate(root,policy,expected,curriculum)
    if report["status"]!="eligible":
        return None,report
    skill,receipt=skill_absorber.absorb(root,curriculum,policy["curriculum_sha256"])
    return skill,{**report,"absorption_receipt":receipt,"quality_sha256":identity(report)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("root","policy","curriculum"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--package-output",type=Path)
    args=parser.parse_args(argv)
    try:
        inputs=args.root,decode(read(args.policy)),args.expect_sha256,decode(read(args.curriculum))
        if args.package_output is not None:
            package,output=sift_and_absorb(*inputs)
            if package is not None:
                with args.package_output.open("xb") as stream:
                    stream.write(canonical(package)+b"\n")
        else:
            output=evaluate(*inputs)
        sys.stdout.buffer.write(canonical(output)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(output["status"]!="eligible")


if __name__=="__main__":
    raise SystemExit(main())
