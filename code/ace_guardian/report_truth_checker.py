"""Periksa nilai klaim pada dokumen bereferensi hash dan pointer JSON yang eksplisit."""
import re

from ._contracts import GuardianError, anchor, cli, decode, digest, identifier, identity, items, obj, schema
from ._snapshots import read_fixture, fingerprint

BAD = re.compile(r"~(?![01])")

def extract(raw, pointer):
    if not isinstance(pointer, str) or len(pointer) > 300 or (pointer != "" and not pointer.startswith("/")) or BAD.search(pointer):
        raise GuardianError("Pointer JSON tidak sah.")
    if not pointer:
        return raw
    for piece in pointer[1:].split("/"):
        if isinstance(raw, dict):
            raw = raw[piece.replace("~1", "/").replace("~0", "~")]
        elif isinstance(raw, list) and re.fullmatch(r"0|[1-9][0-9]{0,5}", piece):
            raw = raw[int(piece)]
        else:
            raise KeyError("Field klaim tidak ada di sumber.")
    return raw

def check(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.report-truth.v1", ("claims",))
    cache = {}
    results = []
    seen = set()
    for row in items(plan["claims"], 3000):
        obj(row, ("id", "path", "sha256", "pointer", "claims"))
        key = identifier(row["id"], "Klaim")
        sha = digest(row["sha256"])
        if key in seen:
            raise GuardianError("Klaim laporan ganda.")
        seen.add(key)
        source = {"path": row["path"], "sha256": sha, "pointer": row["pointer"]}
        if (row["path"], sha) not in cache:
            try:
                data = read_fixture(root, row["path"])
                cache[row["path"], sha] = (True, decode(data)) if fingerprint(data)["sha256"] == sha else (False, None)
            except (OSError, ValueError, TypeError, RecursionError):
                cache[row["path"], sha] = (False, None)
        valid, value = cache[row["path"], sha]
        status = "unsupported"
        if valid:
            try:
                actual = extract(value, row["pointer"])
            except (KeyError, IndexError):
                status = "pointer_missing"
            else:
                status = "supported" if identity(actual) == identity(row["claims"]) else "contradicted"
        results.append({"id": key, "status": status, "source": source})
    return {"examined": len(results), "supported": sum(row["status"] == "supported" for row in results), "claims": results}

if __name__ == "__main__":
    raise SystemExit(cli(check, __doc__, rooted=True))
