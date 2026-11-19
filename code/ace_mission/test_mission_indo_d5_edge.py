"""D5 adversarial & edge-case tests for mission bus, Indo NLP, MCP, chat runner, and reporting.

Covers:
1. ace_mission (schema, admission, bus, generator, proposers)
2. ace_indo_nlp (phonotactics, morphology, lexicon_kb, discourse)
3. ace_mcp (bridge, code_diagnostic, server)
4. ace_chat (task_runner)
5. ace_report (mobile_report)

Genuine bugs discovered during edge-case testing are documented via
`@unittest.expectedFailure` without modifying production module sources.
"""
from __future__ import annotations

import copy
import datetime
import http.client
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from ace_capability_evolution.compositional import bank
from ace_chat import task_runner
from ace_indo_nlp.discourse import (
    analyze_discourse_cues,
    clean_definition_tail,
    extract_query_target,
    format_lexicon_qa_clauses,
    is_question_or_empty_tail,
    parse_teaching_or_correction,
    realize_indonesian_turn,
)
from ace_indo_nlp.lexicon_kb import infer_indonesian_pos
from ace_indo_nlp.morphology import (
    analyze_morphology,
    bounded_edit_distance,
    normalize_colloquial,
)
from ace_indo_nlp.phonotactics import (
    echo_input_syllables,
    syllabify_indonesian,
    synthesize_babble,
    tokenize_phonemes,
)
from ace_mcp.bridge import ACEBridge, PROTOCOL, ToolInputError, json_rpc
from ace_mcp.code_diagnostic import evaluate as eval_code_diagnostic
from ace_mcp.server import MAX_REQUEST_BYTES, main as mcp_main, make_http_server, stdio as mcp_stdio
from ace_cognition.reasoning import SCHEMA as REASONING_SCHEMA
from ace_mission.admission import MAX_ARTIFACT_BYTES, evaluate_submission
from ace_mission.bus import MissionBus
from ace_mission.generator import MissionGenerator
from ace_mission.proposers import LLMAdvisorProposer, ManualAdvisorProposer, TemplateProposer
from ace_mission.schema import MissionSchemaError, validate_mission
from ace_report.mobile_report import generate_indonesian_mobile_report


def _valid_mission(**overrides):
    mission = {
        "schema_version": "ace.mission.v1",
        "id": "mission_edge_001",
        "goal": "Test mission validation boundaries",
        "hypothesis": "Boundary conditions fail closed",
        "task_family_ids": ["parity"],
        "inputs": [],
        "budget": {"time_sec": 10, "max_candidates": 2},
        "acceptance": {"metric": "exact_development_fit", "threshold": 1, "comparator": "none"},
        "forbidden": [],
        "deadline": "2026-11-20T00:00:00Z",
        "status": "PENDING",
    }
    mission.update(overrides)
    return mission


def _valid_reasoning_problem():
    return {
        "schema": REASONING_SCHEMA,
        "id": "p_edge",
        "goal": "Identity add check",
        "train": [{"inputs": {"x": 1, "y": 2}, "output": 3}],
        "validation": [{"inputs": {"x": 2, "y": 3}, "output": 5}],
    }


class TestMissionEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_mission."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        self.bus = MissionBus(self.ws / "bus.sqlite3", escalation_file=self.ws / "ESC.md")

    def test_01_schema_rejects_non_dict_bool_nan_and_budget_bounds(self):
        with self.assertRaises(MissionSchemaError):
            validate_mission("not-a-dict")

        bad_cases = (
            {"schema_version": "ace.mission.v0"},
            {"id": "   "},
            {"task_family_ids": []},
            {"status": "UNKNOWN"},
            {"budget": {"time_sec": True, "max_candidates": 1}},
            {"budget": {"time_sec": float("nan"), "max_candidates": 1}},
            {"budget": {"time_sec": 0, "max_candidates": 1}},
            {"budget": {"time_sec": 10, "max_candidates": True}},
            {"budget": {"time_sec": 10, "max_candidates": 1, "max_primitive_operations": 0}},
            {"budget": {"time_sec": 10, "max_candidates": 1, "max_primitive_operations": 300_001}},
        )
        for patch in bad_cases:
            with self.subTest(patch=patch):
                with self.assertRaises(MissionSchemaError):
                    validate_mission(_valid_mission(**patch))

    def test_02_bug_schema_accepts_non_iso_deadline_string(self):
        # BUG (ace_mission/schema.py:4,88-89): `import datetime` is unused and deadline only
        # checks non-empty string instead of validating ISO-8601 format.
        # DIPERBAIKI (gelombang robustness 2026-11-20): deadline divalidasi fromisoformat + wajib ada komponen waktu.
        with self.assertRaises(MissionSchemaError):
            validate_mission(_valid_mission(deadline="not-an-iso-timestamp"))

    def test_03_admission_rejects_duplicate_json_keys_and_oversize_bytes(self):
        m = _valid_mission(reasoning_problem=_valid_reasoning_problem())
        dup_bytes = b'{"schema": "ace.mission.reasoning-candidate.v1", "schema": "dup", "problem_digest": "a", "program": {}}'
        rec_dup = evaluate_submission(m, dup_bytes, "ACCEPTED")
        self.assertEqual(rec_dup["decision"], "REJECTED")
        self.assertIn("duplicate JSON key", rec_dup["reason"])

        rec_big = evaluate_submission(m, b"x" * (MAX_ARTIFACT_BYTES + 1), "ACCEPTED")
        self.assertEqual(rec_big["decision"], "REJECTED")
        self.assertEqual(rec_big["reason"], "ARTIFACT_SIZE_LIMIT")

    def test_04_admission_rejects_bad_decision_and_unsupported_criterion(self):
        m = _valid_mission(
            acceptance={"metric": "accuracy", "threshold": 0.9, "comparator": "ge"},
            reasoning_problem=_valid_reasoning_problem(),
        )
        with self.assertRaises(ValueError):
            evaluate_submission(m, b"{}", "FORCE_APPROVE")
        with self.assertRaises(ValueError):
            evaluate_submission(m, b"{}", True)

        rec = evaluate_submission(m, b"{}", "ACCEPTED")
        self.assertEqual(rec["decision"], "PENDING_EVALUATION")
        self.assertEqual(rec["reason"], "UNSUPPORTED_ACCEPTANCE_CRITERION")

    def test_05_bus_empty_queue_missing_mission_directory_and_oversize_file(self):
        self.assertIsNone(self.bus.next_mission("agent_1"))

        dummy = self.ws / "ok.txt"
        dummy.write_text("ok", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.bus.submit_mission("nonexistent_id", str(dummy), "agent_1")

        m_id = self.bus.create_mission(
            goal="g", hypothesis="h", task_family_ids=["f"], inputs=[],
            budget={"time_sec": 5, "max_candidates": 1},
            acceptance={"metric": "m", "threshold": 1, "comparator": "none"},
            forbidden=[],
        )
        with self.assertRaises(ValueError):
            self.bus.submit_mission(m_id, str(self.ws), "agent_1")  # directory, not file

        big_file = self.ws / "big.json"
        big_file.write_bytes(b"0" * (MAX_ARTIFACT_BYTES + 1))
        with self.assertRaises(ValueError):
            self.bus.submit_mission(m_id, str(big_file), "agent_1")

    def test_06_bus_tampered_hash_chain_and_evaluation_journal(self):
        m_id = self.bus.create_mission(
            goal="g", hypothesis="h", task_family_ids=["f"], inputs=[],
            budget={"time_sec": 5, "max_candidates": 1},
            acceptance={"metric": "m", "threshold": 1, "comparator": "none"},
            forbidden=[],
        )
        art = self.ws / "cand.py"
        art.write_text("# test\n", encoding="utf-8")
        self.bus.submit_mission(m_id, str(art), "agent_1")
        self.assertTrue(self.bus.verify_hash_chain())
        self.assertTrue(self.bus.verify_evaluation_journal())
        self.assertEqual(len(self.bus.evaluation_history(m_id)), 1)

        with sqlite3.connect(str(self.ws / "bus.sqlite3")) as conn:
            conn.execute("UPDATE hash_chain SET payload_json = '{\"tampered\":1}' WHERE seq = 2")
            conn.commit()

        self.assertFalse(self.bus.verify_hash_chain())
        self.assertFalse(self.bus.verify_evaluation_journal())
        with self.assertRaises(ValueError):
            self.bus.evaluation_history(m_id)

    def test_07_generator_unknown_diagnostic_and_below_saturation_threshold(self):
        gen = MissionGenerator(self.bus)
        self.assertEqual(gen.generate_from_diagnostics([{"type": "NON_EXISTENT"}]), [])

        m_id = self.bus.create_mission(
            goal="g", hypothesis="h_sat", task_family_ids=["f"], inputs=[],
            budget={"time_sec": 5, "max_candidates": 1},
            acceptance={"metric": "m", "threshold": 1, "comparator": "none"},
            forbidden=[],
        )
        art = self.ws / "same.py"
        art.write_text("x = 1\n", encoding="utf-8")
        for i in range(2):
            self.bus.submit_mission(m_id, str(art), f"a_{i}", decision="REJECTED")

        res = self.bus.check_saturation_and_escalate("h_sat", "x = 1\n")
        self.assertFalse(res["escalated"])
        self.assertEqual(res["rejection_count"], 2)
        self.assertFalse((self.ws / "ESC.md").exists())

    def test_08_proposers_forbidden_workspace_and_llm_fail_closed(self):
        (self.ws / "sealed_bank.py").write_text("# sealed", encoding="utf-8")
        adv = ManualAdvisorProposer()
        mission = _valid_mission(forbidden=["tests/sealed_bank.py"])
        with self.assertRaises(PermissionError):
            adv.propose(mission, self.ws)

        for key in (None, "dummy-key"):
            with self.assertRaises(NotImplementedError):
                LLMAdvisorProposer(api_key=key).propose(mission, self.ws)

        tmpl = TemplateProposer().propose(mission, self.ws / "tmpl_ws")
        self.assertEqual(tmpl["provenance"], "TEMPLATE_GENERATOR")
        self.assertTrue(Path(tmpl["artifact_path"]).is_file())


class TestIndoNLPEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_indo_nlp."""

    def test_09_phonotactics_hiatus_monosyllables_and_cluster_failures(self):
        self.assertEqual(tokenize_phonemes("syarat"), ["sy", "a", "r", "a", "t"])
        self.assertEqual(tokenize_phonemes("khusus"), ["kh", "u", "s", "u", "s"])

        mono = syllabify_indonesian("tak")
        self.assertTrue(mono["pronounceable"])
        self.assertEqual(mono["syllables"], ["tak"])
        self.assertEqual(mono["prosody_cue"], "TAK")

        hiatus = syllabify_indonesian("beruang")
        self.assertTrue(hiatus["pronounceable"])
        self.assertEqual(hiatus["syllables"], ["be", "ru", "ang"])

        self.assertEqual(syllabify_indonesian("str")["reason"], "tanpa_vokal")
        self.assertEqual(syllabify_indonesian("xzat")["reason"], "gugus_awal_tidak_valid")
        self.assertEqual(syllabify_indonesian("abcccd")["reason"], "fonotaktik_tidak_wajar")

    def test_10_phonotactics_babble_and_echo_empty_boundaries(self):
        self.assertEqual(synthesize_babble(consonants=["!!", "xz"], vowels=["a"], count=5), [])
        self.assertEqual(synthesize_babble(consonants=["b"], vowels=["q"], count=5), [])
        self.assertEqual(synthesize_babble(consonants=["b", "d"], vowels=["a", "i"], count=0), [])
        self.assertEqual(echo_input_syllables("a i u 123 !", max_words=3), [])

    def test_11_morphology_empty_punct_edit_distance_and_pos_hints(self):
        for empty in ("", "---", "12345", None):
            res = analyze_morphology(empty)
            self.assertEqual(res["root"], "")
            self.assertEqual(res["candidates"], [])

        self.assertEqual(bounded_edit_distance("kata", "kata"), 0)
        self.assertEqual(bounded_edit_distance("a", "abcde"), 99)

        ke_an = analyze_morphology("kebahagiaan", known_roots={"bahagia"})
        self.assertEqual(ke_an["root"], "bahagia")
        self.assertEqual(ke_an["affix_pos_hint"], "objek")

        # Confessional prefix stack ke- + ber- prioritizes ber- ('aksi') per _infer_pos_from_affixes
        ke_ber = analyze_morphology("kebersamaan", known_roots={"sama"})
        self.assertEqual(ke_ber["root"], "sama")
        self.assertEqual(ke_ber["affix_pos_hint"], "aksi")

        ter = analyze_morphology("tercepat", known_roots={"cepat"})
        self.assertEqual(ter["root"], "cepat")
        self.assertEqual(ter["affix_pos_hint"], "sifat")

    def test_12_morphology_colloquial_slang_and_inflected_reduplication(self):
        self.assertEqual(normalize_colloquial(None), ("", {}))
        norm, rw = normalize_colloquial("3 anak wkwkwkwk")
        self.assertEqual(norm, "3 anak haha")
        self.assertEqual(rw["wkwkwkwk"], "haha")

        redup_verb = analyze_morphology("berlari-lari", known_roots={"lari"})
        self.assertTrue(redup_verb["is_reduplicated"])
        self.assertEqual(redup_verb["root"], "lari")

        redup_noun = analyze_morphology("mobil-mobilan", known_roots={"mobil"})
        self.assertTrue(redup_noun["is_reduplicated"])
        self.assertEqual(redup_noun["root"], "mobil")

    def test_13_lexicon_kb_pos_inference_branches(self):
        self.assertEqual(infer_indonesian_pos("z", "", explicit_role="invalid_role"), "objek")
        self.assertEqual(infer_indonesian_pos("subuh", "waktu fajar tiba"), "waktu")
        self.assertEqual(infer_indonesian_pos("halo", "ucapan salam hangat"), "sapaan")
        self.assertEqual(infer_indonesian_pos("rindu", "perasaan kangen"), "emosi")
        self.assertEqual(infer_indonesian_pos("alun", "lokasi pusat kota"), "tempat")
        self.assertEqual(infer_indonesian_pos("bernyanyi", "tindakan merdu"), "aksi")

    def test_14_discourse_definition_clean_question_guards_and_non_teachable(self):
        self.assertEqual(clean_definition_tail("cahaya penuntun (Objek)."), ("cahaya penuntun", "objek"))
        for bad in ("", "???", "siapa itu", "kosong", "12345"):
            self.assertTrue(is_question_or_empty_tail(bad), bad)

        self.assertIsNone(parse_teaching_or_correction("ajarkan kata saya artinya diri sendiri"))
        self.assertIsNone(parse_teaching_or_correction("ajarkan kata senja artinya gelap?"))
        self.assertIsNone(parse_teaching_or_correction("bukan gitu, itu keliru", pending_word="senja"))
        self.assertIsNone(parse_teaching_or_correction("buat skrip python artinya hitung pajak"))

    def test_15_discourse_honest_qa_clauses_and_morphology_query(self):
        unknown_clauses = format_lexicon_qa_clauses(
            query_target={"word": "cakrawala", "query_kind": "meaning"},
            entry=None,
            grounded=[],
            mode_label="Offline",
        )
        self.assertIn("belum ada di leksikon persisten", unknown_clauses[0])

        no_ant = format_lexicon_qa_clauses(
            query_target={"word": "halo", "query_kind": "antonym"},
            entry={"word": "halo", "syllables": ["ha", "lo"], "role": "sapaan", "meaning_id": "sapaan", "source": "curriculum"},
            grounded=[],
            mode_label="Offline",
        )
        self.assertIn("belum didaftarkan", no_ant[0])

        morph_qa = format_lexicon_qa_clauses(
            query_target={"word": "memperbaiki", "query_kind": "morphology"},
            entry=None,
            grounded=[],
            mode_label="Offline",
            known_roots={"baik"},
        )
        self.assertIn("baik", morph_qa[0])

    def test_15b_bug_discourse_pending_word_anaphora_unreachable_for_artinya_apa(self):
        # BUG (ace_indo_nlp/discourse.py:177,205,219): optional `(?:artinya|maknanya)?` at L205
        # matches "artinya" as group 1 before L219's pending_word fallback runs, and "artinya"
        # is absent from `skip_words`.
        # DIPERBAIKI (gelombang robustness 2026-11-20): kata bingkai makna masuk skip_words.
        q = extract_query_target("artinya apa?", pending_word="cakrawala")
        self.assertEqual(q, {"word": "cakrawala", "query_kind": "meaning"})

    def test_16_discourse_greeting_disambiguation_and_turn_empty_fallback(self):
        self.assertFalse(analyze_discourse_cues("malam ini hujan deras")["is_greeting"])
        self.assertTrue(analyze_discourse_cues("assalamualaikum")["is_greeting"])

        cues = analyze_discourse_cues("")
        turn = realize_indonesian_turn(
            user_text="",
            cues=cues,
            grounded=[],
            profile={"vocab_count": 10},
            mode_label="Offline",
            latest_task=None,
            recent_assistant_texts=[],
            history_turns=0,
            curious_word=None,
            recent_messages=[{"role": "assistant", "text": "kamu suka warna apa?"}],
        )
        self.assertTrue(len(turn["clauses"]) >= 1)

    def test_17_bug_discourse_slang_thanks_abbreviations_unrecognized(self):
        # BUG (ace_indo_nlp/discourse.py:320): slang thanks (`mksh`, `mksih`, `thx`) normalize to
        # `"terima"` (not `"terima kasih"`), failing both checks in `is_thanks`.
        # DIPERBAIKI (gelombang robustness 2026-11-20): is_thanks mengenali token singkatan itu.
        for slang in ("mksh", "thx"):
            with self.subTest(slang=slang):
                self.assertTrue(analyze_discourse_cues(slang)["is_thanks"])

    def test_18_discourse_dialogue_acts_and_guessing_followup(self):
        self.assertEqual(analyze_discourse_cues("siapa namamu?")["dialogue_act"], "identity")
        self.assertEqual(analyze_discourse_cues("lagi ngapain nih?")["dialogue_act"], "casual_activity")
        self.assertEqual(analyze_discourse_cues("ceritain sesuatu dong")["dialogue_act"], "story_request")

        guess_res = realize_indonesian_turn(
            user_text="langit",
            cues=analyze_discourse_cues("langit"),
            grounded=[],
            profile={"vocab_count": 50},
            mode_label="Lokal",
            latest_task=None,
            recent_assistant_texts=[],
            history_turns=5,
            curious_word=None,
            conversation_context={"last_topic": "tebak_langit"},
        )
        self.assertIn("Tepat banget", guess_res["clauses"][0])


class TestMCPChatAndReportEdgeCases(unittest.TestCase):
    """Edge-case & adversarial tests for ace_mcp, ace_chat, and ace_report."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_19_mcp_bridge_bool_type_guards_and_diagnostic_tool_listing(self):
        with self.assertRaises(TypeError):
            ACEBridge(self.root, allow_writes=1)
        with self.assertRaises(TypeError):
            ACEBridge(self.root, enable_code_diagnostic=1)

        diag_bridge = ACEBridge(self.root, enable_code_diagnostic=True)
        names = {t["name"] for t in diag_bridge.tools()}
        self.assertEqual(len(names), 9)
        self.assertIn("ace_code_diagnostic", names)
        self.assertIn("ace_patch_diagnostic", names)
        self.assertIn("ace_host_candidate_diagnostic", names)

    def test_20_mcp_bridge_strict_hex_word_and_status_validation(self):
        bridge = ACEBridge(self.root)
        with self.assertRaises(ToolInputError):
            bridge.call("ace_get_report", {"task_id": "A" * 64})
        with self.assertRaises(ToolInputError):
            bridge.call("ace_get_report", {"task_id": "0" * 63})
        with self.assertRaises(ToolInputError):
            bridge.call("ace_predict", {"task_id": "0" * 64, "word": "a" * 101})
        with self.assertRaises(ToolInputError):
            bridge.call("ace_status", {"unexpected": 1})

    def test_21_mcp_json_rpc_errors_and_stdio_oversize_request(self):
        bridge = ACEBridge(self.root)
        self.assertEqual(json_rpc([], bridge)["error"]["code"], -32600)
        self.assertEqual(json_rpc({"jsonrpc": "1.0", "id": 1, "method": "ping"}, bridge)["error"]["code"], -32600)
        self.assertEqual(json_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"x": 1}}, bridge)["error"]["code"], -32602)
        self.assertEqual(json_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": []}, bridge)["error"]["code"], -32602)
        self.assertIsNone(json_rpc({"jsonrpc": "2.0", "method": "notifications/ping"}, bridge))

        sink = io.StringIO()
        oversize = ("a" * (MAX_REQUEST_BYTES + 10)) + "\n"
        mcp_stdio(bridge, io.StringIO(oversize), sink)
        resp = json.loads(sink.getvalue().strip())
        self.assertEqual(resp["error"]["code"], -32600)
        self.assertEqual(resp["error"]["message"], "Request too large")

    def test_22_mcp_http_origins_healthz_404_and_cli_diagnostic_guard(self):
        bridge = ACEBridge(self.root)
        token = "0123456789abcdef0123456789abcdef"
        with self.assertRaises(ValueError):
            make_http_server("127.0.0.1", 0, bridge, token=token, allowed_origins=("http://insecure.example",))
        with self.assertRaises(ValueError):
            make_http_server("127.0.0.1", 0, bridge, token=token, allowed_origins={"https://set.invalid"})

        srv = make_http_server("127.0.0.1", 0, bridge, token=token)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)

        conn = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
        try:
            conn.request("GET", "/healthz")
            r1 = conn.getresponse()
            body1 = json.loads(r1.read())
            self.assertEqual(r1.status, 200)
            self.assertEqual(body1, {"ready": True})

            conn.request("GET", "/unknown")
            r2 = conn.getresponse()
            r2.read()
            self.assertEqual(r2.status, 404)
        finally:
            conn.close()

        with self.assertRaises(SystemExit) as cm:
            mcp_main(["--workspace", str(self.root), "--transport", "http", "--enable-code-diagnostic"])
        self.assertEqual(cm.exception.code, 2)

    def test_23_code_diagnostic_rejects_empty_non_str_and_multibyte_over_4kb(self):
        for bad in ("", 123, "a" * 4000 + "é" * 100):  # 4200 UTF-8 bytes > 4096
            with self.assertRaises(ValueError):
                eval_code_diagnostic(bad)

    def test_24_chat_parse_request_malformed_bytes_and_request_id(self):
        for bad_raw in ("not-bytes", b"", b"{", b"\xff\xfe"):
            with self.assertRaises(task_runner.RequestError):
                task_runner.parse_request(bad_raw)

        for bad_id in ("", "HasUpper", "has space", "a" * 61):
            payload = task_runner.canonical(
                {"schema": task_runner.SCHEMA, "mode": "runtime_demo", "tasks": [], "request_id": bad_id}
            )
            with self.assertRaises(task_runner.RequestError):
                task_runner.parse_request(payload)

    def test_25_chat_parse_request_batch_empty_dup_and_val_overlap(self):
        train, validation, terminal = bank("equal", 20261106)
        base_batch = {
            "schema": task_runner.SCHEMA,
            "mode": "task_batch",
            "request_id": "batch_edge_1",
            "tasks": [],
        }
        with self.assertRaises(task_runner.RequestError):
            task_runner.parse_request(task_runner.canonical(base_batch))

        t_item = {"name": "dup", "train": train, "validation": validation, "terminal": terminal}
        dup_batch = {**base_batch, "tasks": [copy.deepcopy(t_item), copy.deepcopy(t_item)]}
        with self.assertRaises(task_runner.RequestError):
            task_runner.parse_request(task_runner.canonical(dup_batch))

        overlap_term = copy.deepcopy(t_item)
        overlap_term["terminal"][0] = validation[0]
        with self.assertRaises(task_runner.RequestError):
            task_runner.parse_request(task_runner.canonical({**base_batch, "tasks": [overlap_term]}))

        oversize_term = copy.deepcopy(t_item)
        oversize_term["terminal"] = terminal + [("ababab", True)]
        with self.assertRaises(task_runner.RequestError):
            task_runner.parse_request(task_runner.canonical({**base_batch, "tasks": [oversize_term]}))

    def test_26_chat_main_cli_executes_task_batch_cleanly(self):
        train, validation, terminal = bank("equal", 20261106)
        req_path = self.root / "req.json"
        out_path = self.root / "out" / "receipt.json"
        res_path = self.root / "out" / "research.json"
        req_obj = {
            "schema": task_runner.SCHEMA,
            "mode": "task_batch",
            "request_id": "cli_batch_01",
            "tasks": [{"name": "eq_test", "train": train, "validation": validation, "terminal": terminal}],
        }
        req_path.write_bytes(task_runner.canonical(req_obj))
        buf = io.StringIO()
        import contextlib

        with contextlib.redirect_stdout(buf):
            task_runner.main(["--request", str(req_path), "--output", str(out_path), "--research-output", str(res_path)])

        summary = json.loads(buf.getvalue().strip())
        receipt = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["request_id"], "cli_batch_01")
        self.assertEqual(receipt["schema"], task_runner.REPORT_SCHEMA)
        self.assertEqual(receipt["release_decision"], "BLOCK_RELEASE")
        self.assertFalse(res_path.exists())

    def test_27_mobile_report_empty_and_partial_data_defaults(self):
        rep_empty = generate_indonesian_mobile_report({})
        self.assertIn("NOT_ASSESSED", rep_empty)
        self.assertIn("INKONKLUSIF", rep_empty)
        self.assertIn("0.0%", rep_empty)

    def test_28_bug_mobile_report_negative_delta_formats_plus_minus(self):
        # BUG (ace_report/mobile_report.py:38): `f"+{(mean_c_g - mean_b_g) * 100:.1f}%"`
        # produces `+-15.0%` instead of `-15.0%` when condition C underperforms B.
        # DIPERBAIKI (gelombang robustness 2026-11-20): format ":+.1f" sadar-tanda.
        rep = generate_indonesian_mobile_report(
            {"graph_results": {"A": {"mean": 0.8}, "B": {"mean": 0.85}, "C": {"mean": 0.70}}}
        )
        self.assertNotIn("+-", rep)
        self.assertIn("-15.0%", rep)


if __name__ == "__main__":
    unittest.main()
