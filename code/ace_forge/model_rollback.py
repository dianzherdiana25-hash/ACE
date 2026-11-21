"""Susun selector rollback dari registry dan riwayat lokal tertambat.

Riwayat kandidat dicoba dari versi terdahulu terdekat. Versi terpilih
harus berstatus qualified pada domain yang sama dan byte artefaknya
cocok dengan SHA-256. Program menghasilkan selector usulan serta
receipt diagnostik. Penggantian selector live tetap pada pemanggil.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys

from . import model_registry_v2
from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_STEPS = 25_000
MAX_ARTIFACT_BYTES = 32 * 2**30


def _hash_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _verify_bytes(root, relative, expected):
    parts = relative.split("/")
    if not all(part and part not in (".", "..") and "\\" not in part for part in parts):
        return "invalid_artifact_path"
    parent = descriptor = None
    try:
        directory_flags = os.O_NOFOLLOW | os.O_RDONLY | os.O_DIRECTORY
        parent = os.open(root, directory_flags)
        for part in parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=parent)
            os.close(parent)
            parent = next_fd
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_ARTIFACT_BYTES:
            return "artifact_type_or_size"
        hasher = hashlib.sha256()
        observed = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            observed += len(chunk)
            if observed > before.st_size:
                return "artifact_read_changed"
            hasher.update(chunk)
        after = os.fstat(descriptor)
        named = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        if observed != before.st_size or _hash_identity(before) != _hash_identity(after) or _hash_identity(after) != _hash_identity(named):
            return "artifact_read_changed"
        return None if hasher.hexdigest() == expected else "artifact_sha256_mismatch"
    except FileNotFoundError:
        return "artifact_missing"
    except OSError:
        return "artifact_unreadable_or_unsafe"
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def _selector(raw, expected):
    object_fields(raw, ("selector_ref", "domain", "generation", "active_sha256", "history"))
    if identity(raw) != digest(expected):
        raise InputError("Selector berbeda dari anchor.")
    selector_ref = string(raw["selector_ref"], "rujukan selector")
    domain = string(raw["domain"], "domain selector")
    generation = integer(raw["generation"], 1, MAX_STEPS - 1)
    active = digest(raw["active_sha256"])
    earlier = 0
    history = []
    refs = {selector_ref}
    for row in entries(raw["history"], MAX_STEPS):
        object_fields(row, ("generation", "artifact_sha256", "activation_ref"))
        count = integer(row["generation"], earlier + 1, generation)
        earlier = count
        history.append({"generation": count, "artifact_sha256": digest(row["artifact_sha256"]),
                        "activation_ref": reference(row["activation_ref"], refs, "rujukan aktivasi")})
    if not history or history[-1]["generation"] != generation or history[-1]["artifact_sha256"] != active:
        raise InputError("Aktivasi terakhir tidak cocok dengan selector.")
    return selector_ref, refs, domain, generation, active, history


def plan(selector, expected_selector, records, registry_head, request, artifact_root):
    ref, refs, domain, generation, active, history = _selector(selector, expected_selector)
    object_fields(request, ("request_ref", "reason_ref", "from_artifact_sha256"))
    requested = reference(request["request_ref"], refs, "rujukan rollback")
    reason = reference(request["reason_ref"], refs, "alasan rollback")
    if digest(request["from_artifact_sha256"]) != active:
        raise InputError("Rollback diarahkan ke artefak aktif yang berbeda.")
    registry = model_registry_v2.inspect(records, registry_head)
    known = {item["sha256"]: item for item in registry["artifacts"]}
    candidates, tried = [], {active}
    selected = None
    for row in reversed(history):
        key = row["artifact_sha256"]
        if key in tried:
            continue
        tried.add(key)
        item = known.get(key)
        if item is None:
            failure = "not_registered"
        elif item["status"] != "qualified":
            failure = "not_qualified"
        elif item["domain"] != domain:
            failure = "wrong_domain"
        else:
            failure = _verify_bytes(artifact_root, item["artifact_ref"], key)
        scanned = {**row, "artifact_ref": item["artifact_ref"] if item is not None else None,
                   "blocker": failure, "review_ref": item["review"]["result_ref"] if item and item["review"] else None}
        candidates.append(scanned)
        if failure is None:
            selected = scanned
            break

    next_selector = None
    if selected is not None:
        next_selector = {"selector_ref": ref, "domain": domain, "generation": generation + 1,
                         "active_sha256": selected["artifact_sha256"], "history": [
                             *history, {"generation": generation + 1, "artifact_sha256": selected["artifact_sha256"],
                                        "activation_ref": requested},
                         ]}
    return {"schema": "ace.forge-rollback-plan.v1", "request_ref": requested, "reason_ref": reason,
            "request_sha256": identity(request),
            "based_on_selector_sha256": expected_selector, "registry_head_sha256": registry_head,
            "status": "ready" if selected is not None else "hold", "from_artifact_sha256": active,
            "selected": selected, "candidates_checked": candidates, "proposed_selector": next_selector,
            "proposed_selector_sha256": identity(next_selector) if next_selector is not None else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selector", type=Path)
    parser.add_argument("registry", type=Path)
    parser.add_argument("request", type=Path)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("--expect-selector-sha256", required=True)
    parser.add_argument("--expect-registry-head", required=True)
    args = parser.parse_args(argv)
    try:
        result = plan(decode(read_bytes(args.selector, MAX_BYTES)), args.expect_selector_sha256,
                      model_registry_v2._load(args.registry), args.expect_registry_head,
                      decode(read_bytes(args.request, MAX_BYTES)), args.artifacts)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
