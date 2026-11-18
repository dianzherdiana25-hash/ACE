# TAHAP 1 OTAK KUAT — Registrasi Organ Director-Strong

*Eksekusi Ian atas rancangan hub `RANCANGAN_TAHAPAN_OTAK_KUAT.md`
(perintah pemilik 18 Nov 2026). Gerbang Tahap 1: endpoint terdaftar +
smoke terukur + satu produk direktur nyata dengan brain-of-origin
yang benar.*

## Amandemen transport (terverifikasi hub, 18 Nov 2026)

Rute dashboard FreeLLM pada rancangan awal **mati**: browser Muse
menolak navigasi localhost dan alamat IP privat di lapisan alat (tiga
percobaan, dua browser). Pemilik memasukkan kunci provider gratisnya
lewat kartu Secure Vault sebagai gantinya. Transport yang hidup:

| Brain terdaftar | Transport | Helper hub | Model terverifikasi |
|---|---|---|---|
| `director-strong-groq` | connector `custom.groq` | `custom.groq/bin/groq_call.py` | 11 model, termasuk `openai/gpt-oss-120b`, `qwen/qwen3.8-27b` |
| `director-strong-gemini` | connector `custom.gemini` | `custom.gemini/bin/gemini_call.py` | 50 model, termasuk `gemini-2.5-pro` |

Nilai kredensial tinggal di vault; tidak terlihat oleh sesi mana pun.
FreeLLM sendiri tetap terpasang di VM Ian dan menyala untuk pemakaian
pemilik dari perangkatnya sendiri; ia bukan transport Tahap 1.

## Smoke terukur (hub, 18 Nov 2026)

Generasi setara-judge lewat `groq/openai/gpt-oss-120b`: **309 token
penyelesaian dalam 0,64 detik ≈ 481 t/s efektif (wall 1,35 detik)** —
melawan front lokal 0,45–0,79 t/s di bawah beban dan 1.232–1.778
detik untuk generasi sekelas itu secara lokal. Angka proyeksi §0
rancangan kini tergantikan angka rumah. Tercatat juga sebagai
`SMOKE_RECORD` di `code/ace_operational/director_strong.py`.

## Registrasi

`code/ace_operational/director_strong.py` — `register_director_strong
(registry)` mendaftarkan kedua organ di brain registry ACE
(`ace_operational/brain_registry.py`): kind `external-director`,
status `active`, capabilities persis tiga pekerjaan direktur
(`agenda_cycle`, `curriculum_proposal`, `opportunity_synthesis`).
`brain_of_origin(provider, model)` memformat dan memvalidasi asal
setiap panggilan direktur: `groq/<model>` atau `gemini/<model>`;
provider lain ditolak.

## Pagar yang tidak berubah

- Pekerjaan direktur saja. Organ ini bukan subjek ukur di
  praregistrasi mana pun dan keluarannya tidak pernah disamarkan
  sebagai keluaran lokal — brain-of-origin tercatat per produk.
- Slate v2 tidak berubah: tidak ada routing, endpoint, atau organ
  terukur yang disentuh PR ini.
- Fail-closed: connector mati → pekerjaan direktur kembali ke organ
  lokal atau berhenti tercatat; dismissal berjalan lewat registry
  seperti otak lain mana pun (teruji).

## Bukti

`code/ace_operational/test_director_strong.py` — 6 tes (registrasi
kedua organ + capabilities direktur-saja; persistensi + replay event;
registrasi ulang idempotent di tingkat record; dismissal fail-closed
tanpa menyentuh otak lokal; format brain-of-origin; penolakan
provider tak terdaftar). Bersama `test_brain_registry`: 11/11 OK.

## Sisa gerbang

Satu produk direktur nyata (batch usulan agenda dari bahan siklus
pertama, `handover/BAHAN_SIKLUS_DIREKTUR_PERTAMA.md`) masuk register
dengan brain-of-origin yang benar — generasi dijalankan hub lewat
connector; produknya kembali ke meja ini untuk dicatat.
