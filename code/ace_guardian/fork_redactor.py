"""Redaksi fixture menurut daftar path dan pola nama umum tanpa mengeluarkan isi bidang sensitif."""
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from ._contracts import GuardianError, anchor, canonical, cli, decode, identity, items, schema, text
from ._snapshots import build_manifest, verify, write_new
from .state_forker import fork

REDACTED = "[redacted]"
SENSITIVE = re.compile(r"^(?:secret|token|password|passwd|private_key|api_key|access_key|auth(?:orization)?|credentials?)$",
                       re.IGNORECASE)
POINTER = re.compile(r"/(?:[A-Za-z0-9_/-]|~[01]){1,300}")

def redact(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.fork-redaction.v1", ("snapshot", "fields"))
    paths = {item for item in items(plan["fields"], 300) if isinstance(item, str)}
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

def fork_clean(plan, expected, source, destination):
    """Tulis snapshot JSON fixture baru setelah redaksi lolos untuk semua berkas."""
    anchor(plan, expected)
    schema(plan, "ace.guardian.redacted-fork.v1", ("manifest", "redact_fields"))
    if source.is_symlink():
        raise GuardianError("Fork teredaksi memerlukan root fixture nyata.")
    origin = source.resolve(strict=True)
    target = destination.parent.resolve(strict=True) / destination.name
    if origin == target or origin in target.parents or target in origin.parents:
        raise GuardianError("Tujuan fork teredaksi harus berada di luar sumber.")
    data = verify(origin, plan["manifest"], reject_extras=True)
    fields = plan["redact_fields"]
    if not isinstance(fields, dict) or fields.keys() != data.keys():
        raise GuardianError("Izin redaksi harus ditetapkan untuk setiap berkas snapshot.")
    emitted, counts = {}, {}
    for name, raw in sorted(data.items()):
        config = {"schema": "ace.guardian.fork-redaction.v1", "snapshot": decode(raw), "fields": fields[name]}
        report = redact(config, identity(config))
        emitted[name] = canonical(report["snapshot"]) + b"\n"
        counts[name] = report["counts"]
    with TemporaryDirectory(prefix="ace-guardian-redacted-") as tmp:
        stage = Path(tmp)
        for name, value in emitted.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_new(path, value)
        manifest = build_manifest(stage, sorted(emitted))
        record = fork(stage, destination, manifest, identity(manifest))
    return {**record, "redacted_manifest": manifest, "redaction_counts": counts}


if __name__ == "__main__":
    raise SystemExit(cli(redact, __doc__))
