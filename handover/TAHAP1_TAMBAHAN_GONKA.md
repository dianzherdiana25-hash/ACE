# TAHAP 1 — TAMBAHAN ORGAN GONKA (director-strong ketiga)

*Pendaratan registry atas organ yang dihidupkan dan diverifikasi hub
(ila), 18 Nov 2026 — sesudah gerbang Tahap 1 teratifikasi tertutup.
PR ini bertumpuk di atas PR #307.*

## Fakta terverifikasi hub

- Connector `custom.gonka` terhubung (kunci pemilik di Secure Vault,
  nama kunci ace-director); helper hub
  `custom-connectors/custom.gonka/bin/gonka_call.py`, pola sama
  dengan groq_call (models / chat / chatfile).
- Panggilan models berhasil: 4 model — `deepseek-ai/DeepSeek-V4-
  Flash-0731`, `MiniMaxAI/MiniMax-M2.7`, `zai-org/GLM-5.3-Flash`,
  `BAAI/bge-m3`.
- Smoke judge pada DeepSeek-V4-Flash: JSON sah (skor 85), 226 token
  total, wall 2,68 detik. Tercatat sebagai `GONKA_SMOKE_RECORD`.

## Registrasi

`director_strong.py` kini mendaftarkan organ ketiga
`director-strong-gonka` (kind external-director, capabilities
direktur yang sama) dan `brain_of_origin` menerima provider
`gonka` → `gonka/<model>`.

## Dua catatan berdiri (tertulis juga sebagai GONKA_NOTES di modul)

1. **QUIRK model:** DeepSeek-V4-Flash lewat rute ini mengeluarkan
   objek JSON-nya **dua kali tersambung** — konsumen wajib mem-parse
   objek lengkap pertama saja.
2. **Saldo nyata:** 100.000 token mentah/bulan dari dashboard
   (≈24 siklus direktur penuh atau ≈440 panggilan judge per bulan).
   Angka "1 jt" di halaman vendor adalah bingkai nilai-setara model
   termahal, bukan saldo. Gonka diperlakukan sebagai **organ
   kedua/pendapat-kedua**, bukan kolam tak berdasar.

## Pagar khusus rute ini

Broker pihak ketiga: **tanpa materi privat lewat rute Gonka** —
pekerjaan direktur umum saja (siklus agenda, sintesis, pendapat
kedua). Pagar Tahap 1 lainnya tidak berubah: pekerjaan direktur
saja, bukan subjek ukur, slate v2 tak tersentuh, fail-closed lewat
registry.

## Bukti

Tes: test_director_strong 7/7 (termasuk tes gonka baru: origin,
catatan quirk/saldo/privasi, deskriptor second-opinion), bersama
test_brain_registry + test_opportunity_register **21/21 OK**.
