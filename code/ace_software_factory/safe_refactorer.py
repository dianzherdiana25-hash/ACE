"""Ganti nama helper privat ketika binding dan bukti perilakunya jelas.

Snapshot semua pemanggil diikat hash. Nama dinamis, symbol yang tertutup
oleh binding lain, dan referensi lintas modul menahan perubahan. Verifier
menjalankan suite dari snapshot sebelum dan setelah penggantian token.
"""
import argparse
import ast
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import tokenize

from ._contracts import ContractError, canonical, checked, decode, integer, read, schema, text
from .build_loop import _description, _path, _read_tree, _runner
from .repo_scaffolder import materialize


PRIVATE = re.compile(r"_[a-z][a-z0-9_]{0,62}")
DYNAMIC = {"eval", "exec", "getattr", "setattr", "globals", "locals"}


def _private(value):
    if not isinstance(value, str) or not PRIVATE.fullmatch(value):
        raise ContractError("Penggantian hanya mendukung nama helper privat satu underscore.")
    return value


def _tokens(data):
    stream = BytesIO(data)
    tokens = list(tokenize.tokenize(stream.readline))
    if tokens[0].string != "utf-8":
        raise ContractError("Refactor membutuhkan sumber UTF-8.")
    return tokens


def _replacement(source, old, new, path):
    tree = ast.parse(source.decode(), filename=path)
    top = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == old]
    if len(top) != 1 or top[0].decorator_list:
        raise ContractError("Harus ada tepat satu definisi helper top-level tanpa decorator.")
    for node in ast.walk(tree):
        if node is top[0]:
            continue
        if isinstance(node, ast.Name):
            if node.id in DYNAMIC:
                raise ContractError("Akses nama dinamis menahan refactor.")
            if node.id == old and not isinstance(node.ctx, ast.Load):
                raise ContractError("Nama lama dibayangi binding lain.")
        if isinstance(node, (ast.Global, ast.Nonlocal)) and old in node.names:
            raise ContractError("Nama lama dideklarasikan lintas scope.")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and old in node.value:
            raise ContractError("Nama lama ditemukan dalam literal string.")
        locations = [(ast.arg, "arg"), (ast.Attribute, "attr"), (ast.keyword, "arg"), (ast.alias, "name"),
                     (ast.alias, "asname"), (ast.FunctionDef, "name"), (ast.AsyncFunctionDef, "name"),
                     (ast.ClassDef, "name"), (ast.ExceptHandler, "name"), (ast.MatchAs, "name"),
                     (ast.MatchStar, "name"), (ast.MatchMapping, "rest")]
        if any(isinstance(node, kind) and getattr(node, key) == old for kind, key in locations):
            raise ContractError("Nama lama muncul dalam konteks yang tidak didukung.")
    references = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == old]
    if not references:
        raise ContractError("Snapshot tidak memiliki pemanggilan helper.")
    tokens = _tokens(source)
    if any(token.type == tokenize.NAME and token.string == new for token in tokens):
        raise ContractError("Nama baru sudah muncul dalam modul.")
    edits = [(token.start, token.end) for token in tokens if token.type == tokenize.NAME and token.string == old]
    if len(edits) != len(references) + 1:
        raise ContractError("Jumlah token berbeda dari referensi AST yang didukung.")
    lines = source.decode().splitlines(keepends=True)
    for (line, col), (end_line, end_col) in reversed(edits):
        if line != end_line:
            raise ContractError("Token pengganti melintasi baris.")
        original = lines[line - 1]
        lines[line - 1] = original[:col] + new + original[end_col:]
    replacement = "".join(lines).encode()
    top[0].name = new
    for node in references:
        node.id = new
    if ast.dump(ast.parse(replacement.decode(), filename=path)) != ast.dump(tree):
        raise ContractError("Delta AST berisi perubahan selain rename.")
    return replacement, len(edits)


def _audit(files, timeout, runner):
    with TemporaryDirectory(prefix="ace-factory-refactor-") as folder:
        root = Path(folder) / "tree"
        materialize(root, files)
        return runner(root, timeout)


def refactor(root, plan, expected, *, runner=_runner):
    checked(plan, expected)
    schema(plan, "ace.factory-refactor-plan.v1", ("source_ref", "files", "path", "old", "new",
                                                  "timeout_seconds", "test_count"))
    old, new = _private(plan["old"]), _private(plan["new"])
    if new == old:
        raise ContractError("Rename memerlukan nama yang berbeda.")
    path = _path(plan["path"])
    pointer = text(plan["source_ref"], "Sumber perubahan", 200)
    timeout = integer(plan["timeout_seconds"], "Timeout", 1, 30)
    count = integer(plan["test_count"], "Jumlah tes wajib", 1, 20_000)
    files = _read_tree(root, plan["files"])
    if path not in files or not path.endswith(".py") or path.startswith("tests/"):
        raise ContractError("Nama hanya dapat diubah dalam modul produk pada snapshot.")
    name_pattern = re.compile(rb"(?<![A-Za-z0-9_])" + re.escape(old.encode()) + rb"(?![A-Za-z0-9_])")
    for key, payload in sorted(files.items()):
        if key != path and key.endswith(".py") and name_pattern.search(payload):
            raise ContractError(f"Referensi nama di luar modul terdeteksi pada {key}.")
    replacement, edited = _replacement(files[path], old, new, path)
    receipt = {"schema": "ace.factory-refactor-receipt.v1", "plan_sha256": expected,
               "source_ref": pointer, "path": path, "name_changes": edited,
               "before_sha256": sha256(files[path]).hexdigest(), "after_sha256": sha256(replacement).hexdigest(),
               "before": None, "after": None, "status": "baseline_unverified"}
    receipt["before"] = before = _audit(files, timeout, runner)
    if before["status"] != "passed" or before["tests"] != count or before["skipped"] != 0:
        return None, receipt
    result = {**files, path: replacement}
    receipt["after"] = after = _audit(result, timeout, runner)
    if after["status"] != "passed" or after["tests"] != count or after["skipped"] != 0:
        receipt["status"] = "refactor_unverified"
        return None, receipt
    receipt.update(status="verified_refactor", output_files=_description(result))
    return result, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        files, receipt = refactor(args.root, decode(read(args.plan)), args.expect_sha256)
        if files is not None and args.output is not None:
            materialize(args.output, files)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, SyntaxError, ValueError, RecursionError, tokenize.TokenError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(receipt["status"] != "verified_refactor")


if __name__ == "__main__":
    raise SystemExit(main())
