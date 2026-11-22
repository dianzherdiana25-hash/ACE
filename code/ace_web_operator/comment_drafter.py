"""Susun respons komentar dengan template, rujukan fakta, dan telaah.

Routing kategori eksplisit menentukan template. Fakta yang digunakan
harus cocok dengan entri yang terverifikasi pada snapshot rujukan.
Draf tanpa landasan tetap ditahan, dan hasilnya tidak dikirim.
"""
import argparse
from pathlib import Path
import string
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,schema,text


FORMAT=string.Formatter()
LOCALES={"id","en"}


def _template(raw):
    obj(raw,("category","locale","body","facts","source_ref"))
    category=identifier(raw["category"],"Kategori komentar")
    locale=raw["locale"]
    if not isinstance(locale,str) or locale not in LOCALES:
        raise ContractError("Locale draft belum didukung.")
    value=text(raw["body"],"Template",1200)
    fields=[identifier(name,"Fakta template") for name in entries(raw["facts"],30)]
    if len(set(fields))!=len(fields):
        raise ContractError("Fakta template ganda.")
    drawn=[]
    used=set()
    for literal,slot,spec,conversion in FORMAT.parse(value):
        if slot is not None:
            if slot not in fields or spec or conversion:
                raise ContractError("Placeholder di luar deklarasi fakta.")
            used.add(slot)
        drawn.append((literal,slot))
    if used!=set(fields):
        raise ContractError("Ada fakta tidak digunakan dalam template.")
    return (category,locale),(drawn,fields,text(raw["source_ref"],"Rujukan template"))


def draft(settings,expected,inbox,review):
    checked(settings,expected)
    schema(settings,"ace.web.comment-draft-policy.v1",("source_ref","inbox_sha256","facts_sha256","templates"))
    checked(inbox,settings["inbox_sha256"])
    checked(review,settings["facts_sha256"])
    pointer=text(settings["source_ref"],"Sumber kebijakan")
    schema(inbox,"ace.web.comment-inbox.v1",("comments",))
    schema(review,"ace.web.comment-facts.v1",("entries",))
    templates={}
    proofs={}
    for row in entries(settings["templates"],80,1):
        key,value=_template(row)
        if key in templates:
            raise ContractError("Template kategori dan bahasa ganda.")
        templates[key]=value
    for row in entries(review["entries"],300):
        obj(row,("id","value","status","source_ref","evidence_sha256"))
        name=identifier(row["id"],"Fakta")
        if name in proofs or row["status"] not in ("verified","unverified"):
            raise ContractError("Fakta ganda atau status tidak dikenal.")
        anchor=digest(row["evidence_sha256"])
        proofs[name]=(text(row["value"],"Isi fakta",260),row["status"],
                      text(row["source_ref"],"Sumber fakta"),anchor)
    results={}
    for row in entries(inbox["comments"],300):
        obj(row,("id","category","locale","source_ref","comment_sha256"))
        key=identifier(row["id"],"Komentar")
        category=identifier(row["category"],"Kategori")
        locale=row["locale"]
        if key in results or not isinstance(locale,str) or locale not in LOCALES:
            raise ContractError("Komentar ganda atau locale belum didukung.")
        record={"id":key,"source_ref":text(row["source_ref"],"Sumber komentar"),"comment_sha256":digest(row["comment_sha256"]),
                "status":"operator_required","reason":"template_missing","draft":None,"fact_refs":[]}
        if (category,locale) in templates:
            pieces,fields,ref=templates[(category,locale)]
            absent=sorted(name for name in fields if name not in proofs or proofs[name][1]!="verified")
            record.update(template_ref=ref,missing_facts=absent)
            if absent:
                record["reason"]="fact_missing_or_unverified"
            else:
                value="".join(literal+(proofs[slot][0] if slot is not None else "") for literal,slot in pieces)
                text(value,"Draf komentar",1400)
                record.update(status="awaiting_review",reason=None,draft=value,
                              fact_refs=[{"id":name,"source_ref":proofs[name][2],"evidence_sha256":proofs[name][3]}
                                         for name in sorted(fields)])
        results[key]=record
    summary=list(results[key] for key in sorted(results))
    return {"schema":"ace.web.comment-draft-report.v1","policy_sha256":expected,"source_ref":pointer,
            "inbox_sha256":settings["inbox_sha256"],"facts_sha256":settings["facts_sha256"],
            "drafts":summary,"sent":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("policy","inbox","facts"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=draft(decode(read(args.policy)),args.expect_sha256,decode(read(args.inbox)),decode(read(args.facts)))
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
