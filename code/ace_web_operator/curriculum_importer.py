"""Impor dokumen kurikulum berlisensi dari commit lokal yang dipatok.

Git dibaca sebagai objek, tanpa checkout ulang atau eksekusi source.
Lisensi dan setiap blob dicocokkan dengan SHA-256 dari rencana.
Hasilnya berupa snapshot lokal siap dibaca skill absorber.
"""
import argparse
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import sys

from ._artifact import write_new
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,relative_path,schema,text
from .skill_absorber import LICENSES,SOURCE_LIMIT


COMMIT=re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
SPDX=re.compile(r"(?m)^(?:[ #*;]+)?SPDX-License-Identifier:\s*([^\r\n]+)$")


def _git(repo,*arguments):
    config={"PATH":os.defpath,"GIT_CONFIG_NOSYSTEM":"1","GIT_TERMINAL_PROMPT":"0","GIT_NO_LAZY_FETCH":"1"}
    command=["git","-C",os.fspath(repo),"-c","core.hooksPath=/dev/null",*arguments]
    result=subprocess.run(command,capture_output=True,stdin=subprocess.DEVNULL,env=config,timeout=10,check=False)
    if result.returncode!=0 or len(result.stdout)>SOURCE_LIMIT+1024:
        raise ContractError("Objek Git lokal tidak tersedia atau melampaui anggaran.")
    return result.stdout


def _blob(repo,commit,path,limit,expected):
    listing=_git(repo,"--literal-pathspecs","ls-tree","-z",commit,"--",path)
    header,tab,remainder=listing.partition(b"\t")
    values=header.split()
    if not tab or len(values)!=3 or values[:2]!=[b"100644",b"blob"] or remainder!=path.encode()+b"\0":
        raise ContractError("Path kurikulum bukan blob reguler atau tidak ada.")
    object_id=values[2].decode("ascii")
    size=int(_git(repo,"cat-file","-s",object_id))
    if size<1 or size>limit:
        raise ContractError("Blob kurikulum di luar anggaran.")
    payload=_git(repo,"cat-file","blob",object_id)
    if len(payload)!=size or sha256(payload).hexdigest()!=expected:
        raise ContractError("Hash blob tidak cocok dengan rencana.")
    return payload,object_id


def import_sources(repo,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.curriculum-import-plan.v1",("source_ref","repository_ref","commit","license","files"))
    pointer=text(plan["source_ref"],"Sumber impor")
    repository=text(plan["repository_ref"],"Rujukan repo sumber",240)
    commit=plan["commit"]
    if not isinstance(commit,str) or not COMMIT.fullmatch(commit) or _git(repo,"cat-file","-t",commit)!=b"commit\n":
        raise ContractError("Sumber perlu commit Git lokal lengkap.")
    raw=obj(plan["license"],("id","path","sha256","source_ref"))
    license_name=raw["id"]
    if not isinstance(license_name,str) or license_name not in LICENSES:
        raise ContractError("Lisensi tidak termasuk scope yang diterima.")
    license_path=relative_path(raw["path"])
    license_ref=text(raw["source_ref"],"Rujukan lisensi")
    license_hash=digest(raw["sha256"])
    license_data,license_blob=_blob(repo,commit,license_path,160_000,license_hash)
    lines={token.strip() for token in SPDX.findall(license_data.decode("utf-8"))}
    if lines!={license_name}:
        raise ContractError("Deklarasi SPDX lisensi tidak cocok dengan rencana.")
    report=[]
    sources={}
    visited=set()
    aggregate=len(license_data)
    for row in entries(plan["files"],40,1):
        obj(row,("id","path","sha256","source_ref"))
        key=identifier(row["id"],"ID sumber belajar")
        path=relative_path(row["path"])
        extension=Path(path).suffix.lower()
        if key in sources or path in visited or path==license_path or extension not in (".txt",".md",".rst"):
            raise ContractError("Sumber ganda atau bukan file dokumentasi.")
        visited.add(path)
        anchor=digest(row["sha256"])
        payload,object_id=_blob(repo,commit,path,min(SOURCE_LIMIT,2_000_000-aggregate),anchor)
        aggregate+=len(payload)
        valid=payload.decode("utf-8")
        if (not valid.strip() or any(not (char.isprintable() or char in "\r\n\t") for char in valid)
                or {token.strip() for token in SPDX.findall(valid)}-{license_name}):
            raise ContractError("Isi sumber kosong, rusak atau memakai lisensi berbeda.")
        target=f"sources/{key}{extension}"
        sources[key]=(target,payload)
        report.append({"id":key,"path":target,"sha256":anchor,"license":license_name,
                       "license_ref":license_ref,"source_ref":text(row["source_ref"],"Rujukan sumber"),
                       "git_path":path,"git_blob":object_id})
    proof={"schema":"ace.web.curriculum-import-receipt.v1","plan_sha256":expected,"source_ref":pointer,
           "repository_ref":repository,"git_commit":commit,"license":{"id":license_name,"sha256":license_hash,
           "git_path":license_path,"git_blob":license_blob,"source_ref":license_ref},
           "sources":sorted(report,key=lambda row:row["id"]),"status":"imported_snapshot"}
    files={path:payload for path,payload in sources.values()}
    files["license_proof.txt"]=license_data
    files["curriculum_import_receipt.json"]=canonical(proof)+b"\n"
    return files,proof


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("repo","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=import_sources(args.repo,decode(read(args.plan)),args.expect_sha256)
        write_new(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError,subprocess.SubprocessError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
