"""Milestone 1 Iteration 2 Adversarial Stress Test Suite (Challenger 1).

Adversarially challenges:
1. Intent routing for prompts containing 'modul' and boundary conditions (G04).
2. AST security auditor against docstring facades, constant stubs, AST node limits, and destructive calls (G03).
3. Benign collection methods preservation (list.remove, set.remove).
4. Non-keyword novel prompt deterministic fallback execution without NameError under diverse scenarios (G03).
5. End-to-end task execution and conversational engine routing.
"""
from __future__ import annotations

import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_operational.coding_loop import CodingAgentLoop
from ace_operational.language import ConversationalEngine, Intent, classify_intent_frame
from ace_operational.store import OperationalStore


class TestM1Challenger1NovelPromptAndASTAdversarial(unittest.TestCase):
    """Adversarial challenge test cases for novel prompt routing and AST security auditor."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_challenger1_"))
        self.store = OperationalStore(self.temp_dir)
        self.coding = CodingAgentLoop(self.store)
        self.engine = ConversationalEngine(self.store)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. Adversarial "modul" Intent Routing & Natural Language Classification
    # =========================================================================

    def test_novel_modul_prompts_route_to_general_never_multi_file(self):
        """Test novel prompts containing 'modul' route to domain='general', NOT 'multi_file'."""
        novel_modul_prompts = [
            "Buatkan modul kalkulator",
            "modul konversi satuan",
            "Buatkan modul hitung luas bangun datar",
            "modul konversi satuan suhu",
            "bikin modul generator qr",
            "tolong buatkan modul matriks dan vektor",
            "modul parser json mandiri",
            "Buatkan MODUL hitung diskon",
            "Buatkan modul-kalkulator",
            "Modul pemilah bilangan prima",
            "rancang modul enkripsi sha256",
            "bikin modul stopwatch",
            "buat modul web scraping sederhana",
            "modul simulasi antrian kasir",
            "buatkan modul kompresi teks lzw",
        ]
        for prompt in novel_modul_prompts:
            with self.subTest(prompt=prompt):
                frame = classify_intent_frame(prompt)
                self.assertEqual(
                    frame["intent"],
                    Intent.CREATE_OR_MODIFY_CODE,
                    f"Prompt {prompt!r} failed to classify as CREATE_OR_MODIFY_CODE",
                )
                self.assertEqual(
                    frame["domain"],
                    "general",
                    f"Prompt {prompt!r} misrouted to domain {frame['domain']!r} instead of 'general'!",
                )
                self.assertGreaterEqual(
                    frame["domain_confidence"],
                    0.7,
                    f"Prompt {prompt!r} confidence {frame['domain_confidence']} is below threshold 0.7",
                )

    def test_explicit_multi_file_compound_prompts_still_route_to_multi_file(self):
        """Verify explicit multi-file compound expressions are not broken and correctly route to 'multi_file'."""
        multi_file_prompts = [
            "Buat modul multi file terpisah",
            "Bikin multi modul dengan models dan utils",
            "Buat aplikasi dengan dua file modul",
            "Banyak modul dalam paket terstruktur",
            "Struktur modul terpisah dengan file main dan helper",
            "Buatkan proyek multi-modul lengkap",
            "Buat sistem dengan banyak berkas terpisah",
            "Buatkan aplikasi multi berkas",
        ]
        for prompt in multi_file_prompts:
            with self.subTest(prompt=prompt):
                frame = classify_intent_frame(prompt)
                self.assertEqual(frame["intent"], Intent.CREATE_OR_MODIFY_CODE)
                self.assertEqual(
                    frame["domain"],
                    "multi_file",
                    f"Explicit multi-file prompt {prompt!r} failed to route to 'multi_file'!",
                )

    def test_specialized_domain_prompts_with_modul_route_to_specialized_domains(self):
        """Verify specialized domain prompts mentioning 'modul' preserve domain affinity."""
        cases = [
            ("Buatkan modul catat pengeluaran harian", "expense_tracker"),
            ("Buat modul pembaca csv dan filter data", "csv_reader"),
            ("Bikin modul game tebak angka interaktif", "tebak_angka"),
        ]
        for prompt, expected_domain in cases:
            with self.subTest(prompt=prompt):
                frame = classify_intent_frame(prompt)
                self.assertEqual(frame["intent"], Intent.CREATE_OR_MODIFY_CODE)
                self.assertEqual(frame["domain"], expected_domain)

    def test_greeting_with_modul_action_routes_to_coding(self):
        """Verify greeting combined with modul action routes to coding, not passive conversation."""
        mixed_prompts = [
            "Halo ACE, tolong buatkan modul kalkulator",
            "Selamat pagi ACE, bisakah buatkan modul pengolah kata?",
            "Hai ACE, tolong bikinin modul konversi suhu",
        ]
        for prompt in mixed_prompts:
            with self.subTest(prompt=prompt):
                frame = classify_intent_frame(prompt)
                self.assertEqual(frame["intent"], Intent.CREATE_OR_MODIFY_CODE)
                self.assertEqual(frame["domain"], "general")

    # =========================================================================
    # 2. Adversarial AST Auditor Validation (Docstrings, Constants, Limits)
    # =========================================================================

    def test_ast_auditor_rejects_all_docstring_and_constant_facades(self):
        """Adversarially challenge _validate_and_audit_ast with various docstrings and constant facades."""
        facades = [
            # Standard single/multiline docstrings
            '"""Hanya modul kalkulator tanpa kode nyata."""',
            "'''\nModul dokumentasi panjang.\nBaris kedua.\n'''",
            '"""Docstring 1"""\n"""Docstring 2"""\n"""Docstring 3"""',
            '# Komentar saja\n"""Dokumentasi modul"""\n# Komentar penutup',
            # Constant primitives
            '42',
            '3.14159',
            '"hanya string literal"',
            'True',
            'None',
            '...',
            # Whitespace and pass
            'pass',
            '   \n\t\n   ',
            # Type annotations without assignment value
            'x: int',
            'nama: str',
            'angka: list[int]',
            # Imports only without any executable statements, functions, or classes
            'import sys\nimport os',
            'from math import sqrt, sin',
        ]
        for code in facades:
            with self.subTest(code=code[:40]):
                ok, err = self.coding._validate_and_audit_ast(code, "kalkulator")
                self.assertFalse(ok, f"Facade code should be rejected, but was accepted: {code!r}")
                self.assertTrue(len(err) > 0, "Error message must be non-empty")

    def test_ast_auditor_rejects_trivial_stubs(self):
        """Verify dummy success stubs are rejected."""
        stubs = [
            'def selesaikan_tugas(): return {"status": "sukses_terverifikasi"}',
            'def foo(): return "sukses_terverifikasi"',
            'def selesaikan_tugas(): pass',
        ]
        for code in stubs:
            with self.subTest(code=code):
                ok, err = self.coding._validate_and_audit_ast(code, "test")
                self.assertFalse(ok)
                self.assertIn("Trivial stub terdeteksi", err)

    def test_ast_auditor_rejects_ast_node_budget_exhaustion(self):
        """Verify AST auditor rejects payload exceeding 5000 AST nodes."""
        # Build code with > 5000 nodes using assignments (2501 assignments * ~4 nodes = ~10005 nodes)
        huge_code = "\n".join(f"x_{i} = {i}" for i in range(2501))
        ok, err = self.coding._validate_and_audit_ast(huge_code, "stress_test")
        self.assertFalse(ok)
        self.assertIn("melebihi batas 5000 nodes", err)

    # =========================================================================
    # 3. Adversarial Destructive Filesystem Calls & Unsafe Operations
    # =========================================================================

    def test_ast_auditor_rejects_destructive_calls_comprehensive(self):
        """Test rejection of all destructive filesystem deletion functions and methods."""
        destructive_snippets = [
            # Direct imports from os, shutil, pathlib, posix, nt
            ("from os import remove\nremove('data.txt')", "remove"),
            ("from os import unlink\nunlink('data.txt')", "unlink"),
            ("from os import rmdir\nrmdir('data_dir')", "rmdir"),
            ("from shutil import rmtree\nrmtree('data_dir')", "rmtree"),
            ("from pathlib import Path\nPath('data.txt').unlink()", "unlink"),
            ("from posix import remove\nremove('data.txt')", "remove"),
            ("from nt import unlink\nunlink('data.txt')", "unlink"),
            # Aliased imports
            ("from os import remove as delete_file\ndelete_file('data.txt')", "remove"),
            ("from shutil import rmtree as wipe\nwipe('data_dir')", "rmtree"),
            # Direct calls
            ("remove('data.txt')", "remove"),
            ("unlink('data.txt')", "unlink"),
            ("rmdir('data_dir')", "rmdir"),
            ("rmtree('data_dir')", "rmtree"),
            # Attribute calls on Path instances
            ("p = Path('data.txt')\np.unlink()", "unlink"),
            ("p = Path('data_dir')\np.rmdir()", "rmdir"),
            # Attribute calls on os / shutil
            ("import os\nos.remove('data.txt')", "remove"),
            ("import os\nos.unlink('data.txt')", "unlink"),
            ("import os\nos.rmdir('data_dir')", "rmdir"),
            ("import shutil\nshutil.rmtree('data_dir')", "rmtree"),
        ]
        for snippet, expected_token in destructive_snippets:
            with self.subTest(snippet=snippet, expected_token=expected_token):
                ok, err = self.coding._validate_and_audit_ast(snippet, "security_test")
                self.assertFalse(ok, f"Destructive snippet should be rejected: {snippet!r}")
                self.assertIn("operasi destruktif", err)

    def test_ast_auditor_allows_benign_collection_remove(self):
        """Verify list.remove and set.remove on collection instances are NOT falsely rejected."""
        benign_snippets = [
            "items = [1, 2, 3]\nitems.remove(2)",
            "words = ['a', 'b', 'c']\nwords.remove('b')",
            "s = {10, 20, 30}\ns.remove(20)",
            (
                "class Registry:\n"
                "    def __init__(self):\n"
                "        self.data = []\n"
                "    def remove(self, val):\n"
                "        self.data.remove(val)\n"
                "r = Registry()\nr.remove(5)\n"
            ),
        ]
        for snippet in benign_snippets:
            with self.subTest(snippet=snippet):
                ok, err = self.coding._validate_and_audit_ast(snippet, "benign_test")
                self.assertTrue(ok, f"Benign snippet was falsely rejected: {err}\nSnippet:\n{snippet}")
                self.assertEqual(err, "")

    def test_ast_auditor_rejects_interactive_input_and_reflection(self):
        """Verify interactive input() and reflection attributes are rejected."""
        unsafe = [
            ("def run():\n    x = input('Nama: ')\n", "input"),
            ("c = ().__class__.__subclasses__()", "__subclasses__"),
            ("f = lambda: None\ncode = f.__code__", "__code__"),
            ("eval('5 * 5')", "eval"),
            ("exec('y = 10')", "exec"),
            ("__import__('math')", "__import__"),
        ]
        for snippet, reason in unsafe:
            with self.subTest(snippet=snippet, reason=reason):
                ok, err = self.coding._validate_and_audit_ast(snippet, "unsafe_test")
                self.assertFalse(ok, f"Unsafe snippet was accepted: {snippet!r}")
                self.assertTrue(len(err) > 0)

    # =========================================================================
    # 4. Deterministic Fallback Synthesis & Execution (Novel Prompts)
    # =========================================================================

    def test_deterministic_fallback_executes_cleanly_across_diverse_novel_prompts(self):
        """Stress-test _synthesize_deterministic_general_solution across 10 novel prompts."""
        novel_prompts = [
            ("Simulasi Orbit Satelit", "Simulasikan orbit satelit geostasioner pada ketinggian 35786 km"),
            ("Parser Log Server", "Buat parser log HTTP Apache dan hitung kode status 404"),
            ("Analisis Sentimen", "Analisis sentimen kalimat berdasarkan leksikon kata positif dan negatif"),
            ("Rekomendasi Film", "Sistem rekomendasi film berbasis kemiripan konten"),
            ("Kriptografi Caesar", "Enkripsi dan dekripsi teks dengan algoritma Caesar Cipher"),
            ("Optimasi Rute", "Cari rute pengiriman paket terpendek dengan algoritma Dijkstra"),
            ("Matriks Kovariansi", "Hitung matriks variansi dan kovariansi dari data multi-dimensi"),
            ("Simulasi Antrian Bank", "Simulasi sistem antrian multi-teller dengan model Poisson"),
            ("Peringkas Teks Otomatis", "Ekstraksi kalimat penting dari teks artikel panjang"),
            ("Generator Faktur Pembelian", "Buat format teks faktur pembelian barang dengan pajak"),
        ]

        for title, goal in novel_prompts:
            with self.subTest(title=title):
                code = self.coding._synthesize_deterministic_general_solution(title=title, goal=goal)

                # 1. No dummy stubs
                self.assertNotIn("selesaikan_tugas", code)
                self.assertNotIn("sukses_terverifikasi", code)

                # 2. Passes AST audit
                syntax_ok, ast_err = self.coding._validate_and_audit_ast(code, goal)
                self.assertTrue(syntax_ok, f"Fallback code failed AST audit: {ast_err}")

                # 3. Executes with returncode 0 and zero NameError
                script_path = self.temp_dir / f"test_{abs(hash(title))}.py"
                script_path.write_text(code, encoding="utf-8")

                proc = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(
                    proc.returncode,
                    0,
                    f"Script failed for {title!r} with exit code {proc.returncode}.\nStderr: {proc.stderr}\nStdout: {proc.stdout}",
                )
                self.assertNotIn("NameError", proc.stderr)
                self.assertIn("Verifikasi sukses", proc.stdout)

    def test_fallback_handles_special_characters_in_title_and_goal(self):
        """Verify fallback safely handles titles and goals with quotes, newlines, and special characters."""
        special_cases = [
            ('Solusi "Kutipan Ganda" ACE', "Tujuan dengan 'kutipan tunggal' dan \\backslash"),
            ("Modul multi'quote' & \"mixed\"", "Tujuan dengan karakter khusus: <>&%$#@!*()"),
            ("Judul Dengan Simbol Unicode \u2705 \u2764", "Tujuan dengan emoji \U0001f680 roket"),
        ]
        for title, goal in special_cases:
            with self.subTest(title=title):
                code = self.coding._synthesize_deterministic_general_solution(title=title, goal=goal)
                syntax_ok, ast_err = self.coding._validate_and_audit_ast(code, goal)
                self.assertTrue(syntax_ok, f"Failed AST audit for special characters: {ast_err}")

                script_path = self.temp_dir / f"test_special_{abs(hash(title))}.py"
                script_path.write_text(code, encoding="utf-8")
                proc = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, timeout=10)
                self.assertEqual(proc.returncode, 0, f"Failed on special characters: {proc.stderr}")
                self.assertNotIn("NameError", proc.stderr)

    # =========================================================================
    # 5. End-to-End Conversational & General Coding Integration
    # =========================================================================

    def test_e2e_conversational_engine_executes_novel_modul_request(self):
        """Verify ConversationalEngine end-to-end executes a novel 'modul' request successfully."""
        prompt = "Buatkan modul kalkulator pembagi dan pengali"
        frame = classify_intent_frame(prompt)
        self.assertEqual(frame["intent"], Intent.CREATE_OR_MODIFY_CODE)
        self.assertEqual(frame["domain"], "general")

        res = self.engine.handle_user_message(prompt)
        self.assertIsNotNone(res["task"], "Task must be created for novel modul request")
        task = res["task"]
        self.assertEqual(task["status"], "COMPLETED")

        # Verify receipt exists and passed
        receipts = self.store.list_receipts(task_id=task["task_id"])
        self.assertGreaterEqual(len(receipts), 1, "At least one execution receipt must be recorded")
        latest_rcpt = receipts[-1]
        self.assertTrue(latest_rcpt["passed"])
        self.assertEqual(latest_rcpt["exit_code"], 0)

        # Verify generated artifact exists and runs cleanly
        artifacts = task.get("artifacts", [])
        self.assertGreaterEqual(len(artifacts), 1)
        artifact_path = Path(artifacts[0]["path"])
        self.assertTrue(artifact_path.exists())
        proc = subprocess.run([sys.executable, str(artifact_path)], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, f"Generated script crashed: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
