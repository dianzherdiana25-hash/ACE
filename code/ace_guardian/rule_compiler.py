"""Kompilasi DSL dengan tipe action tetap, urutan fail-closed, serta deteksi aturan ganda."""
from ._contracts import GuardianError, anchor, cli, identifier, identity, items, obj, schema
from .rule_dsl import parse_lines

ORDER = {"deny": 0, "review": 1, "allow": 2}
TYPE = {"bool": bool, "int": int, "label": str}

def compile_rules(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.compile-rules.v1", ("revision", "actions", "lines"))
    revision = identifier(plan["revision"], "Versi kebijakan")
    catalog = {}
    for entry in items(plan["actions"], 100, 1):
        obj(entry, ("kind", "fields"))
        key = identifier(entry["kind"], "Kelas aksi")
        if key in catalog or not isinstance(entry["fields"], dict) or len(entry["fields"]) > 40:
            raise GuardianError("Kelas aksi ganda atau bentuk field tidak sah.")
        fields = {}
        for field, kind in entry["fields"].items():
            if kind not in TYPE:
                raise GuardianError("Tipe field aksi tidak didukung.")
            fields[identifier(field, "Field aksi")] = kind
        catalog[key] = fields
    compiled = {kind: [] for kind in catalog}
    used = set()
    signatures = set()
    for row in parse_lines(plan["lines"]):
        key, effect, kind, checks = (row[name] for name in ("rule", "effect", "kind", "conditions"))
        if key in used or kind not in catalog:
            raise GuardianError("Aturan ganda atau kelas aksi tidak dikenal.")
        used.add(key)
        if any(field not in catalog[kind] or TYPE[catalog[kind][field]] is not type(value) for field, value in checks.items()):
            raise GuardianError("Kondisi DSL tidak cocok dengan tipe aksi.")
        signature = (kind, effect, identity(checks))
        if signature in signatures:
            raise GuardianError("Dua aturan memiliki cakupan dan dampak yang identik.")
        signatures.add(signature)
        compiled[kind].append(row)
    for kind, rules in compiled.items():
        rules.sort(key=lambda row: (ORDER[row["effect"]], -len(row["conditions"]), row["rule"]))
    output = {"schema": "ace.guardian.compiled-rules.v1", "revision": revision,
              "catalog": catalog, "by_kind": compiled, "source_sha256": expected}
    return {**output, "compiled_sha256": identity(output)}

if __name__ == "__main__":
    raise SystemExit(cli(compile_rules, __doc__))
