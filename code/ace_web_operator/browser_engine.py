"""Jalankan kontrak browser di situs uji lokal dengan request terdaftar.

Runner hanya menerima origin loopback dan operasi terstruktur. Pembaca
teks mengeluarkan hash dan ukuran, dan verifier per tahap dapat
memeriksa teks tanpa menulis isi halaman ke receipt.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, origin, read, schema, text, web_path


SUPPORTED = {
    "navigate": ("path",),
    "expect_title": ("expected",),
    "expect_url": ("path",),
    "click": ("test_id",),
    "fill": ("test_id", "value"),
    "select": ("test_id", "value"),
    "check": ("test_id", "state"),
    "expect_text": ("test_id", "expected"),
    "expect_value": ("test_id", "expected"),
    "read_text": ("test_id",),
    "screenshot": ("test_id",),
}
MAX_OPERATIONS = 40
MAX_RESPONSE = 900_000
RUNTIME = Path(__file__).with_name("_browser_runtime.cjs")


def _step(raw, paths):
    if not isinstance(raw, dict) or not isinstance(raw.get("op"), str) or raw["op"] not in SUPPORTED:
        raise ContractError("Operasi browser belum didukung.")
    op = raw["op"]
    obj(raw, ("id", "op", *SUPPORTED[op]))
    clean = {"id": identifier(raw["id"], "ID tahap"), "op": op}
    if "path" in raw:
        value = web_path(raw["path"])
        if value not in paths:
            raise ContractError("Tujuan browser di luar rute terdaftar.")
        clean["path"] = value
    if "test_id" in raw:
        clean["test_id"] = identifier(raw["test_id"], "Selector fixture")
    if "expected" in raw:
        clean["expected"] = text(raw["expected"], "Harapan", 500)
    if "value" in raw:
        supplied = raw["value"]
        if not isinstance(supplied, str) or len(supplied) > 500 or supplied != "" and not supplied.isprintable():
            raise ContractError("Nilai kontrol di luar kontrak.")
        clean["value"] = supplied
    if "state" in raw:
        if type(raw["state"]) is not bool:
            raise ContractError("State checkbox harus boolean.")
        clean["state"] = raw["state"]
    return clean


def compile_plan(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.web.browser-plan.v1", ("source_ref", "origin", "allow_paths", "timeout_ms", "request_limit", "steps"))
    allowed_origin, _ = origin(plan["origin"])
    paths = [web_path(path) for path in entries(plan["allow_paths"], 70, 1)]
    if len(paths) != len(set(paths)):
        raise ContractError("Rute browser ganda.")
    steps = [_step(row, paths) for row in entries(plan["steps"], MAX_OPERATIONS, 1)]
    if sum(row["op"] == "screenshot" for row in steps)>1:
        raise ContractError("Satu rencana hanya boleh memuat satu capture.")
    if steps[0]["op"] != "navigate" or len({row["id"] for row in steps}) != len(steps):
        raise ContractError("Alur perlu navigasi awal dan ID tahap unik.")
    return {"schema": "ace.web.browser-runtime.v1", "origin": allowed_origin, "paths": sorted(paths),
            "timeout_ms": integer(plan["timeout_ms"], "Timeout per operasi", 100, 3500),
            "request_limit": integer(plan["request_limit"], "Kuota request browser", 1, 140),
            "source_ref": text(plan["source_ref"], "Sumber alur"), "steps": steps}


def _process(request, timeout):
    node, chromium = shutil.which("node"), shutil.which("chromium")
    if not node or not chromium:
        return None, "runtime_unavailable"
    try:
        result = subprocess.run([node, str(RUNTIME), chromium], input=canonical(request), capture_output=True,
                                check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "runtime_timeout"
    except OSError:
        return None, "runtime_unavailable"
    if result.returncode != 0 or len(result.stdout) > MAX_RESPONSE:
        return None, "runtime_unavailable" if result.returncode == 78 else "runtime_failure"
    try:
        return decode(result.stdout), None
    except (ValueError, UnicodeError, RecursionError):
        return None, "runtime_protocol"


def _records(response, planned):
    obj(response, ("status", "reason", "requests", "blocked", "steps"))
    limited = entries(response["steps"], len(planned["steps"]))
    calls = integer(response["requests"], "Jumlah request", 0, planned["request_limit"])
    blocks = integer(response["blocked"], "Request yang ditolak", 0, 10_000)
    for row, step in zip(limited, planned["steps"], strict=False):
        obj(row, ("id", "op", "status", "evidence"))
        if row["id"] != step["id"] or row["op"] != step["op"] or row["status"] not in ("ok", "failed") or (
            row["evidence"] is not None and not isinstance(row["evidence"], dict)
        ):
            raise ContractError("Runtime menerbitkan langkah yang tidak dikenal.")
    state = response["status"]
    if state not in ("completed", "failed") or (
        state == "completed" and (len(limited) != len(planned["steps"]) or blocks
                                  or any(row["status"] != "ok" for row in limited))
    ):
        raise ContractError("Status browser tidak sesuai receipt tahap.")
    return {"status": state, "reason": response["reason"], "requests": calls, "blocked": blocks, "steps": limited}


def run(plan, expected, *, transport=_process):
    config = compile_plan(plan, expected)
    allowance = len(config["steps"]) * config["timeout_ms"]
    if allowance > 36_000:
        raise ContractError("Anggaran gabungan browser melebihi batas.")
    result, failure = transport(config, 7 + allowance / 1000)
    if failure is not None:
        report = {"status": "held", "reason": failure, "requests": None, "blocked": None, "steps": []}
    else:
        report = _records(result, config)
    return {"schema": "ace.web.browser-receipt.v1", "plan_sha256": expected,
            "source_ref": config["source_ref"], **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = run(decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(result) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["status"] != "completed")


if __name__ == "__main__":
    raise SystemExit(main())
