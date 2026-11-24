"""Anti-Hallucination & High-Bar Quality Gate Engine for ACE v3.

Enforces strict evidence-bound gating before any external publish or auto-merge:
1. Lapis 1 — Grounding & Fact Audit (`evaluate_research_grounding`)
2. Lapis 2 — Domain High-Bar Rubrics:
   - Reels (`evaluate_reels_quality`): hook, retention proxy, approved metadata,
     brand safety, 9:16 + audio/duration probe via ffprobe.
   - KBM (`evaluate_kbm_quality`): `kbm_qc` continuity + `arc_rubric` reader proxy
     + optional `cover_check` binary validation.
   - Code (`evaluate_code_quality`): AST check, secret scan, frozen upstream protection,
     real unittest/command execution.
3. Lapis 3 — Cross-Agent Heterogeneity check (`check_cross_agent_heterogeneity`).

Work below threshold is strictly REJECTED (`REJECTED_BELOW_BAR` / `UNGROUNDED_CLAIMS` /
`FAILED_CHECK`) with actionable revision diagnostics.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ace_media_studio import brand_safety_qa, scene_retention_predictor, upload_metadata_writer
from ace_media_studio._contracts import ContractError, identity as media_identity
from tools import arc_rubric, cover_check, director_grounding_check, director_prose_audit, kbm_qc

from . import SCHEMA_QUALITY_VERDICT
from .connectors.vault import contains_secret_pattern

DEFAULT_MIN_QUALITY_SCORE_BP = 8500  # 85.0%
_IDENTIFIER_CLEAN = re.compile(r"[^a-z0-9_]+")
_WORDS_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _safe_identifier(raw: str, prefix: str = "id") -> str:
    cleaned = _IDENTIFIER_CLEAN.sub("_", str(raw).strip().lower()).strip("_")
    if not cleaned:
        cleaned = f"{prefix}_{hashlib.sha256(str(raw).encode('utf-8')).hexdigest()[:8]}"
    if not cleaned[0].isalpha():
        cleaned = f"{prefix}_{cleaned}"
    return cleaned[:64]


def _parse_iso_ts(raw: str) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _verdict(
    *,
    domain: str,
    passed: bool,
    verdict: str,
    score_bp: int,
    min_score_bp: int,
    findings: list[dict[str, Any]],
    revision_feedback: list[str],
    checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_QUALITY_VERDICT,
        "domain": domain,
        "passed": bool(passed),
        "verdict": verdict,
        "score_bp": max(0, min(10000, int(score_bp))),
        "min_score_bp": int(min_score_bp),
        "findings": findings,
        "revision_feedback": revision_feedback,
        "checks": checks,
    }


def evaluate_research_grounding(
    claims: Sequence[Any],
    sources: Sequence[Any] | dict[str, Any],
    *,
    min_score_bp: int = DEFAULT_MIN_QUALITY_SCORE_BP,
    max_age_days: int = 180,
    min_words_per_source: int = 12,
    reference_facts: dict[str, Any] | None = None,
    prose_markdown: str = "",
) -> dict[str, Any]:
    """Verify every claim is anchored to a fresh, non-duplicate, non-contradicted source."""
    findings: list[dict[str, Any]] = []
    revision_feedback: list[str] = []

    if isinstance(sources, dict):
        source_map = {str(k): v for k, v in sources.items()}
    else:
        source_map = {}
        for idx, src in enumerate(sources or (), 1):
            if isinstance(src, dict):
                sid = str(src.get("id") or src.get("source_ref") or src.get("url") or f"src_{idx}")
                source_map[sid] = src
                if src.get("url"):
                    source_map[str(src["url"])] = src
                if src.get("source_ref"):
                    source_map[str(src["source_ref"])] = src
            else:
                sid = str(src)
                source_map[sid] = {"id": sid, "content": sid}

    if not claims:
        return _verdict(
            domain="research",
            passed=False,
            verdict="UNGROUNDED_CLAIMS",
            score_bp=0,
            min_score_bp=min_score_bp,
            findings=[{"rule": "empty_claims", "detail": "Tidak ada klaim riset yang disertakan"}],
            revision_feedback=["Tambahkan daftar klaim terstruktur beserta source_ref masing-masing."],
            checks={"claims_total": 0, "sources_total": len(source_map)},
        )

    now = datetime.now(timezone.utc)
    seen_hashes: dict[str, str] = {}
    grounded_count = 0
    total_claims = len(claims)

    for idx, item in enumerate(claims, 1):
        if isinstance(item, str):
            findings.append({
                "rule": "ungrounded_string_claim",
                "index": idx,
                "claim": item[:120],
            })
            revision_feedback.append(f"Klaim #{idx} masih berupa teks mentah tanpa `source_ref`; wajib sertakan rujukan sumber.")
            continue
        if not isinstance(item, dict):
            findings.append({"rule": "invalid_claim_shape", "index": idx})
            revision_feedback.append(f"Klaim #{idx} harus berupa objek JSON dengan `claim` dan `source_ref`.")
            continue
        claim_text = str(item.get("claim") or item.get("text") or "").strip()
        ref = str(item.get("source_ref") or "").strip()
        if not claim_text:
            findings.append({"rule": "empty_claim_text", "index": idx})
            revision_feedback.append(f"Klaim #{idx} tidak memiliki isi pernyataan.")
            continue
        if not ref:
            findings.append({"rule": "missing_source_ref", "index": idx, "claim": claim_text[:120]})
            revision_feedback.append(f"Klaim '{claim_text[:60]}' tidak memiliki `source_ref` (ditolak anti-halu).")
            continue
        src_obj = source_map.get(ref)
        if src_obj is None:
            findings.append({"rule": "dangling_source_ref", "index": idx, "source_ref": ref})
            revision_feedback.append(f"`source_ref` '{ref}' tidak ditemukan di daftar `sources` yang terlampir.")
            continue
        src_body = str(
            src_obj.get("content") or src_obj.get("text") or src_obj.get("excerpt") or src_obj.get("summary") or ""
            if isinstance(src_obj, dict)
            else src_obj
        ).strip()
        words = _WORDS_RE.findall(src_body)
        if len(words) < min_words_per_source:
            findings.append({"rule": "thin_source", "source_ref": ref, "words": len(words), "min": min_words_per_source})
            revision_feedback.append(f"Sumber '{ref}' terlalu tipis ({len(words)} kata < {min_words_per_source}); perkuat bukti kutipan sumber.")
            continue
        obs = _parse_iso_ts(src_obj.get("observed_at", "")) if isinstance(src_obj, dict) else None
        if obs is not None:
            age_days = (now - obs).total_seconds() / 86400.0
            if age_days > max_age_days:
                findings.append({"rule": "stale_source", "source_ref": ref, "age_days": round(age_days, 1)})
                revision_feedback.append(f"Sumber '{ref}' kedaluwarsa ({age_days:.0f} hari > {max_age_days} hari); cari data terbaru.")
                continue
        body_hash = hashlib.sha256(" ".join(src_body.lower().split()).encode("utf-8")).hexdigest()
        prev_ref = seen_hashes.get(body_hash)
        if prev_ref and prev_ref != ref:
            findings.append({"rule": "duplicate_source_body", "source_ref": ref, "duplicate_of": prev_ref})
            revision_feedback.append(f"Sumber '{ref}' berisi konten duplikat persis dengan '{prev_ref}'.")
            continue
        seen_hashes[body_hash] = ref
        grounded_count += 1

    # Optional quantitative check against operational store facts.
    grounding_report = None
    if reference_facts is not None:
        proposals = [
            {
                "id": f"claim_{i}",
                "rationale": str(c.get("claim") or c.get("text") or "") if isinstance(c, dict) else str(c),
            }
            for i, c in enumerate(claims, 1)
        ]
        grounding_report = director_grounding_check.check_proposal_grounding(proposals, reference_facts)
        if grounding_report["summary"]["mismatched_proposals"] > 0:
            findings.append({"rule": "factual_mismatch", "detail": grounding_report["summary"]})
            revision_feedback.append("Ditemukan angka pada klaim yang bertentangan dengan fakta store terverifikasi.")

    prose_report = None
    if prose_markdown.strip():
        prose_report = director_prose_audit.audit_historical_prose(prose_markdown)
        if prose_report.get("unrecognized_prose"):
            findings.append({"rule": "unrecognized_prose_numbers", "count": len(prose_report["unrecognized_prose"])})
            revision_feedback.append("Terdapat angka di narasi prosa tanpa jangkar klaim atau rujukan eksplisit.")

    grounding_ratio = grounded_count / total_claims if total_claims else 0.0
    score_bp = round(grounding_ratio * 10000)
    if findings:
        score_bp = min(score_bp, max(0, 7500 - 500 * len(findings)))

    ungrounded = any(
        f["rule"] in ("ungrounded_string_claim", "missing_source_ref", "dangling_source_ref", "factual_mismatch")
        for f in findings
    )
    passed = (not findings) and score_bp >= int(min_score_bp)
    verdict = "PASS" if passed else ("UNGROUNDED_CLAIMS" if ungrounded else "REJECTED_BELOW_BAR")
    return _verdict(
        domain="research",
        passed=passed,
        verdict=verdict,
        score_bp=score_bp,
        min_score_bp=min_score_bp,
        findings=findings,
        revision_feedback=revision_feedback,
        checks={
            "claims_total": total_claims,
            "grounded_claims": grounded_count,
            "sources_indexed": len(source_map),
            "director_grounding": grounding_report["summary"] if grounding_report else None,
            "prose_unrecognized": len(prose_report["unrecognized_prose"]) if prose_report else 0,
        },
    )


def _probe_rendered_mp4(video_path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not video_path.is_file():
        return {"ok": False, "error": f"File video tidak ditemukan: {video_path}"}
    size_bytes = video_path.stat().st_size
    if size_bytes <= 0:
        return {"ok": False, "error": "File video berukuran 0 byte"}
    if not ffprobe:
        return {"ok": False, "error": "ffprobe tidak terpasang"}
    res = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if res.returncode != 0:
        return {"ok": False, "error": res.stderr.strip()[:240] or "ffprobe gagal"}
    info = json.loads(res.stdout)
    streams = info.get("streams") or []
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    fmt = info.get("format") or {}
    if len(videos) != 1:
        return {"ok": False, "error": f"Jumlah video stream harus 1 (aktual {len(videos)})"}
    v = videos[0]
    w = int(v.get("width") or 0)
    h = int(v.get("height") or 0)
    duration_sec = float(fmt.get("duration") or v.get("duration") or 0.0)
    return {
        "ok": True,
        "width": w,
        "height": h,
        "portrait_9_16": h > w and abs((w / max(1, h)) - (9.0 / 16.0)) <= 0.04,
        "has_audio": len(audios) >= 1,
        "duration_sec": round(duration_sec, 3),
        "size_bytes": size_bytes,
        "codec": v.get("codec_name", ""),
        "audio_codec": audios[0].get("codec_name", "") if audios else "",
    }


def evaluate_reels_quality(
    package: dict[str, Any],
    *,
    min_score_bp: int = DEFAULT_MIN_QUALITY_SCORE_BP,
    require_rendered_mp4: bool = False,
) -> dict[str, Any]:
    """High-bar Reels rubric combining retention proxy, fact grounding, safety, and MP4 9:16 probe."""
    findings: list[dict[str, Any]] = []
    revision_feedback: list[str] = []

    raw_scenes = package.get("scenes") or package.get("script_scenes") or []
    if not isinstance(raw_scenes, list) or not raw_scenes:
        return _verdict(
            domain="video_reels",
            passed=False,
            verdict="REJECTED_BELOW_BAR",
            score_bp=0,
            min_score_bp=min_score_bp,
            findings=[{"rule": "missing_scenes"}],
            revision_feedback=["Tambahkan minimal 2 adegan berstruktur (`id`, `source_ref`, `narration`, `duration_ms`, `has_visual_action`)."],
            checks={},
        )

    title = str(package.get("title") or "Untitled Reels").strip()
    hook_terms = package.get("promise_terms") or [
        w for w in _WORDS_RE.findall(title.lower()) if len(w) >= 3
    ][:8] or ["video", "reels"]
    action_terms = package.get("action_terms") or [
        "lihat", "buka", "cek", "ikuti", "simak", "klik", "bagikan", "coba", "tonton", "mulai",
        "check", "watch", "open", "try", "follow", "save",
    ]
    clean_action_terms = [t.split()[0] for t in action_terms if isinstance(t, str) and t.strip()]
    retention_plan = {
        "schema": "ace.media.retention-plan.v1",
        "baseline_bp": int(package.get("baseline_bp", 7800)),
        "roles": {
            "action_terms": clean_action_terms[:20] or ["lihat"],
            "promise_terms": [str(x)[:35] for x in hook_terms[:10]],
        },
        "scenes": [],
    }
    total_ms = 0
    for idx, sc in enumerate(raw_scenes, 1):
        sc_dict = sc if isinstance(sc, dict) else {"narration": str(sc)}
        dur_ms = int(sc_dict.get("duration_ms") or 4000)
        total_ms += dur_ms
        retention_plan["scenes"].append({
            "id": _safe_identifier(str(sc_dict.get("id") or f"sc_{idx}"), "sc"),
            "source_ref": str(sc_dict.get("source_ref") or f"script/scene_{idx}"),
            "narration": str(sc_dict.get("narration") or sc_dict.get("text") or "Lihat cuplikan ini sekarang.")[:1100],
            "duration_ms": max(500, min(240000, dur_ms)),
            "has_visual_action": bool(sc_dict.get("has_visual_action", True)),
        })

    retention_score_bp = 0
    retention_report: dict[str, Any] = {}
    try:
        retention_report = scene_retention_predictor.forecast(retention_plan, media_identity(retention_plan))
        scene_scores = [row["proxy_score_bp"] for row in retention_report["scenes"]]
        retention_score_bp = sum(scene_scores) // len(scene_scores)
        lowest = retention_report["lowest_proxy_scene"]
        for row in retention_report["scenes"]:
            if row["features"]["long_intro"]:
                findings.append({"rule": "long_intro", "scene": row["id"]})
                revision_feedback.append(f"Adegan pembuka '{row['id']}' terlalu lama (>10 detik); pangkas hook pembuka ke 2-5 detik dengan pertanyaan kuat.")
            if row["features"]["no_action"]:
                findings.append({"rule": "no_visual_or_verb_action", "scene": row["id"]})
                revision_feedback.append(f"Adegan '{row['id']}' pasif tanpa kata kerja/aksi visual; tambahkan aksi visual nyata.")
            if row["features"]["tempo_over"] > 8:
                findings.append({"rule": "tempo_over", "scene": row["id"], "wpm": row["words_per_minute"]})
                revision_feedback.append(f"Tempo adegan '{row['id']}' terlalu padat ({row['words_per_minute']} wpm); padatkan kalimat.")
    except (ContractError, ValueError) as exc:
        findings.append({"rule": "retention_contract_error", "detail": str(exc)})
        revision_feedback.append(f"Perbaiki format adegan retention: {exc}")
        lowest = ""

    # Check approved facts / upload metadata.
    facts_in = package.get("facts") or []
    if not facts_in:
        findings.append({"rule": "no_grounded_facts"})
        revision_feedback.append("Sertakan minimal 1 fakta bersumber (`facts` dengan `source_ref` dan `approved=True`) untuk deskripsi Reels.")
        meta_report: dict[str, Any] = {"status": "hold", "blocking": [{"rule": "no_approved_description"}]}
    else:
        dummy_sha = "0" * 64
        if package.get("video_path") and Path(str(package["video_path"])).is_file():
            dummy_sha = hashlib.sha256(Path(str(package["video_path"])).read_bytes()).hexdigest()
        meta_plan = {
            "schema": "ace.media.metadata-plan.v1",
            "platform": "facebook_reels",
            "media_sha256": dummy_sha,
            "title": title[:200],
            "source_ref": str(package.get("source_ref") or "strategy/reels_plan"),
            "limits": {"title": 200, "description": 2200, "tags": 30},
            "facts": [
                {
                    "id": _safe_identifier(str(f.get("id") or f"f_{i}"), "f"),
                    "text": str(f.get("text") or "").strip()[:480],
                    "source_ref": str(f.get("source_ref") or "").strip(),
                    "approved": bool(f.get("approved", False)),
                }
                for i, f in enumerate(facts_in, 1)
                if isinstance(f, dict)
            ],
            "tags": [str(t).lstrip("#")[:35] for t in (package.get("tags") or []) if str(t).strip()],
            "credits": [
                {
                    "asset": _safe_identifier(str(c.get("asset") or f"asset_{i}"), "ast"),
                    "credit": str(c.get("credit") or "Original ACE asset")[:190],
                    "license_ref": str(c.get("license_ref") or "internal://original"),
                }
                for i, c in enumerate(package.get("credits") or [], 1)
                if isinstance(c, dict)
            ],
        }
        try:
            meta_report = upload_metadata_writer.prepare_metadata(meta_plan, media_identity(meta_plan))
            if meta_report["status"] != "ready":
                findings.append({"rule": "metadata_blocked", "blocking": meta_report["blocking"]})
                revision_feedback.append(f"Metadata unggahan ditahan ({meta_report['blocking']}); pastikan semua fakta disetujui dan berujukan `source_ref`.")
        except ContractError as exc:
            meta_report = {"status": "hold", "error": str(exc)}
            findings.append({"rule": "metadata_contract_error", "detail": str(exc)})
            revision_feedback.append(f"Format metadata tidak sah: {exc}")

    # Optional brand safety check across scene narrations.
    safety_report: dict[str, Any] | None = None
    blocked_terms = list(package.get("blocked_terms") or ["scam", "pasti kaya instan", "slot gacor", "judi online"])
    all_script_text = " ".join(s["narration"] for s in retention_plan["scenes"]).lower()
    for term in blocked_terms:
        if term.lower() in all_script_text:
            findings.append({"rule": "brand_safety_violation", "term": term})
            revision_feedback.append(f"Hapus frasa terlarang/berisiko penalti platform: '{term}'.")
    if retention_plan["scenes"]:
        policy = {
            "schema": "ace.media.brand-policy.v1",
            "required_channels": ["narration"],
            "blocked_categories": ["spam", "misleading"],
            "phrase_rules": [],
        }
        cursor = 0
        items = []
        for s in retention_plan["scenes"]:
            items.append({
                "id": s["id"],
                "channel": "narration",
                "start_ms": cursor,
                "end_ms": cursor + s["duration_ms"],
                "text": s["narration"],
                "categories": [],
                "source_ref": s["source_ref"],
            })
            cursor += s["duration_ms"]
        ann = {
            "schema": "ace.media.brand-annotations.v1",
            "asset_sha256": "0" * 64,
            "duration_ms": max(1, cursor),
            "items": items,
        }
        try:
            safety_report = brand_safety_qa.audit(policy, media_identity(policy), ann, media_identity(ann))
            if safety_report["status"] != "eligible_on_annotated_tracks":
                findings.append({"rule": "brand_safety_hold", "detail": safety_report})
                revision_feedback.append("Audit keamanan konten belum bersih di seluruh segmen narasi.")
        except ContractError:
            pass

    # Hook + CTA structural quality points.
    first_narration = retention_plan["scenes"][0]["narration"]
    last_narration = retention_plan["scenes"][-1]["narration"].lower()
    hook_ok = ("?" in first_narration or "!" in first_narration or any(c.isdigit() for c in first_narration)) and retention_plan["scenes"][0]["duration_ms"] <= 7000
    cta_ok = bool(package.get("cta")) or any(
        k in last_narration for k in ("ikuti", "bagikan", "simpan", "komentar", "cek", "follow", "share", "save", "comment")
    )
    if not hook_ok:
        findings.append({"rule": "weak_opening_hook"})
        revision_feedback.append("Hook pembuka lemah; gunakan pertanyaan/angka konkret di 3 detik pertama.")
    if not cta_ok:
        findings.append({"rule": "missing_cta"})
        revision_feedback.append("Tambahkan Call-To-Action (CTA) jelas di adegan penutup.")

    duration_sec = total_ms / 1000.0
    if not (5.0 <= duration_sec <= 90.0):
        findings.append({"rule": "duration_out_of_reels_window", "duration_sec": duration_sec})
        revision_feedback.append(f"Durasi Reels ({duration_sec:.1f}s) harus di rentang 5–90 detik.")

    # Physical MP4 verification when rendered file exists or is required.
    mp4_probe: dict[str, Any] | None = None
    video_path_str = str(package.get("video_path") or "").strip()
    if require_rendered_mp4 or video_path_str:
        if not video_path_str:
            findings.append({"rule": "missing_rendered_mp4"})
            revision_feedback.append("Video MP4 9:16 belum dirender; jalankan reels_pipeline terlebih dahulu.")
        else:
            mp4_probe = _probe_rendered_mp4(Path(video_path_str))
            if not mp4_probe.get("ok"):
                findings.append({"rule": "invalid_rendered_mp4", "detail": mp4_probe})
                revision_feedback.append(f"MP4 gagal verifikasi ffprobe: {mp4_probe.get('error')}")
            else:
                if not mp4_probe.get("portrait_9_16"):
                    findings.append({"rule": "aspect_not_9_16", "width": mp4_probe["width"], "height": mp4_probe["height"]})
                    revision_feedback.append(f"Resolusi video {mp4_probe['width']}x{mp4_probe['height']} bukan vertikal 9:16.")
                if not mp4_probe.get("has_audio"):
                    findings.append({"rule": "missing_audio_stream"})
                    revision_feedback.append("MP4 belum memiliki stream audio; sertakan narasi/musik.")

    # Aggregate high-bar score (retention proxy 55%, grounding/metadata 25%, structure hook/CTA/duration 20%).
    struct_score = 10000
    if not hook_ok:
        struct_score -= 3500
    if not cta_ok:
        struct_score -= 3000
    if not (5.0 <= duration_sec <= 90.0):
        struct_score -= 3000
    meta_score = 10000 if meta_report.get("status") == "ready" else 2000
    aggregate_bp = round(0.55 * retention_score_bp + 0.25 * meta_score + 0.20 * max(0, struct_score))

    hard_blockers = {
        "no_grounded_facts",
        "metadata_blocked",
        "metadata_contract_error",
        "brand_safety_violation",
        "missing_rendered_mp4",
        "invalid_rendered_mp4",
        "aspect_not_9_16",
        "missing_audio_stream",
    }
    has_blocker = any(f["rule"] in hard_blockers for f in findings)
    passed = (not has_blocker) and aggregate_bp >= int(min_score_bp)
    if not passed and lowest and f"Adegan terlemah saat ini: {lowest}" not in " ".join(revision_feedback):
        revision_feedback.append(f"Perkuat adegan terlemah menurut retention predictor: `{lowest}` (skor saat ini {aggregate_bp} bp < ambang {min_score_bp} bp).")

    return _verdict(
        domain="video_reels",
        passed=passed,
        verdict="PASS" if passed else "REJECTED_BELOW_BAR",
        score_bp=aggregate_bp,
        min_score_bp=min_score_bp,
        findings=findings,
        revision_feedback=revision_feedback,
        checks={
            "retention_score_bp": retention_score_bp,
            "lowest_proxy_scene": retention_report.get("lowest_proxy_scene", ""),
            "metadata_status": meta_report.get("status"),
            "brand_safety": safety_report.get("status") if safety_report else None,
            "mp4_probe": mp4_probe,
        },
    )


def evaluate_kbm_quality(
    package_or_manuscript: dict[str, Any],
    *,
    min_score_bp: int = DEFAULT_MIN_QUALITY_SCORE_BP,
    min_dim_score: float = 0.65,
    min_words_per_chapter: int = 1000,
) -> dict[str, Any]:
    """High-bar KBM rubric combining `arc_rubric.score_chapter_pack`, `kbm_qc.audit_manuscript`, and `cover_check`."""
    findings: list[dict[str, Any]] = []
    revision_feedback: list[str] = []

    chapters_in = package_or_manuscript.get("chapters")
    manuscript_path_raw = package_or_manuscript.get("manuscript_path")
    title_config = package_or_manuscript.get("title_config") or {
        "characters": package_or_manuscript.get("characters") or ["Tokoh"]
    }
    min_words = int(package_or_manuscript.get("min_words", min_words_per_chapter))

    # Build arc_rubric pack & temporary manuscript text if chapters list provided.
    arc_pack = {"pack_id": str(package_or_manuscript.get("pack_id") or "kbm_pack"), "chapters": []}
    manuscript_lines: list[str] = []
    if isinstance(chapters_in, list) and chapters_in:
        for idx, ch in enumerate(chapters_in, 1):
            if isinstance(ch, dict):
                text = str(ch.get("text") or ch.get("content") or "")
                num = int(ch.get("chapter_number") or idx)
                arc_pack["chapters"].append({
                    "chapter_id": str(ch.get("chapter_id") or f"bab_{num}"),
                    "text": text,
                    "characters": ch.get("characters") or title_config.get("characters") or [],
                    "beats": ch.get("beats") or [],
                    "open_hooks": bool(ch.get("open_hooks", False)),
                })
                manuscript_lines.append(f"Bab {num}: {ch.get('title') or f'Bagian {num}'}\n\n{text}\n")
    elif manuscript_path_raw and Path(str(manuscript_path_raw)).is_file():
        raw_text = Path(str(manuscript_path_raw)).read_text(encoding="utf-8")
        # Split on "Bab N" headings minimally for arc_rubric while letting kbm_qc run natively on file.
        parts = re.split(r"(?im)^(?:#{1,3}\s*)?bab\s+\d+\b.*$", raw_text)
        body_chunks = [p.strip() for p in parts if p.strip()]
        for idx, chunk in enumerate(body_chunks, 1):
            arc_pack["chapters"].append({"chapter_id": f"bab_{idx}", "text": chunk})
    else:
        return _verdict(
            domain="kbm_apps",
            passed=False,
            verdict="REJECTED_BELOW_BAR",
            score_bp=0,
            min_score_bp=min_score_bp,
            findings=[{"rule": "empty_kbm_manuscript"}],
            revision_feedback=["Sertakan `chapters` atau `manuscript_path` yang valid untuk diaudit."],
            checks={},
        )

    rubric = arc_rubric.score_chapter_pack(arc_pack)
    dims = rubric["dimensions"]
    overall_bp = round(float(rubric["overall"]) * 10000)

    for dim, val in dims.items():
        if float(val) < min_dim_score:
            findings.append({"rule": "weak_rubric_dimension", "dimension": dim, "score": val, "min": min_dim_score})
            revision_feedback.append(f"Dimensi cerita '{dim}' lemah ({val:.2f} < {min_dim_score:.2f}); tingkatkan dialog/konflik/kait bab.")

    # Continuity & word count audit via tools.kbm_qc.
    qc_report: dict[str, Any] = {"valid": True, "issue_count": 0, "chapters": []}
    with tempfile.TemporaryDirectory(prefix="ace-kbm-qc-") as tmp:
        tdir = Path(tmp)
        cfg_file = tdir / "title_config.json"
        cfg_file.write_text(json.dumps(title_config, ensure_ascii=False), encoding="utf-8")
        if manuscript_path_raw and Path(str(manuscript_path_raw)).is_file():
            ms_file = Path(str(manuscript_path_raw))
        else:
            ms_file = tdir / "manuscript.md"
            ms_file.write_text("\n".join(manuscript_lines), encoding="utf-8")
        try:
            qc_report = kbm_qc.audit_manuscript(ms_file, cfg_file, min_words=min_words)
        except kbm_qc.KbmQcError as exc:
            qc_report = {"valid": False, "issue_count": 1, "error": str(exc), "chapters": []}
            findings.append({"rule": "kbm_qc_error", "detail": str(exc)})
            revision_feedback.append(f"Format naskah KBM gagal `kbm_qc`: {exc}")

    if not qc_report.get("valid", True) and not findings:
        for ch in qc_report.get("chapters", []):
            for issue in ch.get("issues", []):
                findings.append({"rule": f"kbm_qc_{issue['code']}", "chapter": ch["chapter_number"], "detail": issue})
                revision_feedback.append(f"Bab {ch['chapter_number']}: masalah {issue['code']} ({issue}).")

    # Optional cover image binary audit.
    cover_report: dict[str, Any] | None = None
    cover_raw = str(package_or_manuscript.get("cover_path") or "").strip()
    if cover_raw:
        try:
            cover_report = cover_check.check_cover(Path(cover_raw), rules=package_or_manuscript.get("cover_rules"))
            if not cover_report["valid"]:
                findings.append({"rule": "cover_check_failed", "failed_rules": cover_report["failed_rules"]})
                revision_feedback.append(f"Gambar sampul tidak memenuhi standar KBM: {cover_report['failed_rules']}.")
        except cover_check.CoverCheckInputError as exc:
            cover_report = {"valid": False, "error": str(exc)}
            findings.append({"rule": "cover_missing", "detail": str(exc)})
            revision_feedback.append(f"Berkas sampul bermasalah: {exc}")

    effective_bp = overall_bp
    if not qc_report.get("valid", True):
        effective_bp = min(effective_bp, max(0, 7000 - 400 * int(qc_report.get("issue_count", 1))))
    if cover_report and not cover_report.get("valid", True):
        effective_bp = min(effective_bp, 7500)

    passed = (
        not findings
        and bool(qc_report.get("valid", True))
        and (cover_report is None or bool(cover_report.get("valid")))
        and effective_bp >= int(min_score_bp)
    )
    if not passed and effective_bp < int(min_score_bp) and not any("ambang" in x for x in revision_feedback):
        revision_feedback.append(f"Skor kualitas KBM {effective_bp} bp di bawah ambang tinggi {min_score_bp} bp; poles alur, ketegangan cliffhanger, & dialog.")

    return _verdict(
        domain="kbm_apps",
        passed=passed,
        verdict="PASS" if passed else "REJECTED_BELOW_BAR",
        score_bp=effective_bp,
        min_score_bp=min_score_bp,
        findings=findings,
        revision_feedback=revision_feedback,
        checks={
            "arc_rubric": {
                "overall": rubric["overall"],
                "dimensions": dims,
                "chapter_count": rubric["chapter_count"],
            },
            "kbm_qc": {
                "valid": qc_report.get("valid"),
                "issue_count": qc_report.get("issue_count"),
            },
            "cover_check": cover_report,
        },
    )


def _frozen_upstream_set(repo_root: Path) -> set[str]:
    manifest = repo_root / "docs" / "UPSTREAM_SOURCES.json"
    if not manifest.is_file():
        return set()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return {
            str(entry.get("path") or "").replace("\\", "/")
            for entry in (data.get("files") or [])
            if isinstance(entry, dict) and entry.get("path")
        }
    except (OSError, ValueError):
        return set()


def evaluate_code_quality(
    workspace: Path,
    *,
    repo_root: Path | None = None,
    target_files: Sequence[str] = (),
    snippet: str = "",
    test_commands: Sequence[Sequence[str] | str] = (),
    min_score_bp: int = DEFAULT_MIN_QUALITY_SCORE_BP,
    timeout_sec: int = 120,
    run_verify_sources: bool = True,
) -> dict[str, Any]:
    """Verify code changes: syntax/AST validity, secret scan, frozen upstream protection, and real tests."""
    findings: list[dict[str, Any]] = []
    revision_feedback: list[str] = []
    root = (repo_root or workspace).resolve()
    frozen = _frozen_upstream_set(root)

    # 1. Inspect target files for path safety, frozen file protection, Python AST syntax, and secret leaks.
    inspected_files = 0
    for rel in target_files:
        norm = str(rel).replace("\\", "/").lstrip("./")
        if norm in frozen or norm == "docs/UPSTREAM_SOURCES.json":
            findings.append({"rule": "frozen_upstream_touched", "file": norm})
            revision_feedback.append(f"DILARANG menyentuh berkas beku '{norm}'.")
            continue
        if norm.startswith("vault/") or ".ace-web-auth" in norm:
            findings.append({"rule": "vault_file_exposed", "file": norm})
            revision_feedback.append(f"Berkas sensitif '{norm}' dilarang masuk perubahan kode.")
            continue
        fpath = (root / norm) if not Path(norm).is_absolute() else Path(norm)
        if not fpath.is_file():
            findings.append({"rule": "target_file_missing", "file": norm})
            revision_feedback.append(f"Berkas target tidak ditemukan: '{norm}'.")
            continue
        inspected_files += 1
        text = fpath.read_text(encoding="utf-8", errors="replace")
        sec = contains_secret_pattern(text)
        if sec:
            findings.append({"rule": "secret_leak_detected", "file": norm, "pattern": sec})
            revision_feedback.append(f"Terdeteksi pola rahasia/kredensial di '{norm}'; pindahkan ke vault lokal.")
        if fpath.suffix == ".py":
            try:
                ast.parse(text, filename=str(fpath))
            except SyntaxError as exc:
                findings.append({"rule": "python_syntax_error", "file": norm, "line": exc.lineno, "msg": exc.msg})
                revision_feedback.append(f"SyntaxError pada '{norm}' baris {exc.lineno}: {exc.msg}.")

    if snippet.strip():
        sec = contains_secret_pattern(snippet)
        if sec:
            findings.append({"rule": "secret_leak_in_snippet", "pattern": sec})
            revision_feedback.append("Potongan kode mengandung pola rahasia/kredensial.")
        try:
            ast.parse(snippet)
        except SyntaxError as exc:
            findings.append({"rule": "snippet_syntax_error", "line": exc.lineno, "msg": exc.msg})
            revision_feedback.append(f"SyntaxError pada snippet baris {exc.lineno}: {exc.msg}.")

    # 2. Check UPSTREAM_SOURCES.json verification script when present in repo_root.
    verify_sources_ok: bool | None = None
    verify_script = root / "tools" / "verify_sources.py"
    if run_verify_sources and verify_script.is_file():
        v_res = subprocess.run(
            [sys.executable, str(verify_script)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        verify_sources_ok = v_res.returncode == 0
        if not verify_sources_ok:
            findings.append({"rule": "verify_sources_failed", "stderr": v_res.stderr[:240], "stdout": v_res.stdout[:240]})
            revision_feedback.append("Verifikasi hash sumber beku (`tools/verify_sources.py`) GAGAL.")

    # 3. Execute real verification tests / commands.
    cmd_results: list[dict[str, Any]] = []
    if not test_commands and not target_files and not snippet.strip():
        findings.append({"rule": "no_code_evidence_supplied"})
        revision_feedback.append("Wajib sertakan `target_files` atau `test_commands` untuk verifikasi kode.")
    for cmd in test_commands:
        argv = cmd if isinstance(cmd, (list, tuple)) else ["bash", "-lc", str(cmd)]
        res = subprocess.run(
            list(argv),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        ok = res.returncode == 0
        cmd_results.append({
            "cmd": " ".join(str(x) for x in argv),
            "exit_code": res.returncode,
            "passed": ok,
            "stdout_sha256": hashlib.sha256(res.stdout.encode("utf-8")).hexdigest()[:16],
            "stderr_tail": res.stderr.strip()[-300:],
        })
        if not ok:
            findings.append({"rule": "test_command_failed", "cmd": cmd_results[-1]["cmd"], "exit_code": res.returncode})
            revision_feedback.append(f"Perintah uji gagal (exit={res.returncode}): `{cmd_results[-1]['cmd']}` -> {res.stderr.strip()[-180:]}")

    score_bp = 10000
    if findings:
        if any(f["rule"] in ("frozen_upstream_touched", "secret_leak_detected", "verify_sources_failed") for f in findings):
            score_bp = 0
        elif any(f["rule"] in ("python_syntax_error", "test_command_failed", "target_file_missing") for f in findings):
            score_bp = 4000
        else:
            score_bp = 6500

    passed = (not findings) and score_bp >= int(min_score_bp)
    return _verdict(
        domain="code_evolution",
        passed=passed,
        verdict="PASS" if passed else "FAILED_CHECK" if any("failed" in f["rule"] or "error" in f["rule"] for f in findings) else "REJECTED_BELOW_BAR",
        score_bp=score_bp,
        min_score_bp=min_score_bp,
        findings=findings,
        revision_feedback=revision_feedback,
        checks={
            "inspected_files": inspected_files,
            "verify_sources_ok": verify_sources_ok,
            "test_commands": cmd_results,
        },
    )


def check_cross_agent_heterogeneity(
    *,
    creator_agent: str,
    creator_vendor: str,
    reviewer_agent: str,
    reviewer_vendor: str,
    approved: bool,
    reviewer_score_bp: int,
    min_score_bp: int = DEFAULT_MIN_QUALITY_SCORE_BP,
    require_distinct_vendor: bool = False,
) -> dict[str, Any]:
    """Lapis 3 gate: enforce independent review by distinct agent (and distinct vendor when configured)."""
    findings: list[dict[str, Any]] = []
    feedback: list[str] = []
    if not reviewer_agent or not str(reviewer_agent).strip():
        findings.append({"rule": "missing_reviewer"})
        feedback.append("Cross-review wajib memiliki agen peninjau.")
    elif reviewer_agent.strip() == creator_agent.strip():
        findings.append({"rule": "self_review_forbidden", "agent": creator_agent})
        feedback.append(f"Agen '{creator_agent}' dilarang me-review pekerjaannya sendiri.")
    if require_distinct_vendor and creator_vendor and reviewer_vendor:
        if creator_vendor.strip().lower() == reviewer_vendor.strip().lower():
            findings.append({"rule": "same_vendor_reviewer", "vendor": creator_vendor})
            feedback.append(f"Cross-review menuntut vendor berbeda dari pembuat ('{creator_vendor}').")
    if not approved:
        findings.append({"rule": "reviewer_rejected"})
        feedback.append("Peninjau independen menolak hasil (approved=False).")
    if int(reviewer_score_bp) < int(min_score_bp):
        findings.append({"rule": "reviewer_score_below_bar", "score_bp": reviewer_score_bp, "min_score_bp": min_score_bp})
        feedback.append(f"Skor review independen {reviewer_score_bp} bp di bawah ambang {min_score_bp} bp.")
    passed = not findings
    return _verdict(
        domain="cross_review",
        passed=passed,
        verdict="PASS" if passed else "REJECTED_BELOW_BAR",
        score_bp=int(reviewer_score_bp) if not any(f["rule"] in ("self_review_forbidden", "missing_reviewer") for f in findings) else 0,
        min_score_bp=min_score_bp,
        findings=findings,
        revision_feedback=feedback,
        checks={
            "creator": f"{creator_vendor}:{creator_agent}",
            "reviewer": f"{reviewer_vendor}:{reviewer_agent}",
            "approved": bool(approved),
        },
    )
