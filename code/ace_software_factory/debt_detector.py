"""Temukan beban pemeliharaan yang dapat dilacak dalam snapshot Python.

Ambang kompleksitas dan ukuran dinyatakan per analisis. Graf memetakan
impor internal yang terlihat di AST; pelaporan menautkan kelompok siklik
dan modul dengan parse gagal. Skor ini memberi prioritas peninjauan.
"""
import argparse
import ast
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, decode, integer, read
from .self_reviewer import inspect_sources, source_summary


NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
BRANCHES = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)


def _body_nodes(function):
    pending = list(reversed(function.body))
    while pending:
        child = pending.pop()
        yield child
        if not isinstance(child, NESTED):
            pending.extend(reversed(list(ast.iter_child_nodes(child))))


def complexity(function):
    branches = 1
    for child in _body_nodes(function):
        if isinstance(child, BRANCHES):
            branches += 1
        elif isinstance(child, ast.BoolOp):
            branches += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            branches += 1 + len(child.ifs)
        elif isinstance(child, ast.match_case):
            if child.guard is not None or not (
                    isinstance(child.pattern, ast.MatchAs) and child.pattern.pattern is None):
                branches += 1
    return branches


def _module(path):
    parts = path.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(tree, path):
    package = _module(path) if path.endswith("/__init__.py") else _module(path).rpartition(".")[0]
    package_parts = package.split(".") if package else []
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            yield from (entry.name for entry in item.names)
        elif isinstance(item, ast.ImportFrom):
            if item.level > len(package_parts):
                continue
            prefix = package_parts[:len(package_parts) - item.level + 1] if item.level else []
            base = ".".join([*prefix, *([item.module] if item.module else [])])
            if item.module:
                yield base
            for entry in item.names:
                if entry.name != "*":
                    yield ".".join(filter(None, (base, entry.name)))


def cycle_groups(graph):
    """Pisahkan komponen kuat dengan dua lintasan DFS."""
    seen = set()
    order = []

    def postorder(node):
        if node in seen:
            return
        seen.add(node)
        for adjacent in sorted(graph[node]):
            postorder(adjacent)
        order.append(node)

    for node in sorted(graph):
        postorder(node)
    reverse = {node: set() for node in graph}
    for node, targets in graph.items():
        for target in targets:
            reverse[target].add(node)
    seen.clear()
    groups = []
    for node in reversed(order):
        if node in seen:
            continue
        group = set()
        pending = [node]
        while pending:
            adjacent = pending.pop()
            if adjacent in seen:
                continue
            seen.add(adjacent)
            group.add(adjacent)
            pending.extend(reverse[adjacent])
        if len(group) > 1 or node in graph[node]:
            groups.append(sorted(group))
    return sorted(groups)


def analyze(root, manifest, expected, *, max_complexity=10, max_lines=65):
    integer(max_complexity, "Ambang kompleksitas", 1, 1000)
    integer(max_lines, "Ambang baris", 1, 5000)
    observed = inspect_sources(root, manifest, expected)
    paths = {}
    for path in sorted(observed):
        module = _module(path)
        if module in paths:
            raise ContractError("Dua path memiliki nama modul yang sama.")
        paths[module] = path
    graph = {module: set() for module in paths}
    missing = []
    functions = []
    for module, path in paths.items():
        tree, failure, anchor, _ = observed[path]
        if failure is not None:
            missing.append({"path": path, "line": failure[0], "sha256": anchor})
            continue
        graph[module].update(dependency for dependency in _imports(tree, path) if dependency in paths)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decisions = complexity(node)
                length = node.end_lineno - node.lineno + 1
                reasons = []
                if decisions > max_complexity:
                    reasons.append("complexity")
                if length > max_lines:
                    reasons.append("length")
                if reasons:
                    functions.append({"function": node.name, "path": path, "line": node.lineno, "sha256": anchor,
                                      "complexity": decisions, "lines": length, "reasons": reasons})
    functions.sort(key=lambda row: (-len(row["reasons"]), -row["complexity"], row["path"], row["line"]))
    return {"schema": "ace.factory-debt-report.v1", "manifest_sha256": expected,
            "thresholds": {"complexity": max_complexity, "lines": max_lines}, "sources": source_summary(observed),
            "functions": functions, "parse_failures": missing, "dependencies": {key: sorted(graph[key]) for key in sorted(graph)},
            "cycles": [{"modules": group, "paths": [paths[name] for name in group]} for group in cycle_groups(graph)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--max-complexity", type=int, default=10)
    parser.add_argument("--max-lines", type=int, default=65)
    args = parser.parse_args(argv)
    try:
        report = analyze(args.root, decode(read(args.manifest)), args.expect_sha256,
                         max_complexity=args.max_complexity, max_lines=args.max_lines)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(bool(report["parse_failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
