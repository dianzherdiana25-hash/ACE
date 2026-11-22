"""Rakit panduan deploy manusia dari rilis terverifikasi dan rencana host.

Graf prasyarat menetapkan urutan pemeriksaan, backup, pemasangan dan
validasi. Setiap tindakan yang bisa mengubah host harus mempunyai
rollback bersumber. Generator tidak membaca host atau menjalankan langkah.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, obj, read, schema, text
from .docs_writer import escape


KINDS = ("preflight", "backup", "install", "activate", "verify")
MUTATING = {"install", "activate"}


def _steps(items):
    result = {}
    for row in entries(items, 60, minimum=4):
        obj(row, ("id", "kind", "requires", "action", "verify", "rollback", "source_ref"))
        key = identifier(row["id"], "ID langkah")
        kind = row["kind"]
        if key in result or kind not in KINDS:
            raise ContractError("Langkah ganda atau jenis tidak didukung.")
        dependencies = [identifier(dep, "Prasyarat") for dep in entries(row["requires"], 30)]
        if len(set(dependencies)) != len(dependencies) or key in dependencies:
            raise ContractError("Prasyarat berulang atau menunjuk ke diri sendiri.")
        action = text(row["action"], "Tindakan", 700)
        verification = text(row["verify"], "Verifikasi", 700)
        rollback = row["rollback"]
        if kind in MUTATING or rollback is not None:
            rollback = text(rollback, "Rollback", 700)
        result[key] = {"id": key, "kind": kind, "requires": sorted(dependencies),
                       "action": action, "verify": verification, "rollback": rollback,
                       "source_ref": text(row["source_ref"], "Rujukan langkah", 300)}
    if not {"preflight", "backup", "install", "verify"} <= {row["kind"] for row in result.values()}:
        raise ContractError("Panduan memerlukan preflight, backup, install, dan verifikasi.")
    return result


def _order(steps):
    pending = set(steps)
    order = []
    ancestors = {}
    for key, row in steps.items():
        if set(row["requires"]) - steps.keys():
            raise ContractError(f"Prasyarat hilang untuk {key}.")
        if any(KINDS.index(steps[dep]["kind"]) > KINDS.index(row["kind"]) for dep in row["requires"]):
            raise ContractError("Prasyarat melanggar urutan fase.")
    while pending:
        earliest = min(KINDS.index(steps[key]["kind"]) for key in pending)
        candidates = sorted(key for key in pending if KINDS.index(steps[key]["kind"]) == earliest
                            and not (set(steps[key]["requires"]) & pending))
        if not candidates:
            raise ContractError("Prasyarat membentuk siklus.")
        for key in candidates:
            row = steps[key]
            before = set(row["requires"])
            for dependency in row["requires"]:
                before.update(ancestors[dependency])
            ancestors[key] = before
            kinds = {steps[dependency]["kind"] for dependency in before}
            if row["kind"] == "backup" and "preflight" not in kinds:
                raise ContractError("Backup perlu preflight sebagai prasyarat.")
            if row["kind"] in MUTATING and not {"preflight", "backup"} <= kinds:
                raise ContractError("Perubahan host perlu preflight dan backup sebagai prasyarat.")
            if row["kind"] == "activate" and "install" not in kinds:
                raise ContractError("Aktivasi perlu pemasangan sebagai prasyarat.")
            if row["kind"] == "verify" and "install" not in kinds:
                raise ContractError("Verifikasi akhir perlu pemasangan sebagai prasyarat.")
            order.append(key)
        pending.difference_update(candidates)
    verified = set().union(*(ancestors[key] for key in order if steps[key]["kind"] == "verify"))
    if any(steps[key]["kind"] in MUTATING and key not in verified for key in steps):
        raise ContractError("Setiap perubahan host harus diikuti verifikasi akhir.")
    return [steps[key] for key in order]


def build(plan, release, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-deploy-plan.v1", ("release_sha256", "product_id", "target", "source_ref", "steps"))
    schema(release, "ace.factory-release-verification.v1", ("status", "zip_sha256", "manifest_sha256", "verified_files"))
    checked(release, plan["release_sha256"])
    if release["status"] != "verified":
        raise ContractError("Deploy guide membutuhkan rilis terverifikasi.")
    product = identifier(plan["product_id"], "Produk")
    target = text(plan["target"], "Target host", 150)
    source = text(plan["source_ref"], "Rujukan rencana", 300)
    archive = digest(release["zip_sha256"])
    order = _order(_steps(plan["steps"]))
    rollback = [row for row in reversed(order) if row["rollback"] is not None]
    lines = [f"# Panduan deploy {escape(product)}", "", f"Target **{escape(target)}**.",
             f"SHA-256 rilis `{archive}`.", f"Sumber {escape(source)}.", "", "## Langkah"]
    for index, step in enumerate(order, 1):
        deps = ", ".join(escape(name) for name in step["requires"]) or "awal"
        lines.extend(["", f"### {index}. {escape(step['id'])}", "", f"- Prasyarat {deps}.",
                      f"- Tindakan {escape(step['action'])}.", f"- Verifikasi {escape(step['verify'])}.",
                      f"- Sumber {escape(step['source_ref'])}."])
    lines.extend(["", "## Rollback", "", "Jalankan hanya langkah untuk perubahan yang sempat diterapkan."])
    for row in rollback:
        lines.append(f"- **{escape(row['id'])}** {escape(row['rollback'])} ({escape(row['source_ref'])}).")
    return "\n".join(lines) + "\n", {"schema": "ace.factory-deploy-guide.v1", "plan_sha256": expected,
                                       "release_zip_sha256": archive, "steps": order,
                                       "rollback_order": [row["id"] for row in rollback]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("release_verification", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        document, report = build(decode(read(args.plan)), decode(read(args.release_verification)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n" if args.json else document.encode())
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
