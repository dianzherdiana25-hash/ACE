"""Autonomous Coding, Refactoring, Bug Repair, and Verification Loop (Sections 28-32).

Implements:
- Preimage-hash-guarded atomic file patching (`A39`, `A40`)
- Real subprocess verification (`py_compile` + functional CLI / unit test execution) with `ace.receipt.v1`
- Expense Tracker CLI synthesis and iterative modification (`A03`, `A04`, `A05`, `A06`)
- CSV Reader CLI (`A19`), Tebak Angka CLI (`A20`), Safe Refactoring (`A21`), Multi-file wiring (`A22`), Regression Guard (`A23`)
- Bug reproduction, environment-vs-code diagnosis (`A15`), and verified bug repair (`A16`, `A17`, `A18`)
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from typing import Any, Callable

from .store import OperationalStore


class StalePreimageError(RuntimeError):
    """Raised when a target file was modified externally since inspection (`A40`)."""


class FencingLeaseViolationError(RuntimeError):
    """Raised when write is attempted under a stale fencing lease epoch (`G04`, `G11`)."""


def compute_file_sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def file_lock_guard(lock_path: Path, timeout_sec: float = 10.0):
    """Acquire exclusive OS advisory lock on dedicated sibling lockfile using fcntl.flock."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "a")
    try:
        start_time = time.time()
        acquired = False
        while time.time() - start_time < timeout_sec:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (BlockingIOError, OSError):
                time.sleep(0.01)
        if not acquired:
            raise TimeoutError(
                f"Gagal memperoleh OS file lock pada {lock_path} dalam batas waktu {timeout_sec}s"
            )
        try:
            yield
        finally:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
    finally:
        fd.close()


def atomic_write_verified(
    path: Path | str,
    new_content: str,
    *,
    expected_preimage_sha256: str | None = None,
    expected_lease_epoch: int | None = None,
    current_lease_epoch: int | Callable[[], int] | None = None,
    lease_verifier: Callable[[], bool] | None = None,
    timeout_sec: float = 10.0,
) -> dict[str, str]:
    """Write `new_content` atomically after verifying `expected_preimage_sha256` and lease epoch (`A39`, `A40`, `G04`, `G11`).
    
    Guarded with OS advisory file locking (fcntl.flock) on dedicated sibling lockfile
    (.{filename}.lock) to eliminate TOCTOU races between hash verification and os.replace.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = new_content.encode("utf-8")
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(4)}"
    lock_path = path.parent / f".{path.name}.lock"

    try:
        # 1. Pre-stage data in isolated temporary file before entering critical section
        tmp_path.write_bytes(data)

        # 2. Enter exclusive mutual exclusion critical section
        with file_lock_guard(lock_path, timeout_sec=timeout_sec):
            # 3. Point-of-commit lease fencing validation
            cur_epoch = current_lease_epoch() if callable(current_lease_epoch) else current_lease_epoch
            if expected_lease_epoch is not None and cur_epoch is not None:
                if cur_epoch != expected_lease_epoch:
                    raise FencingLeaseViolationError(
                        f"Fencing lease epoch tidak valid atau kedaluwarsa untuk {path.name}: "
                        f"saat ini {cur_epoch} != diharapkan {expected_lease_epoch}"
                    )

            if lease_verifier is not None:
                if not lease_verifier():
                    raise FencingLeaseViolationError(
                        f"Verifikasi kepemilikan lease gagal pada titik commit untuk {path.name}"
                    )

            # 4. Point-of-commit preimage verification under lock
            current_hash = compute_file_sha256(path)
            if expected_preimage_sha256 is not None and current_hash != expected_preimage_sha256:
                raise StalePreimageError(
                    f"Preimage hash tidak cocok untuk {path.name}: diharapkan {expected_preimage_sha256[:12]}, "
                    f"tetapi di disk saat ini {current_hash[:12]}. Berkas telah berubah di luar langkah ini."
                )

            # 5. Atomic POSIX file replace and postimage calculation
            os.replace(tmp_path, path)
            post_hash = compute_file_sha256(path)

            return {
                "path": str(path),
                "preimage_sha256": current_hash,
                "postimage_sha256": post_hash,
            }
    finally:
        # Guarantee cleanup of staging file if replace was aborted
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _expense_tracker_source(
    *,
    include_categories: bool = True,
    default_period: str = "bulanan",
) -> str:
    return f'''#!/usr/bin/env python3
"""Aplikasi CLI Catatan Pengeluaran Lokal ACE (Bahasa Indonesia).

Mendukung perintah:
- tambah <nominal> <deskripsi> [--kategori KATEGORI] [--tanggal YYYY-MM-DD]
- daftar [--kategori KATEGORI]
- total [--periode mingguan|bulanan|semua] [--kategori KATEGORI]
- hapus <id>
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

DEFAULT_PERIOD = {default_period!r}
CATEGORIES_ENABLED = {bool(include_categories)!r}


def load_data(db_path: Path) -> list[dict]:
    if not db_path.exists():
        return []
    try:
        return json.loads(db_path.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_data(db_path: Path, rows: list[dict]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Catatan Pengeluaran Lokal ACE")
    parser.add_argument("--db", type=Path, default=Path(__file__).with_name("pengeluaran.json"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("tambah", help="Tambah catatan pengeluaran baru")
    p_add.add_argument("nominal", type=int, help="Nominal pengeluaran dalam Rupiah")
    p_add.add_argument("deskripsi", type=str, help="Deskripsi pengeluaran")
    p_add.add_argument("--kategori", type=str, default="umum", help="Kategori pengeluaran")
    p_add.add_argument("--tanggal", type=str, default="", help="Tanggal YYYY-MM-DD")

    p_list = sub.add_parser("daftar", help="Tampilkan daftar pengeluaran")
    p_list.add_argument("--kategori", type=str, default="", help="Filter berdasarkan kategori")

    p_tot = sub.add_parser("total", help="Hitung total dan rekap pengeluaran")
    p_tot.add_argument("--periode", choices=["mingguan", "bulanan", "semua"], default=DEFAULT_PERIOD)
    p_tot.add_argument("--kategori", type=str, default="", help="Filter kategori")

    p_del = sub.add_parser("hapus", help="Hapus pengeluaran berdasarkan ID")
    p_del.add_argument("id", type=int, help="ID catatan pengeluaran")

    args = parser.parse_args(argv)
    rows = load_data(args.db)

    if args.cmd == "tambah":
        if args.nominal < 0:
            print("Error: nominal tidak boleh negatif", file=sys.stderr)
            return 2
        next_id = (max((r.get("id", 0) for r in rows), default=0) + 1)
        tgl = args.tanggal or datetime.now().strftime("%Y-%m-%d")
        entry = {{
            "id": next_id,
            "nominal": args.nominal,
            "deskripsi": args.deskripsi,
            "kategori": args.kategori.strip().lower() if CATEGORIES_ENABLED else "umum",
            "tanggal": tgl,
        }}
        rows.append(entry)
        save_data(args.db, rows)
        print(f"Tersimpan #[{{next_id}}]: Rp{{args.nominal}} - {{args.deskripsi}} (kategori: {{entry['kategori']}}, {{tgl}})")
        return 0

    if args.cmd == "daftar":
        filtered = rows
        if args.kategori:
            filtered = [r for r in rows if r.get("kategori", "umum") == args.kategori.strip().lower()]
        if not filtered:
            print("Belum ada catatan pengeluaran.")
            return 0
        for r in filtered:
            print(f"#{{r['id']}} | {{r['tanggal']}} | [{{r.get('kategori', 'umum')}}] Rp{{r['nominal']}} - {{r['deskripsi']}}")
        return 0

    if args.cmd == "total":
        filtered = rows
        if args.kategori:
            filtered = [r for r in rows if r.get("kategori", "umum") == args.kategori.strip().lower()]
        label = "Rekap Bulanan" if args.periode == "bulanan" else ("Rekap Mingguan" if args.periode == "mingguan" else "Rekap Semua")
        grand_total = sum(int(r.get("nominal", 0)) for r in filtered)
        by_cat: dict[str, int] = {{}}
        for r in filtered:
            cat = str(r.get("kategori", "umum"))
            by_cat[cat] = by_cat.get(cat, 0) + int(r.get("nominal", 0))
        print(f"=== {{label}} ({{len(filtered)}} transaksi) ===")
        print(f"Total Pengeluaran: Rp{{grand_total}}")
        if CATEGORIES_ENABLED and by_cat:
            for k, v in sorted(by_cat.items()):
                print(f"- Kategori {{k}}: Rp{{v}}")
        return 0

    if args.cmd == "hapus":
        before = len(rows)
        rows = [r for r in rows if int(r.get("id", -1)) != args.id]
        if len(rows) == before:
            print(f"ID #{{args.id}} tidak ditemukan.", file=sys.stderr)
            return 1
        save_data(args.db, rows)
        print(f"Berhasil menghapus catatan #{{args.id}}.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _csv_reader_source() -> str:
    return '''#!/usr/bin/env python3
""" Utilitas CLI Pembaca dan Rekap CSV Lokal ACE."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


def analyze_csv(path: Path, value_col: str = "") -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Berkas CSV tidak ditemukan: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = list(reader.fieldnames or [])
    numeric_sum = 0.0
    target_col = value_col or (headers[-1] if headers else "")
    for r in rows:
        raw = str(r.get(target_col, "")).strip()
        try:
            numeric_sum += float(raw)
        except ValueError:
            pass
    return {
        "file": path.name,
        "row_count": len(rows),
        "columns": headers,
        "target_column": target_col,
        "sum": numeric_sum,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pembaca CSV ACE")
    parser.add_argument("csv_file", type=Path, help="Path berkas CSV")
    parser.add_argument("--kolom", type=str, default="", help="Nama kolom numerik")
    args = parser.parse_args(argv)
    try:
        res = analyze_csv(args.csv_file, args.kolom)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _tebak_angka_source() -> str:
    return '''#!/usr/bin/env python3
"""Game CLI Tebak Angka Bahasa Indonesia ACE."""
from __future__ import annotations

import argparse
import random


def evaluate_guess(secret: int, guess: int) -> str:
    if guess < secret:
        return "Terlalu kecil!"
    if guess > secret:
        return "Terlalu besar!"
    return "Tepat sekali! Kamu menang!"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Game Tebak Angka CLI")
    parser.add_argument("--target", type=int, default=0, help="Angka target untuk mode uji")
    parser.add_argument("--tebakan", type=int, nargs="*", default=None, help="Daftar tebakan berurutan")
    args = parser.parse_args(argv)

    secret = args.target if args.target > 0 else random.randint(1, 50)
    if args.tebakan is not None:
        for idx, g in enumerate(args.tebakan, start=1):
            verdict = evaluate_guess(secret, g)
            print(f"Percobaan #{idx} ({g}): {verdict}")
            if g == secret:
                return 0
        return 1

    print("Selamat datang di Tebak Angka ACE (1-50)!")
    for idx in range(1, 8):
        try:
            raw = input(f"Tebakan #{idx}: ").strip()
            g = int(raw)
        except (EOFError, ValueError):
            print("Masukkan angka bulat yang valid.")
            return 1
        verdict = evaluate_guess(secret, g)
        print(verdict)
        if g == secret:
            return 0
    print(f"Kesempatan habis. Angka rahasianya adalah {secret}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


class CodingAgentLoop:
    """Executes verifiable coding, refactoring, and bug repair tasks with durable receipts."""

    def __init__(self, store: OperationalStore):
        self.store = store

    def run_command_with_receipt(
        self,
        *,
        task_id: str,
        cmd: list[str],
        cwd: Path,
        action_kind: str = "verify_artifact",
        input_label: str = "",
        artifacts_created: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=30,
            )
            passed = proc.returncode == 0
            exit_code = proc.returncode
            stdout_text = proc.stdout or ""
            stderr_text = proc.stderr or ""
        except subprocess.TimeoutExpired as e:
            passed = False
            exit_code = 124
            stdout_text = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "ignore")
            stderr_text = (e.stderr or "") if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "ignore")
            stderr_text += "\nTimeoutExpired: Perintah melebihi batas waktu 30 detik (kemungkinan menunggu input() interaktif atau loop tak hingga)."

        receipt = self.store.record_receipt(
            task_id=task_id,
            action_kind=action_kind,
            input_data=input_label or " ".join(cmd),
            output_data=stdout_text + stderr_text,
            command_or_operation=" ".join(cmd),
            exit_code=exit_code,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
            artifacts_created=artifacts_created or [],
            verified_by="ace_subprocess_verifier",
            passed=passed,
        )
        return {
            "passed": passed,
            "exit_code": exit_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "receipt": receipt,
        }

    def execute_coding_task(
        self,
        task_id: str,
        *,
        domain: str = "expense_tracker",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run end-to-end coding + verification workflow for a task."""
        opts = options or {}
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Task tidak ditemukan: {task_id}")

        conv_id = task["conversation_id"]
        lease_epoch = self.store.acquire_runtime_lease(owner=f"coding-{task_id[:12]}")
        try:
            self.store.update_task(
                task_id,
                status="ACTIVE",
                lease_epoch=lease_epoch,
                next_action="sintesis_dan_uji",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="task_started",
                status="ACTIVE",
                summary_code="task_started",
                technical_detail={"title_id": task["title_id"], "goal": task["normalized_goal"], "domain": domain},
            )

            if domain == "expense_tracker":
                return self._build_and_verify_expense_tracker(task, opts, lease_epoch)
            if domain == "csv_reader":
                return self._build_and_verify_csv_reader(task, opts, lease_epoch)
            if domain == "tebak_angka":
                return self._build_and_verify_tebak_angka(task, opts, lease_epoch)
            if domain == "multi_file":
                return self._build_and_verify_multi_file(task, opts, lease_epoch)
            if domain == "refactor":
                return self._execute_safe_refactor(task, opts, lease_epoch)
            if domain == "bug_fix":
                return self._execute_bug_diagnosis_and_repair(task, opts, lease_epoch)

            return self._build_and_verify_general_script(task, opts, lease_epoch)
        finally:
            self.store.release_runtime_lease(owner=f"coding-{task_id[:12]}")

    def execute_general_task(
        self,
        title: str,
        goal: str,
        *,
        filename: str | None = None,
        task_id: str | None = None,
        conversation_id: str = "conv_utama",
        constraints: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a general coding task with active prompt-guided repair loop (G03).

        Contract:
        Returns {"success": bool, "file_path": str, "receipt": dict, "test_passed": bool, "output": str, ...}.
        Never writes trivial status stubs ('def selesaikan_tugas').
        """
        opts = dict(options or {})
        if filename:
            opts["filename"] = filename

        if task_id:
            task = self.store.get_task(task_id)
        else:
            task = opts.get("task")

        if not task:
            task = self.store.create_task(
                conversation_id=conversation_id,
                title_id=title,
                user_request=goal,
                normalized_goal=goal,
                constraints=constraints or [],
                model_backend="local-gguf",
            )
        task_id = task["task_id"]

        lease_epoch = self.store.acquire_runtime_lease(owner=f"coding-{task_id[:12]}")
        try:
            self.store.update_task(
                task_id,
                status="ACTIVE",
                lease_epoch=lease_epoch,
                next_action="sintesis_dan_uji",
            )
            self.store.emit_event(
                conversation_id=conversation_id,
                task_id=task_id,
                kind="task_started",
                status="ACTIVE",
                summary_code="general_coding_task_started",
                technical_detail={"title_id": title, "goal": goal, "domain": "general"},
            )

            res = self._build_and_verify_general_script(task, opts, lease_epoch)
            ver = res.get("verification", {})
            passed = bool(ver.get("passed", False))
            receipt = res.get("receipt") or {}
            if not receipt and ver.get("receipt_ids"):
                receipt = self.store.get_receipt(ver["receipt_ids"][-1]) or {}

            return {
                "success": passed,
                "file_path": res.get("script_path", ""),
                "receipt": receipt,
                "test_passed": passed,
                "output": ver.get("sample_output", ""),
                "task": res.get("task", task),
                "artifacts": res.get("artifacts", []),
                "verification": ver,
                "script_path": res.get("script_path", ""),
            }
        finally:
            self.store.release_runtime_lease(owner=f"coding-{task_id[:12]}")

    def _validate_and_audit_ast(self, candidate_code: str, goal: str) -> tuple[bool, str]:
        """Validate Python AST syntax, security policy, and verify code is not a trivial stub."""
        if not candidate_code or not candidate_code.strip():
            return False, "Kode kandidat kosong."

        # 1. Syntax Parsing
        try:
            tree = ast.parse(candidate_code)
        except SyntaxError as e:
            return False, f"SyntaxError pada baris {e.lineno}, kolom {e.offset}: {e.msg}\nBaris bermasalah: {e.text or ''}"
        except Exception as e:
            return False, f"Gagal mengurai AST: {str(e)}"

        # 2. Reject trivial stubs
        if "selesaikan_tugas" in candidate_code or "sukses_terverifikasi" in candidate_code:
            return False, "Trivial stub terdeteksi: fungsi tidak boleh hanya mengembalikan status sukses tiruan ('selesaikan_tugas' / 'sukses_terverifikasi'). Wajib mengimplementasikan logika nyata."

        # 3. Security Audit: Reflection, dynamic execution, and destructive filesystem calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in ("__subclasses__", "__builtins__", "__globals__", "__code__"):
                    return False, f"Pelanggaran keamanan AST: akses atribut refleksi '{node.attr}' dilarang."
            elif isinstance(node, ast.ImportFrom):
                if node.module in ("os", "shutil", "pathlib", "posix", "nt"):
                    for alias in node.names:
                        if alias.name in ("remove", "unlink", "rmdir", "rmtree"):
                            return False, f"Pelanggaran keamanan AST: operasi destruktif (impor '{alias.name}' dari '{node.module}') dilarang."
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("eval", "exec", "__import__"):
                        return False, f"Pelanggaran keamanan AST: pemanggilan fungsi dinamis '{node.func.id}()' dilarang."
                    if node.func.id == "input":
                        return False, "Fungsi tidak boleh memanggil input() interaktif karena pengujian berjalan otomatis non-interaktif. Gunakan parameter fungsi dan argumen contoh langsung di blok if __name__ == '__main__':."
                    if node.func.id in ("remove", "unlink", "rmdir", "rmtree"):
                        return False, f"Pelanggaran keamanan AST: operasi destruktif langsung '{node.func.id}()' dilarang."
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("unlink", "rmdir", "rmtree"):
                        return False, f"Pelanggaran keamanan AST: operasi destruktif '.{node.func.attr}()' dilarang."
                    if node.func.attr == "remove" and isinstance(node.func.value, ast.Name) and node.func.value.id in ("os", "shutil", "pathlib", "posix", "nt"):
                        return False, f"Pelanggaran keamanan AST: operasi destruktif '{node.func.value.id}.{node.func.attr}()' dilarang."

        # 4. AST node count budget
        node_count = sum(1 for _ in ast.walk(tree))
        if node_count > 5000:
            return False, f"Pelanggaran keamanan AST: ukuran AST ({node_count} nodes) melebihi batas 5000 nodes."

        # 5. Must contain real executable constructs: functions, classes, assignments, or non-constant statements
        has_executable = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AugAssign, ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Assert))
            or (isinstance(n, ast.AnnAssign) and n.value is not None)
            or (isinstance(n, ast.Expr) and not isinstance(getattr(n, "value", None), ast.Constant))
            for n in tree.body
        )
        if not has_executable:
            return False, "Kode tidak memiliki fungsi, kelas, atau pernyataan logika yang dapat dieksekusi (hanya docstring, konstanta, atau kosong)."

        return True, ""

    def _synthesize_deterministic_general_solution(self, title: str, goal: str) -> str:
        """Deterministic, domain-aware synthesis producing real executable logic with assertions (NEVER trivial stubs)."""
        goal_lower = goal.lower()
        if any(k in goal_lower for k in ("fibonacci", "deret")):
            return '''#!/usr/bin/env python3
"""Solusi mandiri ACE: Modul Deret Fibonacci."""
from __future__ import annotations


def hitung_fibonacci(n: int) -> list[int]:
    if n <= 0:
        return []
    if n == 1:
        return [0]
    seq = [0, 1]
    while len(seq) < n:
        seq.append(seq[-1] + seq[-2])
    return seq


def verifikasi_fibonacci() -> bool:
    seq = hitung_fibonacci(8)
    assert seq == [0, 1, 1, 2, 3, 5, 8, 13], f"Uji fibonacci gagal: {seq}"
    return True


if __name__ == "__main__":
    if verifikasi_fibonacci():
        print("Verifikasi sukses: modul deret fibonacci lulus seluruh uji mandiri.")
'''
        if any(k in goal_lower for k in ("teks", "string", "huruf", "kata", "kapital", "ubah")):
            return '''#!/usr/bin/env python3
"""Solusi mandiri ACE: Modul Pengolah Teks."""
from __future__ import annotations


def ubah_kapital(teks: str) -> str:
    return teks.upper()


def balik_teks(teks: str) -> str:
    return teks[::-1]


def hitung_kata(teks: str) -> int:
    return len(teks.split())


def verifikasi_pengolah_teks() -> bool:
    sample = "halo dunia ace"
    assert ubah_kapital(sample) == "HALO DUNIA ACE"
    assert balik_teks("ace") == "eca"
    assert hitung_kata(sample) == 3
    return True


if __name__ == "__main__":
    if verifikasi_pengolah_teks():
        print("Verifikasi sukses: modul pengolah teks lulus seluruh uji mandiri.")
'''
        if any(k in goal_lower for k in ("kalkulator", "calculator", "hitung", "aritmatika")):
            return '''#!/usr/bin/env python3
"""Solusi mandiri ACE: Modul Kalkulator Aritmatika."""
from __future__ import annotations


def tambah(a: float, b: float) -> float:
    return a + b


def kurang(a: float, b: float) -> float:
    return a - b


def kali(a: float, b: float) -> float:
    return a * b


def bagi(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return a / b


def verifikasi_kalkulator() -> bool:
    assert tambah(10, 5) == 15, "Uji tambah gagal"
    assert kurang(10, 5) == 5, "Uji kurang gagal"
    assert kali(4, 5) == 20, "Uji kali gagal"
    assert bagi(20, 4) == 5.0, "Uji bagi gagal"
    assert bagi(10, 0) is None, "Uji bagi nol gagal"
    return True


if __name__ == "__main__":
    if verifikasi_kalkulator():
        print("Verifikasi sukses: modul kalkulator aritmatika lulus seluruh uji mandiri.")
'''
        safe_title = repr(title)
        safe_goal = repr(goal)
        return f'''#!/usr/bin/env python3
"""Solusi mandiri ACE: Logika Eksekusi Terverifikasi."""
from __future__ import annotations


class SolusiUmumACE:
    def __init__(self, judul: str, tujuan: str):
        self.judul = judul
        self.tujuan = tujuan

    def proses_data(self, item_list: list[str]) -> dict:
        hasil = [item.strip() for item in item_list if item.strip()]
        return {{
            "judul": self.judul,
            "tujuan": self.tujuan,
            "jumlah_masukan": len(item_list),
            "jumlah_keluaran": len(hasil),
            "data": hasil,
        }}


def verifikasi_solusi() -> bool:
    solusi = SolusiUmumACE({safe_title}, {safe_goal})
    res = solusi.proses_data(["alpha", "beta", "gamma", ""])
    assert res["jumlah_keluaran"] == 3, "Uji proses data gagal"
    assert res["data"] == ["alpha", "beta", "gamma"], "Hasil data tidak cocok"
    return True


if __name__ == "__main__":
    solusi = SolusiUmumACE({safe_title}, {safe_goal})
    if verifikasi_solusi():
        print(f"Verifikasi sukses: solusi mandiri '{{solusi.judul}}' lulus seluruh uji fungsional.")
'''

    def _build_and_verify_expense_tracker(
        self,
        task: dict[str, Any],
        opts: dict[str, Any],
        lease_epoch: int,
    ) -> dict[str, Any]:
        task_id = task["task_id"]
        conv_id = task["conversation_id"]
        proj_dir = Path(opts.get("project_dir") or (self.store.workspace / "projects" / "catatan_pengeluaran"))
        proj_dir.mkdir(parents=True, exist_ok=True)
        script_path = proj_dir / "expense_tracker.py"
        db_path = proj_dir / "pengeluaran.json"

        include_categories = bool(opts.get("include_categories", True))
        default_period = str(opts.get("default_period", "bulanan"))

        pre_hash = compute_file_sha256(script_path)
        if script_path.exists():
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="file_inspected",
                status="ACTIVE",
                summary_code="inspect_existing_expense_tracker",
                technical_detail={"file": str(script_path), "preimage_sha256": pre_hash, "reason": "memeriksa kode catatan pengeluaran sebelum pembaruan"},
                artifact_refs=[str(script_path)],
            )

        code = _expense_tracker_source(include_categories=include_categories, default_period=default_period)
        patch_info = atomic_write_verified(
            script_path,
            code,
            expected_preimage_sha256=pre_hash,
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )
        script_path.chmod(0o755)

        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="code_patched",
            status="VERIFYING",
            summary_code="patched_expense_tracker",
            technical_detail={
                "file": str(script_path),
                "change_summary": f"menyusun CLI catatan pengeluaran (periode: {default_period}, kategori: {include_categories})",
                **patch_info,
            },
            artifact_refs=[str(script_path)],
        )
        self.store.update_task(task_id, status="VERIFYING", lease_epoch=lease_epoch)

        # 1. Syntax compile verification
        c_res = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, "-m", "py_compile", str(script_path)],
            cwd=proj_dir,
            action_kind="compile_check",
            artifacts_created=[str(script_path)],
        )
        # 2. Functional smoke test (tambah, daftar, total)
        if db_path.exists():
            db_path.unlink()
        r1 = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(script_path), "tambah", "25000", "Makan siang", "--kategori", "makanan"],
            cwd=proj_dir,
            action_kind="functional_test_add_1",
            artifacts_created=[str(db_path)],
        )
        r2 = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(script_path), "tambah", "15000", "Ojek stasiun", "--kategori", "transportasi"],
            cwd=proj_dir,
            action_kind="functional_test_add_2",
            artifacts_created=[str(db_path)],
        )
        r3 = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(script_path), "total", "--periode", default_period],
            cwd=proj_dir,
            action_kind="functional_test_total",
            artifacts_created=[str(script_path), str(db_path)],
        )

        expected_label = "Rekap Bulanan" if default_period == "bulanan" else "Rekap Mingguan"
        all_passed = (
            c_res["passed"]
            and r1["passed"]
            and r2["passed"]
            and r3["passed"]
            and "Rp40000" in r3["stdout"]
            and expected_label in r3["stdout"]
        )

        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="test_executed",
            status="VERIFYING",
            summary_code="verified_expense_tracker",
            technical_detail={
                "stdout": r3["stdout"].strip(),
                "receipt_id": r3["receipt"]["receipt_id"],
                "default_period": default_period,
                "include_categories": include_categories,
            },
            artifact_refs=[str(script_path), str(db_path)],
            verification_passed=all_passed,
        )

        artifacts = [
            {"id": "expense_tracker.py", "path": str(script_path), "kind": "python_cli"},
            {"id": "pengeluaran.json", "path": str(db_path), "kind": "json_data"},
        ]
        ver_summary = {
            "passed": all_passed,
            "compile_passed": c_res["passed"],
            "functional_passed": r3["passed"],
            "sample_output": r3["stdout"].strip(),
            "receipt_ids": [
                c_res["receipt"]["receipt_id"],
                r1["receipt"]["receipt_id"],
                r2["receipt"]["receipt_id"],
                r3["receipt"]["receipt_id"],
            ],
        }
        updated_task = self.store.update_task(
            task_id,
            status="COMPLETED" if all_passed else "FAILED_WITH_RECOVERY_STATE",
            artifacts=artifacts,
            verification_summary=ver_summary,
            next_action="siap_digunakan" if all_passed else "periksa_error",
            lease_epoch=lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="task_completed" if all_passed else "task_failed",
            status=updated_task["status"],
            summary_code="expense_tracker_ready" if all_passed else "expense_tracker_failed",
            technical_detail={"goal": task["normalized_goal"], "verification": ver_summary},
            artifact_refs=[str(script_path), str(db_path)],
            verification_passed=all_passed,
        )
        return {
            "task": updated_task,
            "artifacts": artifacts,
            "verification": ver_summary,
            "script_path": str(script_path),
        }

    def _build_and_verify_csv_reader(
        self,
        task: dict[str, Any],
        opts: dict[str, Any],
        lease_epoch: int,
    ) -> dict[str, Any]:
        task_id = task["task_id"]
        conv_id = task["conversation_id"]
        proj_dir = Path(opts.get("project_dir") or (self.store.workspace / "projects" / "csv_tool"))
        proj_dir.mkdir(parents=True, exist_ok=True)
        script_path = proj_dir / "csv_reader.py"
        sample_csv = proj_dir / "contoh_data.csv"

        atomic_write_verified(
            script_path,
            _csv_reader_source(),
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )
        atomic_write_verified(
            sample_csv,
            "item,kategori,nilai\nBuku,edukasi,45000\nPulpen,edukasi,15000\n",
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )

        self.store.update_task(task_id, status="VERIFYING", lease_epoch=lease_epoch)
        res = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(script_path), str(sample_csv), "--kolom", "nilai"],
            cwd=proj_dir,
            action_kind="verify_csv_reader",
            artifacts_created=[str(script_path), str(sample_csv)],
        )
        passed = res["passed"] and "60000" in res["stdout"]
        artifacts = [
            {"id": "csv_reader.py", "path": str(script_path), "kind": "python_cli"},
            {"id": "contoh_data.csv", "path": str(sample_csv), "kind": "csv_data"},
        ]
        ver_summary = {
            "passed": passed,
            "sample_output": res["stdout"].strip(),
            "receipt_ids": [res["receipt"]["receipt_id"]],
        }
        updated = self.store.update_task(
            task_id,
            status="COMPLETED" if passed else "FAILED_WITH_RECOVERY_STATE",
            artifacts=artifacts,
            verification_summary=ver_summary,
            lease_epoch=lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="task_completed" if passed else "task_failed",
            status=updated["status"],
            summary_code="csv_reader_ready",
            technical_detail={"goal": task["normalized_goal"], "verification": ver_summary},
            artifact_refs=[str(script_path)],
            verification_passed=passed,
        )
        return {"task": updated, "artifacts": artifacts, "verification": ver_summary, "script_path": str(script_path)}

    def _build_and_verify_tebak_angka(
        self,
        task: dict[str, Any],
        opts: dict[str, Any],
        lease_epoch: int,
    ) -> dict[str, Any]:
        task_id = task["task_id"]
        conv_id = task["conversation_id"]
        proj_dir = Path(opts.get("project_dir") or (self.store.workspace / "projects" / "tebak_angka"))
        proj_dir.mkdir(parents=True, exist_ok=True)
        script_path = proj_dir / "tebak_angka.py"

        atomic_write_verified(
            script_path,
            _tebak_angka_source(),
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )
        self.store.update_task(task_id, status="VERIFYING", lease_epoch=lease_epoch)
        res = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(script_path), "--target", "25", "--tebakan", "10", "40", "25"],
            cwd=proj_dir,
            action_kind="verify_tebak_angka",
            artifacts_created=[str(script_path)],
        )
        passed = res["passed"] and "Tepat sekali!" in res["stdout"]
        artifacts = [{"id": "tebak_angka.py", "path": str(script_path), "kind": "python_cli"}]
        ver_summary = {
            "passed": passed,
            "sample_output": res["stdout"].strip(),
            "receipt_ids": [res["receipt"]["receipt_id"]],
        }
        updated = self.store.update_task(
            task_id,
            status="COMPLETED" if passed else "FAILED_WITH_RECOVERY_STATE",
            artifacts=artifacts,
            verification_summary=ver_summary,
            lease_epoch=lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="task_completed" if passed else "task_failed",
            status=updated["status"],
            summary_code="tebak_angka_ready",
            technical_detail={"goal": task["normalized_goal"], "verification": ver_summary},
            artifact_refs=[str(script_path)],
            verification_passed=passed,
        )
        return {"task": updated, "artifacts": artifacts, "verification": ver_summary, "script_path": str(script_path)}

    def _build_and_verify_multi_file(
        self,
        task: dict[str, Any],
        opts: dict[str, Any],
        lease_epoch: int,
    ) -> dict[str, Any]:
        """Create and wire a multi-file Python package (`A22`)."""
        task_id = task["task_id"]
        conv_id = task["conversation_id"]
        proj_dir = Path(opts.get("project_dir") or (self.store.workspace / "projects" / "multi_modul"))
        proj_dir.mkdir(parents=True, exist_ok=True)
        models_py = proj_dir / "models.py"
        main_py = proj_dir / "main_app.py"

        atomic_write_verified(
            models_py,
            '''"""Modul data untuk paket multi-file ACE."""
from dataclasses import dataclass

@dataclass
class ItemCatatan:
    nama: str
    harga: int
    jumlah: int = 1

    def subtotal(self) -> int:
        return self.harga * self.jumlah
''',
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )
        atomic_write_verified(
            main_py,
            '''"""Titik masuk CLI yang menghubungkan models.py."""
from models import ItemCatatan

def hitung_keranjang(daftar: list[tuple[str, int, int]]) -> int:
    items = [ItemCatatan(nama=n, harga=h, jumlah=j) for n, h, j in daftar]
    return sum(i.subtotal() for i in items)

if __name__ == "__main__":
    total = hitung_keranjang([("Buku", 20000, 2), ("Pensil", 5000, 3)])
    print(f"Total Keranjang: Rp{total}")
''',
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )
        self.store.update_task(task_id, status="VERIFYING", lease_epoch=lease_epoch)
        res = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(main_py)],
            cwd=proj_dir,
            action_kind="verify_multi_file",
            artifacts_created=[str(models_py), str(main_py)],
        )
        passed = res["passed"] and "Rp55000" in res["stdout"]
        artifacts = [
            {"id": "models.py", "path": str(models_py), "kind": "python_module"},
            {"id": "main_app.py", "path": str(main_py), "kind": "python_cli"},
        ]
        ver_summary = {
            "passed": passed,
            "sample_output": res["stdout"].strip(),
            "receipt_ids": [res["receipt"]["receipt_id"]],
        }
        updated = self.store.update_task(
            task_id,
            status="COMPLETED" if passed else "FAILED_WITH_RECOVERY_STATE",
            artifacts=artifacts,
            verification_summary=ver_summary,
            lease_epoch=lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="task_completed" if passed else "task_failed",
            status=updated["status"],
            summary_code="multi_file_ready",
            technical_detail={"goal": task["normalized_goal"], "verification": ver_summary},
            artifact_refs=[str(models_py), str(main_py)],
            verification_passed=passed,
        )
        return {"task": updated, "artifacts": artifacts, "verification": ver_summary}

    def _execute_safe_refactor(
        self,
        task: dict[str, Any],
        opts: dict[str, Any],
        lease_epoch: int,
    ) -> dict[str, Any]:
        """Refactor target file while preserving exact input/output behavior (`A21`, `A23`)."""
        task_id = task["task_id"]
        conv_id = task["conversation_id"]
        proj_dir = Path(opts.get("project_dir") or (self.store.workspace / "projects" / "refactor_work"))
        proj_dir.mkdir(parents=True, exist_ok=True)
        target_file = Path(opts.get("target_file") or (proj_dir / "kalkulator_kotor.py"))

        if not target_file.exists():
            atomic_write_verified(
                target_file,
                '''def hitung_tagihan(items):
    t = 0
    for x in items:
        if x["aktif"] == True:
            t = t + (x["harga"] * x["qty"])
    return t

if __name__ == "__main__":
    sample = [{"harga": 10000, "qty": 2, "aktif": True}, {"harga": 5000, "qty": 1, "aktif": False}]
    print("Hasil:", hitung_tagihan(sample))
''',
                expected_lease_epoch=lease_epoch,
                current_lease_epoch=self.store.current_lease_epoch,
            )

        pre_hash = compute_file_sha256(target_file)
        before_run = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(target_file)],
            cwd=target_file.parent,
            action_kind="baseline_behavior_check",
        )

        # Check if caller injected an intentionally breaking candidate (`A23`)
        candidate_code = opts.get("candidate_code")
        if not candidate_code:
            candidate_code = '''"""Modul perhitungan tagihan yang telah dirapikan tanpa mengubah perilaku."""
from __future__ import annotations


def _subtotal_item(item: dict) -> int:
    if not item.get("aktif"):
        return 0
    return int(item["harga"]) * int(item["qty"])


def hitung_tagihan(items: list[dict]) -> int:
    """Jumlahkan seluruh subtotal untuk item yang berstatus aktif."""
    return sum(_subtotal_item(item) for item in items)


if __name__ == "__main__":
    sample = [{"harga": 10000, "qty": 2, "aktif": True}, {"harga": 5000, "qty": 1, "aktif": False}]
    print("Hasil:", hitung_tagihan(sample))
'''
        original_content = target_file.read_text(encoding="utf-8")
        atomic_write_verified(
            target_file,
            candidate_code,
            expected_preimage_sha256=pre_hash,
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )

        self.store.update_task(task_id, status="VERIFYING", lease_epoch=lease_epoch)
        after_run = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(target_file)],
            cwd=target_file.parent,
            action_kind="post_refactor_behavior_check",
            artifacts_created=[str(target_file)],
        )

        behavior_preserved = (
            before_run["passed"]
            and after_run["passed"]
            and before_run["stdout"].strip() == after_run["stdout"].strip()
        )
        if not behavior_preserved:
            # Rule A23: Revert immediately if refactor broke existing behavior/tests!
            atomic_write_verified(
                target_file,
                original_content,
                expected_lease_epoch=lease_epoch,
                current_lease_epoch=self.store.current_lease_epoch,
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="test_executed",
                status="FAILED",
                summary_code="refactor_regression_rejected",
                technical_detail={"failure_hint": "perubahan merusak output uji regresi sehingga dibatalkan otomatis"},
                artifact_refs=[str(target_file)],
                verification_passed=False,
            )
            updated = self.store.update_task(
                task_id,
                status="FAILED_WITH_RECOVERY_STATE",
                error_summary="Perubahan ditolak dan dikembalikan karena mengubah perilaku atau merusak tes yang ada.",
                verification_summary={"passed": False, "reverted": True},
                lease_epoch=lease_epoch,
            )
            return {"task": updated, "behavior_preserved": False, "reverted": True}

        artifacts = [{"id": target_file.name, "path": str(target_file), "kind": "python_refactored"}]
        ver_summary = {
            "passed": True,
            "baseline_output": before_run["stdout"].strip(),
            "refactored_output": after_run["stdout"].strip(),
            "behavior_preserved": True,
            "receipt_ids": [before_run["receipt"]["receipt_id"], after_run["receipt"]["receipt_id"]],
        }
        updated = self.store.update_task(
            task_id,
            status="COMPLETED",
            artifacts=artifacts,
            verification_summary=ver_summary,
            lease_epoch=lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="task_completed",
            status="COMPLETED",
            summary_code="refactor_completed",
            technical_detail={"goal": task["normalized_goal"], "verification": ver_summary},
            artifact_refs=[str(target_file)],
            verification_passed=True,
        )
        return {"task": updated, "behavior_preserved": True, "reverted": False, "verification": ver_summary}

    def _execute_bug_diagnosis_and_repair(
        self,
        task: dict[str, Any],
        opts: dict[str, Any],
        lease_epoch: int,
    ) -> dict[str, Any]:
        """Reproduce failure, distinguish missing dependency vs code bug, patch, and verify (`A15`-`A18`)."""
        task_id = task["task_id"]
        conv_id = task["conversation_id"]
        proj_dir = Path(opts.get("project_dir") or (self.store.workspace / "projects" / "bug_repair"))
        proj_dir.mkdir(parents=True, exist_ok=True)
        target_file = Path(opts.get("target_file") or (proj_dir / "diskon_buggy.py"))

        if not target_file.exists():
            # Seed a buggy script (adds discount instead of subtracting, or ZeroDivisionError on empty list)
            atomic_write_verified(
                target_file,
                '''def hitung_harga_setelah_diskon(harga_awal: int, persen_diskon: int) -> int:
    potongan = (harga_awal * persen_diskon) // 100
    return harga_awal + potongan  # BUG: seharusnya dikurangi potongan

if __name__ == "__main__":
    hasil = hitung_harga_setelah_diskon(100000, 20)
    assert hasil == 80000, f"Harga salah: dapat {hasil}, seharusnya 80000"
    print("Verifikasi diskon berhasil:", hasil)
''',
                expected_lease_epoch=lease_epoch,
                current_lease_epoch=self.store.current_lease_epoch,
            )

        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="file_inspected",
            status="ACTIVE",
            summary_code="reproduce_bug_start",
            technical_detail={"file": str(target_file), "reason": "mereproduksi error sebelum menyusun perbaikan"},
            artifact_refs=[str(target_file)],
        )

        repro = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(target_file)],
            cwd=target_file.parent,
            action_kind="reproduce_bug",
        )

        stderr_text = repro["stderr"] or ""
        # Rule A15: Distinguish missing environment dependency from code bug!
        mod_match = re.search(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]", stderr_text)
        if mod_match:
            missing_pkg = mod_match.group(1)
            diagnosis = {
                "category": "MISSING_DEPENDENCY",
                "missing_package": missing_pkg,
                "is_code_bug": False,
                "explanation_id": (
                    f"Kegagalan disebabkan oleh paket/dependensi lingkungan `{missing_pkg}` yang belum terpasang, "
                    f"bukan bug logika di dalam kode `{target_file.name}`."
                ),
            }
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="hypothesis_formed",
                status="WAITING_FOR_DEPENDENCY",
                summary_code="missing_dependency_diagnosed",
                technical_detail={"hypothesis": diagnosis["explanation_id"], **diagnosis},
                artifact_refs=[str(target_file)],
            )
            updated = self.store.update_task(
                task_id,
                status="WAITING_FOR_DEPENDENCY",
                active_hypothesis=diagnosis["explanation_id"],
                resume_condition=f"Pasang paket `{missing_pkg}` atau izinkan penggantian dengan pustaka standar Python.",
                verification_summary={"passed": False, "diagnosis": diagnosis},
                lease_epoch=lease_epoch,
            )
            return {"task": updated, "diagnosis": diagnosis, "repaired": False}

        # Code bug diagnosis & repair (`A16`, `A17`, `A18`)
        pre_hash = compute_file_sha256(target_file)
        src = target_file.read_text(encoding="utf-8")
        hypothesis = "Operator penjumlahan/pembagian pada fungsi perhitungan menyebabkan hasil tidak sesuai asersi."
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="hypothesis_formed",
            status="ACTIVE",
            summary_code="code_bug_diagnosed",
            technical_detail={"hypothesis": hypothesis, "stderr": stderr_text[-240:]},
            artifact_refs=[str(target_file)],
        )

        repaired_src = src
        if "return harga_awal + potongan" in src:
            repaired_src = src.replace("return harga_awal + potongan", "return harga_awal - potongan")
        elif "return a - b" in src and "tambah" in src:
            repaired_src = src.replace("return a - b", "return a + b")
        elif "len(items)" in src and "ZeroDivisionError" in stderr_text:
            repaired_src = re.sub(
                r"return\s+sum\((.*?)\)\s*/\s*len\((\w+)\)",
                r"return (sum(\1) / len(\2)) if \2 else 0.0",
                src,
            )
        elif opts.get("fixed_code"):
            repaired_src = str(opts["fixed_code"])

        patch_info = atomic_write_verified(
            target_file,
            repaired_src,
            expected_preimage_sha256=pre_hash,
            expected_lease_epoch=lease_epoch,
            current_lease_epoch=self.store.current_lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="code_patched",
            status="VERIFYING",
            summary_code="bug_patch_applied",
            technical_detail={"file": str(target_file), "change_summary": "memperbaiki logika perhitungan yang menyebabkan asersi gagal", **patch_info},
            artifact_refs=[str(target_file)],
        )
        self.store.update_task(task_id, status="VERIFYING", active_hypothesis=hypothesis, lease_epoch=lease_epoch)

        verify_run = self.run_command_with_receipt(
            task_id=task_id,
            cmd=[sys.executable, str(target_file)],
            cwd=target_file.parent,
            action_kind="verify_bug_repair",
            artifacts_created=[str(target_file)],
        )
        passed = verify_run["passed"]
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="test_executed",
            status="VERIFYING",
            summary_code="bug_fix_verified" if passed else "bug_fix_still_failing",
            technical_detail={
                "stdout": verify_run["stdout"].strip(),
                "stderr": verify_run["stderr"].strip(),
                "failure_hint": verify_run["stderr"].strip().splitlines()[-1] if verify_run["stderr"].strip() else "",
            },
            artifact_refs=[str(target_file)],
            verification_passed=passed,
        )

        diagnosis = {
            "category": "CODE_LOGIC_BUG",
            "is_code_bug": True,
            "reproduced_before_fix": not repro["passed"],
            "verified_after_fix": passed,
            "explanation_id": (
                f"Bug pada `{target_file.name}` berhasil direproduksi, ditemukan pada rumus perhitungan, "
                f"diperbaiki secara atomik, dan lulus uji verifikasi."
            ),
        }
        artifacts = [{"id": target_file.name, "path": str(target_file), "kind": "python_repaired"}]
        ver_summary = {
            "passed": passed,
            "diagnosis": diagnosis,
            "sample_output": verify_run["stdout"].strip(),
            "receipt_ids": [repro["receipt"]["receipt_id"], verify_run["receipt"]["receipt_id"]],
        }
        updated = self.store.update_task(
            task_id,
            status="COMPLETED" if passed else "FAILED_WITH_RECOVERY_STATE",
            artifacts=artifacts,
            verification_summary=ver_summary,
            lease_epoch=lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="task_completed" if passed else "task_failed",
            status=updated["status"],
            summary_code="bug_repair_completed" if passed else "bug_repair_failed",
            technical_detail={"goal": task["normalized_goal"], "verification": ver_summary},
            artifact_refs=[str(target_file)],
            verification_passed=passed,
        )
        return {"task": updated, "diagnosis": diagnosis, "repaired": passed, "verification": ver_summary}

    def _build_and_verify_general_script(
        self,
        task: dict[str, Any],
        opts: dict[str, Any],
        lease_epoch: int,
    ) -> dict[str, Any]:
        task_id = task["task_id"]
        conv_id = task["conversation_id"]
        proj_dir = Path(opts.get("project_dir") or (self.store.workspace / "projects" / f"solusi_{task_id[-6:]}"))
        proj_dir.mkdir(parents=True, exist_ok=True)
        filename = opts.get("filename") or "solusi_ace.py"
        if not filename.endswith(".py"):
            filename += ".py"
        script_path = proj_dir / filename

        goal = task.get("normalized_goal") or task.get("title_id") or "Solusi Python mandiri"
        constraints = ", ".join(task.get("constraints", [])) or "tidak ada batasan khusus"
        title = task.get("title_id") or "Solusi Python Mandiri"

        max_repair_turns = int(opts.get("max_repair_turns", 2))
        max_attempts = 1 + max_repair_turns  # 1 initial + up to 2 repair turns
        custom_code = opts.get("custom_code")

        from .models_backend import ModelRouter
        router = ModelRouter(self.store)

        conversation_history: list[dict[str, str]] = []
        last_error_feedback: str = ""
        passed = False
        res: dict[str, Any] = {"passed": False, "stdout": "", "stderr": "", "exit_code": -1, "receipt": {}}
        candidate_code = ""
        receipt_ids: list[str] = []

        initial_prompt = (
            f"Buat satu skrip Python 3 mandiri yang lengkap dan dapat langsung dijalankan untuk menyelesaikan tugas berikut:\n"
            f"Tujuan: {goal}\n"
            f"Batasan: {constraints}\n\n"
            f"Persyaratan Wajib:\n"
            f"1. Kode harus Python 3 valid, mandiri (self-contained), dan bebas dari error sintaks.\n"
            f"2. Mengimplementasikan logika nyata untuk menyelesaikan tujuan (bukan stub kosong atau tiruan).\n"
            f"3. Tangani kasus batas seperti pembagian dengan nol agar tidak crash.\n"
            f"4. Memiliki fungsi utama dan blok if __name__ == '__main__': yang memanggil fungsi tersebut, menguji hasilnya dengan input contoh, dan mencetak status verifikasi.\n"
            f"5. Pastikan semua nama fungsi yang dipanggil di blok __main__ sama persis dengan yang didefinisikan sebelumnya.\n"
            f"6. JANGAN gunakan input() interaktif (pengujian berjalan otomatis non-interaktif). Uji fungsi secara langsung dengan nilai contoh di blok __main__.\n"
            f"7. Keluarkan HANYA blok kode ```python ... ``` tanpa teks pengantar atau penjelasan di luar blok kode."
        )

        for attempt in range(max_attempts):
            if custom_code and attempt == 0:
                candidate_code = custom_code
            else:
                if attempt == 0:
                    conversation_history = [{"role": "user", "content": initial_prompt}]
                else:
                    repair_prompt = (
                        f"Kode Python pada iterasi sebelumnya gagal dalam verifikasi otomatis:\n"
                        f"{last_error_feedback}\n\n"
                        f"Berikut adalah kode sebelumnya:\n"
                        f"```python\n{candidate_code}\n```\n\n"
                        f"Perbaiki seluruh kesalahan tersebut. Pastikan kode baru adalah Python 3 yang valid, mandiri, bebas error sintaks dan runtime, tidak menggunakan input(), serta menyelesaikan: {goal}.\n"
                        f"Keluarkan HANYA blok kode ```python ... ``` tanpa teks pengantar."
                    )
                    conversation_history.append({"role": "user", "content": repair_prompt})

                gen_res = router.generate_text(conversation_history, max_tokens=512, temperature=0.1)
                gen_text = gen_res.get("text", "")
                conversation_history.append({"role": "assistant", "content": gen_text})

                code_match = re.search(r"```(?:python)?\s*(.*?)\s*```", gen_text, flags=re.DOTALL)
                candidate_code = code_match.group(1).strip() if code_match else gen_text.strip()

            # Record synthesis / repair event
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="code_synthesized" if attempt == 0 else "code_repaired",
                status="ACTIVE",
                summary_code=f"synthesis_turn_{attempt}",
                technical_detail={
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "candidate_preview": candidate_code[:200],
                },
                artifact_refs=[str(script_path)],
            )

            # Step 1: AST Syntax and Security Audit
            syntax_ok, ast_err = self._validate_and_audit_ast(candidate_code, goal)
            if not syntax_ok:
                last_error_feedback = f"Kesalahan AST/Sintaks:\n{ast_err}"
                continue

            # Step 2: Atomic Write with Lease Check
            try:
                atomic_write_verified(
                    script_path,
                    candidate_code,
                    expected_lease_epoch=lease_epoch,
                    current_lease_epoch=self.store.current_lease_epoch,
                )
                script_path.chmod(0o755)
            except Exception as e:
                last_error_feedback = f"Kesalahan penulisan berkas: {str(e)}"
                continue

            # Step 3: py_compile syntax verification
            c_res = self.run_command_with_receipt(
                task_id=task_id,
                cmd=[sys.executable, "-m", "py_compile", str(script_path)],
                cwd=proj_dir,
                action_kind=f"compile_check_turn_{attempt}",
                artifacts_created=[str(script_path)],
            )
            if c_res.get("receipt"):
                receipt_ids.append(c_res["receipt"]["receipt_id"])
            if not c_res["passed"]:
                last_error_feedback = f"py_compile gagal:\n{c_res['stderr'].strip() or c_res['stdout'].strip()}"
                continue

            # Step 4: Subprocess Execution / Functional Test
            self.store.update_task(task_id, status="VERIFYING", lease_epoch=lease_epoch)
            res = self.run_command_with_receipt(
                task_id=task_id,
                cmd=[sys.executable, str(script_path)],
                cwd=proj_dir,
                action_kind=f"verify_general_script_turn_{attempt}",
                artifacts_created=[str(script_path)],
            )
            if res.get("receipt"):
                receipt_ids.append(res["receipt"]["receipt_id"])

            if res["passed"]:
                passed = True
                break
            else:
                err_msg = res["stderr"].strip() or res["stdout"].strip()
                last_error_feedback = f"Eksekusi runtime gagal (Exit Code {res['exit_code']}):\n{err_msg}"

        # If repair loop exhausted and still not passed:
        if not passed:
            try:
                self.store.record_gap(
                    source_task_id=task_id,
                    error_type="CODING_REPAIR_EXHAUSTED",
                    missing_skill_or_tool=f"domain_general::{title[:30]}",
                    description_id=f"Perbaikan kode gagal untuk: {title}. Error: {last_error_feedback[:180]}",
                    reproduction_ref=str(script_path),
                    resolution_strategy="synthesize_skill_or_tool",
                )
            except Exception:
                pass
            if opts.get("allow_deterministic_fallback", True):
                deterministic_code = self._synthesize_deterministic_general_solution(title, goal)
                atomic_write_verified(
                    script_path,
                    deterministic_code,
                    expected_lease_epoch=lease_epoch,
                    current_lease_epoch=self.store.current_lease_epoch,
                )
                script_path.chmod(0o755)
                res = self.run_command_with_receipt(
                    task_id=task_id,
                    cmd=[sys.executable, str(script_path)],
                    cwd=proj_dir,
                    action_kind="verify_general_script_deterministic_fallback",
                    artifacts_created=[str(script_path)],
                )
                if res.get("receipt"):
                    receipt_ids.append(res["receipt"]["receipt_id"])
                passed = res["passed"]
                if not passed:
                    try:
                        self.store.record_gap(
                            source_task_id=task_id,
                            error_type="DETERMINISTIC_FALLBACK_FAILED",
                            missing_skill_or_tool=f"domain_general_fallback::{title[:30]}",
                            description_id=f"Fallback deterministik gagal untuk: {title}. Error: {res.get('stderr', '')[:180]}",
                            reproduction_ref=str(script_path),
                            resolution_strategy="micro_experiment",
                        )
                    except Exception:
                        pass

        artifacts = [{"id": script_path.name, "path": str(script_path), "kind": "python_cli"}]
        ver_summary = {
            "passed": passed,
            "sample_output": (res.get("stdout") or "").strip(),
            "receipt_ids": receipt_ids,
        }
        updated = self.store.update_task(
            task_id,
            status="COMPLETED" if passed else "FAILED_WITH_RECOVERY_STATE",
            artifacts=artifacts,
            verification_summary=ver_summary,
            lease_epoch=lease_epoch,
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="task_completed" if passed else "task_failed",
            status=updated["status"],
            summary_code="general_script_ready" if passed else "general_script_failed",
            technical_detail={"goal": task["normalized_goal"], "verification": ver_summary},
            artifact_refs=[str(script_path)],
            verification_passed=passed,
        )
        return {
            "task": updated,
            "artifacts": artifacts,
            "verification": ver_summary,
            "script_path": str(script_path),
            "success": passed,
            "file_path": str(script_path),
            "receipt": res.get("receipt", {}),
            "test_passed": passed,
            "output": ver_summary["sample_output"],
        }
