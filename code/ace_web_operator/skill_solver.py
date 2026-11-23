"""Jalankan solver atas paket dan prompt kasus held-out, tulis jawaban tertambat.

Runner adalah produsen jawaban dalam rantai Gelombang 3. Ia membaca
paket dan suite yang sudah dibekukan, tetapi solver (LLM di balik
bridge lokal) hanya menerima materi paket dan prompt kasus — tidak
pernah patokan, skor, atau isi suite lain. Jawaban di-hash pada
receipt sebelum verifikasi apa pun dijalankan, dan evaluator_ref
wajib berbeda dari solver_ref. Bridge yang tidak menjawab
menghasilkan receipt gagal yang tercatat, bukan jawaban karangan.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from urllib.request import Request,urlopen

from ._artifact import read_relative,write_new
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identity,integer,obj,origin,read,schema,text
from .web_scheduler import iso


ROLES={"front","coder","validator","judge"}
MAX_PROMPT_CHARS=120_000
PACKAGE_FIELDS=("id","cluster","version","source_ref","plan_sha256","heldout_sha256",
                "sources","objectives","lessons","practice")
SUITE_FIELDS=("skill","scope","source_ref","evaluator_ref","min_cases_per_objective","target_bp","cases")


class SolverUnavailable(RuntimeError):
    """Bridge lokal tidak menjawab atau menjawab di luar kontrak."""

    def __init__(self,reason):
        super().__init__(reason)
        self.reason=reason


class _BadOutput(Exception):
    """Keluaran solver tidak dapat dibaca sebagai peta jawaban."""


def _bridge_transport(origin_value,role,prompt,max_tokens):
    try:
        with urlopen(origin_value+"/health",timeout=5) as response:
            if response.status!=200:
                raise SolverUnavailable("bridge_unreachable")
    except SolverUnavailable:
        raise
    except Exception as error:
        raise SolverUnavailable("bridge_unreachable") from error
    payload=json.dumps({"role":role,"messages":[{"role":"user","content":prompt}],
                        "max_tokens":max_tokens}).encode("utf-8")
    request=Request(origin_value+"/v1/chat/completions",data=payload,
                    headers={"Content-Type":"application/json"})
    try:
        with urlopen(request,timeout=300) as response:
            body=json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise SolverUnavailable("bridge_unreachable") from error
    try:
        content=body["choices"][0]["message"]["content"]
    except (KeyError,IndexError,TypeError) as error:
        raise SolverUnavailable("bridge_bad_response") from error
    if not isinstance(content,str) or not content.strip():
        raise SolverUnavailable("bridge_bad_response")
    return content


def _prompt(package,suite):
    lines=["Kamu adalah solver ujian keterampilan. Materi belajar dan latihan contoh ada di bawah.",
           "Sesudah materi ada daftar soal ujian. Jawab HANYA dengan satu objek JSON yang memetakan id soal ke jawaban.",
           "Format nilai mengikuti kolom op: int_exact = bilangan bulat JSON; contains_all = array string JSON; text_fold dan equals = string JSON.",
           "Jangan menulis penjelasan apa pun di luar objek JSON itu.",
           "","== TUJUAN =="]
    for row in package["objectives"]:
        lines.append(f"- {row['id']}: {row['statement']}")
    lines.append("== PELAJARAN ==")
    for row in package["lessons"]:
        lines.append(f"[{row['id']}] {row['excerpt']}")
    lines.append("== LATIHAN CONTOH (dengan jawaban) ==")
    for row in package["practice"]:
        lines.append(json.dumps({"id":row["id"],"prompt":row["prompt"],"op":row["op"],
                                 "jawaban":row["expected"]},ensure_ascii=False))
    lines.append("== SOAL UJIAN (tanpa jawaban) ==")
    for row in suite["cases"]:
        lines.append(json.dumps({"id":row["id"],"prompt":row["prompt"],"op":row["op"]},ensure_ascii=False))
    prompt="\n".join(lines)
    if len(prompt)>MAX_PROMPT_CHARS:
        raise ContractError("Prompt solver melampaui batas.")
    return prompt


def _parse_answers(content,cases,solver):
    start=content.find("{")
    end=content.rfind("}")
    if start<0 or end<=start:
        raise _BadOutput("tidak ada objek JSON")
    try:
        parsed=json.loads(content[start:end+1])
    except ValueError as error:
        raise _BadOutput("JSON tidak sah") from error
    if not isinstance(parsed,dict):
        raise _BadOutput("bukan objek JSON")
    known={row["id"] for row in cases}
    rows=[]
    for key in sorted(parsed):
        if key not in known or len(canonical(parsed[key]))>8000:
            raise _BadOutput("id jawaban tak dikenal atau nilai terlalu panjang")
        rows.append({"id":key,"value":parsed[key],"source_ref":f"{solver}/{key}"})
    return rows


def _load(root,ref):
    obj(ref,("path","sha256"))
    return decode(read_relative(root,ref["path"],2_000_000,digest(ref["sha256"])))


def solve(root,plan,expected,transport=None,now=None):
    checked(plan,expected)
    schema(plan,"ace.web.skill-solve-plan.v1",("source_ref","solver_ref","bridge","role","max_tokens","package","suite"))
    source=text(plan["source_ref"],"Sumber solve")
    solver=text(plan["solver_ref"],"Rujukan solver")
    bridge,_port=origin(plan["bridge"])
    if plan["role"] not in ROLES:
        raise ContractError("Peran bridge tidak dikenal.")
    budget=integer(plan["max_tokens"],"Batas token",128,16_000)
    package=_load(root,plan["package"])
    suite=_load(root,plan["suite"])
    schema(package,"ace.web.skill-package.v1",PACKAGE_FIELDS)
    schema(suite,"ace.web.heldout-suite.v1",SUITE_FIELDS)
    package_anchor=identity(package)
    suite_anchor=identity(suite)
    if package["heldout_sha256"]!=suite_anchor or suite["skill"]!=package["id"]:
        raise ContractError("Suite dan paket tidak tertambat pada skill yang sama.")
    evaluator=text(suite["evaluator_ref"],"Evaluator independen")
    if evaluator==solver:
        raise ContractError("Evaluator perlu rujukan berbeda dari solver.")
    cases=entries(suite["cases"],250,1)
    for row in cases:
        obj(row,("id","objective","prompt","op","expected","source_ref"))
    at=iso(now if now is not None else time.time())
    base={"schema":"ace.web.skill-solve-receipt.v1","skill":package["id"],"cluster":package["cluster"],
          "version":package["version"],"package_sha256":package_anchor,"suite_sha256":suite_anchor,
          "scope":suite["scope"],"solver_ref":solver,"evaluator_ref":evaluator,"bridge":bridge,
          "role":plan["role"],"at":at,"cases_asked":len(cases)}
    run=transport if transport is not None else _bridge_transport
    try:
        content=run(bridge,plan["role"],_prompt(package,suite),budget)
    except SolverUnavailable as error:
        return None,{**base,"status":"failed","reason":error.reason,"answers_sha256":None,"cases_answered":0}
    try:
        rows=_parse_answers(content,cases,solver)
    except _BadOutput:
        return None,{**base,"status":"failed","reason":"bad_solver_output","answers_sha256":None,"cases_answered":0}
    answers={"schema":"ace.web.heldout-answers.v1","package_sha256":package_anchor,"suite_sha256":suite_anchor,
             "source_ref":source,"solver_ref":solver,"at":at,"answers":rows}
    receipt={**base,"status":"completed","reason":None,"answers_sha256":identity(answers),
             "cases_answered":len(rows)}
    return answers,receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("root","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        answers,receipt=solve(args.root,decode(read(args.plan)),args.expect_sha256)
        files={"solve_receipt.json":canonical(receipt)+b"\n"}
        if answers is not None:
            files["heldout_answers.json"]=canonical(answers)+b"\n"
        write_new(args.output,files)
        sys.stdout.buffer.write(canonical(receipt)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0 if receipt["status"]=="completed" else 1


if __name__=="__main__":
    raise SystemExit(main())
