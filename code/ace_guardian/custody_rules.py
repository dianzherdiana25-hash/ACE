"""Nyatakan pagar program dalam DSL yang sama agar daftar aksi tertutup bisa diaudit."""
from ._contracts import anchor, cli, identity, schema
from .rule_compiler import compile_rules

CLASSES = {
    "local_read": {"verified": "bool", "sealed": "bool"},
    "fixture_copy": {"verified": "bool", "isolated": "bool"},
    "external_send": {"approval": "bool"},
    "publication": {"approval": "bool"},
    "money": {"approval": "bool"},
    "main_merge": {"approval": "bool"},
    "locked_write": {"approval": "bool"},
    "memory_write": {"approval": "bool"},
}
RULES = (
    "deny preserve_sealed local_read if sealed=true",
    "allow read_verified local_read if verified=true and sealed=false",
    "review review_fixture fixture_copy if verified=false",
    "allow isolated_fixture fixture_copy if verified=true and isolated=true",
    "deny external_custody external_send",
    "deny publication_custody publication",
    "deny financial_custody money",
    "deny no_main_merge main_merge",
    "deny locked_custody locked_write",
    "deny memory_custody memory_write",
)

def policy_data():
    return {"schema": "ace.guardian.compile-rules.v1", "revision": "fixture_custody_v1",
            "actions": [{"kind": key, "fields": dict(fields)} for key, fields in CLASSES.items()], "lines": list(RULES)}

def standing(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.custody.v1", ())
    data = policy_data()
    return compile_rules(data, identity(data))

if __name__ == "__main__":
    raise SystemExit(cli(standing, __doc__))
