"""Deterministic Story Projector for 'Cerita ACE' (Appendices Y.5, Y.6, Z.5).

Transforms real `ace.activity.v1` events into concise, honest, 1-2 sentence
(15-45 words) everyday Indonesian stories and maps them to the 5 Anime Studio
companion avatar states (`mendengar`, `bekerja`, `belajar`, `menunggu`, `selesai`)
without fabricating activity on heartbeats or masking failures.
"""
from __future__ import annotations

from typing import Any


AVATAR_STATES = frozenset({
    "mendengar",
    "bekerja",
    "belajar",
    "menunggu",
    "selesai",
})


def _basename_list(refs: list[str]) -> str:
    if not refs:
        return "berkas kerja"
    clean = [str(r).replace("\\", "/").split("/")[-1] for r in refs if str(r).strip()]
    if not clean:
        return "berkas kerja"
    if len(clean) == 1:
        return clean[0]
    return f"{clean[0]} dan {len(clean) - 1} berkas lainnya"


def project_event_to_story(event: dict[str, Any]) -> dict[str, Any]:
    """Project an `ace.activity.v1` event into a human-friendly Indonesian story and avatar state."""
    kind = str(event.get("kind", "")).strip()
    status = str(event.get("status", "ACTIVE")).strip().upper()
    detail = event.get("technical_detail") or {}
    refs = event.get("artifact_refs") or []
    passed = event.get("verification_passed")
    target_file = _basename_list(refs or ([detail["file"]] if "file" in detail else []))
    goal = str(detail.get("goal") or detail.get("title_id") or "permintaanmu").strip()

    # Rule WEB13: Heartbeat NEVER generates a new story card or claims fake work.
    if kind == "heartbeat":
        return {
            "story_text": "",
            "avatar_state": "mendengar",
            "is_story_card": False,
        }

    if kind == "task_started":
        story = (
            f"Aku baru menerima tugas untuk {goal} dan sedang menyusun langkah kerja utamanya. "
            f"Sekarang aku menyiapkan ruang kerja lokal agar perubahan bisa diuji dengan rapi."
        )
        return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}

    if kind == "file_inspected":
        reason = str(detail.get("reason") or "memahami alur kode sebelum melakukan perubahan").strip()
        story = (
            f"Aku sedang memeriksa isi berkas {target_file} untuk {reason}. "
            f"Setelah bagian yang relevan jelas, aku akan menyusun perubahan yang paling aman."
        )
        return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}

    if kind == "hypothesis_formed":
        hyp = str(detail.get("hypothesis") or "masalah utama berasal dari logika pemrosesan input").strip()
        story = (
            f"Dari hasil pemeriksaan awal, dugaanku saat ini adalah {hyp}. "
            f"Aku akan membuktikan dugaan ini lewat pengujian langsung sebelum mengunci perubahan."
        )
        return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}

    if kind == "strategy_changed":
        old_strat = str(detail.get("from_strategy") or "pendekatan awal").replace("_", " ")
        new_strat = str(detail.get("to_strategy") or "strategi baru").replace("_", " ")
        reason = str(detail.get("reason") or "percobaan sebelumnya belum memperbaiki hasil uji").strip()
        story = (
            f"Karena {reason}, aku menghentikan {old_strat} supaya tidak berputar di tempat yang sama. "
            f"Sekarang aku beralih ke {new_strat} yang lebih terarah untuk menyelesaikan tugas ini."
        )
        return {"story_text": story, "avatar_state": "belajar", "is_story_card": True}

    if kind == "code_patched":
        change_desc = str(detail.get("change_summary") or f"memperbarui logika pada {target_file}").strip()
        story = (
            f"Aku baru selesai menulis dan menerapkan perubahan pada {target_file} untuk {change_desc}. "
            f"Langkah berikutnya adalah menjalankan verifikasi otomatis untuk memastikan semuanya berjalan benar."
        )
        return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}

    if kind == "test_executed":
        # Rule WEB14: Never claim success when verification fails!
        if passed is False or status in ("FAILED", "FAILED_WITH_RECOVERY_STATE"):
            err_hint = str(detail.get("failure_hint") or "ada satu pemeriksaan perilaku yang belum sesuai harapan").strip()
            story = (
                f"Aku sudah menjalankan pengujian otomatis pada {target_file}, tetapi verifikasi belum lulus karena {err_hint}. "
                f"Aku sedang memeriksa penyebab kegagalan ini dan menyiapkan perbaikan berikutnya."
            )
            return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}
        story = (
            f"Aku baru menjalankan pengujian otomatis pada {target_file} dan seluruh pemeriksaan berhasil lulus. "
            f"Bukti hasil uji sudah tersimpan dan siap digunakan untuk menyelesaikan tugas."
        )
        return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}

    if kind == "gap_detected":
        missing = str(detail.get("missing_skill_or_tool") or "pola penyelesaian khusus").strip()
        story = (
            f"Aku menemukan batas kemampuanku saat menangani bagian {missing} pada tugas ini. "
            f"Aku mencatat celah ini dan memulai latihan singkat terisolasi agar bisa menyelesaikannya."
        )
        return {"story_text": story, "avatar_state": "belajar", "is_story_card": True}

    if kind == "worker_requested":
        worker_kind = str(detail.get("worker_kind") or "worker AI pendamping").replace("_", " ")
        obj = str(detail.get("objective") or "menyusun kandidat solusi terfokus").strip()
        story = (
            f"Aku mengirim paket tugas terfokus ke {worker_kind} untuk membantu {obj}. "
            f"Setiap hasil dari worker tetap akan kuuji ulang secara independen sebelum dipakai."
        )
        return {"story_text": story, "avatar_state": "menunggu", "is_story_card": True}

    if kind == "worker_completed":
        if passed is False:
            story = (
                f"Worker pendamping sudah mengirim kandidat hasil untuk {target_file}, tetapi gagal saat kuuji ulang di ruang verifikasi. "
                f"Aku menolak kandidat tersebut dan beralih ke perbaikan lokal yang lebih aman."
            )
            return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}
        story = (
            f"Worker pendamping sudah mengembalikan hasil untuk {target_file} dan verifikasi independenku menyatakan hasilnya valid. "
            f"Sekarang aku menggabungkan hasil tersebut ke dalam penyelesaian tugas utama."
        )
        return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}

    if kind == "skill_learned":
        skill_name = str(detail.get("skill_name") or "keterampilan baru").strip()
        story = (
            f"Aku berhasil mempelajari dan menguji keterampilan baru untuk {skill_name} lewat dua kasus uji berbeda. "
            f"Sekarang aku kembali melanjutkan tugas utamamu dengan bekal keterampilan tersebut."
        )
        return {"story_text": story, "avatar_state": "belajar", "is_story_card": True}

    if kind == "task_paused":
        reason = str(detail.get("reason") or "menunggu instruksi atau syarat lanjutan darimu").strip()
        story = (
            f"Aku menjeda pengerjaan tugas ini dengan aman karena {reason}. "
            f"Seluruh progres terakhir sudah tersimpan di checkpoint dan siap dilanjutkan kapan saja."
        )
        return {"story_text": story, "avatar_state": "menunggu", "is_story_card": True}

    if kind == "task_completed":
        if passed is False:
            story = (
                f"Pengerjaan pada {target_file} sudah mencapai batas langkah, namun masih ada pemeriksaan yang belum terverifikasi penuh. "
                f"Silakan tinjau ringkasan bukti untuk menentukan langkah lanjutan."
            )
            return {"story_text": story, "avatar_state": "menunggu", "is_story_card": True}
        story = (
            f"Tugas untuk {goal} sudah selesai kukerjakan dan semua pemeriksaan pada {target_file} berhasil lulus. "
            f"Kamu bisa langsung mencoba hasilnya atau meminta perubahan tambahan lewat chat."
        )
        return {"story_text": story, "avatar_state": "selesai", "is_story_card": True}

    if kind == "task_failed":
        err_reason = str(detail.get("reason") or "terjadi kendala saat verifikasi akhir").strip()
        story = (
            f"Aku belum berhasil menuntaskan tugas ini karena {err_reason}. "
            f"Aku sudah menyimpan kondisi terakhir beserta langkah pemulihan supaya kita bisa memperbaikinya tanpa mengulang dari awal."
        )
        return {"story_text": story, "avatar_state": "menunggu", "is_story_card": True}

    # Default fallback for custom events
    story = (
        f"Aku sedang memproses langkah kerja pada {target_file} untuk menyelesaikan {goal}. "
        f"Setiap perubahan dicatat secara berurutan agar kemajuannya bisa kamu pantau dengan jelas."
    )
    return {"story_text": story, "avatar_state": "bekerja", "is_story_card": True}
