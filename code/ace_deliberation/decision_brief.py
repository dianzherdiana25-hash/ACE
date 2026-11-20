"""Susun brief putusan yang dapat ditelusuri tanpa menghilangkan dissent.

Brief hanya menerima transcript yang dapat diputar ulang. Alasan dipetik
dari catatan putusan, dan rujukan preseden dipilih dari arsip sebelum
tanggal keputusan dengan kondisi yang diperiksa secara eksplisit.
"""
from collections import defaultdict
import json
from pathlib import Path
import re

from . import debate_protocol, precedent_memory


MAX_INPUT_BYTES = 20_000_000
_MARKDOWN = re.compile(r"([\\`*_{}\[\]()<>#!|&])")


class BriefError(ValueError):
    """Brief tidak dapat dirunut ke putusan atau arsip yang sah."""


def _brief_source(turn_id, digest):
    return {"turn_id": turn_id, "debate_sha256": digest}


def _turn_entry(turn, role, digest):
    return {"participant": turn["participant"], "role": role, "move": turn["move"],
            "statement": turn["statement"], "source": _brief_source(turn["turn_id"], digest),
            "evidence_refs": turn["evidence_refs"].copy()}


def _reference_index(basis, dissent, precedent):
    index = defaultdict(set)
    for row in basis:
        for ref in row["evidence_refs"]:
            index[ref].add(("basis", row["source"]["turn_id"]))
    for row in dissent:
        for ref in row["evidence_refs"]:
            index[ref].add(("dissent", row["source"]["turn_id"]))
        for reply in row["responses"]:
            for ref in reply["evidence_refs"]:
                index[ref].add(("response", reply["source"]["turn_id"]))
    if precedent is not None:
        for ref in precedent["evidence_refs"]:
            index[ref].add(("precedent", precedent["case_id"]))
    return [{"source_ref": ref, "uses": [{"kind": kind, "id": identifier}
                                         for kind, identifier in sorted(uses)]}
            for ref, uses in sorted(index.items())]


def make_brief(raw):
    """Kompilasi jejak putusan, sanggahan, dan preseden menjadi brief terstruktur."""
    if not isinstance(raw, dict) or raw.keys() != {"debate", "archive", "precedent_query"}:
        raise BriefError("Brief wajib memiliki debate, archive, dan precedent_query.")
    debate = raw["debate"]
    if not debate_protocol.verify_report(debate) or debate["decision"] is None:
        raise BriefError("Brief memerlukan transcript putusan yang dapat diverifikasi.")
    parameters = raw["precedent_query"]
    if not isinstance(parameters, dict) or parameters.keys() != {"as_of", "tags", "conditions", "limit"}:
        raise BriefError("Parameter preseden tidak sesuai skema.")
    outcome = debate["decision"]["outcome"]
    query = {**parameters, "issue": debate["plan"]["question"], "proposed_outcome": outcome}
    precedents = precedent_memory.PrecedentMemory(raw["archive"]).search(query)
    match = next((candidate for candidate in precedents["matches"]
                  if candidate["applicable_conditions"]), None)
    seats = {seat["participant"]: seat["role"] for seat in debate["plan"]["seats"]}
    turns = {turn["turn_id"]: turn for turn in debate["turns"]}
    digest = debate["sha256"]
    responses = defaultdict(list)
    for turn in debate["turns"]:
        if turn["move"] in {"synthesis", "response"}:
            for target in turn["targets"]:
                if turns[target]["move"] == "objection":
                    responses[target].append(_turn_entry(turn, seats[turn["participant"]], digest))
    dissent = []
    for turn_id in debate["dissent_turns"]:
        turn = turns[turn_id]
        dissent.append({**_turn_entry(turn, seats[turn["participant"]], digest),
                        "responses": responses[turn_id]})
    basis = [
        _turn_entry(turns[turn_id], seats[turns[turn_id]["participant"]], digest)
        for turn_id in debate["decision"]["basis_turns"]
    ]
    return {
        "schema": "ace.decision-brief.v1",
        "debate_id": debate["plan"]["debate_id"], "debate_sha256": digest,
        "question": debate["plan"]["question"], "outcome": outcome,
        "reason_recorded": debate["decision"]["rationale"], "basis": basis,
        "dissent": dissent, "unanswered_dissent_count": sum(not row["responses"] for row in dissent),
        "reference_index": _reference_index(basis, dissent, match),
        "precedent_cutoff": precedents["as_of"], "precedent_candidates": precedents["matches"],
        "precedent": match, "different_outcome_precedent": precedents["best_different_outcome"],
        "precedent_status": "cited" if match else "no_applicable_candidate",
    }


def _escape(text):
    text = " ".join(text.split())
    return _MARKDOWN.sub(r"\\\1", text)


def render_markdown(report):
    lines = [
        "# Brief putusan",
        "",
        f"- Pertanyaan — {_escape(report['question'])}",
        f"- Putusan tercatat — {report['outcome']}",
        f"- Alasan dari transcript — {_escape(report['reason_recorded'])}",
        f"- ID debat — {_escape(report['debate_id'])}",
        f"- SHA-256 transcript — `{report['debate_sha256']}`",
        "",
        "## Dasar putusan",
        "",
    ]
    for item in report["basis"]:
        lines.append(f"- {_escape(item['source']['turn_id'])} · {item['role']} — {_escape(item['statement'])}")
        lines.extend(f"  - Rujukan — {_escape(reference)}" for reference in item["evidence_refs"])
    lines.extend(("", "## Sanggahan dan tanggapan", ""))
    if not report["dissent"]:
        lines.append("Transcript tidak memuat sanggahan.")
    for item in report["dissent"]:
        lines.append(f"- {_escape(item['source']['turn_id'])} — {_escape(item['statement'])}")
        lines.extend(f"  - Rujukan — {_escape(reference)}" for reference in item["evidence_refs"])
        if not item["responses"]:
            lines.append("  - Belum ada tanggapan tercatat.")
        for response in item["responses"]:
            lines.append(f"  - {_escape(response['source']['turn_id'])} — {_escape(response['statement'])}")
            lines.extend(f"    - Rujukan — {_escape(reference)}" for reference in response["evidence_refs"])
    lines.extend(("", "## Preseden", ""))
    if report["precedent"] is None:
        lines.append("Pencarian tidak menemukan kandidat dengan kondisi yang terpenuhi.")
    else:
        item = report["precedent"]
        lines.append(f"- {_escape(item['case_id'])} · {item['decided_on']} · {item['outcome']}")
        lines.append(f"  - Sumber kasus — {_escape(item['source_ref'])}")
        lines.extend(f"  - Bukti — {_escape(reference)}" for reference in item["evidence_refs"])
    if (alternate := report["different_outcome_precedent"]) is not None:
        lines.append(f"- Outcome berbeda — {_escape(alternate['case_id'])} · {_escape(alternate['source_ref'])}")
        for condition in alternate["conditions_missing"]:
            lines.append(f"  - Kondisi belum terpenuhi — {_escape(condition)}")
    if report["reference_index"]:
        lines.extend(("", "## Indeks rujukan", ""))
        for row in report["reference_index"]:
            uses = ", ".join(f"{item['kind']} {_escape(item['id'])}" for item in row["uses"])
            lines.append(f"- {_escape(row['source_ref'])} — {uses}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise BriefError("Berkas brief melampaui batas.")
        report = make_brief(json.loads(data))
        if args.format == "markdown":
            print(render_markdown(report), end="")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
