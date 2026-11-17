# Inventaris Sapuan State Lokal ACE — 15 November 2026

Aturan tetap pemilik (15 Nov 2026, 21:06 WIB): **GitHub =
ingatan persisten ACE.** Tidak ada hasil belajar/ingatan ACE
yang dihitung "tercatat" selama hanya ada di disk lokal (VM
atau sandbox) — semuanya harus berakhir ter-push ke GitHub
(branch/draft PR, tanpa merge). Sapuan ini adalah penerapan
pertama aturan itu atas artefak mirip-ingatan yang saat itu
hanya hidup di disk lokal Ian.

## A. Ter-push di branch ini (`handover/local_state_sweep_20261115/`)

| Isi | Asal lokal | Isi ringkas |
| :--- | :--- | :--- |
| `run-confirm-prep/` | `~/workspace/run-confirm-prep/` (VM) | Lembar larian konfirmasi lineage-guard (RUN_SHEET) + draf akta final ACT_CONFIRM_DRAFT |
| `misi9/` | `~/workspace/misi9-args/` (VM) | Laporan Misi 9 (audit main baru), keluaran re-gate di main baru, catatan inventaris |
| `misi10/` | `~/workspace/misi10-args/` (VM) | Berkas discovery + catatan re-baseline band 20261801–20261805, verifikasi digest, skrip driver discovery |
| `stack-intake/` | `~/workspace/stack-intake/` (VM) | Rekaman intake model tumpukan 15 Nov (2 berkas terunduh terverifikasi hash, terparkir; coder tidak diunduh) |
| `g5-kernel/` | `~/workspace/ace-omega/g5-harvest-kernel/` (VM) | Rekaman kernel praregistrasi panen G5 (`g5-harvest-01.json`) + `results.jsonl` — sebelumnya di luar repo BY DESIGN; salinannya kini di GitHub sesuai aturan |
| `custody-prep/` | `~/workspace/` (VM) | Skrip persiapan kustodi Q1 (verifikasi populasi + pemasangan suplemen/band) |
| `study-ace-77cca3c.md` | `~/workspace/` (VM) | Kajian mesin ACE di main 77cca3c oleh hub (orkestrator) |

Catatan: salinan berkas discovery/re-baseline 20261801–20261804
juga ada di paket PR #226; salinan 20261805 di sapuan ini
adalah salinan GitHub pertamanya (paket bukti larian Q1 akan
membawanya lagi secara resmi).

## B. Sudah di GitHub (tidak perlu disapu)

- Seluruh paket bukti PR #189–#199, #224–#228 (draf, menunggu
  review hub).
- `.ace_evolution/user_missions/` versi repo (misi 0001,
  0001b, 0002 + ratified) — konten tracked di `main`.
- Catatan akses rumah ACE: branch
  `docs/ace-home-access-note-20261115` (PR menyusul jalur hub).

## C. Terdaftar saja (belum ter-push, dengan alasan)

| Item | Lokasi | Alasan / jalur resmi |
| :--- | :--- | :--- |
| State larian kustodi (`evidence/lineage_guard_state/`, `lineage_guard_run.json`) | Sandbox, `/workspace/ace-custody-lineage-guard/` | Dihasilkan oleh larian Q1; mendarat sebagai paket bukti resmi larian (draft PR) begitu larian selesai — menyapunya sekarang akan membelah paket tersegel |
| State runtime `.ace_evolution` (jurnal & state siklus evolusi lini Antigravity) | Sandbox, workspace lini Antigravity | Diinventarisasi & diklasifikasikan oleh AUDIT PENYERAPAN BELAJAR (antrian sesudah Q1); tabel + artefaknya mendarat di GitHub lewat audit itu |
| Log mentah discovery (VM) | `~/workspace/misi10-args/*.log` | Kecil dan turunan; digest + catatan terverifikasinya ter-push di bagian A |
| Berkas model GGUF terparkir (2 berkas, ±3,4 GB) | Sandbox, `/workspace/ace-omega/models/` | Biner model bukan artefak ingatan; rekaman intake + hash-nya ter-push di bagian A |
| LEDGER_PENGHASILAN + foto SLIK UTANG AWAL | VM, `handover/` lokal | Data keuangan pribadi pemilik — tetap tidak ter-push (pengecualian nilai sensitif yang sudah lama berlaku) |

— Sapuan oleh Ian (sesi eksekusi utama), 15 November 2026.
