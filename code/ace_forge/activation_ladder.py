"""Rekonstruksi persetujuan satu artefak secara berjenjang dari receipt.

Resep menyebut tahap, peran wajib, artefak, dan hash bukti per tahap.
Receipt harus masuk pada tahap saat ini dan memakai bukti tersebut.
Penolakan menutup jalur persetujuan. Report untuk telaah manusia
mencatat keputusan yang dideklarasikan oleh sumber tertambat.
"""
import argparse
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string, utc_stamp
from .adapter_zoo import tags
from .dataset_forge import MAX_BYTES


MAX_LEVELS = 32
MAX_RECEIPTS = 2048


def _policy(raw, expected):
    object_fields(raw, ("policy_ref", "artifact_sha256", "stages"))
    if identity(raw) != digest(expected):
        raise InputError("Kebijakan aktivasi berbeda dari anchor.")
    policy_ref = string(raw["policy_ref"], "rujukan kebijakan")
    key = digest(raw["artifact_sha256"])
    stages = []
    names = set()
    for row in entries(raw["stages"], MAX_LEVELS):
        object_fields(row, ("stage", "roles", "evidence_sha256"))
        label = string(row["stage"], "nama tahap")
        if label in names:
            raise InputError("Nama tahap ganda.")
        names.add(label)
        stages.append({"stage": label, "roles": tags(row["roles"], "peran wajib"),
                       "evidence_sha256": digest(row["evidence_sha256"]), "votes": {}, "status": "waiting"})
    if not stages:
        raise InputError("Kebijakan aktivasi tanpa tahap.")
    return policy_ref, key, stages


def evaluate(raw, history, expected, expected_history):
    policy_ref, key, stages = _policy(raw, expected)
    object_fields(history, ("ledger_ref", "events"))
    if identity(history) != digest(expected_history):
        raise InputError("Ledger aktivasi berbeda dari anchor.")
    source = string(history["ledger_ref"], "rujukan ledger")
    index = 0
    stopped = False
    refs = {policy_ref, source}
    previous = None
    for sequence, row in enumerate(entries(history["events"], MAX_RECEIPTS), 1):
        object_fields(row, ("stage", "role", "at", "artifact_sha256", "evidence_sha256",
                            "decision", "receipt_ref"))
        stamp = utc_stamp(row["at"])
        receipt = string(row["receipt_ref"], "rujukan receipt")
        name = string(row["stage"], "nama tahap receipt")
        role = string(row["role"], "peran receipt")
        decision = row["decision"]
        if (receipt in refs or previous is not None and stamp < previous
                or digest(row["artifact_sha256"]) != key or decision not in ("approve", "reject")):
            raise InputError(f"Receipt {sequence} ganda, mundur, atau tidak cocok dengan artefak/putusan.")
        if stopped or index == len(stages):
            raise InputError(f"Receipt {sequence} muncul sesudah hasil terminal.")
        level = stages[index]
        if (name != level["stage"] or role not in level["roles"] or role in level["votes"]
                or digest(row["evidence_sha256"]) != level["evidence_sha256"]):
            raise InputError(f"Receipt {sequence} melompati tahap atau tidak cocok dengan peran/bukti.")
        refs.add(receipt)
        level["votes"][role] = {"role": role, "at": stamp.isoformat(), "receipt_ref": receipt, "decision": decision}
        previous = stamp
        if decision == "reject":
            stopped = True
            level["status"] = "rejected"
        elif len(level["votes"]) == len(level["roles"]):
            level["status"] = "approved"
            index += 1
        else:
            level["status"] = "collecting"
    result = []
    for row in stages:
        votes = row["votes"]
        result.append({**row, "votes": [votes[role] for role in sorted(votes)],
                       "missing_roles": [role for role in row["roles"] if role not in votes]})
    return {"schema": "ace.forge-activation-ladder.v1", "artifact_sha256": key, "policy_ref": policy_ref,
            "policy_sha256": expected, "ledger_ref": source, "ledger_sha256": expected_history,
            "approved_stages": index, "total_stages": len(stages),
            "status": "rejected" if stopped else "approvals_complete" if index == len(stages) else "pending",
            "pending_stage": stages[index]["stage"] if not stopped and index < len(stages) else None, "stages": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--expect-policy-sha256", required=True)
    parser.add_argument("--expect-ledger-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        product = evaluate(decode(read_bytes(args.policy, MAX_BYTES)), decode(read_bytes(args.ledger, MAX_BYTES)),
                           args.expect_policy_sha256, args.expect_ledger_sha256)
        sys.stdout.write(canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(product["status"] != "approvals_complete")


if __name__ == "__main__":
    raise SystemExit(main())
