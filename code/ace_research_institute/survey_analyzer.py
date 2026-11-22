"""Kodekan jawaban terbuka dari codebook dengan konflik dan jalur audit per record."""
from collections import Counter, defaultdict
import re
import unicodedata

from ._contracts import ResearchError, anchor, cli, decode, identifier, identity, integer, items, obj, schema, source_bytes, text


def _normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _phrases(raw):
    return [re.compile(r"(?<!\w)" + re.escape(_normalize(text(value, "Frasa indikator", 110))) + r"(?!\w)")
            for value in items(raw, 30)]


def analyze_answers(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.survey-analysis.v1", ("responses", "codebook", "redact_below"))
    small_n = integer(plan["redact_below"], "Ambang pelaporan", 1, 100)
    ref = obj(plan["responses"], ("path", "sha256"))
    groups = {}
    for row in items(plan["codebook"], 80, 1):
        obj(row, ("id", "exclusive_group", "required", "excluded", "min_hits", "definition_ref"))
        key = identifier(row["id"], "Kode")
        if key in groups:
            raise ResearchError("Kode analisis ganda.")
        yes = _phrases(row["required"])
        no = _phrases(row["excluded"])
        if len({rule.pattern for rule in yes}) != len(yes):
            raise ResearchError("Frasa wajib kode duplikat.")
        minimum = integer(row["min_hits"], "Indikator minimal", 1, len(yes))
        group = row["exclusive_group"] if row["exclusive_group"] is None else identifier(row["exclusive_group"], "Grup eksklusif")
        groups[key] = (group, yes, no, minimum, text(row["definition_ref"], "Pointer codebook"))
    raw = source_bytes(root, ref["path"], ref["sha256"], 2_000_000)
    counts = Counter()
    outcome = []
    tags_by_answer = []
    seen = set()
    for row_number, content in enumerate(raw.splitlines(), 1):
        if row_number > 15000:
            raise ResearchError("Baris respons melebihi batas.")
        if not content.strip():
            continue
        row = obj(decode(content), ("id", "answer", "consented"))
        key = identifier(row["id"], "Respons")
        if key in seen or type(row["consented"]) is not bool:
            raise ResearchError("ID respons ganda atau penanda persetujuan tidak sah.")
        seen.add(key)
        if not row["consented"]:
            outcome.append({"line": row_number, "status": "excluded_no_consent"})
            continue
        answer = _normalize(text(row["answer"], "Jawaban terbuka", 2000))
        found = []
        barriers = defaultdict(list)
        for code, (group, required, excluded, minimum, _) in sorted(groups.items()):
            if sum(bool(regex.search(answer)) for regex in required) >= minimum and not any(regex.search(answer) for regex in excluded):
                found.append(code)
                if group is not None:
                    barriers[group].append(code)
        conflict = {name: codes for name, codes in barriers.items() if len(codes) > 1}
        if conflict:
            withheld = {code for codes in conflict.values() for code in codes}
            found = [code for code in found if code not in withheld]
        counts.update(found)
        state = "ambiguous" if conflict else ("coded" if found else "uncoded")
        outcome.append({"line": row_number, "status": state, "conflicts": sorted(conflict)})
        tags_by_answer.append((row_number, found))
    admitted = {code for code, total in counts.items() if total >= small_n}
    by_code = [{"code": key, "count": counts[key] if key in admitted else None,
                "suppressed": key not in admitted, "definition_ref": groups[key][4]} for key in sorted(groups)]
    spans = [{"line": line, "codes": [key for key in codes if key in admitted]} for line, codes in tags_by_answer]
    return {"schema": "ace.institute.open-response-analysis.v1", "plan_sha256": expected, "source": ref,
            "codebook_sha256": identity(plan["codebook"]), "codes": by_code, "outcomes": outcome,
            "trace": spans, "observed_responses": len(outcome)}


if __name__ == "__main__":
    raise SystemExit(cli(analyze_answers, __doc__, rooted=True))
