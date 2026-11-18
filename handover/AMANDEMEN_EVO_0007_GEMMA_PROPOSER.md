# AMANDEMEN EVO 0007 §10 — Proposer bahasa berpindah ke Gemma 4 31B untuk sisa lengan

Status: AMANDEMEN ARAHAN PEMILIK, 2026-11-18 21:23 WIB
("pake gemma aja"). Mengamendemen PRAREGISTRASI_EVO_0007_FINAL
(PR #311) pada satu titik: identitas organ proposer bahasa
untuk baris lengan yang belum tersegel. Semua ketentuan lain
praregistrasi dan amendemen §1–§9 berdiri utuh.

## 1. Fakta yang memaksa amendemen

Ember gemini-3-flash-preview adalah penghambat paket: kuota
free tier 20 generate/hari/model/kunci × 3 kunci = 60/hari,
sementara sisa lengan membutuhkan 95 panggilan peran-Gemini.
Pada laju itu lengan selesai dalam ±2 napas ember (±20 Nov).
Kuota Gemini bersifat PER MODEL: ember model lain di kunci
yang sama belum tersentuh.

## 2. Katalog hidup dan smoke terukur (2026-11-18 malam)

Katalog yang terbaca di akun sendiri (helper `models`,
kunci-2) memuat tepat dua model Gemma:
`gemma-4-26b-a4b-it` dan `gemma-4-31b-it`. Smoke generate
gemma-4-31b-it lulus isi: jawaban JSON benar ({"ok": true,
"sum": 42}) dan penilaian kode benar (bug pengurangan
terdeteksi, alasan benar). Latensi terukur 33–98 detik per
panggilan. Riset web (laporan 2026-11-18) membaca kuota Gemma
4 ±14.400 request/hari/model dari panel AI Studio — angka
panel, bukan janji Google; kebutuhan sisa paket (±43
panggilan proposer bahasa) jauh di bawahnya pada tafsir
paling konservatif sekalipun.

## 3. Yang berpindah, yang TIDAK berpindah

BERPINDAH: proposer bahasa → ("gemini", "gemma-4-31b-it").

TIDAK berpindah: validator kode tetap
gemini-3-flash-preview. Alasan terukur, bukan selera: prompt
validator runner menuntut jawaban diawali RATIFY/REJECT dan
kode memeriksanya fail-closed
(`validation.strip().upper().startswith("RATIFY")`). Kedua
model Gemma diuji dengan prompt validator PERSIS milik
runner atas proposal yang sempurna — keduanya membuka
dengan analisis berpoin, bukan RATIFY. Memindahkan validator
akan mengubah hampir semua episode kode sisa menjadi
validator_rejected palsu (judge_skipped, accepted=False)
dan meracuni kontras lengan. Sisa panggilan validator kode
±52 muat dalam satu napas ember flash (60/hari).

Juga tidak berpindah: proposer kode (groq qwen3.8-27b),
validator bahasa (groq gpt-oss-120b), judge (cloudflare
llama-3.3-70b), distiller (annex sudah beku; tidak berperan
lagi di fase lengan).

## 4. Batas dan pencatatan

Baris tersegel 1–65 (POLA 40/40 + RECEIPT 25/40) berdiri di
bawah set organ sebelumnya dan TIDAK dijalankan ulang.
Amendemen berlaku dari baris tersegel berikutnya. Setiap
baris lengan mencap brain_proposer dan brain_validator-nya
sendiri, jadi komposisi per lengan (POLA murni set-lama;
RECEIPT campuran pada batas baris ke-65; SHAM/KOSONG set
baru untuk peran proposer bahasa) terbaca dari baris itu
sendiri dan WAJIB ditabulasikan di konsolidasi, bersama
keterbatasan lintas-generator ini sebagai keterbatasan
bernama vonis §6 — bukan disembunyikan, bukan dianggap
tidak ada.

Konsekuensi jadwal: lengan kini dapat selesai dalam SATU
napas ember flash (±15:00 WIB 19 Nov; ±52 panggilan
validator) ditambah ±43 panggilan Gemma yang tidak menunggu
napas — satu hari lebih cepat dari jalur tanpa amendemen.
