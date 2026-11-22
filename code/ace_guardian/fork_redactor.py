"""Redaksi fixture menurut daftar path dan pola nama umum tanpa mengeluarkan isi bidang sensitif."""
import re

from ._contracts import GuardianError, anchor, cli, items, schema, text

REDACTED = "[redacted]"
SENSITIVE = re.compile(r"^(?:secret|token|password|passwd|private_key|api_key|access_key|auth(?:orization)?|credentials?)$",
                       re.IGNORECASE)
POINTER = re.compile(r"/(?:[A-Za-z0-9_/-]|~[01]){1,300}")

def redact(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.fork-redaction.v1", ("snapshot", "fields"))
    paths = {item for item in items(plan["fields"], 300, 1) if isinstance(item, str)}
    if len(paths) != len(plan["fields"]) or any(not POINTER.fullmatch(path) for path in paths):
        raise GuardianError("Pointer redaksi duplikat atau di luar grammar.")
    matched = set()
    stats = {"explicit": 0, "sensitive_name": 0}
    remaining = 20000

    def walk(value, path, depth):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 35:
            raise GuardianError("Fixture redaksi melewati batas struktur.")
        if path in paths:
            matched.add(path)
            stats["explicit"] += 1
            return REDACTED
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                text(key, "Nama field", 200)
                pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
                if SENSITIVE.fullmatch(key):
                    if pointer in paths:
                        matched.add(pointer)
                        stats["explicit"] += 1
                    else:
                        stats["sensitive_name"] += 1
                    result[key] = REDACTED
                else:
                    result[key] = walk(item, pointer, depth + 1)
            return result
        if isinstance(value, list):
            return [walk(item, f"{path}/{index}", depth + 1) for index, item in enumerate(value)]
        return value
    snapshot = walk(plan["snapshot"], "", 0)
    if matched != paths:
        raise GuardianError("Ada penunjuk redaksi yang tidak ditemukan.")
    return {"snapshot": snapshot, "counts": stats}

if __name__ == "__main__":
    raise SystemExit(cli(redact, __doc__))
