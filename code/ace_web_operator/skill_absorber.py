"""Susun paket skill dari sumber lokal berlisensi dan tujuan terdaftar.

Pelajaran mengambil kutipan dengan rentang baris yang dapat diperiksa
ulang. Latihan memakai rubrik mekanis. Suite held-out tetap berada di
luar paket; compiler hanya menerima commitment SHA-256-nya.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from unicodedata import normalize

from ._artifact import read_relative,write_new
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,relative_path,schema,text


LICENSES={"CC0-1.0","CC-BY-4.0","CC-BY-SA-4.0","MIT","Apache-2.0","BSD-3-Clause"}
SOURCE_LIMIT=600_000
OPS={"equals","text_fold","int_exact","contains_all"}


def normalized(value):
    return " ".join(normalize("NFKC",value).casefold().split())


def prompt_identity(value):
    return identity(normalized(value))


def _sources(root,raw):
    result={}
    total=0
    stored=set()
    for row in entries(raw,40,1):
        obj(row,("id","path","sha256","license","license_ref","source_ref"))
        key=identifier(row["id"],"ID sumber")
        path=relative_path(row["path"])
        anchor=digest(row["sha256"])
        license_name=row["license"]
        if key in result or path in stored or Path(path).suffix.lower() not in (".txt",".md",".rst") or (
                not isinstance(license_name,str) or license_name not in LICENSES):
            raise ContractError("Sumber ganda, tipe atau lisensi tidak disetujui.")
        stored.add(path)
        data=read_relative(root,path,min(SOURCE_LIMIT,2_500_000-total),anchor)
        total+=len(data)
        value=data.decode("utf-8")
        if not value.strip() or any(not (char.isprintable() or char in "\r\n\t") for char in value):
            raise ContractError("Sumber latihan kosong atau mengandung kontrol.")
        lines=value.splitlines()
        result[key]=({"id":key,"path":path,"sha256":anchor,"license":license_name,
                      "license_ref":text(row["license_ref"],"Bukti lisensi"),
                      "source_ref":text(row["source_ref"],"Rujukan sumber"),"lines":len(lines)},lines)
    return result


def _objectives(raw):
    result={}
    for row in entries(raw,50,1):
        obj(row,("id","statement","source_ref"))
        key=identifier(row["id"],"ID tujuan")
        if key in result:
            raise ContractError("Tujuan ganda.")
        result[key]={"id":key,"statement":text(row["statement"],"Tujuan",280),
                     "source_ref":text(row["source_ref"],"Sumber tujuan")}
    return result


def _lessons(raw,sources,objectives):
    result={}
    covered=set()
    for row in entries(raw,80,1):
        obj(row,("id","source","first_line","last_line","objectives","source_ref"))
        key=identifier(row["id"],"Pelajaran")
        source=identifier(row["source"],"Sumber pelajaran")
        if key in result or source not in sources:
            raise ContractError("Pelajaran ganda atau sumber tidak ditemukan.")
        evidence,lines=sources[source]
        first=integer(row["first_line"],"Baris pertama",1,len(lines))
        last=integer(row["last_line"],"Baris terakhir",first,min(len(lines),first+79))
        section="\n".join(lines[first-1:last])
        if not section.strip() or len(section)>6500:
            raise ContractError("Kutipan pelajaran kosong atau terlalu panjang.")
        keys=[identifier(name,"Tujuan pelajaran") for name in entries(row["objectives"],50,1)]
        if len(set(keys))!=len(keys) or set(keys)-objectives.keys():
            raise ContractError("Pelajaran menunjuk tujuan ganda atau tak dikenal.")
        covered.update(keys)
        result[key]={"id":key,"source":source,"source_sha256":evidence["sha256"],"first_line":first,
                     "last_line":last,"excerpt":section,"excerpt_sha256":sha256(section.encode()).hexdigest(),
                     "objectives":sorted(keys),"source_ref":text(row["source_ref"],"Rujukan pelajaran")}
    if covered!=objectives.keys():
        raise ContractError("Ada tujuan tanpa pelajaran bersumber.")
    return result


def _practice(raw,objectives):
    tasks={}
    commitments=set()
    used=set()
    supported={"text_fold":str,"int_exact":int,"contains_all":list}
    for row in entries(raw,160,1):
        obj(row,("id","objective","prompt","op","expected","source_ref"))
        key=identifier(row["id"],"Latihan")
        target=identifier(row["objective"],"Tujuan latihan")
        question=text(row["prompt"],"Prompt latihan",900)
        op=row["op"]
        expected=row["expected"]
        stamp=prompt_identity(question)
        if (key in tasks or target not in objectives or stamp in commitments or not isinstance(op,str) or op not in OPS
                or len(canonical(expected))>6000 or op in supported and type(expected) is not supported[op]
                or op=="contains_all" and not expected):
            raise ContractError("Latihan ganda atau tidak dapat diverifikasi.")
        tasks[key]={"id":key,"objective":target,"prompt":question,"prompt_sha256":stamp,"op":op,"expected":expected,
                    "source_ref":text(row["source_ref"],"Rujukan latihan")}
        used.add(target)
        commitments.add(stamp)
    if used!=objectives.keys():
        raise ContractError("Ada tujuan tanpa latihan mekanis.")
    return tasks


def absorb(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.skill-absorb-plan.v1",("id","cluster","version","source_ref","heldout_sha256","sources",
                                                "objectives","lessons","practice"))
    key=identifier(plan["id"],"Skill")
    cluster=identifier(plan["cluster"],"Klaster")
    edition=integer(plan["version"],"Versi skill",1,100_000)
    source=text(plan["source_ref"],"Sumber kurikulum")
    commitment=digest(plan["heldout_sha256"])
    sources=_sources(root,plan["sources"])
    targets=_objectives(plan["objectives"])
    excerpts=_lessons(plan["lessons"],sources,targets)
    practice=_practice(plan["practice"],targets)
    package={"schema":"ace.web.skill-package.v1","id":key,"cluster":cluster,"version":edition,"source_ref":source,
             "plan_sha256":expected,"heldout_sha256":commitment,
             "sources":[sources[name][0] for name in sorted(sources)],
             "objectives":[targets[name] for name in sorted(targets)],
             "lessons":[excerpts[name] for name in sorted(excerpts)],
             "practice":[practice[name] for name in sorted(practice)]}
    report={"schema":"ace.web.skill-absorb-receipt.v1","skill":key,"cluster":cluster,"version":edition,"source_ref":source,
            "package_sha256":identity(package),"heldout_sha256":commitment,
            "sources":len(sources),"objectives":len(targets),"lessons":len(excerpts),"practice":len(practice),
            "status":"curriculum_prepared"}
    return package,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("root","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        package,result=absorb(args.root,decode(read(args.plan)),args.expect_sha256)
        write_new(args.output,{"skill_package.json":canonical(package)+b"\n","absorb_receipt.json":canonical(result)+b"\n"})
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
