"""Ukur tiga bentuk produk dari brief, arsitektur, build dan verifier tetap.

Setiap produk dibuat pada direktori baru. Web berjalan di loopback,
CLI menerima JSON di stdin, dan worker SQLite dijalankan dari proses
terpisah. Bukti mencatat observasi nyata, SHA-256 produk dan verdict
per kriteria agar hasil dapat diperiksa ulang tanpa layanan.
"""
import argparse
from contextlib import closing
from html.parser import HTMLParser
from http.client import HTTPConnection
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread

from . import (acceptance_judge, api_builder, architecture_designer, cli_builder, repo_scaffolder,
               service_builder, spec_writer, test_factory, ui_builder)
from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, obj, read, schema, text
from .build_loop import _description


SURFACES = {"web", "cli", "service"}


class FormProbe(HTMLParser):
    def __init__(self, payload):
        super().__init__()
        self.forms = []
        self.feed(payload.decode("utf-8"))

    def handle_starttag(self, name, attrs):
        if name == "form":
            properties = dict(attrs)
            if "data-endpoint" in properties:
                self.forms.append(properties["data-endpoint"])


def _assemble(spec, recipe, decisions):
    architecture = architecture_designer.design(spec, {**decisions, "spec_sha256": identity(spec)})
    files, _ = repo_scaffolder.build(spec, architecture, identity(architecture))
    files["build/spec.json"] = canonical(spec) + b"\n"
    files["build/architecture.json"] = canonical(architecture) + b"\n"
    surface = spec["surface"]
    if surface == "web":
        obj(recipe, ("model", "api", "ui"))
        relational = recipe["model"]
        api_plan = {**recipe["api"], "model_sha256": identity(relational)}
        html_files, _ = ui_builder.build(recipe["ui"], identity(recipe["ui"]))
        api_files, _ = api_builder.build(relational, api_plan, identity(api_plan))
        files.update({**html_files, **api_files})
    elif surface == "service":
        if recipe.get("id") != spec["product_id"]:
            raise ContractError("Worker dan spesifikasi harus menunjuk produk yang sama.")
        service, _ = service_builder.build(recipe, identity(recipe))
        files.update(service)
    else:
        obj(recipe, ("plan", "examples"))
        if recipe["plan"].get("id") != spec["product_id"]:
            raise ContractError("CLI dan spesifikasi harus menunjuk produk yang sama.")
        products, _ = cli_builder.build(recipe["plan"], identity(recipe["plan"]))
        examples = {**recipe["examples"], "spec_sha256": identity(spec), "module": spec["product_id"]}
        tests, test_report = test_factory.build(spec, examples, identity(examples))
        if test_report["status"] != "ready":
            raise ContractError("Contoh CLI belum mencakup semua acceptance.")
        files.update({**products, **tests})
    return files


def _request(port, method, address, data=None):
    with closing(HTTPConnection("127.0.0.1", port, timeout=4)) as client:
        headers = {"Content-Type": "application/json"} if data is not None else {}
        body = canonical(data) if data is not None else None
        client.request(method, address, body=body, headers=headers)
        response = client.getresponse()
        result = response.read(1_000_001)
        if len(result) > 1_000_000:
            raise ContractError("Respons fixture HTTP terlalu besar.")
        return response.status, result, response.getheader("Content-Security-Policy")


def _web(directory, product, probe):
    obj(probe, ("resource", "field", "value"))
    route = "/" + identifier(probe["resource"], "Rute fixture")
    field = identifier(probe["field"], "Kolom fixture")
    label = text(probe["value"], "Nilai fixture", 180)
    spec = spec_from_file_location("factory_web_bench_backend", directory / "backend.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    with module.server(directory / "data.sqlite", home_page=(directory / "index.html").read_bytes()) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            port = server.server_port
            page_status, page, csp = _request(port, "GET", "/")
            observed_forms = FormProbe(page).forms
            target = observed_forms[0] if observed_forms == [route] else None
            if target is None:
                roundtrip = None
            else:
                create_status, created, _ = _request(port, "POST", target, {field: label})
                fetch_status, output, _ = _request(port, "GET", target + "/1")
                roundtrip = {"created_status": create_status, "fetch_status": fetch_status,
                             "created": decode(created), "fetched": decode(output)}
            invalid_status, _ignored, _ = _request(port, "POST", route, {field: False})
        finally:
            server.shutdown()
            worker.join(4)
    return {"screen": {"status": page_status, "forms": observed_forms, "limits_connect": bool(csp and "connect-src 'self'" in csp)},
            "roundtrip": roundtrip, "invalid_status": invalid_status}


def _process(directory, argv, data=b""):
    return subprocess.run([sys.executable, "-B", *argv], cwd=directory,
                          env={"PATH": "/usr/bin:/bin", "PYTHONUTF8": "1"}, input=data,
                          capture_output=True, timeout=8, check=False)


def _cli(directory, product, probe):
    obj(probe, ("operation", "data", "invalid"))
    operation = identifier(probe["operation"], "Operasi fixture")
    command = ["-m", product, operation]
    valid = _process(directory, command, canonical(probe["data"]))
    invalid = _process(directory, command, canonical(probe["invalid"]))
    unit = _process(directory, ["-m", "unittest", "discover", "-s", "tests", "-q"])
    return {"result": {"status": valid.returncode, "output": decode(valid.stdout) if valid.stdout else None},
            "invalid_status": invalid.returncode, "generated_suite": unit.returncode}


def _service(directory, product, probe):
    obj(probe, ("route", "jobs"))
    route = identifier(probe["route"], "Rute worker fixture")
    jobs = entries(probe["jobs"], 10, minimum=2)
    command = ["-m", product, "--db", "queue.sqlite"]
    init = _process(directory, [*command, "init"])
    if init.returncode != 0:
        return {"init_status": init.returncode}
    ids = []
    prepared = []
    for job in jobs:
        obj(job, ("id", "payload"))
        key = identifier(job["id"], "Pekerjaan fixture")
        ids.append(key)
        result = _process(directory, [*command, "enqueue", key, route], canonical(job["payload"]))
        prepared.append(result.returncode)
    consumed = _process(directory, [*command, "consume"])
    inspected = _process(directory, [*command, "inspect", ids[-1]])
    return {"prepared": prepared,
            "consumed": {"status": consumed.returncode, "output": decode(consumed.stdout) if consumed.stdout else None},
            "inspected": {"status": inspected.returncode, "output": decode(inspected.stdout) if inspected.stdout else None}}


PROBES = {"web": _web, "cli": _cli, "service": _service}


def run(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-bench-plan.v1", ("source_ref", "products"))
    source = text(plan["source_ref"], "Sumber bench", 250)
    items = entries(plan["products"], 3, minimum=3)
    outcomes, evidence = {}, {}
    seen = set()
    for row in items:
        obj(row, ("brief", "architecture", "recipe", "probe", "rules"))
        spec = spec_writer.write(row["brief"])
        surface = spec["surface"]
        key = spec["product_id"]
        if surface in seen or key in outcomes:
            raise ContractError("Bench perlu tepat satu produk setiap bentuk.")
        seen.add(surface)
        files = _assemble(spec, row["recipe"], row["architecture"])
        roster = _description(files)
        artifact = identity(roster)
        contract = {"schema": "ace.factory-acceptance-contract.v1", "spec_sha256": identity(spec),
                    "source_ref": f"{source}#{key}", "rules": row["rules"]}
        contract_key = identity(contract)
        root = f"evidence/{key}"
        with TemporaryDirectory(prefix="ace-factory-product-bench-") as temporary:
            target = Path(temporary) / "product"
            repo_scaffolder.materialize(target, files)
            noticed = PROBES[surface](target, key, row["probe"])
        observed = {"schema": "ace.factory-observations.v1", "product_id": key,
                    "artifact_sha256": artifact, "contract_sha256": contract_key,
                    "records": [{"id": metric, "value": value, "source_ref": f"{root}/observations.json#{metric}"}
                                for metric, value in sorted(noticed.items())]}
        report = acceptance_judge.evaluate(spec, contract, observed, contract_key, identity(observed), artifact)
        for name, data in (("artifacts", roster), ("spec", spec), ("contract", contract),
                           ("observations", observed), ("acceptance", report)):
            evidence[f"{root}/{name}.json"] = canonical(data) + b"\n"
        outcomes[key] = {"product_id": key, "surface": surface, "artifact_sha256": artifact,
                         "acceptance": f"{root}/acceptance.json", "counts": report["counts"], "status": report["status"]}
    if seen != SURFACES:
        raise ContractError("Cakupan produk bench belum lengkap.")
    successful = sum(result["status"] == "passed" for result in outcomes.values())
    summary = {"schema": "ace.factory-bench-report.v1", "plan_sha256": expected, "source_ref": source,
               "product_count": len(outcomes), "passed": successful, "status": "passed" if successful == len(outcomes) else "failed",
               "products": [outcomes[key] for key in sorted(outcomes)]}
    return {**evidence, "factory_bench_report.json": canonical(summary) + b"\n"}, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        files, report = run(decode(read(args.plan)), args.expect_sha256)
        if args.output:
            repo_scaffolder.materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError, subprocess.SubprocessError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
