"""Perbaiki nilai literal Python ketika laporan kegagalan dapat direproduksi.

Lokasi, nilai awal, koreksi yang disetujui, dan verifier dicatat sebelum
sumber dibaca. Satu leaf AST boleh berubah. Tes regresi harus gagal
sebelum perbaikan dan seluruh suite wajib hijau sesudahnya.
"""
import argparse
import ast
from hashlib import sha256
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from ._contracts import ContractError, canonical, checked, decode, digest, integer, obj, read, schema, text
from .build_loop import _description, _path, _read_tree, _runner
from .repo_scaffolder import materialize


TEST_ID = re.compile(r"test_[a-zA-Z_0-9]+(?:\.[a-zA-Z_][a-zA-Z_0-9]*)+")
VALUES = (str, int, bool, type(None))


def _change(settings, files):
    obj(settings, ("path", "source_sha256", "line", "column", "before", "after"))
    path = _path(settings["path"])
    if path not in files or path.startswith("tests/") or not path.endswith(".py"):
        raise ContractError("Lokasi perbaikan harus file Python produk.")
    start_line = integer(settings["line"], "Baris literal", 1, 50_000)
    start_column = integer(settings["column"], "Kolom byte literal", 0, 20_000)
    expected = digest(settings["source_sha256"])
    source = files[path]
    if sha256(source).hexdigest() != expected:
        raise ContractError("Hash berkas perbaikan tidak cocok.")
    before, after = settings["before"], settings["after"]
    if type(before) not in VALUES or type(before) is not type(after) or before == after:
        raise ContractError("Koreksi memerlukan perubahan literal dengan tipe yang sama.")
    if isinstance(after, str):
        text(after, "Literal pengganti", 500)
    if type(after) is int:
        integer(after, "Literal pengganti", 0, 2**63-1)
    parsed = ast.parse(source.decode("utf-8"), filename=path)
    ordinary = [
        node for node in ast.walk(parsed)
        if isinstance(node, ast.Constant) and node.lineno == start_line and node.col_offset == start_column
    ]
    if len(ordinary) != 1:
        raise ContractError("Koordinat tidak menunjuk tepat satu literal.")
    node = ordinary[0]
    if type(node.value) is not type(before) or node.value != before or node.end_lineno != start_line:
        raise ContractError("Literal source berbeda dari laporan.")
    parents = {child: parent for parent in ast.walk(parsed) for child in ast.iter_child_nodes(parent)}
    parent = parents.get(node)
    if not isinstance(parent, (ast.Return, ast.Assign, ast.AnnAssign, ast.keyword, ast.arguments, ast.Dict, ast.List)) or (
            isinstance(parent, ast.Dict) and any(node is key for key in parent.keys)):
        raise ContractError("Konteks literal belum diizinkan untuk koreksi otomatis.")
    cursor = parent
    while cursor in parents:
        if isinstance(cursor, (ast.Assert, ast.JoinedStr, ast.FormattedValue, ast.Match)):
            raise ContractError("Koreksi tidak boleh mengubah assertion, pola atau literal komposit.")
        cursor = parents[cursor]
    lines = source.splitlines(keepends=True)
    line = lines[start_line - 1]
    lines[start_line - 1] = line[:start_column] + repr(after).encode("utf-8") + line[node.end_col_offset:]
    replacement = b"".join(lines)
    node.value = after
    if ast.dump(ast.parse(replacement.decode("utf-8"), filename=path)) != ast.dump(parsed):
        raise ContractError("Perubahan source menghasilkan delta AST di luar literal yang disetujui.")
    corrected = {**files, path: replacement}
    return corrected, {"path": path, "line": start_line, "column_byte": start_column, "before_sha256": expected,
                       "after_sha256": sha256(replacement).hexdigest()}


def _audit(files, seconds, runner):
    with TemporaryDirectory(prefix="ace-factory-bug-") as folder:
        root = Path(folder) / "check"
        materialize(root, files)
        return runner(root, seconds)


def fix(root, report, expected, *, runner=_runner):
    checked(report, expected)
    schema(report, "ace.factory-bug-report.v1", ("source_ref", "files", "regression_test", "expected_tests",
                                               "timeout_seconds", "change"))
    source_ref = text(report["source_ref"], "Rujukan bug", 200)
    name = text(report["regression_test"], "ID verifier", 200)
    if not TEST_ID.fullmatch(name):
        raise ContractError("Tes regresi perlu nama unittest discover lengkap.")
    seconds = integer(report["timeout_seconds"], "Timeout", 1, 30)
    count = integer(report["expected_tests"], "Jumlah tes wajib", 1, 20_000)
    files = _read_tree(root, report["files"])
    corrected, patch_info = _change(report["change"], files)
    before = _audit(files, seconds, runner)
    result = {"schema": "ace.factory-bug-fix-receipt.v1", "report_sha256": expected, "source_ref": source_ref,
              "regression_test": name, "before": before, "after": None, "change": patch_info,
              "output_files": None, "status": "not_reproduced"}
    if before["status"] != "failed" or before["failures"] != [name] or before["tests"] != count:
        return None, result
    result["after"] = after = _audit(corrected, seconds, runner)
    if after["status"] != "passed" or after["tests"] != count or after["skipped"] != 0:
        result["status"] = "repair_unverified"
        return None, result
    result.update(status="verified_repair", output_files=_description(corrected))
    return corrected, result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        files, receipt = fix(args.root, decode(read(args.report)), args.expect_sha256)
        if files is not None and args.output is not None:
            materialize(args.output, files)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, SyntaxError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(receipt["status"] != "verified_repair")


if __name__ == "__main__":
    raise SystemExit(main())
