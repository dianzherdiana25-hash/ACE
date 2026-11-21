"""Hasilkan acceptance tests dari spesifikasi dan vektor yang ditautkan.

Setiap kasus menunjuk rujukan acceptance yang benar. Tes memanggil
entry point Python dengan argumen dan JSON masukan, lalu memeriksa
exit code serta keluaran terdaftar. Matriks coverage memperlihatkan
acceptance yang belum punya pengujian.
"""
import argparse
from hashlib import sha256
import keyword
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


SCRIPT = r'''"""Acceptance tests generated from declared examples."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


PATH = Path(__file__).with_name("acceptance_cases.json")
SPEC = json.loads(PATH.read_text(encoding="utf-8"))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def run_case(testcase, row):
    source = row["stdin"]
    payload = "" if source is None else _canonical(source)+"\n"
    process = subprocess.run(
        [sys.executable, "-m", SPEC["module"], *row["arguments"]],
        cwd=PATH.parent.parent,
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=SPEC["timeout_seconds"],
    )
    testcase.assertEqual(process.returncode, row["exit_code"], row["acceptance_ref"])
    rule = row["stdout"]
    if rule["format"] == "json":
        actual = json.loads(process.stdout, object_pairs_hook=_unique)
        testcase.assertEqual(_canonical(actual), _canonical(rule["value"]), row["acceptance_ref"])
    else:
        testcase.assertEqual(process.stdout, rule["value"], row["acceptance_ref"])


class ProductAcceptanceTests(unittest.TestCase):
    pass


def named_test(row):
    def verify(self):
        run_case(self, row)
    verify.__name__ = "test_"+row["id"]
    return verify


for fixture in SPEC["cases"]:
    name = "test_"+fixture["id"]
    setattr(ProductAcceptanceTests, name, named_test(fixture))
'''


def _target(value):
    if not isinstance(value,str) or len(value)>200:
        raise ContractError("Entry point pengujian tidak sah.")
    parts = value.split(".")
    if not 1 <= len(parts) <= 6:
        raise ContractError("Kedalaman modul acceptance melampaui batas.")
    for item in parts:
        identifier(item,"Komponen modul")
        if keyword.iskeyword(item):
            raise ContractError("Komponen modul bukan identifier Python.")
    return value


def _criteria(spec):
    schema(spec,"ace.factory-product-spec.v1",("brief_sha256","product_id","name","surface","objective",
                                              "objective_ref","requirements","constraints","non_goals","pending","status"))
    associations = {}
    for row in entries(spec["requirements"], 512, minimum=1):
        obj(row,("id","statement","source_ref","acceptance"))
        key=identifier(row["id"],"ID kebutuhan")
        for item in entries(row["acceptance"], 128):
            obj(item,("statement","source_ref"))
            source=text(item["source_ref"],"Rujukan acceptance",200)
            if source in associations:
                raise ContractError("Rujukan acceptance ganda.")
            associations[source]=key
    return associations


def build(spec, examples, expected):
    checked(examples,expected)
    schema(examples,"ace.factory-acceptance-examples.v1",("spec_sha256","module","timeout_seconds","cases","example_ref"))
    checked(spec,examples["spec_sha256"])
    criteria=_criteria(spec)
    module=_target(examples["module"])
    budget=integer(examples["timeout_seconds"],"Timeout",1,30)
    ids, observed = set(),set()
    records=[]
    for row in entries(examples["cases"],300,minimum=1):
        obj(row,("id","acceptance_ref","arguments","stdin","exit_code","stdout"))
        key=identifier(row["id"],"ID kasus")
        source=text(row["acceptance_ref"],"Rujukan acceptance",200)
        if key in ids or source not in criteria:
            raise ContractError("Kasus ganda atau rujukan di luar spesifikasi.")
        ids.add(key)
        observed.add(source)
        args=[text(item,"Argumen",256) for item in entries(row["arguments"],24)]
        if len(canonical(row["stdin"]))>100_000:
            raise ContractError("JSON masukan kasus terlalu besar.")
        code=integer(row["exit_code"],"Exit code",0,255)
        rule=obj(row["stdout"],("format","value"))
        if rule["format"] not in ("json","text") or (rule["format"] == "text" and not isinstance(rule["value"],str)):
            raise ContractError("Perbandingan stdout belum didukung.")
        if len(canonical(rule["value"]))>100_000:
            raise ContractError("JSON keluaran kasus terlalu besar.")
        records.append({"id":key,"acceptance_ref":source,"arguments":args,"stdin":row["stdin"],"exit_code":code,"stdout":rule})
    payload=canonical({"module":module,"cases":sorted(records,key=lambda row:row["id"]),"timeout_seconds":budget})+b"\n"
    missing=sorted(criteria.keys()-observed)
    result={"schema":"ace.factory-acceptance-suite.v1","status":"partial" if missing or spec["status"]!="ready" else "ready",
            "spec_sha256":examples["spec_sha256"],"examples_sha256":expected,
            "example_ref":text(examples["example_ref"],"Rujukan contoh",200),
            "missing_acceptance":missing,"cases":len(records),
            "trace":[{"case":row["id"],"requirement":criteria[row["acceptance_ref"]],"acceptance_ref":row["acceptance_ref"]} for row in records],
            "suite_sha256":sha256(SCRIPT.encode()).hexdigest(),"fixtures_sha256":sha256(payload).hexdigest()}
    return {"tests/test_product_acceptance.py":SCRIPT.encode(),"tests/acceptance_cases.json":payload},result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("spec","examples","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        entries_,report=build(decode(read(args.spec)),decode(read(args.examples)),args.expect_sha256)
        materialize(args.output,entries_)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,OverflowError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="ready")


if __name__=="__main__":
    raise SystemExit(main())
