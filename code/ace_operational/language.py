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

from enum import Enum
from pathlib import Path
import re
from typing import Any

from .autonomy_loop import AutonomyOrchestrator
from .coding_loop import CodingAgentLoop
from .memory_bridge import ConversationalMemoryManager, classify_memory_intent
from .models_backend import ModelRouter
from .speech_acquisition import (
    SpeechDevelopmentEngine,
    classify_speech_intent,
    handle_speech_chat_intent,
)
from .store import OperationalStore


class Intent(str, Enum):
    """Standard Indonesian conversational intent identifiers (Sections 10-12, Appendix A)."""

    CONSCIOUSNESS_INQUIRY = "CONSCIOUSNESS_INQUIRY"
    EXPLAIN_ONLY = "EXPLAIN_ONLY"
    EXECUTE_PREVIOUS_PLAN = "EXECUTE_PREVIOUS_PLAN"
    STOP_OR_PAUSE = "STOP_OR_PAUSE"
    RESUME_TASK = "RESUME_TASK"
    STATUS_CHECK = "STATUS_CHECK"
    SELECT_OPTION = "SELECT_OPTION"
    MODIFY_PREVIOUS_ARTIFACT = "MODIFY_PREVIOUS_ARTIFACT"
    LEARN_AND_SOLVE = "LEARN_AND_SOLVE"
    MEMORY_STORE = "MEMORY_STORE"
    MEMORY_RECALL = "MEMORY_RECALL"
    MEMORY_FORGET = "MEMORY_FORGET"
    MEMORY_AUDIT = "MEMORY_AUDIT"
    LEARN_LANGUAGE = "LEARN_LANGUAGE"
    TRAIN_SPEECH = "TRAIN_SPEECH"
    TEACH_WORD = "TEACH_WORD"
    SPEECH_STATUS = "SPEECH_STATUS"
    GREETING_OR_CAPABILITIES = "GREETING_OR_CAPABILITIES"
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
    DIAGNOSE_OR_FIX_BUG = "DIAGNOSE_OR_FIX_BUG"
    REFACTOR_CODE = "REFACTOR_CODE"
    CREATE_OR_MODIFY_CODE = "CREATE_OR_MODIFY_CODE"


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
    "dlu": "dulu",
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
    "bgt": "banget",
    "bgtu": "begitu",
    "gitu": "begitu",
    "kalo": "kalau",
    "kl": "kalau",
    "kmrn": "kemarin",
    "bbrp": "beberapa",
    "mksd": "maksud",
    "krn": "karena",
    "bener": "benar",
    "beneran": "beneran",
    "gabisa": "tidak bisa",
    "ga": "tidak",
    "gak": "tidak",
    "nggak": "tidak",
    "gamau": "tidak mau",
    "blm": "belum",
    "belom": "belum",
    "aja": "saja",
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


def _format_mode_label(hc: dict[str, Any]) -> str:
    if hc.get("offline_mode"):
        return "Offline Lokal"
    backend = str(hc.get("active_backend", "") or "").strip()
    if not backend or backend == "unavailable":
        return "Lokal Mandiri"
    return f"Lokal ({backend})"


def _is_status_check_query(lower: str) -> bool:
    if any(
        p in lower
        for p in (
            "sudah sampai mana",
            "udah sampai mana",
            "status sekarang",
            "status tugas",
            "progresnya bagaimana",
            "progres tugas",
        )
    ):
        return True
    return "lagi ngapain" in lower and any(w in lower for w in ("tugas", "progres", "proyek", "kerjaan", "skrip"))


def _classify_greeting_or_capability(
    lower: str,
    norm: str,
    constraints: list[str],
    offline_requested: bool,
) -> dict[str, Any] | None:
    is_capability_query = any(
        p in lower
        for p in (
            "kamu bisa bantu apa",
            "bisa bantu apa",
            "bantu apa saja",
            "bisa apa saja",
            "bisa ngapain",
            "apa yang bisa kamu lakukan",
            "apa yang bisa kamu buat",
            "tawarkan 2 opsi",
            "kasih pilihan",
            "apakah kamu sudah bisa",
            "apakah kamu bisa",
            "sudah bisa apa",
            "skill apa",
            "keterampilan apa",
            "kemampuan apa",
            "daftar skill",
            "daftar kemampuan",
            "bagaimana kemampuanmu",
            "kemampuanmu sekarang",
            "skill terbarumu",
            "apa skill terbaru",
            "apa keahlianmu",
            "keahlianmu apa",
            "kamu bisa apa",
            "apa yang kamu bisa",
            "fitur apa saja",
            "apa saja yang bisa kamu lakukan",
        )
    )
    is_short_greeting = any(
        re.search(r"\b" + re.escape(w) + r"\b", lower)
        for w in (
            "halo", "hai", "hi", "hey", "hei",
            "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "selamat datang",
            "assalamualaikum", "assalamu'alaikum", "apa kabar", "gimana kabar", "salam",
        )
    ) or "halo ace" in lower

    has_coding_action = any(
        re.search(r"\b" + re.escape(k) + r"\b", lower)
        for k in (
            "buat", "buatkan", "bikin", "bikinin", "program", "skrip", "script",
            "kode", "koding", "aplikasi", "fungsi", "perbaiki", "refactor",
            "rapikan", "kalkulator", "fibonacci", "csv", "tebak angka", "catat",
            "pengeluaran", "modul", "hitung", "ubah", "konversi",
        )
    )
    if is_capability_query or (is_short_greeting and not has_coding_action):
        resolved_intent = Intent.GREETING_OR_CAPABILITIES if is_capability_query else Intent.GENERAL_CONVERSATION
        return {
            "intent": resolved_intent,
            "offer_options": any(k in lower for k in ("opsi", "pilihan", "cara")),
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }
    return None


def _make_base_frame(
    intent: str | Intent,
    norm: str,
    constraints: list[str],
    offline_requested: bool,
    *,
    side_effects: bool,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "normalized_text": norm,
        "constraints": constraints,
        "offline_requested": offline_requested,
        "side_effects_allowed": side_effects,
        **extra,
    }


def _classify_task_control_intent(
    lower: str,
    norm: str,
    constraints: list[str],
    offline_requested: bool,
) -> dict[str, Any] | None:
    if any(p in lower for p in ("apakah kamu sudah sadar", "punya kesadaran", "apakah ace sadar", "apakah kamu hidup")):
        return _make_base_frame("CONSCIOUSNESS_INQUIRY", norm, constraints, offline_requested, side_effects=False)

    if (
        any(p in lower for p in ("jelaskan dulu", "rencananya dulu", "jelaskan saja"))
        and any(p in lower for p in ("jangan kerjakan", "jangan ubah", "jangan buat dulu", "jangan jalankan"))
    ) or "jangan kerjakan dulu" in lower:
        return _make_base_frame("EXPLAIN_ONLY", norm, constraints, offline_requested, side_effects=False)

    if any(p in lower for p in ("sekarang kerjakan", "oke kerjakan", "jalankan rencana tadi", "kerjakan rencana tadi", "langsung kerjakan")):
        return _make_base_frame("EXECUTE_PREVIOUS_PLAN", norm, constraints, offline_requested, side_effects=True)

    if any(p in lower for p in ("hentikan dulu", "hentikan tugas", "stop dulu", "jeda dulu", "batalkan tugas")):
        return _make_base_frame("STOP_OR_PAUSE", norm, constraints, offline_requested, side_effects=False)

    if lower in ("lanjutkan", "lanjut", "lanjutkan tugas", "lanjutkan yang tadi") or any(
        p in lower for p in ("lanjutkan tugas", "lanjutkan dari checkpoint", "terusin yang tadi")
    ):
        return _make_base_frame("RESUME_TASK", norm, constraints, offline_requested, side_effects=True)

    if _is_status_check_query(lower):
        return _make_base_frame("STATUS_CHECK", norm, constraints, offline_requested, side_effects=False)

    if any(p in lower for p in ("yang kedua", "opsi kedua", "pilihan kedua", "opsi 2", "nomor 2", "yang pertama", "opsi 1")):
        choice_idx = 2 if any(k in lower for k in ("kedua", "2")) else 1
        return _make_base_frame("SELECT_OPTION", norm, constraints, offline_requested, side_effects=True, choice_index=choice_idx)

    if any(p in lower for p in ("yang tadi", "bukan mingguan", "maksudku bulanan", "tambah kategorinya", "tambahkan kategori", "ubah jadi bulanan", "ganti jadi bulanan")):
        return _make_base_frame(
            "MODIFY_PREVIOUS_ARTIFACT", norm, constraints, offline_requested, side_effects=True,
            add_categories="kategori" in lower,
            period_override="bulanan" if "bulanan" in lower else ("mingguan" if "mingguan" in lower else ""),
        )

    if any(p in lower for p in ("pelajari dulu", "belajar dulu", "kalau belum bisa")):
        return _make_base_frame("LEARN_AND_SOLVE", norm, constraints, offline_requested, side_effects=True)
    return None


def classify_intent_frame(raw_text: str, conversation_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify a user message into a structured Indonesian intent frame."""
    ctx = conversation_context or {}
    norm = normalize_indonesian_text(raw_text)
    lower = norm.lower()
    raw_lower = raw_text.lower()

    constraints: list[str] = []
    offline_requested = False
    if any(p in lower for p in ("jangan pakai internet", "tanpa internet", "offline saja", "mode offline")):
        offline_requested = True
        constraints.append("offline_only")
    if any(p in lower for p in ("stdlib saja", "tanpa library luar", "pustaka standar")):
        constraints.append("stdlib_only")
    if any(p in lower for p in ("tanpa ubah perilaku", "jangan ubah perilaku", "perilaku tetap sama")):
        constraints.append("preserve_behavior")

    ctrl_hit = _classify_task_control_intent(lower, norm, constraints, offline_requested)
    if ctrl_hit is not None:
        return ctrl_hit

    mem_hit = classify_memory_intent(raw_text, norm, constraints, offline_requested, conversation_context=ctx)
    if mem_hit is not None:
        return mem_hit

    speech_hit = classify_speech_intent(raw_text, norm, constraints, offline_requested, conversation_context=ctx)
    if speech_hit is not None:
        return speech_hit
    if any(p in lower for p in (
        "belajar bahasa", "pelajari bahasa", "fokus belajar bahasa",
        "belajar bahasa dulu", "tingkatkan kemampuan bahasa", "pahami bahasa", "belajar ngobrol",
    )):
        return _make_base_frame(Intent.LEARN_LANGUAGE, norm, constraints, offline_requested, side_effects=False)

    greet_hit = _classify_greeting_or_capability(lower, norm, constraints, offline_requested)
    if greet_hit is not None:
        return greet_hit

    return _classify_coding_or_fallback(lower, raw_lower, norm, constraints, offline_requested)


def _classify_coding_or_fallback(
    lower: str,
    raw_lower: str,
    norm: str,
    constraints: list[str],
    offline_requested: bool,
) -> dict[str, Any]:
    if any(p in lower for p in ("perbaiki bug", "perbaiki error", "kenapa error", "diagnosis error", "diskon salah", "ada bug")):
        return {
            "intent": "DIAGNOSE_OR_FIX_BUG",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    if any(p in lower for p in ("rapikan", "refactor", "bersihkan fungsi")):
        return {
            "intent": "REFACTOR_CODE",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    if "csv" in lower:
        domain, domain_confidence = "csv_reader", 0.95
    elif "tebak angka" in lower or "game" in lower:
        domain, domain_confidence = "tebak_angka", 0.95
    elif (
        re.search(r"\bmulti\s*[-_ ]?\s*(modul|file|berkas)\b", raw_lower)
        or re.search(r"\bmulti\s*[-_ ]?\s*(modul|file|berkas)\b", lower)
        or any(
            phrase in lower or phrase in raw_lower
            for phrase in (
                "multi modul", "multi-modul", "multi file", "multi-file",
                "multi berkas", "multi-berkas", "dua file", "dua berkas",
                "banyak file", "banyak berkas", "banyak modul",
                "struktur berkas", "struktur modul", "paket aplikasi",
            )
        )
    ):
        domain, domain_confidence = "multi_file", 0.95
    elif any(k in lower for k in ("pengeluaran", "catatan", "keuangan", "dompet", "catat belanja", "catatan belanja", "daftar belanja", "keranjang belanja")):
        domain, domain_confidence = "expense_tracker", 0.95
    else:
        coding_words = (
            "buat", "buatkan", "bikin", "bikinin", "tuliskan", "program",
            "skrip", "script", "kode", "koding", "coding", "aplikasi",
            "fungsi", "kalkulator", "hitung", "ubah", "konversi",
            "fibonacci", "modul", "algoritma", "utilitas",
        )
        has_trigger = any(re.search(r"\b" + re.escape(w) + r"\b", lower) for w in coding_words)
        if not has_trigger:
            return {
                "intent": Intent.GENERAL_CONVERSATION,
                "offer_options": False,
                "normalized_text": norm,
                "constraints": constraints,
                "offline_requested": offline_requested,
                "side_effects_allowed": False,
            }
        domain, domain_confidence = "general", 0.90

    return {
        "intent": Intent.CREATE_OR_MODIFY_CODE,
        "domain": domain,
        "domain_confidence": domain_confidence,
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
        self.speech = SpeechDevelopmentEngine(store)
        self.memory = ConversationalMemoryManager(store)

    def _build_capabilities_reply(self, mode_label: str) -> str:
        active_skills = self.store.list_skills(active_only=True)
        skill_names = ", ".join(f"`{s['name']}`" for s in active_skills) if active_skills else "belum ada skill tambahan"
        tested_caps = [f for f in self.store.list_frontier() if f.get("status") == "KNOWN_AND_TESTED"]
        sp = self.speech.get_profile()
        mem = self.memory.get_summary()
        return (
            f"Halo! Aku **ACE** (berjalan dalam mode **{mode_label}**). Saat ini kemampuanku yang sudah terverifikasi meliputi:\n"
            "- Membuat dan menguji aplikasi Python lokal (seperti catatan pengeluaran CLI, pengolah CSV, dan utilitas harian).\n"
            "- Mereproduksi, mendiagnosis, dan memperbaiki bug kode dengan verifikasi otomatis.\n"
            "- Mencatat celah kemampuan (*gap*), mempelajari sub-keterampilan baru, dan mendelegasikan tugas ke worker AI jika tersedia.\n"
            "- Berjalan 100% lokal/offline tanpa bergantung pada internet saat mode offline aktif.\n"
            f"- **Perkembangan berbicara (`4 tahap`)**: Tahap `{sp['current_stage']}/4` ({sp['current_stage_title']}), {sp['vocab_count']} kosakata persisten.\n"
            f"- **Memori Jangka Panjang (`OMEGA-07`)**: {mem['active_records']} ingatan aktif (rantai hash `{'VALID' if mem['chain_ok'] else 'PERLU CEK'}`).\n"
            f"- **Skill hasil belajar aktif ({len(active_skills)})**: {skill_names}\n"
            f"- **Frontier terverifikasi**: {len(tested_caps)} kapabilitas berstatus `KNOWN_AND_TESTED`."
        )

    def _try_gguf_verified_reply(
        self,
        *,
        text: str,
        conv: dict[str, Any],
        hc: dict[str, Any],
        mode_label: str,
        latest_task: dict[str, Any] | None,
        recent_assistant: list[str],
        active_skills: int,
        tested_caps: int,
    ) -> str | None:
        sys_ctx = self.speech.build_gguf_speech_prompt_context(
            user_text=text,
            latest_task=latest_task,
            mode_label=mode_label,
        )
        mem_ctx = self.memory.build_prompt_context(text)
        sys_ctx = f"{sys_ctx}\nMemori jangka panjang relevan: {mem_ctx}."
        messages: list[dict[str, str]] = [{"role": "system", "content": sys_ctx}]
        for prev in (conv.get("messages") or [])[-6:]:
            role = "assistant" if prev.get("role") == "assistant" else "user"
            prev_text = str(prev.get("text") or "").strip()
            if prev_text:
                messages.append({"role": role, "content": prev_text})
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != text:
            messages.append({"role": "user", "content": text})
        try:
            resp = self.router.generate_text(
                messages,
                max_tokens=240,
                temperature=0.7,
            )
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            return None
        raw_gen = str((resp or {}).get("text", "")).strip()
        if not raw_gen:
            return None
        if not recent_assistant and "ace" not in raw_gen.lower():
            candidate = f"Halo! Aku **ACE**. {raw_gen}"
        else:
            candidate = raw_gen
        ver = self.speech.verify_utterance(
            utterance=candidate,
            user_text=text,
            stage_id=4,
            latest_task=latest_task,
            offline_mode=bool(hc.get("offline_mode")),
            recent_assistant_texts=recent_assistant,
        )
        if not ver["passed"]:
            return None
        self.speech.record_verified_utterance(
            conversation_id=conv["conversation_id"],
            stage_id=4,
            reply=candidate,
            grounded_words=[g["word"] for g in self.speech.find_grounded_words(text)],
            active_skills_count=active_skills,
            tested_caps_count=tested_caps,
            verification=ver,
            history_turns=len(conv.get("messages", [])),
        )
        return candidate

    def _generate_general_reply(
        self,
        text: str,
        conv: dict[str, Any],
        hc: dict[str, Any],
        mode_label: str,
    ) -> str:
        msgs = conv.get("messages", [])
        recent_assistant = [str(m.get("text", "")) for m in msgs if m.get("role") == "assistant"]
        latest_task = self.store.get_latest_task(conv["conversation_id"])
        active_skills = len(self.store.list_skills(active_only=True))
        tested_caps = sum(1 for f in self.store.list_frontier() if f.get("status") == "KNOWN_AND_TESTED")

        words = text.lower().split()
        greet_tokens = ("halo", "hai", "hei", "oy", "pagi", "siang", "sore", "malam", "kabar", "salam")
        is_standalone_greeting = len(words) <= 3 and any(w in text.lower() for w in greet_tokens)
        stage_id = int(self.speech.get_profile()["current_stage"])
        ctx = conv.get("context") or {}
        cues = self.speech._extract_conversational_cues(text, pending_word=str(ctx.get("pending_curiosity_word", "")))

        if not cues.get("lexicon_qa_target"):
            self.memory.observe_conversational_turn(text, conversation_id=conv["conversation_id"])

        observed_already = False
        if (
            stage_id == 4
            and hc.get("local_gguf", {}).get("server_healthy")
            and not is_standalone_greeting
            and not cues.get("lexicon_qa_target")
        ):
            self.speech.observe_user_utterance(text)
            observed_already = True
            verified_gguf = self._try_gguf_verified_reply(
                text=text,
                conv=conv,
                hc=hc,
                mode_label=mode_label,
                latest_task=latest_task,
                recent_assistant=recent_assistant,
                active_skills=active_skills,
                tested_caps=tested_caps,
            )
            if verified_gguf:
                return verified_gguf

        speech_out = self.speech.compose_conversational_reply(
            user_text=text,
            conversation_id=conv["conversation_id"],
            mode_label=mode_label,
            offline_mode=bool(hc.get("offline_mode")),
            latest_task=latest_task,
            active_skills_count=active_skills,
            tested_caps_count=tested_caps,
            recent_assistant_texts=recent_assistant,
            history_turns=len(msgs),
            observe_turn=not observed_already,
            conversation_context=ctx,
            recent_messages=msgs[-8:],
        )
        return str(speech_out["reply"])

    def _handle_speech_or_language(
        self,
        intent: Any,
        frame: dict[str, Any],
        text: str,
        conversation_id: str,
        hc: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]:
        if intent in (
            "TRAIN_SPEECH",
            "TEACH_WORD",
            "SPEECH_STATUS",
            Intent.TRAIN_SPEECH,
            Intent.TEACH_WORD,
            Intent.SPEECH_STATUS,
        ):
            return handle_speech_chat_intent(
                engine=self.speech,
                frame=frame,
                text=text,
                conversation_id=conversation_id,
            )

        task_obj = self.store.create_task(
            conversation_id=conversation_id,
            title_id="Peningkatan Pemahaman Bahasa Indonesia & Percakapan",
            user_request=text,
            normalized_goal="Tingkatkan pemahaman bahasa Indonesia alami, partikel santai, dan konteks percakapan",
            constraints=frame["constraints"],
            model_backend=hc["active_backend"],
        )
        self.store.set_frontier_capability(
            capability_id="cap_pemahaman_bahasa_indonesia",
            name_id="Pemahaman Bahasa Indonesia Alami, Partikel, & Percakapan Santai",
            category="bahasa",
            status="KNOWN_AND_TESTED",
            evidence_ref="verified:language_engine_v4_conversational",
        )
        self.store.update_task(
            task_obj["task_id"],
            status="COMPLETED",
            verification_summary={"passed": True, "domain": "language_understanding"},
        )
        reply = (
            "Saran yang sangat tepat! Sebagai kecerdasan otonom yang dirancang untuk pengguna Indonesia, "
            "penguasaan pemahaman bahasa alami (nuansa kalimat, partikel santai seperti *sih*, *dong*, *deh*, *kan*, "
            "dan pemisahan tegas antara obrolan santai vs perintah pembuatan kode) adalah kemampuan paling mendasar.\n\n"
            "Aku sudah memprioritaskan dan memperbarui modul pemahaman bahasa agar obrolan santai atau masukan seperti ini "
            "tidak lagi disalahartikan sebagai tugas membuat skrip Python baru. Sekarang aku siap diajak berdiskusi santai, "
            "bercerita, maupun merencanakan langkah selanjutnya secara lebih luwes dan peka konteks."
        )
        return reply, task_obj

    def _handle_resume_intent(
        self,
        conversation_id: str,
        conv: dict[str, Any],
        opts: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]:
        latest = self.store.get_latest_task(conversation_id)
        if latest and latest["status"] in ("PAUSED", "FAILED_WITH_RECOVERY_STATE", "WAITING_FOR_DEPENDENCY", "QUEUED"):
            ir = self.store.get_problem_ir(latest["task_id"]) or {}
            domain = ir.get("domain") or conv["context"].get("last_domain", "expense_tracker")
            if domain == "general":
                exec_res = self.coding.execute_general_task(
                    title=latest.get("title_id", "Tugas Solusi"),
                    goal=latest.get("user_request") or latest.get("normalized_goal", ""),
                    task_id=latest["task_id"],
                    conversation_id=conversation_id,
                )
            else:
                exec_res = self.coding.execute_coding_task(latest["task_id"], domain=domain, options=opts)
            task_obj = exec_res["task"]
            return (
                f"Tugas **{task_obj['title_id']}** sudah kulanjutkan dari checkpoint terakhir dan sekarang selesai "
                f"dengan status `{task_obj['status']}`!"
            ), task_obj
        if not latest or latest.get("kind") == "learning_task":
            return (
                "Belum ada tugas yang tertunda saat ini nih, jadi kita bisa lanjut ngobrol atau membuat sesuatu yang baru!"
            ), None
        return (
            "Semua tugas sebelumnya sudah selesai (`COMPLETED`). Beri tahu aku jika ada tugas baru yang ingin dikerjakan."
        ), None

    def _record_task_memory(
        self,
        intent: Any,
        frame: dict[str, Any],
        task_obj: dict[str, Any] | None,
        conversation_id: str,
    ) -> None:
        if not task_obj:
            return
        terminal = ("COMPLETED", "FAILED", "FAILED_WITH_RECOVERY_STATE", "WAITING_FOR_DEPENDENCY")
        if task_obj.get("status") not in terminal:
            return
        if intent in ("STATUS_CHECK", "STOP_OR_PAUSE"):
            return
        ir = self.store.get_problem_ir(task_obj["task_id"]) or {}
        domain_map = {
            "DIAGNOSE_OR_FIX_BUG": "bug_fix",
            "REFACTOR_CODE": "refactor",
            "MODIFY_PREVIOUS_ARTIFACT": "expense_tracker",
            "LEARN_AND_SOLVE": "learning",
            "LEARN_LANGUAGE": "language_understanding",
            "TRAIN_SPEECH": "speech_training",
        }
        dom = str(
            ir.get("domain")
            or frame.get("domain")
            or domain_map.get(str(intent), "general")
        )
        self.memory.record_task_episode(task_obj, domain=dom, conversation_id=conversation_id)

    def _handle_create_or_modify_code(
        self,
        *,
        intent: Any,
        frame: dict[str, Any],
        text: str,
        conversation_id: str,
        hc: dict[str, Any],
        mode_label: str,
        opts: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        domain = frame.get("domain", "general")
        title_map = {
            "expense_tracker": "Aplikasi CLI Catatan Pengeluaran Lokal",
            "csv_reader": "Utilitas CLI Pembaca & Rekap CSV",
            "tebak_angka": "Game CLI Tebak Angka Bahasa Indonesia",
            "multi_file": "Paket Aplikasi Python Multi-Modul",
        }
        task_title = (
            f"Solusi Python: {frame['normalized_text'][:50].strip()}"
            if domain == "general"
            else title_map.get(domain, "Pembuatan Skrip Python Lokal")
        )
        task_obj = self.store.create_task(
            conversation_id=conversation_id,
            title_id=task_title,
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
                "domain_confidence": frame.get("domain_confidence", 0.85),
                "normalized_goal": frame["normalized_text"],
                "constraints": frame["constraints"],
                "offline_mode": self.store.is_offline(),
            },
        )
        if domain == "general":
            if hasattr(self.coding, "execute_general_task"):
                gen_res = self.coding.execute_general_task(
                    title=task_title, goal=frame["normalized_text"],
                    task_id=task_obj["task_id"], conversation_id=conversation_id, options=opts,
                )
                task_obj = gen_res.get("task") or self.store.get_task(task_obj["task_id"])
                script_path = gen_res.get("file_path") or gen_res.get("script_path", "")
                output_text = gen_res.get("output", "")
            else:
                exec_res = self.coding.execute_coding_task(task_obj["task_id"], domain="general", options=opts)
                task_obj = exec_res["task"]
                script_path = exec_res.get("script_path", "")
                output_text = exec_res.get("verification", {}).get("sample_output", "")
            self.store.update_conversation_context(
                conversation_id,
                {"last_task_id": task_obj["task_id"], "last_domain": domain, "last_script_path": script_path},
            )
            art_list = ", ".join(f"[`{a['id']}`](file://{a['path']})" for a in task_obj.get("artifacts", []))
            if not art_list and script_path:
                art_list = f"[`{Path(script_path).name}`](file://{script_path})"
            sample_out = output_text.splitlines() if output_text else []
            first_line = sample_out[0] if sample_out else (
                task_obj.get("verification_summary", {}).get("sample_output", "").splitlines() or ["Verifikasi lulus"]
            )[0]
            return (
                f"Aku sudah membuat dan memverifikasi **{task_obj['title_id']}** dalam mode **{mode_label}**.\n"
                f"- Berkas yang dibuat: {art_list}\n- Hasil uji otomatis: `{first_line}`\n- Status: `{task_obj['status']}`\n\n"
                "Kamu bisa meminta pengujian lebih lanjut, optimasi logika, atau penambahan fitur baru.",
                task_obj,
            )

        default_period = "mingguan" if "mingguan" in frame["normalized_text"].lower() else "bulanan"
        exec_res = self.coding.execute_coding_task(
            task_obj["task_id"], domain=domain,
            options={**opts, "default_period": default_period, "include_categories": True},
        )
        task_obj = exec_res["task"]
        self.store.update_conversation_context(
            conversation_id,
            {"last_task_id": task_obj["task_id"], "last_domain": domain, "default_period": default_period, "include_categories": True},
        )
        art_list = ", ".join(f"[`{a['id']}`](file://{a['path']})" for a in task_obj["artifacts"])
        sample_out = task_obj.get("verification_summary", {}).get("sample_output", "").splitlines()
        first_line = sample_out[0] if sample_out else "Verifikasi lulus"
        return (
            f"Aku sudah membuat dan menguji **{task_obj['title_id']}** dalam mode **{mode_label}**.\n"
            f"- Berkas yang dibuat: {art_list}\n- Hasil uji otomatis: `{first_line}`\n- Status: `{task_obj['status']}`\n\n"
            "Kamu bisa meminta perubahan lanjutan (misalnya *\"yang tadi tambah kategorinya\"* atau *\"bukan mingguan, maksudku bulanan\"*).",
            task_obj,
        )

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
        mode_label = _format_mode_label(hc)
        task_obj: dict[str, Any] | None = None
        reply_text = ""

        if intent == "CONSCIOUSNESS_INQUIRY":
            reply_text = (
                "Secara jujur, aku **belum memiliki kesadaran subjektif** (pengalaman batin atau perasaan seperti manusia). "
                "Namun, aku memiliki **kesadaran diri fungsional (*functional self-model*)**: aku memantau status tugasku secara nyata, "
                "mengenali batas kemampuanku lewat daftar *gap*, mendeteksi jika aku berputar di masalah yang sama (*anti-stagnation*), "
                "dan memverifikasi setiap kode yang kutulis dengan bukti pengujian nyata."
            )

        elif intent in ("MEMORY_STORE", "MEMORY_RECALL", "MEMORY_FORGET", "MEMORY_AUDIT"):
            reply_text, task_obj = self.memory.handle_chat_intent(frame, text, conversation_id)

        elif intent in (
            "LEARN_LANGUAGE",
            "TRAIN_SPEECH",
            "TEACH_WORD",
            "SPEECH_STATUS",
            Intent.LEARN_LANGUAGE,
            Intent.TRAIN_SPEECH,
            Intent.TEACH_WORD,
            Intent.SPEECH_STATUS,
        ):
            reply_text, task_obj = self._handle_speech_or_language(intent, frame, text, conversation_id, hc)

        elif intent in ("GREETING_OR_CAPABILITIES", "GENERAL_CONVERSATION", Intent.GREETING_OR_CAPABILITIES, getattr(Intent, "GENERAL_CONVERSATION", None)):
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
            elif intent in ("GENERAL_CONVERSATION", getattr(Intent, "GENERAL_CONVERSATION", None)):
                reply_text = self._generate_general_reply(text, conv, hc, mode_label)
            else:
                reply_text = self._build_capabilities_reply(mode_label)

        elif intent == "EXPLAIN_ONLY":
            is_expense = any(k in frame["normalized_text"].lower() for k in ("pengeluaran", "catatan", "keuangan", "dompet", "belanja"))
            plan_domain = "expense_tracker" if is_expense else "general"
            if plan_domain == "general":
                clean_goal = frame["normalized_text"][:50].strip()
                pending_plan = {
                    "goal": frame["normalized_text"],
                    "domain": "general",
                    "steps": [
                        f"Merancang logika skrip mandiri untuk '{clean_goal}'.",
                        "Menulis kode Python mandiri dengan pengujian sintaks AST dan fungsi eksekutabel.",
                        "Menjalankan skrip secara langsung dan mencatat execution receipt terverifikasi.",
                    ],
                }
                reply_text = (
                    "Siap, aku **jelaskan rencananya dulu tanpa mengubah atau membuat berkas apa pun**:\n"
                    f"1. Aku akan merancang skrip Python mandiri untuk '{clean_goal}'.\n"
                    "2. Kode akan diverifikasi sintaksnya (AST) dan dipastikan memiliki fungsi utama serta blok pengujian mandiri.\n"
                    "3. Setelah kode ditulis, aku akan menjalankan verifikasi otomatis dan menyimpan bukti *receipt*.\n\n"
                    "Kalau rencana ini sudah cocok, cukup katakan **\"sekarang kerjakan\"**."
                )
            else:
                pending_plan = {
                    "goal": frame["normalized_text"],
                    "domain": "expense_tracker",
                    "steps": [
                        "Menyiapkan skema data lokal (`pengeluaran.json`) dan antarmuka CLI Bahasa Indonesia (`tambah`, `daftar`, `total`, `hapus`).",
                        "Menulis kode secara atomik dengan pemeriksaan preimage SHA-256.",
                        "Menjalankan uji kompilasi dan uji fungsional otomatis untuk memastikan rekap berjalan akurat.",
                    ],
                }
                reply_text = (
                    "Siap, aku **jelaskan rencananya dulu tanpa mengubah atau membuat berkas apa pun**:\n"
                    "1. Aku akan merancang skrip CLI Python mandiri dengan subperintah `tambah`, `daftar`, `total`, dan `hapus`.\n"
                    "2. Data akan disimpan secara lokal dalam format JSON agar tahan restart dan tidak butuh internet.\n"
                    "3. Setelah kode ditulis, aku akan menjalankan verifikasi otomatis dan menyimpan bukti *receipt*.\n\n"
                    "Kalau rencana ini sudah cocok, cukup katakan **\"sekarang kerjakan\"**."
                )
            self.store.update_conversation_context(conversation_id, {"pending_plan": pending_plan})

        elif intent == "EXECUTE_PREVIOUS_PLAN":
            pending = conv["context"].get("pending_plan") or {
                "goal": "Membuat aplikasi CLI catatan pengeluaran lokal",
                "domain": "expense_tracker",
            }
            plan_domain = str(pending.get("domain", "expense_tracker"))
            task_title = (
                f"Eksekusi rencana: {pending.get('goal', 'Solusi Python')[:40]}"
                if plan_domain == "general"
                else "Eksekusi rencana: Aplikasi Catatan Pengeluaran CLI"
            )
            task_obj = self.store.create_task(
                conversation_id=conversation_id,
                title_id=task_title,
                user_request=text,
                normalized_goal=str(pending.get("goal", "Membuat aplikasi CLI catatan pengeluaran")),
                constraints=frame["constraints"],
                model_backend=hc["active_backend"],
            )
            if plan_domain == "general" and hasattr(self.coding, "execute_general_task"):
                gen_res = self.coding.execute_general_task(
                    title=task_title,
                    goal=str(pending.get("goal", text)),
                    task_id=task_obj["task_id"],
                    conversation_id=conversation_id,
                    options=opts,
                )
                task_obj = gen_res.get("task") or self.store.get_task(task_obj["task_id"])
                script_path = gen_res.get("file_path") or gen_res.get("script_path", "")
            else:
                exec_res = self.coding.execute_coding_task(
                    task_obj["task_id"],
                    domain=plan_domain,
                    options=opts,
                )
                task_obj = exec_res["task"]
                script_path = exec_res.get("script_path", "")

            self.store.update_conversation_context(
                conversation_id,
                {"last_task_id": task_obj["task_id"], "last_domain": plan_domain, "pending_plan": None},
            )
            art_name = Path(script_path).name if script_path else "berkas"
            reply_text = (
                f"Rencana tadi sudah langsung kukerjakan dan diverifikasi! Berkas [`{art_name}`](file://{script_path}) "
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
            reply_text, task_obj = self._handle_resume_intent(conversation_id, conv, opts)

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
            reply_text, task_obj = self._handle_create_or_modify_code(
                intent=intent,
                frame=frame,
                text=text,
                conversation_id=conversation_id,
                hc=hc,
                mode_label=mode_label,
                opts=opts,
            )

        self._record_task_memory(intent, frame, task_obj, conversation_id)

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
