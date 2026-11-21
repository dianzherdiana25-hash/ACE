"""Ukur tugas web pada situs tertutup dan segel bukti per kasus.

Server fixture hanya melayani GET dan mencatat percobaan mutasi.
Setiap tugas memiliki manifest untuk workflow, hasil, dan snapshot
halaman. Kriteria tuntas serta cakupan bukti dinilai terpisah.
"""
import argparse
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import sys
from threading import Thread

from . import workflow_runner
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text,web_path


MUTATING=("POST","PUT","PATCH","DELETE")
MONEY={"order","checkout","purchase","pay","payment"}


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def _answer(self,code,mime,payload):
        self.send_response(code)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        page=self.server.pages.get(self.path)
        self.server.requests.append((self.command,self.path))
        if page is None:
            self._answer(404,"text/plain",b"Fixture path not found.")
        else:
            self._answer(200,page[0],page[1])

    def _reject(self):
        self.server.requests.append((self.command,self.path))
        self._answer(405,"text/plain",b"Read only.")

    do_POST=_reject
    do_PUT=_reject
    do_PATCH=_reject
    do_DELETE=_reject


def _fixture(layout):
    pages={}
    for row in entries(layout,80,1):
        obj(row,("path","media_type","body","source_ref"))
        path=web_path(row["path"])
        mime=row["media_type"]
        payload=row["body"]
        if (path in pages or mime not in ("text/html","text/css","text/javascript","application/json","text/plain")
                or not isinstance(payload,str) or len(payload.encode())>140_000
                or MONEY & set(path.casefold().split("/"))):
            raise ContractError("Halaman fixture ganda, media salah, atau rute transaksi.")
        pages[path]=(mime,payload.encode(),text(row["source_ref"],"Rujukan halaman"))
    if sum(len(body) for _,body,_ in pages.values())>2_000_000:
        raise ContractError("Situs fixture melebihi budget.")
    return pages


def _case_plan(case,base,allowed):
    obj(case,("id","source_ref","timeout_ms","request_limit","allow_paths","stages"))
    paths=[web_path(value) for value in entries(case["allow_paths"],70,1)]
    if set(paths)-allowed:
        raise ContractError("Tugas merujuk rute tanpa snapshot fixture.")
    return {"schema":"ace.web.workflow-plan.v1","source_ref":text(case["source_ref"],"Sumber tugas"),
            "browser":{"origin":base,"allow_paths":paths,"timeout_ms":case["timeout_ms"],
                       "request_limit":case["request_limit"]},"stages":case["stages"]}


def write_case(key,job,observed,requests,pages):
    directory=f"evidence/{key}"
    files={f"{directory}/workflow.json":canonical(job)+b"\n",
           f"{directory}/receipt.json":canonical(observed)+b"\n",
           f"{directory}/http.json":canonical([{"method":method,"path":path} for method,path in requests])+b"\n"}
    links=[]
    for path in sorted({path for _,path in requests if path in pages}):
        mime,data,source=pages[path]
        marker=sha256(data).hexdigest()
        name=f"{directory}/snapshots/{marker}"
        files[name]=data
        links.append({"path":path,"media_type":mime,"source_ref":source,"file":name,"sha256":marker})
    record={"schema":"ace.web.bench-evidence.v1","task_id":key,"workflow_sha256":identity(job),
            "receipt_sha256":identity(observed),"snapshots":links,
            "files":[{"path":name,"sha256":sha256(content).hexdigest(),"bytes":len(content)}
                     for name,content in sorted(files.items())]}
    manifest_path=f"{directory}/manifest.json"
    files[manifest_path]=canonical(record)+b"\n"
    manifest_sha=sha256(files[manifest_path]).hexdigest()
    verify_case(files,manifest_path,manifest_sha)
    return files,{"manifest":manifest_path,"manifest_sha256":manifest_sha,"snapshots":len(links)}


def verify_case(files,manifest_path,expected):
    if manifest_path not in files or sha256(files[manifest_path]).hexdigest()!=digest(expected):
        raise ContractError("Manifest bench tidak cocok.")
    manifest=decode(files[manifest_path])
    schema(manifest,"ace.web.bench-evidence.v1",("task_id","workflow_sha256","receipt_sha256","snapshots","files"))
    key=identifier(manifest["task_id"],"ID bench")
    directory=f"evidence/{key}/"
    declared=set()
    for item in entries(manifest["files"],85,3):
        obj(item,("path","sha256","bytes"))
        name=item["path"]
        if not isinstance(name,str) or not name.startswith(directory) or name in declared or name not in files:
            raise ContractError("Ruang file bukti tidak cocok.")
        declared.add(name)
        found=files[name]
        if len(found)!=item["bytes"] or sha256(found).hexdigest()!=item["sha256"]:
            raise ContractError("Objek bench tidak utuh.")
    for short,anchor in (("workflow.json","workflow_sha256"),("receipt.json","receipt_sha256")):
        name=directory+short
        if name not in declared or identity(decode(files[name]))!=manifest[anchor]:
            raise ContractError("Rencana atau receipt bench berubah.")
    for item in entries(manifest["snapshots"],80):
        obj(item,("path","media_type","source_ref","file","sha256"))
        if item["file"] not in declared or sha256(files[item["file"]]).hexdigest()!=item["sha256"]:
            raise ContractError("Snapshot tidak tertambat.")
    return manifest


def run(plan,expected,*,runner=workflow_runner.execute):
    checked(plan,expected)
    schema(plan,"ace.web.operator-bench-plan.v1",("source_ref","pages","cases","target_bp"))
    source=text(plan["source_ref"],"Sumber bench")
    threshold=integer(plan["target_bp"],"Ambang bench",0,10_000)
    pages=_fixture(plan["pages"])
    cases=entries(plan["cases"],30,1)
    files={}
    observations=[]
    with ThreadingHTTPServer(("127.0.0.1",0),FixtureHandler) as server:
        server.pages=pages
        server.requests=[]
        origin=f"http://127.0.0.1:{server.server_port}"
        planned={}
        for case in cases:
            key=identifier(case["id"],"ID kasus")
            if key in planned:
                raise ContractError("ID kasus ganda.")
            job=_case_plan(case,origin,set(pages))
            workflow_runner.compile_workflow(job,identity(job))
            planned[key]=job
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            for key,job in sorted(planned.items()):
                first=len(server.requests)
                anchor=identity(job)
                observed=runner(job,anchor)
                if observed.get("workflow_sha256")!=anchor:
                    raise ContractError("Receipt task tidak cocok.")
                receipts=server.requests[first:]
                proof,links=write_case(key,job,observed,receipts,pages)
                files.update(proof)
                plan_ok=observed["status"]=="completed" and links["snapshots"]>0
                mutations=sum(method in MUTATING or bool(MONEY & set(path.casefold().split("/"))) for method,path in receipts)
                observations.append({"id":key,"source_ref":job["source_ref"],"completed":plan_ok and not mutations,
                                     "runtime_status":observed["status"],"reason":observed["reason"],
                                     "mutating_requests":mutations,**links})
        finally:
            server.shutdown()
            thread.join(3)
    successes=sum(row["completed"] for row in observations)
    total=len(observations)
    violations=sum(row["mutating_requests"] for row in observations)
    rate=successes*10_000//total
    coverage=sum(row["snapshots"]>0 for row in observations)
    result={"schema":"ace.web.operator-bench-report.v1","plan_sha256":expected,"source_ref":source,"scope":"closed_loopback_fixture",
            "tasks":total,"completed":successes,"completion_bp":rate,"target_bp":threshold,"with_snapshot_proof":coverage,
            "mutating_requests_observed":violations,"cases":observations,
            "status":"passed" if rate>=threshold and coverage==total and not violations else "failed"}
    files["operator_bench_report.json"]=canonical(result)+b"\n"
    return files,result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        files,result=run(decode(read(args.plan)),args.expect_sha256)
        if args.output:
            args.output.mkdir(mode=0o700)
            for name,payload in sorted(files.items()):
                path=args.output/name
                path.parent.mkdir(parents=True,exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(payload)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="passed")


if __name__=="__main__":
    raise SystemExit(main())
