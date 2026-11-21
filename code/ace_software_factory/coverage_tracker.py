"""Ukur cakupan line test per modul produk di namespace lokal.

Verifier menelusuri baris Python yang dieksekusi oleh unittest dan
menghitung denominator dari bytecode snapshot yang sama. Modul yang
tidak diimpor tetap muncul. Tes produk dijalankan hanya di Bubblewrap.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._contracts import ContractError, canonical, checked, decode, entries, integer, obj, read, schema, text
from .build_loop import _description, _path, _read_tree, _sandbox_process
from .repo_scaffolder import materialize


DRIVER_PATH="_ace_coverage_driver.py"
PREFIX=b"ACE_FACTORY_COVERAGE "
DRIVER=r'''"""Driver khusus snapshot coverage produk."""
import dis
import json
from pathlib import Path
import sys
import threading
from types import CodeType
import unittest


BASE=Path("/work")
SOURCE=json.loads((BASE/"_ace_coverage_paths.json").read_text())
HITS={str(BASE/path):set() for path in SOURCE}


def executable(path):
    source=Path(path).read_bytes()
    pending=[compile(source,path,"exec",dont_inherit=True, optimize=0)]
    lines=set()
    while pending:
        code=pending.pop()
        for instruction in dis.get_instructions(code):
            line=instruction.positions.lineno
            if instruction.opname!="RESUME" and line is not None and line>0:
                lines.add(line)
        pending.extend(value for value in code.co_consts if isinstance(value,CodeType))
    return lines


def record(frame,event,arg):
    filename=frame.f_code.co_filename
    if filename not in HITS:
        return None
    if event=="line":
        HITS[filename].add(frame.f_lineno)
    return record


def main():
    expected={path:executable(path) for path in HITS}
    threading.settrace(record)
    sys.settrace(record)
    try:
        suite=unittest.defaultTestLoader.discover("tests")
        run=unittest.TextTestRunner(stream=sys.stderr).run(suite)
    finally:
        sys.settrace(None)
        threading.settrace(None)
    rows=[{"path":path,"executable":sorted(expected[str(BASE/path)]),
           "covered":sorted(HITS[str(BASE/path)]&expected[str(BASE/path)])} for path in SOURCE]
    print("ACE_FACTORY_COVERAGE "+json.dumps({"rows":rows,"tests":run.testsRun,"skipped":len(run.skipped),
                                            "valid":run.wasSuccessful()},sort_keys=True,separators=(",",":")))
    return 0 if run.wasSuccessful() and run.testsRun>len(run.skipped) else 1


if __name__=="__main__":
    raise SystemExit(main())
'''


def _scan(raw, payload, names):
    rows=entries(raw["rows"],len(names),minimum=len(names))
    computed=[]
    for path,row in zip(names,rows,strict=True):
        if path!=row["path"]:
            raise ContractError("Urutan coverage berbeda dari snapshot.")
        counts=set(row["executable"])
        covered=set(row["covered"])
        if (covered-counts or len(counts)!=len(row["executable"]) or len(covered)!=len(row["covered"]) or any(
                type(value) is not int or not 1<=value<=50_000 for value in counts)):
            raise ContractError("Nomor baris coverage rusak.")
        computed.append({"path":path,"sha256":sha256(payload[path]).hexdigest(),"executable":len(counts),
                         "covered":len(covered),"ratio_bp":len(covered)*10_000//len(counts) if counts else None,
                         "missing_lines":sorted(counts-covered)})
    return computed


def track(root,plan,expected,*,runner=_sandbox_process):
    checked(plan,expected)
    schema(plan,"ace.factory-coverage-plan.v1",("source_ref","files","modules","timeout_seconds","expected_tests"))
    source=text(plan["source_ref"],"Rujukan suite")
    maximum=integer(plan["timeout_seconds"],"Batas waktu",1,30)
    expected_tests=integer(plan["expected_tests"],"Jumlah tes",1,2000)
    files=_read_tree(root,plan["files"])
    names=sorted(_path(name) for name in entries(plan["modules"],80,minimum=1))
    private_inputs={DRIVER_PATH,"_ace_coverage_paths.json"}
    if private_inputs & files.keys():
        raise ContractError("Nama driver coverage bentrok dengan sumber.")
    if len(set(names))!=len(names) or any(name not in files or not name.endswith(".py") or name.startswith("tests/") for name in names):
        raise ContractError("Daftar modul coverage tidak cocok dengan sumber terdaftar.")
    package={**files,DRIVER_PATH:DRIVER.encode(),"_ace_coverage_paths.json":canonical(names)}
    with TemporaryDirectory(prefix="ace-factory-coverage-") as folder:
        tree=Path(folder)/"product"
        materialize(tree,package)
        code,stdout,stderr,expired=runner(tree,maximum,[DRIVER_PATH])
    report={"schema":"ace.factory-coverage-report.v1","plan_sha256":expected,"source_ref":source,
            "files":_description(files),"modules":[],"test_count":None,"skipped":None,
            "stdout_sha256":sha256(stdout).hexdigest(),"stderr_sha256":sha256(stderr).hexdigest(),"status":"tests_failed"}
    if expired or code is None or stderr.startswith(b"bwrap:"):
        report["status"]="timeout" if expired else "sandbox_unavailable"
        return report
    values=[line[len(PREFIX):] for line in stdout.splitlines() if line.startswith(PREFIX)]
    if len(values)!=1:
        return report
    raw=decode(values[0])
    obj(raw,("rows","tests","skipped","valid"))
    report["test_count"]=integer(raw["tests"],"Tes teramati",0,50_000)
    report["skipped"]=integer(raw["skipped"],"Tes dilewati",0,report["test_count"])
    report["modules"]=_scan(raw,files,names)
    if code==0 and raw["valid"] is True and report["test_count"]==expected_tests and report["skipped"]==0:
        report["status"]="measured"
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        output=track(args.root,decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(output)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(output["status"]!="measured")


if __name__=="__main__":
    raise SystemExit(main())
