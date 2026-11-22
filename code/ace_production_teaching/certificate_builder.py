"""Buat sertifikat draf untuk peserta dengan persetujuan dan capaian yang tertambat."""
import argparse
from pathlib import Path
import sys

from ._artifacts import evidence
from ._contracts import (ProductionError, anchor, canonical, day, decode, identifier,
                         identity, integer, items, obj, read, schema, source_bytes, text)
from .document_builder import make_document


def certify(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.certificate-plan.v1", ("course", "issuer", "date", "passing_bp", "participants", "formats"))
    course = text(plan["course"], "Nama kursus", 100)
    issuer = text(plan["issuer"], "Penyelenggara", 90)
    stamp = day(plan["date"])
    threshold = integer(plan["passing_bp"], "Ambang capaian", 1, 10000)
    results = {}
    passes = []
    holds = []
    seen = set()
    formats = plan["formats"]
    for row in items(plan["participants"], 80, 1):
        obj(row, ("id", "display_label", "authorized", "achievement"))
        key = identifier(row["id"], "ID penerima")
        if key in seen or type(row["authorized"]) is not bool:
            raise ProductionError("Peserta ganda atau persetujuan tidak sah.")
        seen.add(key)
        if not row["authorized"]:
            holds.append({"id": key, "reason": "label_not_authorized"})
            continue
        recipient = text(row["display_label"], "Label pada sertifikat", 120)
        ref = obj(row["achievement"], ("path", "sha256"))
        result = decode(source_bytes(root, ref["path"], ref["sha256"], 160000))
        schema(result, "ace.production.course-proof.v1", ("id", "course", "score_bp", "completed", "source_ref"))
        if result["id"] != key or result["course"] != course or day(result["completed"]) > stamp:
            raise ProductionError("Bukti peserta, kursus, atau tanggal tidak sesuai.")
        score = integer(result["score_bp"], "Skor receipt", 0, 10000)
        proof = text(result["source_ref"], "Pointer capaian")
        if score < threshold:
            holds.append({"id": key, "reason": "below_passing_score", "achievement_sha256": ref["sha256"]})
            continue
        draft = {"schema": "ace.production.document-plan.v1", "title": "Sertifikat Penyelesaian",
                 "formats": formats, "bindings": [], "blocks": [
                    {"kind": "heading", "level": 1, "body": recipient},
                    {"kind": "paragraph", "body": f"Menyelesaikan {course}."},
                    {"kind": "paragraph", "body": f"{issuer} · {stamp.isoformat()}"},
                    {"kind": "paragraph", "body": f"Rujukan capaian {proof}"}]}
        data, _ = make_document(draft, identity(draft))
        for name, payload in data.items():
            results[key + "." + name.rsplit(".", 1)[-1]] = payload
        passes.append({"id": key, "achievement_sha256": ref["sha256"], "source_ref": proof})
    return results, {"schema": "ace.production.certificate-draft.v1", "plan_sha256": expected,
                     "state": "local_draft", "certified": sorted(passes, key=lambda row: row["id"]),
                     "held": sorted(holds, key=lambda row: row["id"]), "artifacts": evidence(results)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = certify(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for key, payload in files.items():
            (args.output / key).write_bytes(payload)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
