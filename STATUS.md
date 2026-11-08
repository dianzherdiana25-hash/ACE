# ACE Status — 8 November 2026

Dokumen ini adalah **satu-satunya sumber kebenaran (Single Source of Truth)** untuk status operasional, arsitektur, dan capaian ilmiah repositori ACE (`dianzherdiana25-hash/ACE`). Dokumen ini diperbarui secara berkelanjutan pada setiap tahapan kerja.

---

## 1. Metadata Repositori & Cabang
- **Tanggal Status:** 8 November 2026
- **Base Commit `main`:** `80104ce` (6 November 2026)
- **Cabang Integrasi Aktif:** `integration/ace-consolidated-20261108`
- **Cabang Arsip Data & Evidence:** `origin/ace-data` (519 berkas `.json.gz` dan `cycle_*.json` dipisahkan dari cabang kode)
- **PR Terbuka:**
  - PR #89: Autonomous Software-Development Researcher Bootstrap V0.3
  - PR #90: [ACE Autonomous Research PR #90](https://github.com/dianzherdiana25-hash/ACE/pull/90) (Dibuat otomatis oleh runtime ACE)

---

## 2. Kondisi Komponen Saat Ini

| Komponen | Status Operasional | Status Ilmiah | Bukti / Catatan |
| :--- | :--- | :--- | :--- |
| **Pembelajar Inti** (`ace_runtime`, `ace_candidate_search`, `ace_capability_evolution`, `ace_research_primitives`) | Aktif & Lulus Tes | `NOT_ASSESSED` | Byte-identik dengan `main` (`80104ce`). Memiliki 4 bug batas terbukti (lihat Bagian 3). |
| **Perancah & Autonomi** (`ace_autonomy`, `ace_host_controller`, `ace_loop`) | Aktif & Teruji | `OPERATIONAL_PROTOTYPE` | Autonomi berlease, isolasi host, dan escrow lulus pengujian unittest (25/25 `verify_sources`). |
| **Studi Riset F12–F14, R9** | Lengkap di Cabang Integrasi | Hasil Negatif Sah Tercatat | Bukti terkompresi dan prescore tercatat; H1 & H2 cross-family ditolak (0/16 fit). |
| **Loop Self-Dev Historis** | Dipindahkan ke `ace-data` | 252 `REJECTED`, 1 `STAGNATED`, 0 `ACCEPTED` | Siklus 1–253 diarsipkan di `origin/ace-data`; tidak lagi mengotori riwayat git kode. |
| **Code Agent V0.4** | Operasional Mandiri | `NOT_ASSESSED` | Menghasilkan patch AST dinamis, menguji di worktree terisolasi, membuka PR #90 (11/11 CI pass). |
| **Mission Bus (W1)** | Aktif & Teruji (5/5 tes lulus) | `OPERATIONAL_PROTOTYPE` | Skema `ace.mission.v1`, SQLite hash chain, CLI (`next`, `submit`, `status`, `generate`), anti-idle, dan eskalasi penjenuhan selesai. |
| **Penilai Tersegel (W2)** | Dalam Implementasi | - | Mengganti bank literal 8 baris dengan generator keluarga tugas bersegel parameter. |

---

## 3. Bug Batas Terbukti & Daftar Masalah (Akan Diperbaiki di W3)
1. **Seleksi Overfit & Mengutamakan Validasi:** Model yang gagal admission terpilih karena prioritas validasi; 1 label salah dapat menolak seluruh tugas.
2. **Guard Overfit:** Guard "mengandung aa" mencapai 63/63 pada data latih namun turun ke 88/128 pada validasi.
3. **Deteksi Drift Lemah:** Late-flip dan drift tersembunyi diterima salah (10/10 pada G2, 2/2 pada studi perbandingan).
4. **Bank Evaluator Terbuka:** Bank "privat" 8 baris per tugas tertulis literal di kode; tabel hafalan lolos 8/8.
5. **Ketiadaan Jalur Keluar Misi:** Loop daemon mengulang hipotesis yang sama hingga jenuh lalu tidur tanpa eskalasi.

---

## 4. Angka-Angka Terakhir yang Sah
- `verify_sources.py`: **25/25 PASS** (offline blob integrity).
- Pengujian Unit Lokal: **6/6 PASS** pada `code/ace_code_agent/test_operational_proof.py`.
- Matrix CI PR #90: **11/11 PASS** (termasuk Python 3.12 & 3.13 pada regressions, research, evidence, reptransfer).
- Cross-Family Transfer: Menghemat **0 dari 16** fit (H1 & H2 ditolak, hasil negatif sah).
- Graph Family Transfer: ACE sumber **50%–58%** vs Library BFS Manusia **100%**.
- Generasi G0 ke G2: Skor publik 0,511 → 0,688 → 0,963 (`NOT_ASSESSED`; drift tersembunyi 10/10 diterima salah).

---

## 5. Tata Kelola & Batasan Keras (Hard Invariants)
- **Biaya Keuangan:** **$0.00 / Rp0** (hanya komputasi CPU lokal / GitHub Actions standar).
- **Invarian Rilis:** `release_gate=BLOCK_RELEASE`, `scientific_status=NOT_ASSESSED`, `oaie_established=False`.
- **Integritas Penilai:** Dilarang mengedit penilai/bank untuk meloloskan kandidat; dilarang merge ke `main` tanpa komentar `APPROVE-MERGE` dari pemilik repositori.
- **Identitas Agen:** Kode atau usulan dari Antigravity dicatat dengan provenance `ADVISOR_AGENT` (sesuai PRD FR-12).
