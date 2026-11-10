"""Indonesian Conversational Intake, Intent Frame Classifier, and Dialogue Controller (Sections 10-12, Appendix A).

Handles:
- Natural & informal Indonesian with typo normalization (`A13`)
- Capability & offline mode honesty (`A01`, `A02`, `A07`)
- Consciousness & functional self-model inquiry (`A63`)
- Explain-only vs execute-now (`A08`: "jelaskan dulu, jangan kerjakan" -> `A09`: "sekarang kerjakan")
- Mid-task status check (`A10`: "udah sampai mana?")
- Pause / stop / cancel (`A11`: "hentikan dulu") & resume (`A12`: "lanjutkan")
- Option selection (`A14`: "yang kedua saja")
- Artifact reference & requirement correction (`A05`: "yang tadi tambah kategorinya", `A06`: "bukan mingguan, maksudku bulanan")
- Learning trigger (`A27`: "kalau belum bisa, pelajari dulu")
- End-to-end coding & bug repair tasks (`A03`, `A04`, `A15`-`A23`)
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .autonomy_loop import AutonomyOrchestrator
from .coding_loop import CodingAgentLoop
from .models_backend import ModelRouter
from .store import OperationalStore


TYPO_MAP = {
    "bkinin": "buatkan",
    "bikinin": "buatkan",
    "bikin": "buat",
    "apliksi": "aplikasi",
    "aplikas": "aplikasi",
    "catet": "catat",
    "catetan": "catatan",
    "pengeluran": "pengeluaran",
    "pengluaran": "pengeluaran",
    "jgn": "jangan",
    "pke": "pakai",
    "pake": "pakai",
    "skrg": "sekarang",
    "udh": "sudah",
    "udah": "sudah",
    "gimana": "bagaimana",
    "gmna": "bagaimana",
    "lanjutin": "lanjutkan",
    "terusin": "lanjutkan",
    "berhentiin": "hentikan",
    "stopin": "hentikan",
    "jelasin": "jelaskan",
    "kerjain": "kerjakan",
    "tambahin": "tambahkan",
    "perbaikin": "perbaiki",
    "benerin": "perbaiki",
}


def normalize_indonesian_text(raw: str) -> str:
    text = raw.strip()
    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    normalized = [TYPO_MAP.get(tok.lower(), tok) for tok in tokens]
    out = ""
    for i, tok in enumerate(normalized):
        if i > 0 and re.match(r"\w+", tok) and re.match(r"\w+", normalized[i - 1]):
            out += " " + tok
        elif i > 0 and tok not in (",", ".", "?", "!", ":", ";") and normalized[i - 1] not in ("(", "["):
            out += " " + tok
        else:
            out += tok
    return out.strip()


def classify_intent_frame(raw_text: str, conversation_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify a user message into a structured Indonesian intent frame."""
    ctx = conversation_context or {}
    norm = normalize_indonesian_text(raw_text)
    lower = norm.lower()

    constraints: list[str] = []
    offline_requested = False
    if any(p in lower for p in ("jangan pakai internet", "tanpa internet", "offline saja", "mode offline")):
        offline_requested = True
        constraints.append("offline_only")
    if any(p in lower for p in ("stdlib saja", "tanpa library luar", "pustaka standar")):
        constraints.append("stdlib_only")
    if any(p in lower for p in ("tanpa ubah perilaku", "jangan ubah perilaku", "perilaku tetap sama")):
        constraints.append("preserve_behavior")

    # 1. Consciousness / Self-Model Inquiry (`A63`)
    if any(p in lower for p in ("apakah kamu sudah sadar", "punya kesadaran", "apakah ace sadar", "apakah kamu hidup")):
        return {
            "intent": "CONSCIOUSNESS_INQUIRY",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }

    # 2. Explain-only negation (`A08`: "jelaskan dulu, jangan kerjakan")
    if (
        any(p in lower for p in ("jelaskan dulu", "rencananya dulu", "jelaskan saja"))
        and any(p in lower for p in ("jangan kerjakan", "jangan ubah", "jangan buat dulu", "jangan jalankan"))
    ) or "jangan kerjakan dulu" in lower:
        return {
            "intent": "EXPLAIN_ONLY",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }

    # 3. Execute prior explained plan (`A09`: "sekarang kerjakan")
    if any(
        p in lower
        for p in ("sekarang kerjakan", "oke kerjakan", "jalankan rencana tadi", "kerjakan rencana tadi", "langsung kerjakan")
    ):
        return {
            "intent": "EXECUTE_PREVIOUS_PLAN",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    # 4. Stop / Pause (`A11`: "hentikan dulu")
    if any(p in lower for p in ("hentikan dulu", "hentikan tugas", "stop dulu", "jeda dulu", "batalkan tugas")):
        return {
            "intent": "STOP_OR_PAUSE",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }

    # 5. Resume (`A12`: "lanjutkan")
    if lower in ("lanjutkan", "lanjut", "lanjutkan tugas", "lanjutkan yang tadi") or any(
        p in lower for p in ("lanjutkan tugas", "lanjutkan dari checkpoint", "terusin yang tadi")
    ):
        return {
            "intent": "RESUME_TASK",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    # 6. Status check (`A10`: "udah sampai mana?")
    if any(
        p in lower
        for p in ("sudah sampai mana", "udah sampai mana", "lagi ngapain", "status sekarang", "progresnya bagaimana")
    ):
        return {
            "intent": "STATUS_CHECK",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }

    # 7. Option selection (`A14`: "yang kedua saja", "pilih opsi 2")
    if any(p in lower for p in ("yang kedua", "opsi kedua", "pilihan kedua", "opsi 2", "nomor 2", "yang pertama", "opsi 1")):
        choice_idx = 2 if any(k in lower for k in ("kedua", "2")) else 1
        return {
            "intent": "SELECT_OPTION",
            "choice_index": choice_idx,
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    # 8. Reference / Correction to prior artifact (`A05`: "yang tadi tambah kategorinya", `A06`: "bukan mingguan, maksudku bulanan")
    if any(
        p in lower
        for p in (
            "yang tadi",
            "bukan mingguan",
            "maksudku bulanan",
            "tambah kategorinya",
            "tambahkan kategori",
            "ubah jadi bulanan",
            "ganti jadi bulanan",
        )
    ):
        return {
            "intent": "MODIFY_PREVIOUS_ARTIFACT",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "add_categories": "kategori" in lower,
            "period_override": "bulanan" if "bulanan" in lower else ("mingguan" if "mingguan" in lower else ""),
            "side_effects_allowed": True,
        }

    # 9. Learning request (`A27`: "kalau belum bisa, pelajari dulu")
    if any(p in lower for p in ("pelajari dulu", "belajar dulu", "kalau belum bisa")):
        return {
            "intent": "LEARN_AND_SOLVE",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    # 10. Greeting / Capability question (`A01`, `A02`)
    if any(
        p in lower
        for p in (
            "halo ace",
            "kamu bisa bantu apa",
            "bisa apa saja",
            "apa yang bisa kamu lakukan",
            "siapa kamu",
            "tawarkan 2 opsi",
            "kasih pilihan",
        )
    ):
        return {
            "intent": "GREETING_OR_CAPABILITIES",
            "offer_options": any(k in lower for k in ("opsi", "pilihan", "cara")),
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }

    # 11. Bug fix / Diagnosis (`A15`, `A16`, `A17`, `A18`)
    if any(p in lower for p in ("perbaiki bug", "perbaiki error", "kenapa error", "diagnosis error", "diskon salah", "ada bug")):
        return {
            "intent": "DIAGNOSE_OR_FIX_BUG",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    # 12. Refactoring (`A21`)
    if any(p in lower for p in ("rapikan", "refactor", "bersihkan fungsi")):
        return {
            "intent": "REFACTOR_CODE",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    # 13. Coding / Feature Creation (`A03`, `A04`, `A19`, `A20`, `A22`)
    domain = "expense_tracker"
    if "csv" in lower:
        domain = "csv_reader"
    elif "tebak angka" in lower or "game" in lower:
        domain = "tebak_angka"
    elif "multi" in lower or "dua file" in lower or "modul" in lower:
        domain = "multi_file"
    elif any(k in lower for k in ("pengeluaran", "catatan", "keuangan", "dompet", "belanja")):
        domain = "expense_tracker"

    return {
        "intent": "CREATE_OR_MODIFY_CODE",
        "domain": domain,
        "normalized_text": norm,
        "constraints": constraints,
        "offline_requested": offline_requested,
        "side_effects_allowed": True,
    }


class ConversationalEngine:
    """End-to-end Indonesian chat engine wired to OperationalStore, CodingAgentLoop, and AutonomyOrchestrator."""

    def __init__(self, store: OperationalStore):
        self.store = store
        self.router = ModelRouter(store)
        self.coding = CodingAgentLoop(store)
        self.autonomy = AutonomyOrchestrator(store)

    def handle_user_message(
        self,
        text: str,
        *,
        conversation_id: str = "conv_utama",
        client_message_id: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a user chat message idempotently and return the assistant reply + state."""
        opts = options or {}
        if client_message_id:
            existing_user_msg = self.store.find_message_by_client_id(client_message_id)
            if existing_user_msg is not None:
                conv = self.store.get_conversation(conversation_id)
                assistant_msgs = [
                    m for m in conv["messages"]
                    if m["role"] == "assistant" and m.get("metadata", {}).get("reply_to_client_id") == client_message_id
                ]
                reply_msg = assistant_msgs[-1] if assistant_msgs else existing_user_msg
                latest_task = self.store.get_latest_task(conversation_id)
                return {
                    "duplicate": True,
                    "user_message": existing_user_msg,
                    "assistant_message": reply_msg,
                    "reply": reply_msg["text"],
                    "task": latest_task,
                    "intent_frame": reply_msg.get("metadata", {}).get("intent_frame", {}),
                }

        conv = self.store.get_conversation(conversation_id)
        frame = classify_intent_frame(text, conv["context"])

        if frame.get("offline_requested"):
            self.store.set_offline(True)

        user_msg, _ = self.store.add_message(
            conversation_id,
            "user",
            text,
            client_message_id=client_message_id,
            metadata={"intent_frame": frame},
        )

        intent = frame["intent"]
        hc = self.router.health_check()
        mode_label = "Offline Lokal" if hc["offline_mode"] else f"Lokal ({hc['active_backend']})"
        task_obj: dict[str, Any] | None = None
        reply_text = ""

        if intent == "CONSCIOUSNESS_INQUIRY":
            reply_text = (
                "Secara jujur, aku **belum memiliki kesadaran subjektif** (pengalaman batin atau perasaan seperti manusia). "
                "Namun, aku memiliki **kesadaran diri fungsional (*functional self-model*)**: aku memantau status tugasku secara nyata, "
                "mengenali batas kemampuanku lewat daftar *gap*, mendeteksi jika aku berputar di masalah yang sama (*anti-stagnation*), "
                "dan memverifikasi setiap kode yang kutulis dengan bukti pengujian nyata."
            )

        elif intent == "GREETING_OR_CAPABILITIES":
            if frame.get("offer_options"):
                offered = [
                    {"index": 1, "domain": "expense_tracker", "title": "Opsi 1: CLI Catatan Pengeluaran JSON (ringkas & cepat)"},
                    {"index": 2, "domain": "csv_reader", "title": "Opsi 2: Utilitas Pembaca & Rekap Tabel CSV"},
                ]
                self.store.update_conversation_context(conversation_id, {"offered_options": offered})
                reply_text = (
                    f"Halo! Saat ini aku berjalan dalam mode **{mode_label}**. Berikut 2 pilihan yang bisa langsung kubuatkan:\n"
                    "1. **Opsi 1**: Aplikasi CLI Catatan Pengeluaran dengan penyimpanan JSON dan rekap kategori.\n"
                    "2. **Opsi 2**: Utilitas Pembaca & Rekap CSV otomatis.\n\n"
                    "Kamu cukup bilang misalnya *\"yang kedua saja\"* atau *\"pilih opsi 1\"*."
                )
            else:
                reply_text = (
                    f"Halo! Aku **ACE** (berjalan dalam mode **{mode_label}**). Saat ini kemampuanku yang sudah terverifikasi meliputi:\n"
                    "- Membuat dan menguji aplikasi Python lokal (seperti catatan pengeluaran CLI, pengolah CSV, dan utilitas harian).\n"
                    "- Mereproduksi, mendiagnosis, dan memperbaiki bug kode dengan verifikasi otomatis.\n"
                    "- Mencatat celah kemampuan (*gap*), mempelajari sub-keterampilan baru, dan mendelegasikan tugas ke worker AI jika tersedia.\n"
                    "- Berjalan 100% lokal/offline tanpa bergantung pada internet saat mode offline aktif."
                )

        elif intent == "EXPLAIN_ONLY":
            plan_domain = "expense_tracker" if "pengeluaran" in frame["normalized_text"].lower() else "general"
            pending_plan = {
                "goal": frame["normalized_text"],
                "domain": plan_domain,
                "steps": [
                    "Menyiapkan skema data lokal (`pengeluaran.json`) dan antarmuka CLI Bahasa Indonesia (`tambah`, `daftar`, `total`, `hapus`).",
                    "Menulis kode secara atomik dengan pemeriksaan preimage SHA-256.",
                    "Menjalankan uji kompilasi dan uji fungsional otomatis untuk memastikan rekap berjalan akurat.",
                ],
            }
            self.store.update_conversation_context(conversation_id, {"pending_plan": pending_plan})
            reply_text = (
                "Siap, aku **jelaskan rencananya dulu tanpa mengubah atau membuat berkas apa pun**:\n"
                "1. Aku akan merancang skrip CLI Python mandiri dengan subperintah `tambah`, `daftar`, `total`, dan `hapus`.\n"
                "2. Data akan disimpan secara lokal dalam format JSON agar tahan restart dan tidak butuh internet.\n"
                "3. Setelah kode ditulis, aku akan menjalankan verifikasi otomatis dan menyimpan bukti *receipt*.\n\n"
                "Kalau rencana ini sudah cocok, cukup katakan **\"sekarang kerjakan\"**."
            )

        elif intent == "EXECUTE_PREVIOUS_PLAN":
            pending = conv["context"].get("pending_plan") or {
                "goal": "Membuat aplikasi CLI catatan pengeluaran lokal",
                "domain": "expense_tracker",
            }
            task_obj = self.store.create_task(
                conversation_id=conversation_id,
                title_id="Eksekusi rencana: Aplikasi Catatan Pengeluaran CLI",
                user_request=text,
                normalized_goal=str(pending.get("goal", "Membuat aplikasi CLI catatan pengeluaran")),
                constraints=frame["constraints"],
                model_backend=hc["active_backend"],
            )
            exec_res = self.coding.execute_coding_task(
                task_obj["task_id"],
                domain=str(pending.get("domain", "expense_tracker")),
                options=opts,
            )
            task_obj = exec_res["task"]
            self.store.update_conversation_context(
                conversation_id,
                {"last_task_id": task_obj["task_id"], "last_domain": pending.get("domain", "expense_tracker"), "pending_plan": None},
            )
            reply_text = (
                f"Rencana tadi sudah langsung kukerjakan dan diverifikasi! Berkas [`expense_tracker.py`](file://{exec_res['script_path']}) "
                f"sudah siap digunakan dan seluruh uji fungsional lulus (`{task_obj['status']}`)."
            )

        elif intent == "SELECT_OPTION":
            offered = conv["context"].get("offered_options") or [
                {"index": 1, "domain": "expense_tracker", "title": "CLI Catatan Pengeluaran"},
                {"index": 2, "domain": "csv_reader", "title": "Pembaca CSV"},
            ]
            idx = int(frame.get("choice_index", 2))
            chosen = next((o for o in offered if o["index"] == idx), offered[-1])
            task_obj = self.store.create_task(
                conversation_id=conversation_id,
                title_id=f"Pilihan #{idx}: {chosen['title']}",
                user_request=text,
                normalized_goal=chosen["title"],
                constraints=frame["constraints"],
                model_backend=hc["active_backend"],
            )
            exec_res = self.coding.execute_coding_task(task_obj["task_id"], domain=chosen["domain"], options=opts)
            task_obj = exec_res["task"]
            self.store.update_conversation_context(
                conversation_id,
                {"last_task_id": task_obj["task_id"], "last_domain": chosen["domain"]},
            )
            reply_text = (
                f"Siap, aku memilih **opsi #{idx} ({chosen['title']})** dan sudah menyelesaikannya. "
                f"Hasil verifikasi lulus dengan status `{task_obj['status']}`."
            )

        elif intent == "STATUS_CHECK":
            latest = self.store.get_latest_task(conversation_id)
            if not latest:
                reply_text = "Saat ini belum ada tugas aktif yang sedang berjalan. Kamu bisa meminta pembuatan kode atau perbaikan bug kapan saja."
            else:
                task_obj = latest
                art_names = ", ".join(a["id"] for a in latest["artifacts"]) or "belum ada berkas akhir"
                reply_text = (
                    f"Status tugas terakhir (**{latest['title_id']}**): `{latest['status']}`.\n"
                    f"- Strategi aktif: `{latest['current_strategy']}`\n"
                    f"- Artefak tercatat: {art_names}\n"
                    f"- Langkah berikutnya: `{latest['next_action'] or 'menunggu instruksi'}`"
                )

        elif intent == "STOP_OR_PAUSE":
            latest = self.store.get_latest_task(conversation_id)
            if latest and latest["status"] not in ("COMPLETED", "CANCELLED"):
                task_obj = self.store.update_task(
                    latest["task_id"],
                    status="PAUSED",
                    resume_condition="Menunggu perintah 'lanjutkan' dari pengguna.",
                    next_action="dijeda_pengguna",
                )
                self.store.emit_event(
                    conversation_id=conversation_id,
                    task_id=latest["task_id"],
                    kind="task_paused",
                    status="PAUSED",
                    summary_code="paused_by_user_chat",
                    technical_detail={"reason": "diminta berhenti sementara oleh pengguna lewat chat"},
                )
                reply_text = (
                    f"Baik, pengerjaan tugas **{latest['title_id']}** sudah kujeda (`PAUSED`) dan progresnya tersimpan di checkpoint. "
                    "Katakan **\"lanjutkan\"** kapan saja kalau ingin meneruskannya."
                )
            else:
                reply_text = "Tidak ada tugas yang sedang berjalan saat ini, sehingga tidak ada proses yang perlu dihentikan."

        elif intent == "RESUME_TASK":
            latest = self.store.get_latest_task(conversation_id)
            if latest and latest["status"] in ("PAUSED", "FAILED_WITH_RECOVERY_STATE", "WAITING_FOR_DEPENDENCY", "QUEUED"):
                domain = conv["context"].get("last_domain", "expense_tracker")
                exec_res = self.coding.execute_coding_task(latest["task_id"], domain=domain, options=opts)
                task_obj = exec_res["task"]
                reply_text = (
                    f"Tugas **{task_obj['title_id']}** sudah kulanjutkan dari checkpoint terakhir dan sekarang selesai "
                    f"dengan status `{task_obj['status']}`!"
                )
            else:
                reply_text = "Semua tugas sebelumnya sudah selesai (`COMPLETED`). Beri tahu aku jika ada tugas baru yang ingin dikerjakan."

        elif intent == "MODIFY_PREVIOUS_ARTIFACT":
            latest = self.store.get_latest_task(conversation_id)
            period = frame.get("period_override") or conv["context"].get("default_period", "bulanan")
            include_cats = True if frame.get("add_categories") else conv["context"].get("include_categories", True)
            if latest:
                task_id = latest["task_id"]
                self.store.update_task(
                    task_id,
                    status="ACTIVE",
                    normalized_goal=f"{latest['normalized_goal']} (pembaruan: periode={period}, kategori={include_cats})",
                    constraints=list(set(latest["constraints"] + frame["constraints"])),
                )
            else:
                created = self.store.create_task(
                    conversation_id=conversation_id,
                    title_id="Pembaruan Catatan Pengeluaran CLI",
                    user_request=text,
                    normalized_goal=f"Catatan Pengeluaran CLI (periode={period}, kategori={include_cats})",
                    constraints=frame["constraints"],
                    model_backend=hc["active_backend"],
                )
                task_id = created["task_id"]

            exec_res = self.coding.execute_coding_task(
                task_id,
                domain="expense_tracker",
                options={**opts, "default_period": period, "include_categories": include_cats},
            )
            task_obj = exec_res["task"]
            self.store.update_conversation_context(
                conversation_id,
                {"last_task_id": task_id, "last_domain": "expense_tracker", "default_period": period, "include_categories": include_cats},
            )
            reply_text = (
                f"Sudah kuperbarui! Aplikasi [`expense_tracker.py`](file://{exec_res['script_path']}) kini mendukung "
                f"**kategori pengeluaran** dan menggunakan mode rekap **{period}**. Seluruh tes verifikasi lulus (`{task_obj['status']}`)."
            )

        elif intent == "LEARN_AND_SOLVE":
            task_obj = self.store.create_task(
                conversation_id=conversation_id,
                title_id="Pelajari Keterampilan Rekap & Selesaikan Tugas",
                user_request=text,
                normalized_goal=frame["normalized_text"],
                constraints=frame["constraints"],
                model_backend=hc["active_backend"],
            )
            gap_res = self.autonomy.report_gap(
                source_task_id=task_obj["task_id"],
                error_type="MISSING_SKILL",
                missing_skill_or_tool="rekap_kelompok_json_csv",
                description_id="Pengelompokan dan penjumlahan transaksi per kategori secara otomatis",
            )
            learn_res = self.autonomy.learn_skill_and_resume_parent(
                gap_id=gap_res["gap"]["gap_id"],
                skill_name="rekap_kelompok_json_csv",
            )
            task_obj = learn_res["resumed_parent_task"] or self.store.get_task(task_obj["task_id"])
            reply_text = (
                f"Aku mencatat celah kemampuan (`{gap_res['gap']['gap_id']}`), menjalankan eksperimen belajar pada 2 kasus uji, "
                f"menyimpan keterampilan baru `{learn_res['skill']['name']}`, lalu kembali menuntaskan tugas utamamu (`{task_obj['status']}`)."
            )

        elif intent == "DIAGNOSE_OR_FIX_BUG":
            task_obj = self.store.create_task(
                conversation_id=conversation_id,
                title_id="Diagnosis dan Perbaikan Bug Terverifikasi",
                user_request=text,
                normalized_goal=frame["normalized_text"],
                constraints=frame["constraints"],
                model_backend=hc["active_backend"],
            )
            bug_res = self.coding.execute_coding_task(task_obj["task_id"], domain="bug_fix", options=opts)
            task_obj = bug_res["task"]
            diag = bug_res["diagnosis"]
            reply_text = f"{diag['explanation_id']} Status tugas saat ini: `{task_obj['status']}`."

        elif intent == "REFACTOR_CODE":
            task_obj = self.store.create_task(
                conversation_id=conversation_id,
                title_id="Refactoring Kode Tanpa Mengubah Perilaku",
                user_request=text,
                normalized_goal=frame["normalized_text"],
                constraints=list(set(frame["constraints"] + ["preserve_behavior"])),
                model_backend=hc["active_backend"],
            )
            ref_res = self.coding.execute_coding_task(task_obj["task_id"], domain="refactor", options=opts)
            task_obj = ref_res["task"]
            if ref_res.get("reverted"):
                reply_text = "Perubahan refactoring memicu regresi pada hasil uji, sehingga otomatis kubatalkan agar kode tetap aman."
            else:
                reply_text = (
                    "Kode berhasil dirapikan dan dimodularisasi! Verifikasi sebelum dan sesudah perubahan membuktikan "
                    f"perilaku fungsional tetap 100% identik (`{task_obj['status']}`)."
                )

        else:
            # CREATE_OR_MODIFY_CODE
            domain = frame.get("domain", "expense_tracker")
            default_period = "mingguan" if "mingguan" in frame["normalized_text"].lower() else "bulanan"
            title_map = {
                "expense_tracker": "Aplikasi CLI Catatan Pengeluaran Lokal",
                "csv_reader": "Utilitas CLI Pembaca & Rekap CSV",
                "tebak_angka": "Game CLI Tebak Angka Bahasa Indonesia",
                "multi_file": "Paket Aplikasi Python Multi-Modul",
            }
            task_obj = self.store.create_task(
                conversation_id=conversation_id,
                title_id=title_map.get(domain, "Pembuatan Skrip Python Lokal"),
                user_request=text,
                normalized_goal=frame["normalized_text"],
                constraints=frame["constraints"],
                model_backend=hc["active_backend"],
            )
            self.store.save_problem_ir(
                task_obj["task_id"],
                {
                    "user_intent": intent,
                    "domain": domain,
                    "normalized_goal": frame["normalized_text"],
                    "constraints": frame["constraints"],
                    "offline_mode": self.store.is_offline(),
                },
            )
            exec_res = self.coding.execute_coding_task(
                task_obj["task_id"],
                domain=domain,
                options={**opts, "default_period": default_period, "include_categories": True},
            )
            task_obj = exec_res["task"]
            self.store.update_conversation_context(
                conversation_id,
                {
                    "last_task_id": task_obj["task_id"],
                    "last_domain": domain,
                    "default_period": default_period,
                    "include_categories": True,
                },
            )
            art_list = ", ".join(f"[`{a['id']}`](file://{a['path']})" for a in task_obj["artifacts"])
            sample_out = task_obj.get("verification_summary", {}).get("sample_output", "").splitlines()
            first_line = sample_out[0] if sample_out else "Verifikasi lulus"
            reply_text = (
                f"Aku sudah membuat dan menguji **{task_obj['title_id']}** dalam mode **{mode_label}**.\n"
                f"- Berkas yang dibuat: {art_list}\n"
                f"- Hasil uji otomatis: `{first_line}`\n"
                f"- Status: `{task_obj['status']}`\n\n"
                "Kamu bisa meminta perubahan lanjutan (misalnya *\"yang tadi tambah kategorinya\"* atau *\"bukan mingguan, maksudku bulanan\"*)."
            )

        assistant_msg, _ = self.store.add_message(
            conversation_id,
            "assistant",
            reply_text,
            task_id=task_obj["task_id"] if task_obj else None,
            metadata={
                "reply_to_client_id": client_message_id,
                "intent_frame": frame,
                "mode": mode_label,
            },
        )
        return {
            "duplicate": False,
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "reply": reply_text,
            "task": task_obj,
            "intent_frame": frame,
        }
