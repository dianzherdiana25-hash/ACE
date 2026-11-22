"""Uji kombinasi fakta fixture untuk mencari izin yang bertabrakan dengan invarian kebijakan."""
from itertools import product

from ._contracts import GuardianError, anchor, cli, identifier, identity, integer, items, obj, schema
from .action_gate import decide
from .rule_compiler import TYPE, compile_rules

def probe(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.policy-probe.v1", ("policy", "invariants", "domains", "case_limit"))
    table = compile_rules(plan["policy"], identity(plan["policy"]))
    limit = integer(plan["case_limit"], "Batas produk kasus", 1, 5000)
    domain = {}
    for row in items(plan["domains"], 200):
        obj(row, ("kind", "field", "values"))
        kind = identifier(row["kind"], "Kelas aksi")
        field = identifier(row["field"], "Field")
        key = (kind, field)
        fields = table["catalog"].get(kind, {})
        if field not in fields or key in domain:
            raise GuardianError("Domain field ganda atau belum terdaftar.")
        values = items(row["values"], 20, 1)
        expected_type = TYPE[fields[field]]
        if any(type(value) is not expected_type for value in values) or len(set(values)) != len(values):
            raise GuardianError("Domain probe duplikat atau tipe salah.")
        if expected_type is int:
            values = [integer(value, "Domain numerik", 0, 9_999_999) for value in values]
        if expected_type is str:
            values = [identifier(value, "Label domain") for value in values]
        domain[key] = values
    rules = {}
    for data in items(plan["invariants"], 500, 1):
        obj(data, ("id", "kind", "when", "must_not"))
        label = identifier(data["id"], "Invarian")
        kind = identifier(data["kind"], "Kelas aksi")
        if label in rules or kind not in table["catalog"] or data["must_not"] not in ("allow", "deny", "review"):
            raise GuardianError("Invarian duplikat, di luar tipe, atau larangan tidak sah.")
        facts = data["when"]
        if not isinstance(facts, dict) or any(
            field not in table["catalog"][kind] or type(value) is not TYPE[table["catalog"][kind][field]]
            for field, value in facts.items()
        ):
            raise GuardianError("Kondisi invarian salah.")
        rules[label] = data
    observed = {key: 0 for key in rules}
    hits = []
    examined = 0
    for kind, fields in sorted(table["catalog"].items()):
        chosen = [(key, row) for key, row in rules.items() if row["kind"] == kind]
        if not chosen:
            continue
        keys = sorted(fields)
        values = [domain.get((kind, key), [False, True] if fields[key] == "bool" else []) for key in keys]
        if any(not values_for_field for values_for_field in values):
            raise GuardianError("Domain nonboolean perlu disebutkan untuk kelas yang diaudit.")
        for combination in product(*values):
            examined += 1
            if examined > limit:
                raise GuardianError("Kasus invarian melebihi batas, persempit domain eksplisit.")
            facts = dict(zip(keys, combination))
            check = decide({"id": f"case_{examined}", "kind": kind, "facts": facts}, table)
            for key, row in chosen:
                if all(facts[field] == value for field, value in row["when"].items()):
                    observed[key] += 1
                    if check["outcome"] == row["must_not"]:
                        hits.append({"invariant": key, "facts": facts, "decision": check})
    untested = sorted(key for key, count in observed.items() if count == 0)
    return {"tested": examined, "invariant_counts": observed, "violations": hits, "untested": untested,
            "passed": not hits and not untested}

if __name__ == "__main__":
    raise SystemExit(cli(probe, __doc__))
