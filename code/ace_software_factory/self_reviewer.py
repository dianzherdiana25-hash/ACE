"""Tinjau perubahan Python tanpa menjalankan kode yang sedang diperiksa.

Temuan menunjuk ke byte sumber yang disetujui dan dapat dibaca kembali.
Aturan ini memeriksa pola yang terlihat di AST. Semua skor dan keputusan
rilis tetap memakai hasil verifier yang sesuai dengan produknya.
"""
import argparse
import ast
from pathlib import Path
import sys
import tokenize
from io import BytesIO

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, obj, read, schema, text


SOURCE_SCHEMA = "ace.factory-python-sources.v1"
FILE_MAX = 160_000
TOTAL_MAX = 2_000_000


def inspect_sources(root, manifest, expected):
    checked(manifest, expected)
    schema(manifest, SOURCE_SCHEMA, ("source_ref", "files"))
    text(manifest["source_ref"], "Rujukan sumber")
    observed = {}
    total = 0
    for entry in entries(manifest["files"], 150, minimum=1):
        obj(entry, ("path", "sha256"))
        path = text(entry["path"], "Path Python", 500)
        if not path.endswith(".py") or path in observed:
            raise ContractError("Path Python ganda atau ekstensi tidak cocok.")
        file_hash = digest(entry["sha256"])
        payload = read_relative(root, path, min(FILE_MAX, TOTAL_MAX - total), file_hash)
        total += len(payload)
        failure = None
        node = None
        try:
            encoding, _ = tokenize.detect_encoding(BytesIO(payload).readline)
            node = ast.parse(payload.decode(encoding), filename=path)
        except (SyntaxError, UnicodeError, ValueError, RecursionError) as error:
            failure = (getattr(error, "lineno", None) or 1, getattr(error, "offset", None) or 1)
        observed[path] = (node, failure, file_hash, len(payload))
    return observed


def source_summary(observed):
    return [
        {"path": path, "sha256": file_hash, "bytes": size, "parse_ok": node is not None}
        for path, (node, _, file_hash, size) in sorted(observed.items())
    ]


def _mutable(node):
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"list", "set", "dict", "bytearray"})


class Review(ast.NodeVisitor):
    """Catat keputusan sempit yang dapat diperiksa pada sumber."""

    def __init__(self, path, anchor):
        self.path = path
        self.anchor = anchor
        self.findings = []

    def add(self, rule, node, severity):
        self.findings.append({
            "rule": rule,
            "severity": severity,
            "path": self.path,
            "line": node.lineno,
            "column": node.col_offset + 1,
            "sha256": self.anchor,
        })

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.add("bare_except", node, "high")
        caught = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        broad = any(isinstance(kind, ast.Name) and kind.id in {"Exception", "BaseException"} for kind in caught)
        body = [statement for statement in node.body if not (
            isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str))]
        if broad and body and all(isinstance(statement, (ast.Pass, ast.Continue)) for statement in body):
            self.add("broad_exception_suppressed", node, "high")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for default in node.args.defaults + node.args.kw_defaults:
            if _mutable(default):
                self.add("mutable_default", default, "medium")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Compare(self, node):
        operands = [node.left, *node.comparators]
        for left, right, comparison in zip(operands, operands[1:], node.ops):
            if isinstance(comparison, (ast.Is, ast.IsNot)) and any(
                isinstance(operand, ast.Constant) and type(operand.value) in (str, int, float, bytes)
                for operand in (left, right)
            ):
                self.add("identity_compares_value_literal", node, "medium")
                break
        self.generic_visit(node)

    def visit_Assert(self, node):
        if isinstance(node.test, ast.Tuple) and node.test.elts:
            self.add("assertion_uses_nonempty_tuple", node, "high")
        self.generic_visit(node)

    def generic_visit(self, node):
        for _, contents in ast.iter_fields(node):
            if not isinstance(contents, list):
                continue
            for index, statement in enumerate(contents[:-1]):
                if isinstance(statement, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                    self.add("unreachable_statement", contents[index + 1], "medium")
                    break
        super().generic_visit(node)


def review(root, manifest, expected):
    observed = inspect_sources(root, manifest, expected)
    findings = []
    for path, (tree, failure, file_hash, _) in sorted(observed.items()):
        if failure is not None:
            findings.append({"rule": "syntax_error", "severity": "high", "path": path, "line": failure[0],
                             "column": failure[1], "sha256": file_hash})
            continue
        reviewer = Review(path, file_hash)
        reviewer.visit(tree)
        findings.extend(reviewer.findings)
    findings.sort(key=lambda finding: (finding["path"], finding["line"], finding["column"], finding["rule"]))
    return {"schema": "ace.factory-source-review.v1", "manifest_sha256": expected,
            "sources": source_summary(observed), "findings": findings,
            "status": "review_required" if findings else "no_rule_matches"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = review(args.root, decode(read(args.manifest)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "review_required")


if __name__ == "__main__":
    raise SystemExit(main())
