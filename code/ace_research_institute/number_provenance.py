"""Audit setiap angka prosa dari posisi persis sampai pengukuran sumber ber-anchor."""
from decimal import Decimal
from hashlib import sha256
import re

from ._contracts import ResearchError, anchor, cli, digest, fmt, identifier, identity, integer, items, obj, schema, source_bytes
from ._evidence import dimension, quantity, reviewed


NUMBERS = re.compile(r"(?<![\w.,])([+-]?[0-9]+(?:[.,][0-9]+)?)(%?)(?![%\w]|[.,]\d)")
CODE = re.compile(r"`[^`]+`")


def scan_prose(content):
    """Ambil offset 1-based. Judul, angka klaim, dan badan prosa ikut diperiksa."""
    code = None
    for line, original in enumerate(content.splitlines(), 1):
        marker = original.strip()[:3]
        if marker in ("```", "~~~"):
            code = marker if code is None else (None if code == marker else code)
            continue
        if code:
            continue
        without_code = CODE.sub(lambda match: " " * len(match[0]), original)
        for match in NUMBERS.finditer(without_code):
            yield (line, match.start() + 1), (match[0], match[1].replace(",", "."), match[2] == "%")


def verify_numbers(plan, expected, root, *, draft_bytes=None):
    anchor(plan, expected)
    schema(plan, "ace.institute.number-proof-plan.v1", ("draft", "source_plan", "citations"))
    draft = obj(plan["draft"], ("path", "sha256"))
    if draft_bytes is None:
        draft_bytes = source_bytes(root, draft["path"], draft["sha256"], 500000)
    elif len(draft_bytes) > 500000 or sha256(draft_bytes).hexdigest() != digest(draft["sha256"]):
        raise ResearchError("Prosa yang diberikan berbeda dari anchor laporan.")
    content = draft_bytes.decode("utf-8")
    found = dict(scan_prose(content))
    if len(found) > 2000:
        raise ResearchError("Angka dalam prosa melampaui batas audit.")
    source_index, facts, held = reviewed(plan["source_plan"], root)
    known = {(row["source_id"], row["id"]): row for row in facts}
    cites = {}
    for row in items(plan["citations"], 2000):
        obj(row, ("line", "column", "source_id", "measurement_id", "dimensions", "document_unit", "tolerance"))
        key = (integer(row["line"], "Baris angka", 1, 500000), integer(row["column"], "Kolom angka", 1, 500000))
        if key in cites:
            raise ResearchError("Posisi sitasi angka ganda.")
        source = identifier(row["source_id"], "ID sumber")
        measurement = identifier(row["measurement_id"], "ID pengukuran")
        family, radius = quantity(row["tolerance"], row["document_unit"])
        if radius < 0:
            raise ResearchError("Toleransi angka tidak boleh negatif.")
        cites[key] = (source, measurement, dimension(row["dimensions"]), family, radius, row["document_unit"])
    result = []
    for (line, column), (token, value, percent) in sorted(found.items()):
        row = {"line": line, "column": column, "token": token, "status": "missing_citation"}
        if (line, column) in cites:
            source, measurement, context, family, radius, unit = cites[(line, column)]
            item = known.get((source, measurement))
            if percent and unit != "pct":
                row["status"] = "document_unit_conflict"
            elif item is None:
                row["status"] = "measurement_unavailable"
            elif item["unit"] != family or dimension(item["dimensions"]) != context:
                row["status"] = "evidence_scope_conflict"
            else:
                _, measure = quantity(value, unit)
                difference = abs(measure - Decimal(item["estimate"]))
                row.update({"status": "verified" if difference <= radius else "value_mismatch",
                            "source": item["source"], "normalized_value": fmt(measure),
                            "source_value": item["estimate"], "difference": fmt(difference)})
        result.append(row)
    extras = [{"line": line, "column": column, "status": "citation_without_numeric_token"}
              for line, column in sorted(cites.keys() - found.keys())]
    successes = sum(row["status"] == "verified" for row in result)
    return {"schema": "ace.institute.number-provenance.v1", "plan_sha256": expected, "draft": draft,
            "source_register_sha256": identity(source_index), "held_rows": held,
            "verified": successes, "observed": len(result), "numeric_tokens": result, "unused_citations": extras,
            "coverage_bp": successes * 10000 // len(result) if result else None,
            "status": "complete" if result and successes == len(result) and not extras else ("no_numbers" if not result and not extras else "hold")}


if __name__ == "__main__":
    raise SystemExit(cli(verify_numbers, __doc__, rooted=True))
