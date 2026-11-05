"""Restore archived E1.4 public regression fixtures in a disposable Git snapshot."""

import argparse
import gzip
import json
import tarfile
from pathlib import Path

ARCHIVES = {
    "code/e14/e14e_frozen_source_2026-11-04.tar.gz": (
        "code/e14/e14e_bank.py",
        "code/e14/e14e_policy.py",
        "code/e14/e14e_run.py",
        "code/e14/test_e14e.py",
    ),
    "code/e14/e14f_frozen_source_2026-11-04.tar.xz": (
        "code/e14/e14f_bank.py",
        "code/e14/e14f_run.py",
        "code/e14/e14f_selector.py",
        "code/e14/e14f_audit.py",
        "code/e14/test_e14f_prescore.py",
        "design/e1.4/E14F_OPPORTUNITY_PRELOCK_v1.md",
    ),
}


def restore(snapshot):
    if (snapshot / ".git").exists():
        raise ValueError("use a disposable git archive snapshot")
    fixtures = {}
    for archive_path, names in ARCHIVES.items():
        with tarfile.open(snapshot / archive_path) as archive:
            if sorted(archive.getnames()) != sorted(names):
                raise ValueError(f"unexpected members in {archive_path}")
            for name in names:
                member = archive.getmember(name)
                if not member.isfile():
                    raise ValueError(f"expected an archived regular file: {name}")
                with archive.extractfile(member) as source:
                    fixtures[name] = source.read()

    for phase in ("d", "e", "f"):
        path = f"evidence/e14/e14{phase}_public_development_v1.json"
        fixtures[path] = gzip.decompress((snapshot / f"{path}.gz").read_bytes())

    for name, content in fixtures.items():
        target = snapshot / name
        if target.resolve() != target or target.exists() and target.read_bytes() != content:
            raise ValueError(f"refusing to overwrite a different fixture: {name}")
    for name, content in fixtures.items():
        (snapshot / name).write_bytes(content)
    return sorted(fixtures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    restored = restore(args.snapshot.resolve(strict=True))
    print(json.dumps({"status": "COMPLETE", "restored": restored}, sort_keys=True))


if __name__ == "__main__":
    main()
