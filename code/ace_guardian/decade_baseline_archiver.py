"""Bentuk arsip baseline byte-identik dari daftar manifest tetap tanpa mengambil state dari jalur hidup."""
from io import BytesIO
import gzip
import tarfile

from ._contracts import anchor, cli, identity, schema
from ._snapshots import fingerprint, verify

def archive(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.archive-baseline.v1", ("manifest",))
    selected = verify(root, plan["manifest"])
    stream = BytesIO()
    with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
            for name, data in sorted(selected.items()):
                entry = tarfile.TarInfo("fixture/" + name)
                entry.mode, entry.mtime, entry.size = 0o600, 0, len(data)
                target.addfile(entry, BytesIO(data))
    return stream.getvalue()

def report(plan, expected, root):
    data = archive(plan, expected, root)
    return {"encoding": "tar+gzip", "custody": identity(plan["manifest"]), **fingerprint(data)}

if __name__ == "__main__":
    raise SystemExit(cli(report, __doc__, rooted=True))
