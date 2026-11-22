"""Uraikan tabel aturan aksi sederhana dengan kondisi deklaratif dan diagnostics baris."""
import re

from ._contracts import GuardianError, anchor, cli, items, schema, text

HEADER = re.compile(r"(allow|deny|review) ([a-z][a-z0-9_]{0,63}) ([a-z][a-z0-9_]{0,63})(?: if (.+))?")
CLAUSE = re.compile(r"([a-z][a-z0-9_]{0,63})=(true|false|[0-9]{1,7}|[a-z][a-z0-9_]{0,63})")

def parse_lines(lines):
    rows = []
    for number, raw in enumerate(items(lines, 1000, 1), 1):
        if isinstance(raw, str) and len(raw) <= 750 and not raw.strip():
            continue
        line = text(raw, "Aturan", 750).strip()
        if line.startswith("#"):
            continue
        match = HEADER.fullmatch(line)
        if not match:
            raise GuardianError(f"Grammar aturan salah pada baris {number}.")
        action, key, kind, condition = match.groups()
        checks = {}
        if condition:
            for clause in condition.split(" and "):
                pair = CLAUSE.fullmatch(clause)
                if not pair or pair[1] in checks:
                    raise GuardianError(f"Kondisi aturan tidak sah pada baris {number}.")
                token = pair[2]
                if token in ("true", "false"):
                    value = token == "true"
                elif token.isdecimal():
                    value = int(token)
                else:
                    value = token
                checks[pair[1]] = value
        rows.append({"rule": key, "effect": action, "kind": kind, "conditions": checks, "line": number})
    if not rows:
        raise GuardianError("Kebijakan tanpa satu aturan pun.")
    return rows

def parse(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.rule-text.v1", ("lines",))
    return {"rules": parse_lines(plan["lines"]), "source_sha256": expected}

if __name__ == "__main__":
    raise SystemExit(cli(parse, __doc__))
