"""Pembangkit pertanyaan ingin tahu terbuka & terdeduplikasi dari gap model dunia + anomali hipotesis (AG96).

Menerima snapshot model dunia (bentuk ``ace.house-world-model.v1`` dengan
``world_gaps``, ``stale_subsystems``, ``exhausted_roles``) beserta buku hipotesis
(``ace.hypothesis-book.v1`` / daftar anomali), menggabungkan gap atau anomali yang
tumpang-tindih menjadi satu pertanyaan terpadu yang berbobot lebih tinggi,
menyingkirkan pertanyaan yang sudah pernah diajukan, dan mengurutkannya berdasar
prioritas secara deterministik.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.curiosity-questions.v1"
_TOKEN_RE = re.compile(r"[0-9a-zA-Z]+")
_STOPWORDS = frozenset({"di", "ke", "dari", "yang", "dan", "atau", "pada", "untuk", "dengan", "karena", "the", "of", "in", "on", "to", "for"})


def _normalize_topic(raw: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", raw.lower()).strip("_")
    return cleaned or "umum"


def _meaningful_tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 3 and t not in _STOPWORDS)


def _extract_world_signals(world_model: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not world_model:
        return []
    signals: list[dict[str, Any]] = []

    raw_gaps = world_model.get("world_gaps", world_model.get("gaps", []))
    if isinstance(raw_gaps, Sequence) and not isinstance(raw_gaps, (str, bytes)):
        for gap in raw_gaps:
            if not isinstance(gap, Mapping):
                continue
            sub = str(gap.get("subsystem") or gap.get("domain") or gap.get("topic") or "umum").strip()
            reason = str(gap.get("reason") or gap.get("description") or f"Gap di {sub}").strip()
            severity = float(gap.get("severity", 0.7))
            signals.append(
                {
                    "source_type": "world_gap",
                    "source_id": str(gap.get("gap_id") or f"world:{sub}"),
                    "topic_key": _normalize_topic(str(gap.get("topic_key") or sub)),
                    "subsystem": sub,
                    "detail": reason,
                    "base_weight": severity,
                }
            )

    existing_keys = {s["topic_key"] for s in signals}
    for sub in world_model.get("stale_subsystems", []) or ():
        key = _normalize_topic(str(sub))
        if key in existing_keys:
            continue
        signals.append(
            {
                "source_type": "stale_subsystem",
                "source_id": f"stale:{sub}",
                "topic_key": key,
                "subsystem": str(sub),
                "detail": f"Subsistem {sub} berstatus basi dan belum segar",
                "base_weight": 0.65,
            }
        )

    for role in world_model.get("exhausted_roles", []) or ():
        key = _normalize_topic(f"budget_{role}")
        signals.append(
            {
                "source_type": "exhausted_role",
                "source_id": f"budget:{role}",
                "topic_key": key,
                "subsystem": f"budget:{role}",
                "detail": f"Kuota peran {role} habis dan perlu diagnosis alokasi",
                "base_weight": 0.75,
            }
        )
    return signals


def _extract_hypothesis_anomalies(hyp_book: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not hyp_book:
        return []
    items = hyp_book.get("anomalies")
    if items is None:
        items = hyp_book.get("hypotheses", [])
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return []

    signals: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("status") or "").lower()
        explicit_anomaly = "anomalies" in hyp_book
        if not explicit_anomaly and status not in {"belum_tentu", "gugur", "terdaftar"}:
            continue
        hid = str(row.get("hypothesis_id") or row.get("anomaly_id") or "hyp")
        domain = str(row.get("subsystem") or row.get("domain") or "umum").strip()
        cause = str(row.get("cause") or row.get("reason") or row.get("description") or hid).strip()
        weight = 0.85 if status == "gugur" else (0.75 if status == "belum_tentu" else 0.55)
        if isinstance(row.get("severity"), (int, float)):
            weight = float(row["severity"])
        signals.append(
            {
                "source_type": f"hypothesis_{status or 'anomaly'}",
                "source_id": hid,
                "topic_key": _normalize_topic(str(row.get("topic_key") or domain)),
                "subsystem": domain,
                "detail": f"Hipotesis {hid} ({status or 'anomali'}): {cause}",
                "base_weight": weight,
            }
        )
    return signals


def _clusters_overlap(cluster_sig: Mapping[str, Any], new_sig: Mapping[str, Any]) -> bool:
    if cluster_sig["topic_key"] == new_sig["topic_key"]:
        return True
    toks_a = _meaningful_tokens(cluster_sig["detail"] + " " + cluster_sig["subsystem"])
    toks_b = _meaningful_tokens(new_sig["detail"] + " " + new_sig["subsystem"])
    union = toks_a | toks_b
    if not union:
        return False
    return (len(toks_a & toks_b) / len(union)) >= 0.45


def _already_asked_match(
    cluster: Mapping[str, Any],
    asked_questions: Sequence[Any],
) -> bool:
    cluster_key = cluster["topic_key"]
    cluster_qnorm = " ".join(_meaningful_tokens(cluster["question"]))
    cluster_tokens = _meaningful_tokens(cluster["question"] + " " + " ".join(cluster["reasons"]))

    for item in asked_questions:
        if isinstance(item, Mapping):
            asked_key = _normalize_topic(str(item.get("topic_key") or "")) if item.get("topic_key") else None
            asked_text = str(item.get("question") or item.get("text") or "")
        else:
            asked_key = None
            asked_text = str(item)

        if asked_key and asked_key == cluster_key:
            return True
        asked_norm = " ".join(_meaningful_tokens(asked_text))
        if asked_norm and asked_norm == cluster_qnorm:
            return True
        asked_tokens = _meaningful_tokens(asked_text)
        union = cluster_tokens | asked_tokens
        if union and (len(cluster_tokens & asked_tokens) / len(union)) >= 0.60:
            return True
    return False


def generate_curiosity_questions(
    world_model: Mapping[str, Any] | None,
    hypothesis_book: Mapping[str, Any] | None = None,
    *,
    asked_questions: Sequence[Any] = (),
) -> dict[str, Any]:
    """Bangkitkan pertanyaan terbuka berperingkat, tergabung bila tumpang-tindih, dan tanpa ulangan."""
    all_signals = _extract_world_signals(world_model) + _extract_hypothesis_anomalies(hypothesis_book)

    clusters: list[dict[str, Any]] = []
    for sig in all_signals:
        matched_cluster: dict[str, Any] | None = None
        for cl in clusters:
            if any(_clusters_overlap(existing, sig) for existing in cl["signals"]):
                matched_cluster = cl
                break
        if matched_cluster is None:
            clusters.append(
                {
                    "topic_key": sig["topic_key"],
                    "subsystems": [sig["subsystem"]],
                    "signals": [sig],
                    "reasons": [sig["detail"]],
                }
            )
        else:
            matched_cluster["signals"].append(sig)
            if sig["subsystem"] not in matched_cluster["subsystems"]:
                matched_cluster["subsystems"].append(sig["subsystem"])
            if sig["detail"] not in matched_cluster["reasons"]:
                matched_cluster["reasons"].append(sig["detail"])

    kept_questions: list[dict[str, Any]] = []
    excluded_already_asked: list[dict[str, Any]] = []

    for cl in clusters:
        subsystems = sorted(cl["subsystems"])
        reasons = cl["reasons"]
        source_ids = [s["source_id"] for s in cl["signals"]]
        max_weight = max(s["base_weight"] for s in cl["signals"])
        merged_count = len(cl["signals"])
        # Sinyal tumpang-tindih dari berbagai sumber meningkatkan skor prioritas.
        priority = round(min(1.0, max_weight + 0.10 * (merged_count - 1)), 6)

        scope_label = ", ".join(subsystems)
        if merged_count > 1:
            question_text = (
                f"Mengapa {scope_label} menunjukkan sinyal ganda ({'; '.join(reasons)}) "
                f"dan eksperimen terkecil apa yang membedakan akar penyebabnya?"
            )
        else:
            question_text = (
                f"Apa akar penyebab '{reasons[0]}' pada {scope_label} "
                f"serta bukti apa yang menutup celah ini?"
            )

        qid_seed = f"{cl['topic_key']}:{'|'.join(sorted(source_ids))}"
        question_id = "cur-" + hashlib.sha256(qid_seed.encode("utf-8")).hexdigest()[:10]
        item = {
            "question_id": question_id,
            "topic_key": cl["topic_key"],
            "subsystems": subsystems,
            "question": question_text,
            "priority_score": priority,
            "merged_signal_count": merged_count,
            "source_ids": source_ids,
            "reasons": reasons,
        }
        if _already_asked_match(item, asked_questions):
            excluded_already_asked.append(item)
        else:
            kept_questions.append(item)

    kept_questions.sort(key=lambda x: (-x["priority_score"], -x["merged_signal_count"], x["topic_key"], x["question_id"]))
    for rank, item in enumerate(kept_questions, start=1):
        item["rank"] = rank

    return {
        "schema": SCHEMA,
        "input_signal_count": len(all_signals),
        "merged_cluster_count": len(clusters),
        "question_count": len(kept_questions),
        "excluded_already_asked_count": len(excluded_already_asked),
        "questions": kept_questions,
        "excluded_already_asked": [
            {"question_id": x["question_id"], "topic_key": x["topic_key"]}
            for x in excluded_already_asked
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pembangkit pertanyaan ingin tahu terdeduplikasi (AG96)")
    parser.add_argument("--world-model", required=True, help="Path JSON model dunia")
    parser.add_argument("--hypotheses", help="Opsional path JSON buku hipotesis / anomali")
    parser.add_argument("--asked", help="Opsional path JSON daftar pertanyaan yang pernah diajukan")
    args = parser.parse_args(argv)

    wm = json.loads(Path(args.world_model).read_text(encoding="utf-8"))
    hb = json.loads(Path(args.hypotheses).read_text(encoding="utf-8")) if args.hypotheses else None
    asked = json.loads(Path(args.asked).read_text(encoding="utf-8")) if args.asked else ()
    report = generate_curiosity_questions(wm, hb, asked_questions=asked)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
