#!/usr/bin/env python3
"""Periksa amplop self-send secara lokal sebelum operator memakai jalur kirim."""

import argparse
import json
import os
from pathlib import Path
import sys

# Skrip dapat dijalankan juga dari checkout tanpa paket terinstal.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ace_operational import self_send as _core


_CREDENTIAL_MARKERS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


def check_envelope(branch, *, merge_authority, environ):
    """Cek penanda env. Keabsahan token dan izin server berada di luar preflight."""
    valid_branch = (isinstance(branch, str) and branch == branch.strip()
                    and branch != "main" and _core.validate_branch_name(branch))
    credential = any(marker in environ for marker in _CREDENTIAL_MARKERS)
    checks = {
        "target_branch": {"passed": valid_branch,
                          "reason": "branch_allowed" if valid_branch else "branch_refused"},
        "merge_authority": {"passed": merge_authority is False,
                            "reason": "absent" if merge_authority is False else "not_absent"},
        "credential": {"passed": credential, "reason": "present" if credential else "absent"},
    }
    return {"mode": "dry_run", "passed": all(check["passed"] for check in checks.values()),
            "checks": checks}


def main(argv=None):
    args_list = list(sys.argv[1:] if argv is None else argv)
    if "--dry-run" not in args_list:
        return _core._main(args_list)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--merge-authority", action="store_true")
    args = parser.parse_args(args_list)
    result = check_envelope(args.branch, merge_authority=args.merge_authority, environ=os.environ)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
