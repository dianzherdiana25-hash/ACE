"""Harness uji kekacauan (chaos-kill) untuk memverifikasi kelanjutan checkpoint AG74 (AG75).

Menjalankan urutan langkah deterministik di proses anak terisolasi dengan
penyimpanan checkpoint berantai hash:
1. Lari utuh (baseline) dari awal hingga akhir;
2. Lari terputus dengan membunuh proses anak (``SIGKILL``) pada titik injeksi
   tertentu lalu melanjutkannya di proses anak baru dari checkpoint terakhir;
3. Membandingkan state akhir hasil lanjut terhadap lari utuh — wajib identik.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence


SCHEMA = "ace.chaos-kill-harness.v1"

_CODE_DIR = str(Path(__file__).resolve().parents[1] / "code")
if _CODE_DIR not in sys.path:
    sys.path.insert(0, _CODE_DIR)

try:
    from ace_operational.step_checkpoint import (
        load_latest_checkpoint,
        save_step_checkpoint,
    )

    USING_STEP_CHECKPOINT_MODULE = True
except ImportError:
    USING_STEP_CHECKPOINT_MODULE = False

    def _canonical(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _ckpt_hash(seq: int, prev: str, step_id: str, state: Any) -> str:
        raw = _canonical({"seq": seq, "prev": prev, "step_id": step_id, "state": state}).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def load_latest_checkpoint(path: Path) -> dict[str, Any] | None:
        target = Path(path)
        if not target.exists():
            return None
        prev = "GENESIS"
        last = None
        for expected_seq, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
            obj = json.loads(line)
            if obj["seq"] != expected_seq or obj["prev"] != prev:
                raise ValueError("Urutan checkpoint rusak")
            if obj["hash"] != _ckpt_hash(obj["seq"], obj["prev"], obj["step_id"], obj["state"]):
                raise ValueError("Hash checkpoint tidak cocok")
            prev = obj["hash"]
            last = obj
        return last

    def save_step_checkpoint(path: Path, *, step_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
        target = Path(path)
        entries: list[dict[str, Any]] = []
        prev = "GENESIS"
        if target.exists():
            for expected_seq, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
                obj = json.loads(line)
                if obj["seq"] != expected_seq or obj["prev"] != prev:
                    raise ValueError("Urutan checkpoint rusak")
                if obj["hash"] != _ckpt_hash(obj["seq"], obj["prev"], obj["step_id"], obj["state"]):
                    raise ValueError("Hash checkpoint tidak cocok")
                prev = obj["hash"]
                entries.append(obj)
        seq = len(entries) + 1
        clean_state = json.loads(_canonical(dict(state)))
        digest = _ckpt_hash(seq, prev, step_id, clean_state)
        entry = {
            "schema": "ace.step-checkpoint.v1",
            "seq": seq,
            "prev": prev,
            "step_id": step_id,
            "state": clean_state,
            "hash": digest,
        }
        entries.append(entry)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / f".{target.name}.tmp"
        with tmp.open("w", encoding="utf-8") as fh:
            for item in entries:
                fh.write(_canonical(item) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        return entry


def _run_toy_worker(ckpt_path: Path, state_out: Path, total_steps: int, kill_after: int | None) -> int:
    latest = load_latest_checkpoint(ckpt_path)
    if latest is None:
        state: dict[str, Any] = {"step": 0, "accumulator": 0, "history": []}
    else:
        state = dict(latest["state"])

    start_step = int(state["step"]) + 1
    for step_idx in range(start_step, total_steps + 1):
        new_acc = int(state["accumulator"]) + (step_idx * 17)
        new_hist = list(state["history"]) + [f"op-{step_idx}:{new_acc}"]
        state = {"step": step_idx, "accumulator": new_acc, "history": new_hist}
        save_step_checkpoint(ckpt_path, step_id=f"step-{step_idx}", state=state)
        if kill_after is not None and step_idx == kill_after:
            # Simulasikan penghentian mendadak (SIGKILL) tepat setelah checkpoint step ini.
            os.kill(os.getpid(), signal.SIGKILL)

    state["digest"] = hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    state_out.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


def _spawn_worker(
    ckpt_path: Path,
    state_out: Path,
    total_steps: int,
    *,
    kill_after: int | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--_worker",
        "--ckpt",
        str(ckpt_path),
        "--state-out",
        str(state_out),
        "--steps",
        str(total_steps),
    ]
    if kill_after is not None:
        cmd.extend(["--kill-after", str(kill_after)])
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": f"{Path(__file__).resolve().parents[1]}:{_CODE_DIR}"}
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=15)


def run_chaos_kill_experiment(
    kill_points: Sequence[int] = (2, 4),
    *,
    total_steps: int = 6,
) -> dict[str, Any]:
    """Jalankan baseline utuh dan eksperimen bunuh+lanjut di setiap titik bunuh."""
    if total_steps < 2:
        raise ValueError("total_steps minimal 2.")
    for kp in kill_points:
        if not 1 <= int(kp) < total_steps:
            raise ValueError(f"Titik bunuh tidak sah {kp!r}; harus dalam [1, {total_steps - 1}].")

    with TemporaryDirectory(prefix="ace_chaos_kill_") as tmp:
        root = Path(tmp)
        base_ckpt = root / "baseline.ckpt.jsonl"
        base_state_path = root / "baseline_final.json"
        base_proc = _spawn_worker(base_ckpt, base_state_path, total_steps)
        if base_proc.returncode != 0:
            raise RuntimeError(f"Baseline worker gagal: {base_proc.stderr}")
        baseline_state = json.loads(base_state_path.read_text(encoding="utf-8"))

        scenarios: list[dict[str, Any]] = []
        all_identical = True

        for idx, kp in enumerate(kill_points, 1):
            ckpt = root / f"chaos_{idx}.ckpt.jsonl"
            final_state_path = root / f"chaos_{idx}_final.json"

            kill_proc = _spawn_worker(ckpt, final_state_path, total_steps, kill_after=kp)
            killed_by_signal = kill_proc.returncode != 0 and not final_state_path.exists()
            mid_ckpt = load_latest_checkpoint(ckpt)
            mid_step = int(mid_ckpt["state"]["step"]) if mid_ckpt else 0

            resume_proc = _spawn_worker(ckpt, final_state_path, total_steps)
            if resume_proc.returncode != 0 or not final_state_path.exists():
                raise RuntimeError(f"Resume worker gagal setelah kill@{kp}: {resume_proc.stderr}")
            resumed_state = json.loads(final_state_path.read_text(encoding="utf-8"))

            matches = resumed_state == baseline_state
            if not matches or not killed_by_signal or mid_step != kp:
                all_identical = False

            scenarios.append(
                {
                    "kill_after_step": kp,
                    "child_killed_before_completion": killed_by_signal,
                    "kill_returncode": kill_proc.returncode,
                    "resumed_from_checkpoint_step": mid_step,
                    "matches_unbroken_baseline": matches,
                    "baseline_digest": baseline_state["digest"],
                    "resumed_digest": resumed_state["digest"],
                }
            )

    return {
        "schema": SCHEMA,
        "using_step_checkpoint_module": USING_STEP_CHECKPOINT_MODULE,
        "total_steps": total_steps,
        "all_identical": all_identical,
        "baseline_final_state": baseline_state,
        "scenarios": scenarios,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Harness chaos-kill untuk menguji pemulihan state identik via step_checkpoint."
    )
    parser.add_argument("--steps", type=int, default=6)
    parser.add_argument("--kill-at", default="2,4", help="Daftar titik bunuh terpisah koma (mis. 2,4).")
    parser.add_argument("--out", help="Path output laporan JSON opsional.")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ckpt", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--state-out", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--kill-after", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args._worker:
        return _run_toy_worker(args.ckpt, args.state_out, args.steps, args.kill_after)

    try:
        kill_points = [int(x.strip()) for x in args.kill_at.split(",") if x.strip()]
        report = run_chaos_kill_experiment(kill_points, total_steps=args.steps)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["all_identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
