"""E2E Test Suite: Milestone 1 Novel Intent Routing, General Coding, and Atomic Fencing (G04, G03, G11).

Covers:
- G04: Novel domain intent routing and classification confidence.
- G03: AST security validation, trivial stub elimination, and execute_general_task.
- G11: Advisory sibling file locking, concurrent race protection, and dynamic callable lease fencing.
"""
from __future__ import annotations

import ast
import concurrent.futures
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_operational.coding_loop import (
    CodingAgentLoop,
    FencingLeaseViolationError,
    StalePreimageError,
    atomic_write_verified,
)
from ace_operational.language import ConversationalEngine, Intent, classify_intent_frame
from ace_operational.store import OperationalStore


class TestM1GeneralCodingAndFencingE2E(unittest.TestCase):
    """End-to-end tests for Milestone 1 contracts."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_e2e_m1_"))
        self.store = OperationalStore(self.temp_dir)
        self.coding = CodingAgentLoop(self.store)
        self.engine = ConversationalEngine(self.store)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # G04: Intent Classification & Routing
    # -------------------------------------------------------------------------

    def test_g04_novel_prompts_classify_as_general_with_high_confidence(self):
        """Verify novel coding prompts classify to domain='general' with confidence >= 0.7."""
        novel_prompts = [
            "Buatkan kalkulator sederhana",
            "Buat program hitung deret fibonacci",
            "Buatkan utilitas pengubah teks dan penghitung kata",
            "Bikin skrip konversi satuan suhu",
            "Buat kode algoritma pencarian biner",
            # Novel modular prompts that must NOT be hijacked to multi_file shopping cart
            "Buatkan modul hitung luas dan keliling bangun datar",
            "Buatkan modul enkripsi data sederhana",
            "Bikin modul kalkulator aritmatika",
        ]
        for prompt in novel_prompts:
            with self.subTest(prompt=prompt):
                frame = classify_intent_frame(prompt)
                self.assertEqual(frame["intent"], Intent.CREATE_OR_MODIFY_CODE)
                self.assertEqual(frame["domain"], "general")
                self.assertGreaterEqual(frame["domain_confidence"], 0.7)

    def test_g04_template_keywords_preserve_specialized_domains(self):
        """Verify established template domains remain preserved for specific trigger words."""
        cases = [
            ("Catat pengeluaran makan siang Rp25.000", "expense_tracker"),
            ("Baca file rekap.csv dan hitung total", "csv_reader"),
            ("Buatkan game tebak angka seru", "tebak_angka"),
            ("Buat aplikasi multi modul dua file terpisah", "multi_file"),
            ("Buat paket multi-file dengan models.py dan main.py", "multi_file"),
            ("Buatkan aplikasi dengan struktur berkas multi berkas", "multi_file"),
        ]
        for prompt, expected_domain in cases:
            with self.subTest(prompt=prompt):
                frame = classify_intent_frame(prompt)
                self.assertEqual(frame["intent"], Intent.CREATE_OR_MODIFY_CODE)
                self.assertEqual(frame["domain"], expected_domain)
                self.assertGreaterEqual(frame["domain_confidence"], 0.9)

    def test_g04_short_indonesian_greetings_route_to_conversation_not_coding(self):
        """Verify short Indonesian greetings route to GENERAL_CONVERSATION / GREETING, never coding synthesis."""
        greetings = [
            "halo",
            "hai",
            "selamat pagi",
            "selamat siang",
            "selamat malam",
            "apa kabar",
            "Halo ACE",
        ]
        for greeting in greetings:
            with self.subTest(greeting=greeting):
                frame = classify_intent_frame(greeting)
                self.assertNotEqual(
                    frame["intent"],
                    Intent.CREATE_OR_MODIFY_CODE,
                    f"Greeting {greeting!r} must not route to coding synthesis!"
                )
                self.assertIn(
                    frame["intent"],
                    (Intent.GENERAL_CONVERSATION, Intent.GREETING_OR_CAPABILITIES),
                )
                self.assertFalse(frame.get("side_effects_allowed", True))

                # ConversationalEngine must reply without launching coding task or creating task records
                res = self.engine.handle_user_message(greeting)
                self.assertIsNone(res["task"], f"No task should be created for greeting {greeting!r}")
                self.assertIn("ACE", res["reply"])

    def test_g04_greeting_with_coding_request_routes_to_coding(self):
        """Verify greeting combined with coding command correctly routes to code creation."""
        mixed_prompts = [
            ("Halo ACE, buatkan saya program kalkulator", "general"),
            ("Selamat pagi, tolong bikinin skrip rekap csv", "csv_reader"),
            ("Hai, tolong buatkan game tebak angka", "tebak_angka"),
        ]
        for prompt, expected_domain in mixed_prompts:
            with self.subTest(prompt=prompt):
                frame = classify_intent_frame(prompt)
                self.assertEqual(frame["intent"], Intent.CREATE_OR_MODIFY_CODE)
                self.assertEqual(frame["domain"], expected_domain)

    # -------------------------------------------------------------------------
    # G03: AST Security, Docstring-Only Rejection & General Fallback
    # -------------------------------------------------------------------------

    def test_g03_ast_audit_rejects_trivial_stubs(self):
        """Verify _validate_and_audit_ast strictly rejects trivial stubs."""
        stubs = [
            'def selesaikan_tugas(): return {"status": "sukses_terverifikasi"}',
            'def foo(): return {"status": "sukses_terverifikasi"}',
            'def selesaikan_tugas(): pass',
        ]
        for stub in stubs:
            with self.subTest(stub=stub):
                ok, err = self.coding._validate_and_audit_ast(stub, "kalkulator")
                self.assertFalse(ok)
                self.assertIn("Trivial stub terdeteksi", err)

    def test_g03_ast_audit_rejects_docstring_only_facade(self):
        """Verify _validate_and_audit_ast strictly rejects docstring-only files and constant expressions."""
        facades = [
            '"""Hanya docstring tanpa fungsi atau kode logika apa pun"""',
            "'''Multi-line docstring\ntanpa kode eksekusi'''",
            '"""Docstring"""\n# Hanya komentar',
            '12345',
            '"hanya sebuah string konstan"',
            'pass',
        ]
        for snippet in facades:
            with self.subTest(snippet=snippet):
                ok, err = self.coding._validate_and_audit_ast(snippet, "kalkulator")
                self.assertFalse(ok)
                self.assertIn("Kode tidak memiliki fungsi, kelas, atau pernyataan logika yang dapat dieksekusi", err)

    def test_g03_ast_audit_rejects_unsafe_constructs_and_input(self):
        """Verify _validate_and_audit_ast rejects reflection, dynamic evaluation, and input()."""
        unsafe = [
            ("eval('1 + 1')", "eval"),
            ("exec('print(1)')", "exec"),
            ("input('Masukkan angka: ')", "input"),
            ("x = ().__class__.__subclasses__()", "__subclasses__"),
            ("import shutil\nshutil.rmtree('/tmp')", "rmtree"),
        ]
        for snippet, violation in unsafe:
            with self.subTest(snippet=snippet):
                ok, err = self.coding._validate_and_audit_ast(snippet, "test")
                self.assertFalse(ok)
                self.assertTrue(len(err) > 0)

    def test_g03_ast_audit_rejects_destructive_calls_direct_and_attributes(self):
        """Verify _validate_and_audit_ast rejects direct name calls and Path.unlink while allowing benign collection methods."""
        unsafe_destructive = [
            ("from os import remove\nremove('file.txt')", "remove"),
            ("from os import unlink\nunlink('file.txt')", "unlink"),
            ("from shutil import rmtree\nrmtree('/tmp')", "rmtree"),
            ("from pathlib import Path\nPath('file.txt').unlink()", "unlink"),
            ("p = Path('file.txt')\np.unlink()", "unlink"),
            ("p = Path('dir')\np.rmdir()", "rmdir"),
            ("import os\nos.unlink('file.txt')", "unlink"),
            ("import os\nos.rmdir('dir')", "rmdir"),
        ]
        for snippet, violation in unsafe_destructive:
            with self.subTest(snippet=snippet):
                ok, err = self.coding._validate_and_audit_ast(snippet, "test")
                self.assertFalse(ok)
                self.assertIn("operasi destruktif", err)

        # Verify benign collection methods are permitted
        benign_codes = [
            "items = [1, 2, 3]\nitems.remove(2)",
            "seen = {'a', 'b'}\nseen.remove('a')",
        ]
        for snippet in benign_codes:
            with self.subTest(snippet=snippet):
                ok, err = self.coding._validate_and_audit_ast(snippet, "test")
                self.assertTrue(ok)
                self.assertEqual(err, "")

    def test_g03_ast_audit_accepts_clean_python(self):
        """Verify valid Python functions and assertions pass AST audit."""
        clean_code = (
            "def tambah(a: int, b: int) -> int:\n"
            "    return a + b\n\n"
            "if __name__ == '__main__':\n"
            "    assert tambah(2, 3) == 5\n"
            "    print('OK')\n"
        )
        ok, err = self.coding._validate_and_audit_ast(clean_code, "kalkulator")
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_g03_general_fallback_executes_without_name_error(self):
        """Verify _synthesize_deterministic_general_solution executes cleanly without NameError."""
        code = self.coding._synthesize_deterministic_general_solution(
            title="Solusi Novel Mandiri",
            goal="Buatkan sistem simulasi orbit satelit",
        )
        self.assertIn("class SolusiUmumACE:", code)
        self.assertIn("solusi = SolusiUmumACE(", code)

        with tempfile.TemporaryDirectory() as td:
            script_path = Path(td) / "solusi_novel.py"
            script_path.write_text(code, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"Script crashed: {proc.stderr}")
            self.assertIn("Verifikasi sukses: solusi mandiri 'Solusi Novel Mandiri' lulus seluruh uji fungsional.", proc.stdout)

    def test_g03_execute_general_task_public_contract(self):
        """Verify execute_general_task returns genuine script with verified receipt and semantic invariants."""
        res = self.coding.execute_general_task(
            title="Modul Kalkulator Aritmatika",
            goal="Buatkan kalkulator sederhana",
            options={"allow_deterministic_fallback": True},
        )
        # 1. Structural task success invariants
        self.assertTrue(res["success"], "General task execution must succeed")
        self.assertTrue(res["test_passed"], "Test verification must pass")
        self.assertTrue(Path(res["file_path"]).exists(), "Generated script artifact must exist on disk")
        self.assertGreater(Path(res["file_path"]).stat().st_size, 0, "Artifact file must not be empty")

        # 2. Cryptographic receipt validation
        receipt = res.get("receipt", {})
        self.assertIn("rcpt_", receipt.get("receipt_id", ""), "Receipt ID must have rcpt_ prefix")
        self.assertTrue(receipt.get("passed"), "Receipt passed must be True")
        self.assertEqual(receipt.get("exit_code"), 0, "Receipt exit code must be 0")

        # 3. Execution output validation (non-empty output, clean exit)
        self.assertIsNotNone(res.get("output"), "Output text must not be None")
        self.assertGreater(len(res["output"].strip()), 0, "Output must contain execution logs or test output")

        # 4. Anti-cheating & AST semantic invariant checks (replaces brittle substring matching)
        script_text = Path(res["file_path"]).read_text(encoding="utf-8")
        self.assertNotIn("selesaikan_tugas", script_text, "Dummy stub 'selesaikan_tugas' must not be present")
        self.assertNotIn("sukses_terverifikasi", script_text, "Dummy stub 'sukses_terverifikasi' must not be present")

        # Must parse as valid Python AST and contain at least one function or class
        tree = ast.parse(script_text)
        has_executable_structure = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for node in tree.body
        )
        self.assertTrue(has_executable_structure, "Script must define at least one genuine function or class")

        # 5. Independent subprocess execution verification
        proc = subprocess.run([sys.executable, res["file_path"]], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, f"Script must execute with returncode 0. Stderr: {proc.stderr}")

    # -------------------------------------------------------------------------
    # G11: Sibling Lockfile, Mutual Exclusion & Lease Fencing
    # -------------------------------------------------------------------------

    def test_g11_sibling_lockfile_and_concurrent_preimage_guard(self):
        """Verify sibling lockfile is used and 10 concurrent threads resolve with exactly 1 winner."""
        target = self.temp_dir / "projects" / "concurrent_fencing.py"
        init_res = atomic_write_verified(target, "v = 1\n", expected_lease_epoch=1, current_lease_epoch=1)
        orig_hash = init_res["postimage_sha256"]

        # Lockfile must exist as sibling
        lock_file = target.parent / f".{target.name}.lock"
        self.assertTrue(lock_file.exists())

        num_threads = 10
        def race_worker(idx: int) -> str:
            try:
                atomic_write_verified(
                    target,
                    f"v = {idx + 10}\n",
                    expected_preimage_sha256=orig_hash,
                    expected_lease_epoch=1,
                    current_lease_epoch=1,
                )
                return "WIN"
            except StalePreimageError:
                return "STALE"

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            results = list(executor.map(race_worker, range(num_threads)))

        wins = [r for r in results if r == "WIN"]
        stales = [r for r in results if r == "STALE"]
        self.assertEqual(len(wins), 1, "Exactly one thread should win the race")
        self.assertEqual(len(stales), num_threads - 1, "All other threads must receive StalePreimageError")

    def test_g11_dynamic_callable_lease_epoch_fencing(self):
        """Verify dynamic callable lease epoch fences out commits if lease invalidated at commit point."""
        target = self.temp_dir / "projects" / "dynamic_fence.py"
        atomic_write_verified(target, "a = 1\n", expected_lease_epoch=5, current_lease_epoch=5)

        epoch_state = [5]
        def dynamic_epoch() -> int:
            return epoch_state[0]

        # Succeeds when dynamic epoch is valid
        atomic_write_verified(target, "a = 2\n", expected_lease_epoch=5, current_lease_epoch=dynamic_epoch)
        self.assertEqual(target.read_text(encoding="utf-8"), "a = 2\n")

        # Invalidate lease epoch dynamically before commit: epoch mismatched (lower)
        epoch_state[0] = 4
        with self.assertRaises(FencingLeaseViolationError):
            atomic_write_verified(target, "a = 3\n", expected_lease_epoch=5, current_lease_epoch=dynamic_epoch)

        # Invalidate lease epoch dynamically before commit: epoch monotonic advancement (higher)
        epoch_state[0] = 6
        with self.assertRaises(FencingLeaseViolationError):
            atomic_write_verified(target, "a = 4\n", expected_lease_epoch=5, current_lease_epoch=dynamic_epoch)

        # Confirm target content was not modified and no dangling staging files remain
        self.assertEqual(target.read_text(encoding="utf-8"), "a = 2\n")
        dangling = list(target.parent.glob(".*.tmp.*"))
        self.assertEqual(len(dangling), 0)


if __name__ == "__main__":
    unittest.main()
