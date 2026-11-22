"""Bagi log fixture berurutan menjadi arsip hari lama dan log aktif yang dapat diverifikasi."""
from collections import defaultdict
from datetime import timedelta
import gzip
import io

from ._contracts import GuardianError, anchor, cli, day, decode, integer, obj, schema, source_bytes, text
from ._snapshots import fingerprint
from .snapshot_scheduler import instant

def split(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.rotate-log.v1", ("source", "as_of", "active_days"))
    today = day(plan["as_of"])
    width = integer(plan["active_days"], "Hari aktif", 1, 90)
    threshold = today - timedelta(days=width - 1)
    ref = obj(plan["source"], ("path", "sha256"))
    raw = source_bytes(root, ref["path"], ref["sha256"], 1_000_000)
    partitions = defaultdict(list)
    last = None
    for line in raw.splitlines():
        row = obj(decode(line), ("at", "kind", "message"))
        stamp = instant(row["at"])
        if stamp.date() > today or (last is not None and stamp < last):
            raise GuardianError("Urutan log mendahului data sebelumnya atau melewati hari laporan.")
        text(row["kind"], "Kategori log", 60)
        text(row["message"], "Pesan log", 1500)
        last = stamp
        group = "active" if stamp.date() >= threshold else stamp.date().isoformat()
        partitions[group].append(line + b"\n")
    result = {}
    for group, lines in sorted(partitions.items()):
        joined = b"".join(lines)
        if group == "active":
            blob = joined
        else:
            sink = io.BytesIO()
            with gzip.GzipFile(filename="", fileobj=sink, mode="wb", mtime=0) as stream:
                stream.write(joined)
            blob = sink.getvalue()
        result[group] = blob
    return result

def manifest(plan, expected, root):
    data = split(plan, expected, root)
    return {"source": plan["source"], "partitions": [
        {"name": name, "encoding": "jsonl" if name == "active" else "gzip_jsonl", **fingerprint(raw)}
        for name, raw in data.items()]}

if __name__ == "__main__":
    raise SystemExit(cli(manifest, __doc__, rooted=True))
