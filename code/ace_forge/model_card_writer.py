"""Buat kartu artefak tempa dengan profil, sumber, dan observasi lokal.

Rujukan pemakaian dan batas berasal dari metadata yang disediakan.
Tabel hasil diputar ulang dari input bench yang dikomit. Bagian
pengukuran menampilkan gap ketika catatan belum tersedia, sehingga
angka tanpa pasangan tidak menjadi klaim kemampuan.
"""
import argparse
from fractions import Fraction
from html import escape
from pathlib import Path
import sys

from . import brain_bench
from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


STATUS = {"registered", "qualified", "rejected", "retired"}
FORMATS = {"dense_adapter", "linear_preference_adapter", "weights_snapshot", "other"}


def _notes(raw):
    result, refs = [], set()
    for row in entries(raw, 50):
        object_fields(row, ("text", "ref"))
        result.append({"text": string(row["text"], "catatan", max_chars=4000),
                       "ref": reference(row["ref"], refs, "rujukan catatan")})
    return result


def _datasets(raw, refs):
    result, seen = [], set()
    for row in entries(raw, 100):
        object_fields(row, ("head_sha256", "dataset_ref", "train", "held_out", "license_audit_ref"))
        key = digest(row["head_sha256"])
        if key in seen:
            raise InputError("Dataset tempa ganda.")
        seen.add(key)
        result.append({
            "head_sha256": key, "dataset_ref": reference(row["dataset_ref"], refs, "rujukan dataset"),
            "train": integer(row["train"], 0, 10**9), "held_out": integer(row["held_out"], 0, 10**9),
            "license_audit_ref": reference(row["license_audit_ref"], refs, "rujukan audit lisensi")
            if row["license_audit_ref"] is not None else None,
        })
    return sorted(result, key=lambda row: row["head_sha256"])


def _registry(raw, artifact, refs):
    if raw is None:
        return None
    object_fields(raw, ("ref", "artifact_sha256", "status"))
    status = string(raw["status"], "status registry")
    if digest(raw["artifact_sha256"]) != artifact or status not in STATUS:
        raise InputError("Status registry tidak cocok dengan artefak kartu.")
    return {"ref": reference(raw["ref"], refs, "rujukan registry"), "status": status}


def _evaluation(raw, artifact, refs):
    if raw is None:
        return None
    object_fields(raw, ("ref", "input", "bench_sha256"))
    result = brain_bench.report(raw["input"], raw["bench_sha256"])
    if result["after_sha256"] != artifact:
        raise InputError("Penilaian bench merujuk artefak berbeda.")
    return {
        "ref": reference(raw["ref"], refs, "rujukan bench"), "protocol_ref": result["protocol_ref"],
        "rubric_ref": result["rubric_ref"], "baseline_sha256": result["before_sha256"],
        "bench_sha256": result["bench_sha256"],
        "domains": [{
            "domain": domain["domain"], "status": domain["status"], "registered": domain["registered"],
            "compared": domain["compared"],
            "baseline_score_bp": domain["before_mean"]["score_bp"] if domain["before_mean"] is not None else None,
            "artifact_score_bp": domain["after_mean"]["score_bp"] if domain["after_mean"] is not None else None,
            "score_delta_bp": domain["mean_delta"]["score_bp"] if domain["mean_delta"] is not None else None,
        } for domain in result["domains"]],
    }


def compose(raw, expected):
    object_fields(raw, ("artifact", "training", "intended_use", "limitations", "registry", "benchmark"))
    if identity(raw) != digest(expected):
        raise InputError("Sumber kartu berbeda dari anchor.")
    in_card = raw["artifact"]
    object_fields(in_card, ("id", "sha256", "format", "source_ref", "license", "parents"))
    artifact = digest(in_card["sha256"])
    ref = string(in_card["source_ref"], "rujukan artefak")
    kind = string(in_card["format"], "format artefak")
    if kind not in FORMATS:
        raise InputError("Format artefak kartu tidak dikenal.")
    parents = [digest(value) for value in entries(in_card["parents"], 12)]
    if artifact in parents or len(set(parents)) != len(parents):
        raise InputError("Lineage kartu memuat parent ganda atau artefak sendiri.")
    metadata = {
        "id": string(in_card["id"], "ID artefak"), "sha256": artifact, "source_ref": ref, "format": kind,
        "license": string(in_card["license"], "lisensi artefak") if in_card["license"] is not None else None,
        "parents": sorted(parents),
    }
    training = raw["training"]
    refs = {ref}
    if training is not None:
        object_fields(training, ("recipe_ref", "receipt_ref", "datasets"))
        training = {"recipe_ref": reference(training["recipe_ref"], refs, "rujukan resep"),
                    "receipt_ref": reference(training["receipt_ref"], refs, "rujukan receipt"),
                    "datasets": _datasets(training["datasets"], refs)}
    return {"schema": "ace.forge-model-card.v1", "input_sha256": expected, "artifact": metadata,
            "training": training, "intended_use": _notes(raw["intended_use"]), "limitations": _notes(raw["limitations"]),
            "registry": _registry(raw["registry"], artifact, refs), "benchmark": _evaluation(raw["benchmark"], artifact, refs)}


SPECIALS = str.maketrans({symbol: f"&#{ord(symbol)};" for symbol in "|[]`#_*\\"})


def _text(value):
    return escape(" ".join(value.split()), quote=False).translate(SPECIALS)


def _ratio(raw):
    if raw is None:
        return "TIDAK TAHU"
    value = Fraction(**raw)
    return str(value)


def markdown(card):
    artifact = card["artifact"]
    lines = [f"# Kartu artefak {_text(artifact['id'])}", "", f"- SHA-256 `{artifact['sha256']}`",
             f"- Format `{artifact['format']}`", f"- Lisensi {_text(artifact['license'] or 'TIDAK TAHU')}",
             f"- Sumber artefak {_text(artifact['source_ref'])}"]
    if artifact["parents"]:
        lines.append("- Parent SHA-256 " + ", ".join(f"`{key}`" for key in artifact["parents"]))
    registry = card["registry"]
    if registry is not None:
        lines.append(f"- Status registry `{registry['status']}`. Sumber {_text(registry['ref'])}.")
    for key, name in (("intended_use", "Pemakaian yang dimaksud"), ("limitations", "Batas penggunaan")):
        lines += ["", f"## {name}", ""]
        lines += [f"- {_text(row['text'])} Sumber {_text(row['ref'])}." for row in card[key]] or ["TIDAK TAHU."]
    lines += ["", "## Data dan resep", ""]
    training = card["training"]
    if training is None:
        lines.append("TIDAK TAHU. Receipt pelatihan belum disertakan.")
    else:
        lines.append(f"Resep {_text(training['recipe_ref'])}. Receipt {_text(training['receipt_ref'])}.")
        for data in training["datasets"]:
            license_ref = _text(data["license_audit_ref"] or "TIDAK TAHU")
            lines.append(f"- Train {data['train']}, held-out {data['held_out']}. Head `{data['head_sha256']}`. "
                         f"Audit lisensi {license_ref}. Sumber {_text(data['dataset_ref'])}.")
    lines += ["", "## Pengukuran", ""]
    bench = card["benchmark"]
    if bench is None:
        lines.append("TIDAK TAHU. Hasil bench belum disertakan.")
    else:
        lines += [f"Rubrik {_text(bench['rubric_ref'])}. Protokol {_text(bench['protocol_ref'])}.",
                  f"Baseline `{bench['baseline_sha256']}`. Sumber {_text(bench['ref'])}.", "",
                  "| Domain | Pasangan | Baseline (bp) | Artefak (bp) | Delta (bp) |",
                  "|---|---:|---:|---:|---:|"]
        for row in bench["domains"]:
            cells = (_text(row["domain"]), f"{row['compared']}/{row['registered']}", _ratio(row["baseline_score_bp"]),
                     _ratio(row["artifact_score_bp"]), _ratio(row["score_delta_bp"]))
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", f"SHA-256 sumber kartu `{card['input_sha256']}`."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    try:
        card = compose(decode(read_bytes(args.input, MAX_BYTES)), args.expect_input_sha256)
        sys.stdout.write(markdown(card) if args.format == "markdown" else canonical(card).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
