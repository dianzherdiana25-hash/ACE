"""Static inventory of declared historical unittest modules; no code execution."""
import argparse
import ast
import json
from pathlib import Path


def inspect(root):
    manifest = root / "tools" / "ace_e15_regression.py"
    if not manifest.is_file():
        raise ValueError("manifest absent")
    tree = ast.parse(manifest.read_text(encoding="utf-8"))
    assignments = [node.value for node in tree.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "TESTS" for t in node.targets)]
    if len(assignments) != 1:
        raise ValueError("expected exactly one TESTS declaration")
    groups = ast.literal_eval(assignments[0])
    if not isinstance(groups, dict) or not groups:
        raise ValueError("invalid TESTS declaration")
    records = []
    for group, modules in groups.items():
        if not isinstance(group, str) or not group or not isinstance(modules, list) or not modules:
            raise ValueError("invalid group")
        for module in modules:
            if not isinstance(module, str) or not all(p.isidentifier() for p in module.split(".")):
                raise ValueError("invalid module")
            path = Path(*module.split(".")).with_suffix(".py")
            base = root if module.startswith("tools.") else root / "code"
            full = base / path
            found = full.is_file() or (base / Path(*module.split(".")) / "__init__.py").is_file()
            records.append({"group": group, "module": module, "path": str(full.relative_to(root)),
                            "status": "PRESENT" if found else "MISSING"})
    missing = [x for x in records if x["status"] == "MISSING"]
    return {"decision": "BLOCK_MISSING_MODULES" if missing else "INVENTORY_COMPLETE_NOT_TESTED",
            "checked": len(records), "missing": len(missing), "records": records}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = inspect(args.root.resolve())
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2 if result["missing"] else 0
    except (ValueError, OSError, SyntaxError) as exc:
        print(json.dumps({"decision": "HALT_INVALID_MANIFEST", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
