"""Jalankan build-uji-perbaiki pada salinan dengan sandbox lokal.

Budget dan snapshot awal dibekukan dalam rencana. Perbaikan
terdaftar hanya berlaku terhadap hash pohon dan byte lama yang
cocok. Tiap ronde memakai direktori baru. Linux bubblewrap
membatasi jaringan dan penulisan tes sebelum source dieksekusi.
"""
import argparse
from hashlib import sha256
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identity, integer, obj, read, schema, text
from .repo_scaffolder import _relative, materialize


MAX_FILES = 192
MAX_ARTIFACT = 2_000_000
MAX_TREE = 12_000_000
MAX_TRANSCRIPT = 524_288
TESTS = re.compile(rb"^Ran ([0-9]{1,8}) tests?\b", re.MULTILINE)


def _path(value):
    if not isinstance(value,str) or not value.isprintable() or len(value)>500:
        raise ContractError("Path build tidak sah.")
    parts=_relative(value)
    if any(part.startswith(".") for part in parts) or any(
            re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,120}",part) is None for part in parts):
        raise ContractError("Path build menyentuh metadata atau nama terlarang.")
    return value


def _description(files):
    return [{"path":path,"sha256":sha256(payload).hexdigest(),"bytes":len(payload)}
            for path,payload in sorted(files.items())]


def _read_tree(root, roster):
    files={}
    total=0
    for row in entries(roster,MAX_FILES,minimum=1):
        obj(row,("path","bytes","sha256"))
        name=_path(row["path"])
        if name in files:
            raise ContractError("Path build ganda.")
        size=integer(row["bytes"],"Byte artefak",0,MAX_ARTIFACT)
        total+=size
        if total>MAX_TREE:
            raise ContractError("Pohon awal melampaui batas byte.")
        payload=read_relative(root,name,size,digest(row["sha256"]))
        if len(payload)!=size:
            raise ContractError("Ukuran artefak berbeda dari rencana.")
        files[name]=payload
    if not any(path.startswith("tests/test_") and path.endswith(".py") for path in files):
        raise ContractError("Pohon build perlu setidaknya satu file verifier.")
    return files


def _repair_rules(source, permitted, files):
    if not isinstance(permitted,list) or len(permitted)>MAX_FILES:
        raise ContractError("Daftar path perbaikan tidak sah.")
    editable={_path(path) for path in permitted}
    if len(editable)!=len(permitted) or editable-files.keys() or any(path.startswith("tests/") for path in editable):
        raise ContractError("Path perbaikan di luar pohon sumber yang diizinkan.")
    plans={}
    for patch in entries(source,24):
        obj(patch,("based_on_tree","ref","patch"))
        anchor=digest(patch["based_on_tree"])
        if anchor in plans:
            raise ContractError("Dua perbaikan menunjuk ronde yang sama.")
        ref=text(patch["ref"],"Rujukan perubahan",200)
        rows={}
        for item in entries(patch["patch"],MAX_FILES,minimum=1):
            obj(item,("path","before_sha256","replacement"))
            name=_path(item["path"])
            if name not in editable or name in rows:
                raise ContractError("Edit ganda atau menyentuh path di luar daftar.")
            code=item["replacement"]
            if not isinstance(code,str) or len(code.encode())>MAX_ARTIFACT or "\0" in code:
                raise ContractError("Konten perbaikan tidak sah.")
            rows[name]=(digest(item["before_sha256"]),code.encode("utf-8"))
        plans[anchor]=(ref,rows)
    return plans


def _apply(files, repairs):
    patch_ref, changes=repairs
    fixed=dict(files)
    edited=[]
    for name,(anchor,payload) in sorted(changes.items()):
        if sha256(files[name]).hexdigest()!=anchor:
            raise ContractError("Anchor byte perbaikan tidak cocok.")
        if payload==files[name]:
            raise ContractError("Perbaikan tidak mengubah artefak.")
        fixed[name]=payload
        edited.append({"path":name,"before_sha256":anchor,"after_sha256":sha256(payload).hexdigest()})
    if sum(map(len,fixed.values()))>MAX_TREE:
        raise ContractError("Pohon setelah perbaikan melampaui batas byte.")
    return fixed,{"source_ref":patch_ref,"changes":edited}


def _runner(directory, timeout):
    bubblewrap=shutil.which("bwrap")
    if bubblewrap is None or not all(Path(name).is_file() for name in ("/usr/bin/python3","/usr/bin/prlimit")):
        return {"status":"sandbox_unavailable","tests":None,"exit_code":None,
                "stdout_sha256":None,"stderr_sha256":None}

    command=[bubblewrap,"--unshare-all","--die-with-parent","--cap-drop","ALL","--clearenv",
             "--ro-bind","/usr","/usr","--symlink","usr/lib","/lib","--symlink","usr/lib64","/lib64",
             "--dev","/dev","--proc","/proc","--tmpfs","/tmp","--ro-bind",str(directory),"/work","--chdir","/work",
             "--setenv","PATH","/usr/bin","--setenv","PYTHONDONTWRITEBYTECODE","1","--setenv","LANG","C.UTF-8",
             "--","/usr/bin/prlimit","--as=536870912","--cpu="+str(timeout),"--fsize="+str(MAX_TRANSCRIPT),
             "--","/usr/bin/python3","-m","unittest","discover","-s","tests","-v"]
    code=None
    expired=False
    with TemporaryDirectory(prefix="ace-factory-test-log-") as folder:
        files=[Path(folder)/name for name in ("stdout","stderr")]
        with files[0].open("wb") as stdout, files[1].open("wb") as stderr:
            try:
                completed=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                                         check=False,timeout=timeout)
                code=completed.returncode
            except subprocess.TimeoutExpired:
                expired=True
            except OSError:
                return {"status":"sandbox_unavailable","tests":None,"exit_code":None,
                        "stdout_sha256":None,"stderr_sha256":None}
        stdout,stderr=(read(path,MAX_TRANSCRIPT) for path in files)
    parsed=TESTS.findall(stderr)
    count=int(parsed[-1]) if parsed else None
    if expired:
        status="timeout"
    elif code==0 and count:
        status="passed"
    elif code==0:
        status="no_tests"
    elif stderr.startswith(b"bwrap:") and count is None:
        status="sandbox_unavailable"
    else:
        status="failed"
    return {"status":status,"tests":count,"exit_code":code,"stdout_sha256":sha256(stdout).hexdigest(),
            "stderr_sha256":sha256(stderr).hexdigest()}


def run(root, plan, expected):
    checked(plan,expected)
    schema(plan,"ace.factory-build-loop.v1",("source_ref","maximum_attempts","timeout_seconds","files","editable","repairs"))
    pointer=text(plan["source_ref"],"Rujukan build",200)
    maximum=integer(plan["maximum_attempts"],"Percobaan maksimum",1,10)
    timeout=integer(plan["timeout_seconds"],"Timeout",1,60)
    files=_read_tree(root,plan["files"])
    rules=_repair_rules(plan["repairs"],plan["editable"],files)
    result=[]
    tried=set()
    last=None
    success=False
    for i in range(1,maximum+1):
        head=identity(_description(files))
        if head in tried:
            break
        tried.add(head)
        with TemporaryDirectory(prefix="ace-factory-build-") as folder:
            trial=Path(folder)/"trial"
            materialize(trial,files)
            audit=_runner(trial,timeout)
        step={"attempt":i,"tree_sha256":head,"inputs":_description(files),"test":audit,"repair":None}
        result.append(step)
        last=audit["status"]
        if last=="passed":
            success=True
            break
        if last!="failed" or i==maximum or head not in rules:
            break
        files,step["repair"]=_apply(files,rules[head])
    published=files if success else None
    return published,{"schema":"ace.factory-build-loop-report.v1","plan_sha256":expected,"source_ref":pointer,
                      "status":"verified" if success else "held","reason":None if success else last,
                      "output_tree_sha256":identity(_description(files)) if success else None,"attempts":result}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        products,report=run(args.root,decode(read(args.plan)),args.expect_sha256)
        if products is not None and args.output is not None:
            materialize(args.output,products)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,OverflowError,RecursionError,ValueError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="verified")


if __name__=="__main__":
    raise SystemExit(main())
