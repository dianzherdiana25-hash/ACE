#!/usr/bin/env python3
"""
ACE Auto-Curriculum Runner
-------------------------
Membangun dan mengeksekusi kurikulum evolusioner otomatis untuk ACE.
Menghasilkan tantangan bertingkat (level) untuk menguji sintesis model,
pewarisan kapabilitas (inheritance reuse), dan adaptasi modular.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

# Pastikan path kode ACE tersedia
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "code"))

from ace_runtime.engine import Runtime
from ace_capability_evolution.compositional import bank, TASKS

CURRICULUM = [
    # Level 1: Pengenalan Dasar (Equality & Balance)
    {"id": "L1_equal_base", "task": "equal", "seed": 20261101, "desc": "Pola dasar: jumlah 'a' sama dengan jumlah 'b'"},
    {"id": "L1_equal_transfer", "task": "equal", "seed": 20261102, "desc": "Uji pewarisan (reuse) kapabilitas L1 pada data baru"},
    
    # Level 2: Modular Boundary Guards (Prefix & Suffix constraints)
    {"id": "L2_starts_guard", "task": "starts", "seed": 20261101, "desc": "Equal counts + harus diawali dengan 'a'"},
    {"id": "L2_ends_guard", "task": "ends", "seed": 20261101, "desc": "Equal counts + harus diakhiri dengan 'b'"},
    {"id": "L2_boundaries_guard", "task": "boundaries", "seed": 20261101, "desc": "Equal counts + diawali 'a' DAN diakhiri 'b'"},
    
    # Level 3: Substring Constraints
    {"id": "L3_contains_guard", "task": "contains", "seed": 20261101, "desc": "Equal counts + harus mengandung substring 'ab'"},
    {"id": "L3_contains_transfer", "task": "contains", "seed": 20261102, "desc": "Uji transfer kapabilitas L3"},

    # Level 4: Ratio Scaling (Aritmatika lebih tinggi)
    {"id": "L4_ratio2_boundaries", "task": "ratio2_boundaries", "seed": 20261101, "desc": "Rasio 2:1 ('a' = 2x 'b') dengan boundary guards"},
]


def print_banner():
    print("\n" + "=" * 65)
    print("   🧬 ACE AUTONOMOUS CAPABILITY EVOLUTION — AUTO CURRICULUM")
    print("=" * 65)


def show_status(runtime: Runtime):
    status = runtime.status()
    print("\n📊 [Status Evolusi ACE]")
    print(f" • Total Kapabilitas Tersimpan : {status['capabilities']}")
    print(f" • Tugas Selesai              : {status['completed']}")
    print(f" • Tugas Gagal                : {status['failed']}")
    print(f" • Evaluasi Terminal          : {status['evaluations']}")
    print(f" • Log Kejadian (Audit Events): {status['events']}")
    
    if status["tasks"]:
        print("\n📜 [Riwayat Tugas Selesai]")
        for t in status["tasks"]:
            phase_icon = "🔁 [REUSED]" if t["phase"] == "REUSE_VALIDATED" else "✨ [LEARNED]" if t["phase"] == "LEARNED_STAGED" else "⚠️ [LIMIT] "
            m_id = (t.get("model_id") or "None")[:8]
            print(f" • {t['name']:<24} | {phase_icon} {t['phase']:<18} | Model: {m_id}")
    print("-" * 65)


def run_curriculum(runtime: Runtime, max_steps: int = 10, delay: float = 0.5):
    status = runtime.status()
    completed_names = {t["name"] for t in status.get("tasks", [])}
    
    pending_levels = [lvl for lvl in CURRICULUM if lvl["id"] not in completed_names]
    
    if not pending_levels:
        print("\n🎉 Semua level kurikulum telah diselesaikan oleh ACE!")
        show_status(runtime)
        return

    print(f"\n🚀 Memulai kurikulum: {len(pending_levels)} level menunggu...")
    
    steps = 0
    for lvl in pending_levels:
        if steps >= max_steps:
            print(f"\n⏱️ Mencapai batas maksimum langkah ({max_steps}). Berhenti sementara.")
            break
            
        print(f"\n▶ [{lvl['id']}] {lvl['desc']}")
        print(f"   Menghasilkan dataset untuk: '{lvl['task']}' (seed={lvl['seed']})...")
        
        train, validation, terminal = bank(lvl["task"], lvl["seed"])
        task_payload = {
            "name": lvl["id"],
            "train": train,
            "validation": validation,
        }
        
        task_id = runtime.enqueue(task_payload)
        print(f"   ↳ Enqueued Task ID: {task_id[:12]}...")
        
        print("   ↳ Menjalankan siklus evolusi model...")
        outcomes = runtime.run(max_tasks=1)
        
        if outcomes:
            outcome = outcomes[0]
            phase = outcome.get("phase", "UNKNOWN")
            raw_model_id = outcome.get("model_id")
            model_id = raw_model_id[:8] if raw_model_id else "None"
            
            if phase == "REUSE_VALIDATED":
                print(f"   ✅ SUCCESS [REUSE_VALIDATED]: Kapabilitas berhasil diwariskan dari model {model_id}!")
            elif phase == "LEARNED_STAGED":
                print(f"   ✨ SUCCESS [LEARNED_STAGED]: Model baru berhasil dipelajari & disimpan (Model {model_id})!")
            elif phase == "NO_VALIDATED_MODEL":
                print(f"   ⚠️ BATAS KEMAMPUAN [NO_VALIDATED_MODEL]: ACE belum menemukan program yang 100% lolos validasi.")
                fit_report = outcome.get("fit_report") or {}
                arms = fit_report.get("arms", {})
                for arm_name, arm_val in arms.items():
                    print(f"      • Arm '{arm_name}': train {arm_val.get('train_correct')}/{lvl['task']}, val {arm_val.get('validation_correct')}/128")
            else:
                print(f"   ℹ️ STATUS [{phase}]: Model: {model_id}")
            
            # Evaluasi terminal jika model berhasil di-stage
            if outcome.get("staged"):
                eval_res = runtime.evaluate(task_id, terminal)
                correct = eval_res.get("correct", 0)
                total = eval_res.get("total", 0)
                print(f"   🎯 Evaluasi Terminal Independen: {correct}/{total} akurat ({(correct/total)*100:.1f}%)")
        else:
            print("   ⚠️ Tidak ada hasil atau tugas gagal diselesaikan.")
            
        steps += 1
        time.sleep(delay)

    print("\n" + "=" * 65)
    print("🏁 Sesi Kurikulum Selesai!")
    show_status(runtime)


def main():
    parser = argparse.ArgumentParser(description="ACE Auto-Curriculum Runner")
    parser.add_argument("--workspace", default=str(ROOT_DIR / "ace-work"),
                        help="Path ke workspace ACE (default: ./ace-work)")
    parser.add_argument("--steps", type=int, default=10,
                        help="Jumlah level maksimal yang dijalankan sesi ini")
    parser.add_argument("--status", action="store_true",
                        help="Hanya tampilkan status evolusi tanpa menjalankan tugas")
    
    args = parser.parse_args()
    print_banner()
    
    workspace = Path(args.workspace).resolve()
    print(f"📁 Workspace: {workspace}")
    runtime = Runtime(workspace)
    
    if args.status:
        show_status(runtime)
    else:
        run_curriculum(runtime, max_steps=args.steps)


if __name__ == "__main__":
    main()
