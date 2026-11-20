"""Pembuat paket pelajaran bertingkat & penilai peningkatan murid pra/pasca ajar (AG97).

Menyusun rencana pelajaran terstruktur dari spesifikasi keahlian (materi ajar,
latihan bertingkat ``dasar``/``menengah``/``lanjut``, serta kunci penilaian),
lalu menilai jawaban murid sebelum dan sesudah pengajaran untuk menghasilkan
laporan peningkatan per murid dan ringkasan kelas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


PLAN_SCHEMA = "ace.teaching-lesson-plan.v1"
GAIN_SCHEMA = "ace.teaching-gain-report.v1"
TIER_ORDER = ("dasar", "menengah", "lanjut")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-zA-Z]+", " ", text.lower())).strip()


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_lesson_plan(skill_spec: Mapping[str, Any]) -> dict[str, Any]:
    """Susun rencana pelajaran bertingkat (materi, latihan, kunci nilai) dari ``skill_spec``."""
    skill_id = str(skill_spec.get("skill_id") or "").strip()
    title = str(skill_spec.get("title") or skill_id).strip()
    if not skill_id:
        raise ValueError("skill_spec wajib memiliki skill_id.")

    raw_concepts = skill_spec.get("concepts", [])
    if not isinstance(raw_concepts, Sequence) or isinstance(raw_concepts, (str, bytes)) or not raw_concepts:
        raise ValueError("skill_spec wajib memiliki daftar 'concepts' yang tidak kosong.")

    tiers_bucket: dict[str, list[dict[str, Any]]] = {t: [] for t in TIER_ORDER}
    exercises: list[dict[str, Any]] = []
    grading_key: dict[str, dict[str, Any]] = {}

    for idx, row in enumerate(raw_concepts, start=1):
        tier = str(row.get("tier") or "dasar").lower()
        if tier not in tiers_bucket:
            raise ValueError(f"Tier tidak sah {tier!r}; pilih dari {TIER_ORDER}.")
        cid = str(row.get("concept_id") or f"{skill_id}-c{idx}").strip()
        ex_id = f"ex:{cid}"
        explanation = str(row.get("explanation") or "").strip()
        prompt = str(row.get("exercise_prompt") or "").strip()
        expected = str(row.get("expected_answer") or "").strip()
        if not explanation or not prompt or not expected:
            raise ValueError(f"Konsep {cid!r} wajib memiliki explanation, exercise_prompt, dan expected_answer.")

        keywords = [str(k).strip() for k in row.get("keywords", []) or () if str(k).strip()]
        if not keywords:
            keywords = [tok for tok in _normalize(expected).split() if len(tok) >= 3]
        weight = float(row.get("weight", 1.0))

        material_item = {
            "concept_id": cid,
            "tier": tier,
            "title": str(row.get("title") or cid),
            "explanation": explanation,
            "exercise_id": ex_id,
        }
        tiers_bucket[tier].append(material_item)
        exercises.append(
            {
                "exercise_id": ex_id,
                "concept_id": cid,
                "tier": tier,
                "prompt": prompt,
            }
        )
        grading_key[ex_id] = {
            "exercise_id": ex_id,
            "tier": tier,
            "expected_answer": expected,
            "keywords": keywords,
            "weight": weight,
        }

    # Urutkan latihan & materi mengikuti jenjang dasar -> menengah -> lanjut.
    tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
    exercises.sort(key=lambda x: (tier_rank[x["tier"]], x["exercise_id"]))
    materials = [item for t in TIER_ORDER for item in tiers_bucket[t]]

    plan = {
        "schema": PLAN_SCHEMA,
        "skill_id": skill_id,
        "title": title,
        "tiers": tiers_bucket,
        "materials": materials,
        "exercises": exercises,
        "grading_key": grading_key,
    }
    plan["plan_hash"] = _canonical_hash(plan)
    return plan


def _score_single_answer(answer: str, key_row: Mapping[str, Any]) -> float:
    norm_ans = _normalize(answer)
    if not norm_ans:
        return 0.0
    norm_exp = _normalize(str(key_row["expected_answer"]))
    if norm_ans == norm_exp or (norm_exp and re.search(rf"\b{re.escape(norm_exp)}\b", norm_ans)):
        return 1.0
    keywords = [_normalize(str(k)) for k in key_row.get("keywords", ()) if _normalize(str(k))]
    if not keywords:
        return 0.0
    ans_tokens = set(norm_ans.split())
    hits = 0
    for kw in keywords:
        if " " in kw:
            if re.search(rf"\b{re.escape(kw)}\b", norm_ans):
                hits += 1
        elif kw in ans_tokens:
            hits += 1
    return hits / len(keywords)


def _score_submission(
    answers: Mapping[str, Any],
    grading_key: Mapping[str, Mapping[str, Any]],
) -> tuple[float, dict[str, float]]:
    total_w = 0.0
    weighted_sum = 0.0
    per_tier_vals: dict[str, list[float]] = {t: [] for t in TIER_ORDER}

    for ex_id, key_row in grading_key.items():
        w = float(key_row.get("weight", 1.0))
        raw_ans = str(answers.get(ex_id, ""))
        sc = _score_single_answer(raw_ans, key_row)
        total_w += w
        weighted_sum += w * sc
        per_tier_vals[str(key_row["tier"])].append(sc)

    overall = round(weighted_sum / total_w, 6) if total_w > 0 else 0.0
    per_tier = {
        t: round(sum(vals) / len(vals), 6) if vals else None
        for t, vals in per_tier_vals.items()
    }
    return overall, per_tier


def evaluate_student_gains(
    lesson_plan: Mapping[str, Any],
    students: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Nilai peningkatan jawaban murid pra-ajar vs pasca-ajar memakai ``lesson_plan``."""
    grading_key = lesson_plan.get("grading_key", {})
    if not grading_key:
        raise ValueError("lesson_plan wajib memiliki grading_key tidak kosong.")

    results: list[dict[str, Any]] = []
    improving = 0
    non_improving = 0

    for stu in students:
        sid = str(stu.get("student_id") or "").strip()
        if not sid:
            raise ValueError("Entri murid wajib memiliki student_id.")
        pre_ans = stu.get("pre_answers", {}) or {}
        post_ans = stu.get("post_answers", {}) or {}

        pre_score, pre_tier = _score_submission(pre_ans, grading_key)
        post_score, post_tier = _score_submission(post_ans, grading_key)
        gain = round(post_score - pre_score, 6)
        improved = gain > 0.0
        if improved:
            status = "meningkat"
            improving += 1
        elif gain < 0.0:
            status = "menurun"
            non_improving += 1
        else:
            status = "stagnan"
            non_improving += 1

        results.append(
            {
                "student_id": sid,
                "pre_score": pre_score,
                "post_score": post_score,
                "gain": gain,
                "improved": improved,
                "status": status,
                "pre_by_tier": pre_tier,
                "post_by_tier": post_tier,
            }
        )

    gains = [r["gain"] for r in results]
    return {
        "schema": GAIN_SCHEMA,
        "skill_id": str(lesson_plan.get("skill_id") or ""),
        "plan_hash": lesson_plan.get("plan_hash"),
        "student_count": len(results),
        "improving_count": improving,
        "non_improving_count": non_improving,
        "mean_gain": round(sum(gains) / len(gains), 6) if gains else 0.0,
        "students": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generator rencana ajar & penilai peningkatan murid (AG97)")
    parser.add_argument("--skill", required=True, help="Path JSON spesifikasi keahlian")
    parser.add_argument("--students", help="Opsional path JSON jawaban pra/pasca murid")
    args = parser.parse_args(argv)

    spec = json.loads(Path(args.skill).read_text(encoding="utf-8"))
    plan = build_lesson_plan(spec)
    if args.students:
        subs = json.loads(Path(args.students).read_text(encoding="utf-8"))
        out = evaluate_student_gains(plan, subs)
    else:
        out = plan
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
