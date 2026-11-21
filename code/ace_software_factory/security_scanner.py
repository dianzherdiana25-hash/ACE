"""Periksa pola keamanan Python secara statis pada source produk sendiri.

Temuan menyebut aturan dan alamat AST. Scanner tidak menampilkan nilai
kandidat rahasia, menjalankan source, atau menguji layanan. Ketiadaan
temuan berarti aturan yang didukung tidak menemukan kecocokan.
"""
import argparse
import ast
import re
from pathlib import Path
import sys

from ._contracts import canonical, decode, read
from .self_reviewer import inspect_sources, source_summary


CREDENTIAL_SUFFIX = re.compile(r"(?:^|_)(?:api_key|access_token|client_secret|private_key|passwd|password)$", re.I)
DYNAMIC_CODE = {"eval", "exec", "builtins.eval", "builtins.exec"}
PROCESS_CALLS = {f"subprocess.{name}" for name in ("run", "Popen", "check_output", "check_call", "call")}
LEGACY_DIGESTS = {"hashlib.md5", "hashlib.sha1"}
SEVERITY = {"credential_literal": "high", "dynamic_code": "high", "interpolated_sql": "high",
            "shell_enabled": "high", "unverified_tls_context": "high", "legacy_digest": "review"}


def _symbol(node, aliases):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join([aliases.get(node.id, node.id), *reversed(parts)])


def _imports(tree):
    candidates = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                candidates.setdefault(local, set()).add(alias.name if alias.asname else local)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            for alias in node.names:
                candidates.setdefault(alias.asname or alias.name, set()).add(f"{node.module}.{alias.name}")
    return {local: next(iter(target)) for local, target in candidates.items() if len(target) == 1}


def _binding_name(target):
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str):
        return target.slice.value
    return ""


def _literal(value):
    return isinstance(value, ast.Constant) and isinstance(value.value, (str, bytes)) and bool(value.value.strip())


def _interpolated(node):
    return isinstance(node, ast.JoinedStr) or (
        isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add))) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format")


class Scan(ast.NodeVisitor):
    def __init__(self, path, anchor, aliases):
        self.path = path
        self.anchor = anchor
        self.aliases = aliases
        self.rows = []

    def finding(self, key, node):
        self.rows.append({"rule": key, "severity": SEVERITY[key], "path": self.path,
                          "ref": f"{self.path}:{node.lineno}:{node.col_offset + 1}",
                          "line": node.lineno, "column": node.col_offset + 1, "sha256": self.anchor})

    def _bindings(self, targets, literal):
        if _literal(literal):
            for target in targets:
                if CREDENTIAL_SUFFIX.search(_binding_name(target)):
                    self.finding("credential_literal", target)

    def visit_Assign(self, node):
        self._bindings(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._bindings([node.target], node.value)
        self.generic_visit(node)

    def visit_Dict(self, node):
        for key, value in zip(node.keys, node.values):
            if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                    and CREDENTIAL_SUFFIX.search(key.value) and _literal(value)):
                self.finding("credential_literal", key)
        self.generic_visit(node)

    def visit_Call(self, node):
        name = _symbol(node.func, self.aliases)
        if name in DYNAMIC_CODE:
            self.finding("dynamic_code", node)
        elif name == "ssl._create_unverified_context":
            self.finding("unverified_tls_context", node)
        elif name in LEGACY_DIGESTS:
            self.finding("legacy_digest", node)
        elif name in PROCESS_CALLS and any(
                item.arg == "shell" and isinstance(item.value, ast.Constant) and item.value.value is True
                for item in node.keywords):
            self.finding("shell_enabled", node)
        if (isinstance(node.func, ast.Attribute) and node.func.attr in {"execute", "executemany", "executescript"}
                and node.args and _interpolated(node.args[0])):
            self.finding("interpolated_sql", node)
        self.generic_visit(node)


def scan(root, manifest, expected):
    observed = inspect_sources(root, manifest, expected)
    findings, unscanned = [], []
    for path, (tree, failure, file_hash, _) in sorted(observed.items()):
        if failure:
            unscanned.append({"path": path, "line": failure[0], "sha256": file_hash})
            continue
        scanner = Scan(path, file_hash, _imports(tree))
        scanner.visit(tree)
        findings.extend(scanner.rows)
    findings.sort(key=lambda row: (row["path"], row["line"], row["column"], row["rule"]))
    return {"schema": "ace.factory-sast-report.v1", "manifest_sha256": expected, "findings": findings,
            "rules": sorted(SEVERITY), "sources": source_summary(observed), "unscanned": unscanned,
            "status": "incomplete" if unscanned else ("review_required" if findings else "no_rule_matches")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = scan(args.root, decode(read(args.manifest)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "no_rule_matches")


if __name__ == "__main__":
    raise SystemExit(main())
