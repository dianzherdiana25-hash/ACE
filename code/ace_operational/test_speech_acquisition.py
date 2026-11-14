"""Unit and integration tests for 4-Stage Developmental Indonesian Speech Acquisition."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.language import ConversationalEngine, Intent, classify_intent_frame
from ace_operational.speech_acquisition import (
    CORE_SEED_LEXICON,
    SpeechDevelopmentEngine,
    classify_speech_intent,
    syllabify_indonesian,
    synthesize_babble,
    tokenize_phonemes,
    validate_telegraphic_phrase,
)
from ace_operational.store import OperationalStore
from ace_operational.story_projector import project_event_to_story
from ace_operational.web_server import ACEWebServer


class SpeechAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ace-speech-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.speech = SpeechDevelopmentEngine(self.store)

    def test_stage1_phonotactics_digraphs_and_babbling(self) -> None:
        self.assertEqual(tokenize_phonemes("menyayangi"), ["m", "e", "ny", "a", "y", "a", "ng", "i"])
        cases = {
            "bernyanyi": ["ber", "nya", "nyi"],
            "menyayangi": ["me", "nya", "ya", "ngi"],
            "kebersamaan": ["ke", "ber", "sa", "ma", "an"],
            "pengalaman": ["pe", "nga", "la", "man"],
            "syukur": ["syu", "kur"],
            "khusus": ["khu", "sus"],
        }
        for word, expected_syls in cases.items():
            res = syllabify_indonesian(word)
            self.assertTrue(res["pronounceable"], word)
            self.assertEqual(res["syllables"], expected_syls, word)
            self.assertIn("·", res["prosody_cue"] if len(expected_syls) > 1 else res["prosody_cue"] + "·")

        for invalid_tok in ("bcdfg", "strkkk", "123!", ""):
            self.assertFalse(syllabify_indonesian(invalid_tok)["pronounceable"], invalid_tok)

        bab1 = synthesize_babble(consonants=["d", "l", "r"], vowels=["e", "o"], count=4, seed=1)
        bab2 = synthesize_babble(consonants=["b", "m", "n"], vowels=["a", "u"], count=4, seed=4)
        self.assertEqual(len(bab1), 4)
        self.assertEqual(len(bab2), 4)
        self.assertTrue(all(b["pronounceable"] and set(b["word"]).issubset({"d", "l", "r", "e", "o"}) for b in bab1))
        self.assertNotEqual([b["word"] for b in bab1], [b["word"] for b in bab2])
        self.assertEqual(synthesize_babble(consonants=[], vowels=["a"], count=3), [])

    def test_stage2_lexicon_persistence_typos_and_live_teaching(self) -> None:
        taught = self.speech.teach_word("lentera", "cahaya penuntun di kegelapan", role="objek")
        self.assertTrue(taught["accepted"])
        self.assertEqual(taught["entry"]["syllables"], ["len", "te", "ra"])
        self.assertEqual(taught["entry"]["source"], "user_taught")

        bad = self.speech.teach_word("bcdfg", "bukan kata")
        self.assertFalse(bad["accepted"])
        self.assertIn("fonotaktik", bad["reason"])

        self.store.close()
        reopened = OperationalStore(self.ws)
        self.addCleanup(reopened.close)
        restored_speech = SpeechDevelopmentEngine(reopened)
        hit = restored_speech.lookup_word("lentera")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["meaning_id"], "cahaya penuntun di kegelapan")

        grad = restored_speech.train_and_graduate()
        self.assertTrue(grad["passed"])
        self.assertGreaterEqual(grad["profile"]["vocab_count"], len(CORE_SEED_LEXICON) + 1)

        for probe, target in (("belajr", "belajar"), ("katakan", "kata"), ("mengingat", "ingat"), ("terdengar", "dengar")):
            found = restored_speech.lookup_word(probe)
            self.assertIsNotNone(found, probe)
            self.assertEqual(found["word"], target)

        q_frame = classify_speech_intent("arti kata lentera itu apa?", "arti kata lentera itu apa?", [], False)
        self.assertIsNone(q_frame)
        t_frame = classify_speech_intent("ajarkan kata merdu artinya indah didengar (sifat)", "ajarkan kata merdu artinya indah didengar (sifat)", [], False)
        self.assertIsNotNone(t_frame)
        self.assertEqual(t_frame["intent"], "TEACH_WORD")
        self.assertEqual(t_frame["taught_word"]["role"], "sifat")

    def test_stage3_telegraphic_grammar_and_dynamic_composition(self) -> None:
        self.assertTrue(validate_telegraphic_phrase([("aku", "aktor"), ("belajar", "aksi")])["valid"])
        self.assertTrue(validate_telegraphic_phrase([("aku", "aktor"), ("ingat", "aksi"), ("kata", "objek")])["valid"])
        self.assertFalse(validate_telegraphic_phrase([("kata", "objek"), ("halo", "sapaan")])["valid"])
        self.assertFalse(validate_telegraphic_phrase([("aku", "aktor"), ("aku", "aktor")])["valid"])
        self.assertFalse(validate_telegraphic_phrase([("aku", "aktor")])["valid"])

        self.speech.train_and_graduate()
        taught = self.speech.teach_word("lentera", "cahaya penuntun", role="objek")["entry"]
        phrase = self.speech.compose_telegraphic_phrase(("aktor", "aksi", "objek"), preferred_words=[taught])
        self.assertTrue(phrase["valid"])
        self.assertIn("lentera", phrase["phrase"])

    def test_stage4_progression_anti_hallucination_and_fail_closed_gate(self) -> None:
        stages_out = {}
        self.speech.teach_word("mentari", "cahaya pagi", role="objek")
        for st_id in (0, 1, 2, 3, 4):
            out = self.speech.compose_conversational_reply(
                user_text="Halo ACE, bagaimana latihan bicara mentari?",
                conversation_id="conv_prog",
                mode_label="Offline Lokal",
                offline_mode=True,
                latest_task=None,
                active_skills_count=0,
                tested_caps_count=0,
                recent_assistant_texts=[],
                history_turns=st_id,
                override_stage=st_id,
                persist_utterance=False,
            )
            stages_out[st_id] = out["reply"]
        self.assertIn("0/4", stages_out[0])
        self.assertIn("1/4", stages_out[1])
        self.assertIn("2/4", stages_out[2])
        self.assertIn("3/4", stages_out[3])
        self.assertIn("mentari", stages_out[4])

        fake_claim = self.speech.verify_utterance(
            utterance="Berkas telah kubuat lewat terhubung ke internet secara penuh.",
            user_text="halo",
            stage_id=4,
            latest_task=None,
            offline_mode=True,
            recent_assistant_texts=[],
        )
        self.assertFalse(fake_claim["passed"])
        self.assertIn("claimed_nonexistent_task", fake_claim["hallucination_violations"])
        self.assertIn("claimed_network_while_offline", fake_claim["hallucination_violations"])

        dup_check = self.speech.verify_utterance(
            utterance="Halo ACE siap mendengarkan kamu sekarang.",
            user_text="halo ace",
            stage_id=4,
            latest_task=None,
            offline_mode=True,
            recent_assistant_texts=["Halo ACE siap mendengarkan kamu sekarang."],
        )
        self.assertFalse(dup_check["non_repetitive"])
        self.assertFalse(dup_check["passed"])

        with patch.object(
            self.speech,
            "_run_stage_3_exam",
            return_value={"stage_id": 3, "status": "FAILED", "score": 0.0, "passed": False, "receipt_id": "rcpt_fail", "evidence": {}},
        ):
            failed_grad = self.speech.train_and_graduate(conversation_id="conv_fail")
        self.assertFalse(failed_grad["passed"])
        self.assertEqual(failed_grad["task"]["status"], "FAILED_WITH_RECOVERY_STATE")
        self.assertEqual(failed_grad["profile"]["current_stage"], 2)
        self.assertFalse(any(s["name"] == "keterampilan_berbicara_bertahap_id" for s in self.store.list_skills()))

    def test_chat_engine_speech_lifecycle_and_coding_non_regression(self) -> None:
        chat = ConversationalEngine(self.store)

        r_pre = chat.handle_user_message("Halo ACE")
        self.assertIn("0/4", r_pre["reply"])

        r_train = chat.handle_user_message("Coba skill berbicara dulu")
        self.assertEqual(r_train["intent_frame"]["intent"], "TRAIN_SPEECH")
        self.assertEqual(r_train["task"]["status"], "COMPLETED")
        self.assertIn("keterampilan_berbicara_bertahap_id", r_train["reply"])

        r_teach = chat.handle_user_message("Ajarkan kata cakrawala artinya batas pandang luas di langit (objek)")
        self.assertEqual(r_teach["intent_frame"]["intent"], "TEACH_WORD")
        self.assertIsNone(r_teach["task"])
        self.assertIn("ca-kra-wa-la", r_teach["reply"])

        r_status = chat.handle_user_message("Bagaimana perkembangan berbicara kamu sekarang?")
        self.assertEqual(r_status["intent_frame"]["intent"], "SPEECH_STATUS")
        self.assertIn("cakrawala", r_status["reply"])

        # Asking about meaning must NOT overwrite taught meaning with "apa"
        r_ask = chat.handle_user_message("Arti kata cakrawala itu apa?")
        self.assertNotEqual(r_ask["intent_frame"]["intent"], "TEACH_WORD")
        self.assertIn("batas pandang luas di langit", r_ask["reply"])

        r_cap = chat.handle_user_message("Kamu bisa bantu apa sekarang?")
        self.assertIn("Perkembangan berbicara", r_cap["reply"])
        self.assertIn("Tahap `4/4`", r_cap["reply"])

        # Coding requests still classify to CREATE_OR_MODIFY_CODE
        code_frame = classify_intent_frame("Buatkan aplikasi catatan pengeluaran sederhana")
        self.assertEqual(code_frame["intent"], Intent.CREATE_OR_MODIFY_CODE)

    def test_story_projector_autonomous_engine_and_web_api(self) -> None:
        failed_story = project_event_to_story({
            "kind": "skill_learned",
            "status": "FAILED",
            "verification_passed": False,
            "technical_detail": {"skill_name": "keterampilan_berbicara_bertahap_id"},
        })
        self.assertIn("belum lulus", failed_story["story_text"])

        ok_story = project_event_to_story({
            "kind": "skill_learned",
            "status": "COMPLETED",
            "verification_passed": True,
            "technical_detail": {"skill_name": "keterampilan_berbicara_bertahap_id", "vocab_count": 46},
        })
        self.assertIn("46 kosakata", ok_story["story_text"])
        self.assertEqual(ok_story["avatar_state"], "belajar")

        auto_ws = self.ws / "auto_ws"
        auto_store = OperationalStore(auto_ws)
        self.addCleanup(auto_store.close)
        auto_eng = ContinuousAutonomousEngine(store=auto_store, workspace=auto_ws)
        res = auto_eng.execute_continuous_language_learning()
        self.assertIsNotNone(res)
        self.assertEqual(res["skill"], "keterampilan_berbicara_bertahap_id")

        server = ACEWebServer(self.store, host="127.0.0.1", port=0)
        url = server.start_background()
        self.addCleanup(server.stop)

        with urlopen(f"{url}/") as home:
            html = home.read().decode("utf-8")
        self.assertIn("badge-speech", html)
        self.assertIn("Latih skill berbicara", html)

        req_chat = Request(
            f"{url}/api/chat",
            data=json.dumps({"text": "Latih skill berbicara bertahap", "client_message_id": "web_speech_01"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req_chat) as r_chat:
            chat_data = json.loads(r_chat.read().decode("utf-8"))
        self.assertEqual(chat_data["task"]["status"], "COMPLETED")

        with urlopen(f"{url}/api/status") as r_st:
            st_data = json.loads(r_st.read().decode("utf-8"))
        self.assertEqual(st_data["speech_profile"]["current_stage"], 4)

        with urlopen(f"{url}/api/speech") as r_sp:
            sp_data = json.loads(r_sp.read().decode("utf-8"))
        self.assertTrue(sp_data["graduated"])
        self.assertGreaterEqual(sp_data["vocab_count"], len(CORE_SEED_LEXICON))

    def test_sequential_stage_gating_and_dynamic_stage_utterances(self) -> None:
        chat = ConversationalEngine(self.store)

        blocked = chat.handle_user_message("Naik ke tahap 2 dulu")
        self.assertEqual(blocked["intent_frame"]["intent"], "TRAIN_SPEECH")
        self.assertIn("LOCKED", blocked["reply"])
        self.assertEqual(self.speech.get_profile()["current_stage"], 0)

        r1 = chat.handle_user_message("Latih berbicara tahap 1 dulu")
        self.assertEqual(r1["task"]["status"], "COMPLETED")
        self.assertEqual(self.speech.get_profile()["current_stage"], 1)

        babble_turn = chat.handle_user_message("Halo minum kopi pahit")
        self.assertIn("1/4", babble_turn["reply"])
        self.assertLessEqual(len(babble_turn["reply"].split()), 30)

        r2 = chat.handle_user_message("Naik ke tahap 2")
        self.assertEqual(r2["task"]["status"], "COMPLETED")
        self.assertEqual(self.speech.get_profile()["current_stage"], 2)

        holo_turn = chat.handle_user_message("kopi pahit sekali")
        self.assertIn("2/4", holo_turn["reply"])
        self.assertTrue(any(w in holo_turn["reply"].lower() for w in ("kopi", "pahit")))

        taught_st2 = chat.handle_user_message("kopi itu artinya minuman seduh hangat")
        self.assertEqual(taught_st2["intent_frame"]["intent"], "TEACH_WORD")
        holo_known = chat.handle_user_message("aku suka kopi")
        self.assertIn("2/4", holo_known["reply"])
        self.assertIn("**kopi** (*minuman seduh hangat*)", holo_known["reply"].lower())

        r3 = chat.handle_user_message("Lanjut tahap berikutnya")
        self.assertEqual(self.speech.get_profile()["current_stage"], 3)

        p_emp = self.speech.compose_telegraphic_phrase(
            ("aktor", "aksi", "objek"), user_text="aku bingung sekali", history_turns=1
        )
        p_lang = self.speech.compose_telegraphic_phrase(
            ("aktor", "aksi", "objek"), user_text="bicara memori kata baru", history_turns=4
        )
        self.assertTrue(p_emp["valid"])
        self.assertTrue(p_lang["valid"])
        self.assertNotEqual(p_emp["phrase"], "ace baca arti")
        self.assertNotEqual(p_emp["phrase"], p_lang["phrase"])

        r4 = chat.handle_user_message("Naik ke tahap 4")
        self.assertEqual(r4["task"]["status"], "COMPLETED")
        self.assertTrue(self.speech.get_profile()["graduated"])
        self.assertTrue(any(s["name"] == "keterampilan_berbicara_bertahap_id" for s in self.store.list_skills()))

        st1_story = project_event_to_story({
            "kind": "skill_learned",
            "status": "COMPLETED",
            "verification_passed": True,
            "technical_detail": {"skill_name": "tahap_bicara_1_babbling_phonotactics", "stage": 1, "vocab_count": 46},
        })
        self.assertIn("Tahap 1/4", st1_story["story_text"])

    def test_passive_exposure_natural_teaching_and_stage4_qa(self) -> None:
        self.speech.train_and_graduate()
        chat = ConversationalEngine(self.store)

        r_p1 = chat.handle_user_message("Aku melihat samudra luas dan lentera di malam")
        r_p2 = chat.handle_user_message("Suasana samudra tenang sekali")
        self.assertIn("samudra", r_p2["reply"].lower())
        self.assertNotIn("status tugas terakhir", r_p1["reply"].lower())

        self.store.close()
        reopened = OperationalStore(self.ws)
        self.addCleanup(reopened.close)
        restored = SpeechDevelopmentEngine(reopened)
        heard_map = {h["word"]: h for h in restored.list_heard_words(ungrounded_only=True, limit=15)}
        self.assertIn("samudra", heard_map)
        self.assertIn("lentera", heard_map)
        self.assertGreaterEqual(heard_map["samudra"]["exposure_count"], 2)

        chat2 = ConversationalEngine(reopened)
        r_curious = chat2.handle_user_message("Malam ini angin sejuk")
        self.assertTrue(any(w in r_curious["reply"].lower() for w in ("angin", "sejuk", "samudra")))
        self.assertNotIn("kata **`samudra`**", r_curious["reply"].lower())

        r_nat1 = chat2.handle_user_message("lentera itu artinya cahaya penuntun di malam gelap")
        self.assertEqual(r_nat1["intent_frame"]["intent"], "TEACH_WORD")
        r_nat2 = chat2.handle_user_message("kata senja itu warna jingga di langit sore")
        self.assertEqual(r_nat2["intent_frame"]["intent"], "TEACH_WORD")

        ungrounded_after = {h["word"] for h in restored.list_heard_words(ungrounded_only=True, limit=15)}
        self.assertNotIn("lentera", ungrounded_after)

        r_known = chat2.handle_user_message("Apa arti kata senja?")
        self.assertNotEqual(r_known["intent_frame"]["intent"], "TEACH_WORD")
        self.assertIn("warna jingga di langit sore", r_known["reply"])

        r_known_alt = chat2.handle_user_message("lentera artinya apa?")
        self.assertNotEqual(r_known_alt["intent_frame"]["intent"], "TEACH_WORD")
        self.assertIn("cahaya penuntun di malam gelap", r_known_alt["reply"])

        r_unknown = chat2.handle_user_message("Apa makna nirwana?")
        self.assertIn("belum ada di leksikon", r_unknown["reply"])
        self.assertNotIn("sebenarnya nirwana adalah", r_unknown["reply"].lower())

        # Preserving user-taught custom meaning across re-running stage 2 curriculum
        restored.teach_word("kata", "simbol bermakna ajaran khusus pengguna")
        restored._run_stage_2_exam("task_preserve_test")
        self.assertEqual(restored.lookup_word("kata")["meaning_id"], "simbol bermakna ajaran khusus pengguna")

    def test_gguf_conditioning_and_hallucination_fallback(self) -> None:
        chat = ConversationalEngine(self.store)
        chat.handle_user_message("Latih berbicara tahap 1 dulu")
        healthy_hc = {
            "mode": "local-complete",
            "offline_mode": True,
            "active_backend": "local-gguf-server",
            "egress_attempts_blocked": 0,
            "local_gguf": {"server_healthy": True, "ready": True, "valid_models": [], "corrupted_models": []},
        }

        # Stage 1 must NOT be bypassed by GGUF adult prose
        with patch.object(chat.router, "health_check", return_value=healthy_hc), patch.object(
            chat.router, "generate_text", side_effect=AssertionError("GGUF must not run below stage 4")
        ):
            r_st1 = chat.handle_user_message("Selamat pagi sahabat baru")
            self.assertIn("1/4", r_st1["reply"])

        # Promote to Stage 4 and teach a word
        chat.handle_user_message("Latih skill berbicara bertahap")
        chat.handle_user_message("samudra itu artinya lautan luas penuh kehidupan")

        # Valid GGUF output is conditioned with SQLite memory and accepted
        captured_prompts: list[list[dict[str, str]]] = []

        def fake_good_gen(messages: list[dict[str, str]], **_kwargs: object) -> dict[str, object]:
            captured_prompts.append(messages)
            return {"text": "ACE mengingat kata samudra yang berarti lautan luas. Laut memang menenangkan."}

        with patch.object(chat.router, "health_check", return_value=healthy_hc), patch.object(
            chat.router, "generate_text", side_effect=fake_good_gen
        ):
            r_good = chat.handle_user_message("Ceritakan kesanmu soal samudra sekarang")
            self.assertIn("lautan luas", r_good["reply"])
            self.assertEqual(len(captured_prompts), 1)
            self.assertIn("samudra = lautan luas penuh kehidupan", captured_prompts[0][0]["content"])

        # Hallucinated GGUF output while offline + no active task is rejected and falls back cleanly
        with patch.object(chat.router, "health_check", return_value=healthy_hc), patch.object(
            chat.router,
            "generate_text",
            return_value={"text": "Berkas telah kubuat dan aku sudah terhubung ke internet."},
        ):
            r_halluc = chat.handle_user_message("Bagaimana pendapatmu soal perjalanan malam?")
            self.assertNotIn("terhubung ke internet", r_halluc["reply"].lower())
            self.assertNotIn("berkas telah kubuat", r_halluc["reply"].lower())
            self.assertIn("ACE", r_halluc["reply"])

    def test_v3_anaphora_revision_colloquial_semantics_and_provenance(self) -> None:
        self.speech.train_and_graduate()
        chat = ConversationalEngine(self.store)

        # 1. Passive exposure in real sentence captures sample_context, followed by curiosity & anaphora answer
        r_ask = chat.handle_user_message("Aku melihat samudra tenang di malam gelap")
        self.assertIn("samudra", r_ask["reply"].lower())

        ctx_mid = self.store.get_conversation("conv_utama")["context"]
        pending = ctx_mid.get("pending_curiosity_word", "")
        self.assertTrue(pending)

        r_ana = chat.handle_user_message("oh, itu artinya hamparan lautan sangat luas (tempat)")
        self.assertEqual(r_ana["intent_frame"]["intent"], "TEACH_WORD")
        self.assertIn(pending, r_ana["reply"].lower())
        self.assertIn("kubahas", r_ana["reply"].lower())
        self.assertEqual(self.store.get_conversation("conv_utama")["context"].get("pending_curiosity_word"), "")

        # Authentic conversational sample_context carried over into taught entry examples
        entry = self.speech.lookup_word(pending, allow_fuzzy=False)
        self.assertIsNotNone(entry)
        self.assertTrue(any(pending in ex.lower() for ex in entry["examples"]))

        # 2. Corrective revision increments revision_count and updates meaning
        r_rev = chat.handle_user_message(f"ralat kata {pending} jadi bentangan laut biru yang dalam (tempat)")
        self.assertEqual(r_rev["intent_frame"]["intent"], "TEACH_WORD")
        self.assertIn("revisi", r_rev["reply"].lower())
        revised = self.speech.lookup_word(pending, allow_fuzzy=False)
        self.assertEqual(revised["meaning_id"], "bentangan laut biru yang dalam")
        self.assertGreaterEqual(revised["revision_count"], 1)

        # 3. Colloquial slang dialogue, synonym/antonym Q&A, and morphology Q&A
        r_slang = chat.handle_user_message("gmn kbr lu skrg, blm lupa kan?")
        self.assertIn("kabar", r_slang["reply"].lower())
        self.assertGreaterEqual(self.speech.get_profile()["vocab_count"], 180)

        r_syn = chat.handle_user_message("Apa sinonim kata tenang?")
        self.assertIn("damai", r_syn["reply"].lower())

        r_ant = chat.handle_user_message("Lawan kata gelap apa?")
        self.assertIn("terang", r_ant["reply"].lower())

        r_morph = chat.handle_user_message("Apa kata dasar menyayangiku?")
        self.assertIn("me-nya-ya-ngi", r_morph["reply"].lower())

    def test_v3_legacy_schema_migration_and_web_speech_drawer(self) -> None:
        # Simulate an older V2 SQLite database missing V3 columns before engine initialization
        legacy_ws = self.ws / "legacy_v2_ws"
        legacy_store = OperationalStore(legacy_ws)
        self.addCleanup(legacy_store.close)
        with legacy_store._lock:
            legacy_store._conn.execute(
                """
                CREATE TABLE speech_lexicon (
                    word TEXT PRIMARY KEY,
                    syllables_json TEXT NOT NULL,
                    role TEXT NOT NULL,
                    meaning_id TEXT NOT NULL,
                    contexts_json TEXT NOT NULL,
                    examples_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    mastery REAL NOT NULL DEFAULT 0.5,
                    exposure_count INTEGER NOT NULL DEFAULT 1,
                    taught_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            legacy_store._conn.execute(
                "INSERT INTO speech_lexicon VALUES ('lentera','[\"len\",\"te\",\"ra\"]','objek','pelita kecil','[\"alam\"]','[\"Lentera malam.\"]','user_taught',0.85,1,'','2026-01-01','2026-01-01')"
            )
            legacy_store._conn.commit()

        migrated = SpeechDevelopmentEngine(legacy_store)
        entry = migrated.lookup_word("lentera", allow_fuzzy=False)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["meaning_id"], "pelita kecil")
        self.assertEqual(entry["revision_count"], 0)
        self.assertEqual(entry["synonyms"], [])

        migrated.train_and_graduate()
        server = ACEWebServer(legacy_store, host="127.0.0.1", port=0)
        url = server.start_background()
        self.addCleanup(server.stop)
        with urlopen(f"{url}/") as home:
            html = home.read().decode("utf-8")
        self.assertIn("speech-drawer", html)
        self.assertIn("speech-teach-form", html)
        self.assertIn("toggleSpeechDrawer", html)
        with urlopen(f"{url}/api/speech") as r_sp:
            sp_data = json.loads(r_sp.read().decode("utf-8"))
        self.assertGreaterEqual(sp_data["vocab_count"], 180)
        self.assertTrue(any(w["word"] == "lentera" for w in sp_data["user_taught_words"]))

    def test_v4_natural_casual_conversation_stage0_and_stage4(self) -> None:
        chat = ConversationalEngine(self.store)

        r_halo = chat.handle_user_message("Halo ACE")
        self.assertIn("0/4", r_halo["reply"])
        self.assertNotIn("unavailable", r_halo["reply"].lower())

        r_kabar = chat.handle_user_message("apa kabar?")
        self.assertIn("kabar", r_kabar["reply"].lower())
        self.assertNotIn("0/4", r_kabar["reply"])

        r_act = chat.handle_user_message("kamu lagi ngapain sekarang?")
        self.assertNotEqual(r_act["intent_frame"]["intent"], "STATUS_CHECK")
        self.assertNotIn("belum ada tugas aktif", r_act["reply"].lower())

        r_tired = chat.handle_user_message("aku cape bgt")
        self.assertIn("capek", r_tired["reply"].lower())
        self.assertNotIn("sabar", r_tired["reply"].lower())
        self.assertNotIn("bingung", r_tired["reply"].lower())

        r_id = chat.handle_user_message("siapa namamu?")
        self.assertIn("Lokal Mandiri", r_id["reply"])
        self.assertNotIn("unavailable", r_id["reply"].lower())

        r_laugh = chat.handle_user_message("wkwkwk lucu")
        self.assertTrue("ketawa" in r_laugh["reply"].lower() or "haha" in r_laugh["reply"].lower())
        heard_words = {h["word"] for h in self.speech.list_heard_words(ungrounded_only=False, limit=30)}
        self.assertNotIn("wkwkwk", heard_words)

        r_rep = chat.handle_user_message("kata teman nasi goreng itu enak")
        self.assertNotEqual(r_rep["intent_frame"]["intent"], "TEACH_WORD")
        self.assertIsNone(self.speech.lookup_word("teman", allow_fuzzy=False))

        r_col = chat.handle_user_message("kamu suka warna apa?")
        self.assertIn("biru", r_col["reply"].lower())
        r_col_follow = chat.handle_user_message("biru")
        self.assertIn("biru", r_col_follow["reply"].lower())

        r_lanjut_empty = chat.handle_user_message("lanjut")
        self.assertNotIn("COMPLETED", r_lanjut_empty["reply"])

        self.speech.train_and_graduate()
        r_s4 = chat.handle_user_message("kamu lagi ngapain?")
        self.assertEqual(r_s4["intent_frame"]["intent"], "GENERAL_CONVERSATION")
        self.assertNotIn("Kata kunci yang kutangkap", r_s4["reply"])
        self.assertNotIn("Pesanmu kuterima", r_s4["reply"])

        r_bored = chat.handle_user_message("aku bosen banget nih")
        self.assertIn("bosan", r_bored["reply"].lower())
        r_story = chat.handle_user_message("ceritain sesuatu dong")
        self.assertIn("cerita", r_story["reply"].lower())

    def test_v4_web_studio_natural_ui_and_chat_api(self) -> None:
        server = ACEWebServer(self.store, host="127.0.0.1", port=0)
        url = server.start_background()
        self.addCleanup(server.stop)

        with urlopen(f"{url}/") as home:
            html = home.read().decode("utf-8")
        self.assertIn("textContent = msg.text", html)
        self.assertIn("formatSafeMarkdown", html)
        self.assertIn("Bahasa Lokal", html)
        self.assertIn("Sapa ACE", html)
        self.assertIn("speechSynthesis", html)

        chat_req = Request(
            f"{url}/api/chat",
            data=json.dumps({"conversation_id": "conv_utama", "text": "aku cape bgt"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(chat_req) as r_chat:
            data = json.loads(r_chat.read().decode("utf-8"))
        self.assertIn("capek", data["reply"].lower())
        self.assertNotIn("unavailable", data["reply"].lower())
        self.assertEqual(data["avatar_state"], "mendengar")

        bad_req = Request(
            f"{url}/api/chat",
            data=json.dumps({"text": "   "}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx_err:
            urlopen(bad_req)
        self.assertEqual(ctx_err.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
