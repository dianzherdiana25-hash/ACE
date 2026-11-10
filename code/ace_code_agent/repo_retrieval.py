"""Bounded, read-only AST repository retrieval for ACE coding research.

This extends the existing CodebaseReader approach. It indexes source as data;
candidate source is never imported or executed. Semantic embeddings and patch
execution are deliberately out of scope.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .codebase_reader import CodebaseReader


def _tokens(value: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9]*", spaced.replace("_", " "))}


def _callee(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


class _Symbols(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.records: list[dict[str, Any]] = []

    def _add(self, node: ast.AST, name: str, kind: str) -> None:
        calls = sorted({called for item in ast.walk(node)
                        if isinstance(item, ast.Call)
                        if (called := _callee(item.func)) is not None}) if kind != "class" else []
        signature = ast.unparse(node.args) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else ""
        self.records.append({
            "name": name,
            "qualname": ".".join([*self.scope, name]),
            "kind": kind,
            "signature": signature,
            "line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "calls": calls[:80],
        })

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node, node.name, "class")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(node, node.name, "function")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add(node, node.name, "async_function")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


class BoundedRepositoryRetriever(CodebaseReader):
    """AST symbol index with exact Git ignore behavior and explicit resource caps."""

    def __init__(
        self,
        repo_root: Path,
        *,
        max_depth: int = 12,
        max_files: int = 1000,
        max_file_bytes: int = 131072,
        time_budget_seconds: float = 15.0,
    ) -> None:
        super().__init__(Path(repo_root).resolve())
        if not 0 <= max_depth <= 32:
            raise ValueError("max_depth must be between 0 and 32")
        if not 1 <= max_files <= 10000:
            raise ValueError("max_files must be between 1 and 10000")
        if not 128 <= max_file_bytes <= 1048576:
            raise ValueError("max_file_bytes must be between 128 and 1048576")
        if not 0.1 <= time_budget_seconds <= 120:
            raise ValueError("time_budget_seconds out of range")
        self.max_depth = max_depth
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.time_budget_seconds = time_budget_seconds

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        # Fixed argv, no shell, hooks and fsmonitor disabled, read-only.
        return subprocess.run(
            ["git", "-C", str(self.repo_root), "-c", "core.fsmonitor=false",
             "-c", "core.hooksPath=/dev/null", "--no-optional-locks", *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=min(10.0, self.time_budget_seconds),
            check=True,
        )

    def build_index(self) -> dict[str, Any]:
        begin = time.monotonic()
        filenames = self._git("ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
        if len(filenames) > 4_000_000:
            raise ValueError("git file-list exceeds 4 MB safety cap")
        candidates = sorted({Path(part.decode("utf-8", errors="surrogateescape"))
                             for part in filenames.split(b"\0") if part})
        files: list[dict[str, Any]] = []
        rejected: dict[str, int] = {}
        errors: list[dict[str, str]] = []

        def skip(reason: str) -> None:
            rejected[reason] = rejected.get(reason, 0) + 1

        for rel in candidates:
            if time.monotonic() - begin >= self.time_budget_seconds:
                skip("TIME_BUDGET")
                break
            if rel.is_absolute() or ".." in rel.parts:
                skip("PATH_ESCAPE")
                continue
            if rel.suffix != ".py":
                continue
            if len(rel.parts) - 1 > self.max_depth:
                skip("DEPTH_LIMIT")
                continue
            if len(files) >= self.max_files:
                skip("FILE_LIMIT")
                break

            path = self.repo_root / rel
            try:
                real_path = path.resolve(strict=True)
                real_path.relative_to(self.repo_root)
                if path.is_symlink() or not real_path.is_file():
                    skip("SYMLINK_OR_NOT_FILE")
                    continue
                if real_path.stat().st_size > self.max_file_bytes:
                    skip("FILE_SIZE")
                    continue
                text = real_path.read_text(encoding="utf-8")
                tree = ast.parse(text, filename=rel.as_posix())
            except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
                errors.append({"path": rel.as_posix(), "error_type": type(exc).__name__})
                continue

            symbols = _Symbols()
            symbols.visit(tree)
            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add("." * node.level + (node.module or ""))
            file_tokens = sorted(_tokens(text))[:1024]
            files.append({
                "path": rel.as_posix(),
                "imports": sorted(imports)[:128],
                "symbols": symbols.records[:512],
                "lexical_terms": file_tokens,
            })
        try:
            head = self._git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        except (subprocess.CalledProcessError, UnicodeError):
            head = "UNBORN"
        return {
            "schema": "ace.repo.retrieval.v1",
            "head": head,
            "files": files,
            "file_count": len(files),
            "symbol_count": sum(len(f["symbols"]) for f in files),
            "skipped": rejected,
            "parse_errors": errors,
            "elapsed_ms": round((time.monotonic() - begin) * 1000, 3),
        }

    @staticmethod
    def search(index: dict[str, Any], query: str, *, mode: str = "hybrid", limit: int = 5) -> list[dict[str, Any]]:
        if mode not in {"hybrid", "lexical", "structural"}:
            raise ValueError("unknown search mode")
        if not query.strip() or len(query) > 256:
            raise ValueError("query must contain 1-256 characters")
        if not 1 <= limit <= 100:
            raise ValueError("invalid limit")
        wanted = _tokens(query)
        if not wanted:
            return []
        needle = query.lower().strip()
        results: list[dict[str, Any]] = []
        for record in index["files"]:
            file_terms = set(record["lexical_terms"]) | _tokens(record["path"])
            lexical = 3.0 * len(wanted & file_terms) / len(wanted)
            structural, top_symbol = 0.0, None
            for symbol in record["symbols"]:
                sym_terms = _tokens(symbol["qualname"])
                if needle in {symbol["name"].lower(), symbol["qualname"].lower()}:
                    score = 10.0
                elif wanted <= sym_terms:
                    score = 6.0
                else:
                    score = 2.0 * len(wanted & sym_terms) / len(wanted)
                if score > structural:
                    structural, top_symbol = score, symbol
            score = (lexical if mode == "lexical" else
                     structural if mode == "structural" else
                     lexical + structural)
            if score <= 0:
                continue
            results.append({
                "path": record["path"],
                "score": round(score, 3),
                "lexical_score": round(lexical, 3),
                "structural_score": round(structural, 3),
                "symbol": top_symbol if mode != "lexical" else None,
                "imports": record["imports"][:12],
            })
        return sorted(results, key=lambda result: (-result["score"], result["path"]))[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description="ACE read-only bounded repository/symbol retrieval")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--query", required=True)
    parser.add_argument("--mode", choices=["hybrid", "lexical", "structural"], default="hybrid")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-depth", type=int, default=12)
    parser.add_argument("--max-files", type=int, default=1000)
    args = parser.parse_args()
    retriever = BoundedRepositoryRetriever(args.repo, max_depth=args.max_depth, max_files=args.max_files)
    index = retriever.build_index()
    print(json.dumps({
        "schema": index["schema"],
        "head": index["head"],
        "files_indexed": index["file_count"],
        "symbols_indexed": index["symbol_count"],
        "skipped": index["skipped"],
        "parse_errors": index["parse_errors"][:20],
        "index_elapsed_ms": index["elapsed_ms"],
        "mode": args.mode,
        "query": args.query,
        "results": retriever.search(index, args.query, mode=args.mode, limit=args.limit),
        "provider_calls": 0,
        "candidate_code_executed": False,
        "scientific_status": "NOT_ASSESSED",
        "release_gate": "BLOCK_RELEASE",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
