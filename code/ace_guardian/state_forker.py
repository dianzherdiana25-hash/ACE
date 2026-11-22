"""Fork snapshot fixture memakai byte tervalidasi dan inode terpisah untuk menahan perubahan silang."""
import argparse
from pathlib import Path
import shutil
import sys

from ._contracts import GuardianError, anchor, canonical, decode, read
from ._snapshots import verify, write_new

def fork(source, destination, manifest, expected):
    anchor(manifest, expected)
    original = source.resolve(strict=True)
    target = destination.parent.resolve(strict=True) / destination.name
    if original == target or original in target.parents or target in original.parents:
        raise GuardianError("Sumber dan tujuan fork harus terpisah dan sejajar.")
    if source.is_symlink() or not original.is_dir():
        raise GuardianError("Root fixture harus direktori nyata.")
    staged = verify(original, manifest)
    target.mkdir(mode=0o700, exist_ok=False)
    try:
        for name, data in sorted(staged.items()):
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_new(path, data)
        verify(target, manifest, reject_extras=True)
    except (OSError, ValueError):
        shutil.rmtree(target)
        raise
    return {"status": "forked", "manifest_sha256": expected, "files": len(staged),
            "bytes": sum(len(data) for data in staged.values())}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = decode(read(args.manifest))
        result = fork(args.source, args.destination, manifest, args.expect_sha256)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Error: {error}\n")
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
