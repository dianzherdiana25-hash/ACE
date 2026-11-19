#!/usr/bin/env python3
"""Audit klaim aset pada produk direktur terhadap snapshot Git lokal."""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path, PurePosixPath

if __package__:
    from ._director_sources import GitSnapshot, SourceError, parse_json, repo_path, write_json
else:
    from _director_sources import GitSnapshot, SourceError, parse_json, repo_path, write_json


KINDS = {"file", "module", "function", "pr"}
DOTTED = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", re.ASCII)
PR = re.compile(r"(?:(?P<repo>[\w.-]+/[\w.-]+)#|#)?(?P<number>[1-9][0-9]*)", re.ASCII)
PR_URL = re.compile(r"https://github\.com/(?P<repo>[\w.-]+/[\w.-]+)/pull/(?P<number>[1-9][0-9]*)", re.ASCII)
MARKDOWN_PRS = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/[1-9][0-9]*|"
                         r"(?<![\w/#])(?:[\w.-]+/[\w.-]+)?#[1-9][0-9]*\b")
FILE_LITERAL = re.compile(r"(?:[\w.-]+/)*[\w.-]+\.(?:py|md|jsonl?|csv|txt|toml|ya?ml|sh|log|gz)\b")
LABELLED_LINE = re.compile(r"^\s*[-*]\s*(?:\*\*)?(?:kombinasi aset|aset rumah dipakai ulang|aset)\s*:(?:\*\*)?\s*(.*)$", re.I)


_HEX_HASH = re.compile(r"^[0-9a-f]{7,64}$")
_ALL_CAPS_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _resolve_md_link(raw_path: str, product_dir: PurePosixPath | None) -> str:
    path = raw_path.split("#", 1)[0].strip()
    if not path or "://" in path or path.startswith("/") or "\\" in path:
        return path
    if product_dir and str(product_dir) != "." and (path.startswith("./") or path.startswith("../")):
        joined = (product_dir / path).parts
        resolved: list[str] = []
        for part in joined:
            if part in ("", "."):
                continue
            if part == "..":
                if not resolved:
                    return path  # Keep escaping ../ so _check flags invalid_repo_path
                resolved.pop()
            else:
                resolved.append(part)
        if resolved:
            return "/".join(resolved)
    return path


def _read_claims(text, is_json, *, product_path: str | None = None):
    if is_json:
        product = parse_json(text)
        if not isinstance(product, dict) or not isinstance(product.get("assets"), list):
            raise SourceError("Produk JSON perlu daftar assets.")
        for index, item in enumerate(product["assets"]):
            if (not isinstance(item, dict) or not isinstance(item.get("kind"), str)
                    or item["kind"] not in KINDS
                    or not isinstance(item.get("target"), str) or not item["target"].strip()):
                raise SourceError(f"Klaim aset pada /assets/{index} tidak sah.")
            yield f"/assets/{index}", item["kind"], item["target"].strip()
        return

    product_dir = PurePosixPath(product_path).parent if product_path else None
    for index, line in enumerate(text.splitlines(), 1):
        location = f"L{index}"
        seen = set()
        covered = []
        for match in re.finditer(r"`([^`]+)`", line):
            token = match[1].strip()
            prefix, separator, target = token.partition(":")
            if separator and prefix in KINDS and target.strip():
                seen.add((prefix, target.strip()))
                covered.append(match.span())
            elif "::" in token:
                seen.add(("function", token))
                covered.append(match.span())
            elif FILE_LITERAL.fullmatch(token):
                seen.add(("file", token))
                covered.append(match.span())
            elif DOTTED.fullmatch(token) and "." in token and not _HEX_HASH.fullmatch(token):
                seen.add(("module", token))
                covered.append(match.span())
            elif DOTTED.fullmatch(token) and (_HEX_HASH.fullmatch(token) or _ALL_CAPS_TOKEN.fullmatch(token)):
                covered.append(match.span())
        for start, end in covered:
            line = line[:start] + " " * (end - start) + line[end:]
        for match in MARKDOWN_PRS.finditer(line):
            seen.add(("pr", match[0]))
        md_link_spans = []
        for match in re.finditer(r"\]\(([^)]+)\)", line):
            resolved = _resolve_md_link(match[1], product_dir)
            if FILE_LITERAL.fullmatch(resolved):
                seen.add(("file", resolved))
                md_link_spans.append(match.span())
        for start, end in md_link_spans:
            line = line[:start] + " " * (end - start) + line[end:]
        for match in FILE_LITERAL.finditer(line):
            if not re.search(r"[:/\w.-]$", line[:match.start()]):
                seen.add(("file", match[0]))
        label = LABELLED_LINE.match(line)
        if label:
            # Historical products also describe assets as free text.
            for part in re.split(r"\s+\+\s+|[,;]", label[1]):
                part = MARKDOWN_PRS.sub("", part).strip(" \t`*")
                if DOTTED.fullmatch(part) and not _HEX_HASH.fullmatch(part) and not _ALL_CAPS_TOKEN.fullmatch(part):
                    seen.add(("module", part))
                elif FILE_LITERAL.fullmatch(part):
                    seen.add(("file", part))
                elif part:
                    seen.add(("label", part))
        for kind, target in sorted(seen):
            yield location, kind, target


def _pr_ids(snapshot):
    if snapshot is None:
        return None, set()
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("repository"), str)
            or not re.fullmatch(r"[\w.-]+/[\w.-]+", snapshot["repository"], re.ASCII)
            or not isinstance(snapshot.get("pull_requests"), list)):
        raise SourceError("Snapshot PR perlu repository dan daftar pull_requests.")
    numbers = set()
    for number in snapshot["pull_requests"]:
        if type(number) is not int or number < 1 or number in numbers:
            raise SourceError("Nomor PR harus unik dan positif.")
        numbers.add(number)
    return snapshot["repository"].lower(), numbers


def _modules(repo, module):
    if not DOTTED.fullmatch(module):
        return []
    matches = []
    for path, entry in repo.entries.items():
        if entry[0] not in ("100644", "100755") or not path.endswith(".py"):
            continue
        stem = path.removesuffix(".py").removesuffix("/__init__")
        full = stem.replace("/", ".")
        package = stem.removeprefix("code/").replace("/", ".")
        if module in {full, package} or ("." not in module and module == package.rsplit(".", 1)[-1]):
            matches.append(path)
    return sorted(matches)


def _function_location(repo, target):
    module, separator, symbol = target.partition("::")
    if not separator or not DOTTED.fullmatch(symbol):
        return "ambiguous", [], "function_requires_module_and_symbol"
    if module.endswith(".py"):
        file = repo_path(module)
        paths = [file] if file in repo.entries else []
    else:
        paths = _modules(repo, module)
    if len(paths) != 1:
        return ("ambiguous" if paths else "not_found"), paths, "function_module_lookup"
    path = paths[0]
    try:
        tree = ast.parse(repo.read_text(path))
    except (SourceError, SyntaxError, ValueError):
        return "ambiguous", paths, "source_not_parseable"
    body = tree.body
    *owners, symbol = symbol.split(".")
    for owner in owners:
        classes = [node for node in body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(classes) != 1:
            return ("ambiguous" if classes else "not_found"), paths, "function_owner_lookup"
        body = classes[0].body
    functions = [node for node in body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol]
    if len(functions) == 1:
        return "verified", [f"{path}:{functions[0].lineno}"], "typed_ast_declaration"
    if len(functions) > 1:
        return "ambiguous", [f"{path}:{fn.lineno}" for fn in functions], "multiple_declarations"
    return "not_found", paths, "declaration_not_found"


def _check(repo, kind, target, origin, numbers):
    if kind == "file":
        path = repo_path(target)
        entry = repo.entries.get(path)
        if entry is None and "/" not in path:
            matches = sorted(name for name in repo.entries if PurePosixPath(name).name == path)
            if len(matches) > 1:
                return "ambiguous", matches, "multiple_basename_matches"
            if matches:
                path = matches[0]
                entry = repo.entries[path]
        if entry is None:
            return "not_found", [], "path_not_in_snapshot"
        if entry[0] not in ("100644", "100755"):
            return "ambiguous", [path], "nonregular_entry"
        return "verified", [path], "tracked_blob"
    if kind == "module":
        if not DOTTED.fullmatch(target):
            return "ambiguous", [], "module_name_required"
        matches = _modules(repo, target)
        if len(matches) != 1:
            return ("ambiguous" if matches else "not_found"), matches, "module_lookup"
        return "verified", matches, "python_source"
    if kind == "function":
        return _function_location(repo, target)
    if kind == "pr":
        match = PR.fullmatch(target) or PR_URL.fullmatch(target)
        if not match or origin is None or (match["repo"] and match["repo"].lower() != origin):
            return "ambiguous", [], "pr_snapshot_required_for_repository"
        if int(match["number"]) not in numbers:
            return "not_found", [], "pr_not_listed_in_snapshot"
        return "verified", [f"{origin}#{match['number']}"], "pr_listed_in_snapshot"
    return "ambiguous", [], "asset_label_needs_identifier"


def verify_assets(repo, product_path, *, pr_snapshot_path=None):
    origin, numbers = _pr_ids(repo.read_json(pr_snapshot_path) if pr_snapshot_path else None)
    claims = _read_claims(
        repo.read_text(product_path),
        PurePosixPath(product_path).suffix == ".json",
        product_path=product_path,
    )
    rows = []
    for location, kind, target in claims:
        try:
            status, matches, reason = _check(repo, kind, target, origin, numbers)
        except SourceError:
            status, matches, reason = "ambiguous", [], "invalid_repo_path"
        rows.append({"location": location, "kind": kind, "target": target, "status": status,
                     "matches": matches, "reason": reason})
    return {"schema": "ace.director.asset-check.v1", "commit": repo.commit, "product": product_path,
            "pr_snapshot": pr_snapshot_path, "assets": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", help="Path produk Markdown atau JSON dalam commit.")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--pr-snapshot", help="Path daftar PR offline dalam commit.")
    args = parser.parse_args(argv)
    try:
        result = verify_assets(GitSnapshot(args.repo, args.revision), args.product,
                               pr_snapshot_path=args.pr_snapshot)
    except SourceError as exc:
        parser.exit(2, f"Error. {exc}\n")
    write_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
