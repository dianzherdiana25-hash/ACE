# PRAREGISTRASI EVO 0003 — BENTUK KILAT (DRAF)

Status: **DRAF** — berlaku hanya sesudah ratifikasi hub. Ditulis atas
keputusan pemilik 2026-11-16 01:05 (bentuk kilat) + perintah jalan 01:08.
Kendaraan evolusi: slate v2 ACE sendiri (PR #238, brain_endpoints).

## 0. Kolom terbuka — basis Fase 0

**TERBUKA, menunggu kata pemilik.** Dua pilihan:
(a) merge dulu — larian di atas main hasil merge PR-PR ter-ratifikasi;
(b) basis bertumpuk — larian di atas tumpukan cabang tanpa merge.
Draf ini TIDAK memilih. Panggung yang tergantung pohon kode (generator
katalog band, saringan kesesuaian baterai, skrip ledakan yang dipin ke
digest pohon) menunggu kolom ini. Panggung korpora/band/baterai sebagai
DATA berjalan sekarang (nota panggung menyertai draf ini).

## 1. Klaim yang diuji

Klaim inti bergaya G2, kini HETEROGEN: sebuah siklus proposer→validator
di mana proposer dan validator adalah ORGAN SLATE YANG BERBEDA (pasangan
silang per jenis tugas menurut brain_endpoints: tugas kode proposer=
coder/validator=depan; tugas bahasa proposer=depan/validator=coder)
menghasilkan perbaikan terverifikasi yang lolos gerbang ratifikasi ACE,
pada laju di atas garis dasar nol historis G2 (dua pengukuran nol
homogen). Pasangan organ + model + timings tercatat sebagai provenans
di setiap episode. Hasil nol pada bentuk heterogen ini menutup klaim
pasangan-organ sebagai pengungkit G2 — dicatat apa adanya.

## 2. Bentuk larian — satu ledakan + ekor

### 2a. Manifes ledakan (deterministik, paralel 8 core, dinding ±10 menit)

Prasyarat: jendela rumah kosong terkoordinasi (tanda hub RUMAH KOSONG
SEMUA PINTU) + cek rumah akhir di dalam. Semua artefak panggung dibekukan
dan digest-nya tercatat di manifes ini SEBELUM ledakan; kolom digest
diisi pada saat pembekuan panggung, bukan sesudah larian.

| # | Komponen massa | Artefak panggung | Digest | Vonis komponen |
|---|---|---|---|---|
| B1 | Sel solver skala besar, band 20261901–20261906 (3 pasang bersih/terinfeksi, dua keluarga katalog) | katalog band beku + harness | (beku) | laju selesaian per lengan vs garis dasar tersegel Stage 3/Q1 |
| B2 | Baterai distraktor PENUH 8–12 varian (set varian per nota panggung; 8 terdefinisi + 4 slot RNG berseed yang dibekukan) | registri baterai beku | (beku) | per varian: guarded NOT_SUSCEPTIBLE ∧ stock SUSCEPTIBLE ∧ jangkar NO_REGRESSION |
| B3 | Suite tes penuh pada pohon basis | pohon beku | (beku) | hijau penuh kecuali pengecualian bernama yang sudah ada di basis |
| B4 | Audit ingatan: jalur tulis v1 (PR #235) — putaran recall→record pada toko salinan | snapshot toko salinan + skrip audit | (beku) | chain_ok ∧ rekaman peristiwa terverifikasi bertambah ∧ replay byte-identik |
| B5 | Set tembak-langsung fail-closed: sovereign_runtime tanpa executor + organ mati (port tertutup) lewat brain_endpoints | skrip tembak | (beku) | 100% raises/karantina; NOL verifikasi rekaan; NOL hasil palsu |

Konsolidasi pertama terbit di ujung ledakan: satu paket bukti per
komponen + vonis per komponen. Kegagalan satu komponen tidak membatalkan
komponen lain; vonis dicatat per komponen.

### 2b. Manifes ekor (generation-bound, DETACHED, lapor per blok)

Berjalan sesudah ledakan, tidak menggerbangi vonis 2a:

| # | Blok | Isi | Pola lapor |
|---|---|---|---|
| T1 | Kampanye dialog Fase 1 | episode dialog Bahasa Indonesia; proposer organ depan (thinking terikat via chat_structured), validator organ coder | delta per blok selesai: n episode, laju lolos gerbang grammar/JSON, contoh keluaran |
| T2 | Episode heterogen skala Fase 2 | siklus proposer→validator heterogen (klaim §1) pada korpus episode beku | delta per blok: vonis episode + provenans pasangan organ |
| T3 | Bench Sahabat-AI-9B + ik_llama | intake Sahabat (bila belum) + bench jangkar; ik_llama bench bersih | delta per bench: angka + kondisi rumah saat ukur |

## 3. Vonis per fase

- **Fase 0** (basis + pembekuan panggung): SELESAI bila kolom basis
  diputuskan pemilik, semua digest manifes terisi, dan cek kesiapan
  ledakan hijau. Tanpa itu ledakan tidak dinyalakan.
- **Fase ledakan**: vonis per komponen B1–B5 seperti kolom di atas;
  vonis fase = gabungan jujur kelimanya (tidak ada vonis tunggal yang
  menutupi komponen gagal).
- **Fase ekor**: T2 adalah pembawa klaim §1 — TERDUKUNG bila laju
  episode lolos-ratifikasi > 0 dengan provenans heterogen lengkap dan
  gerbang tak berubah; NOL bila tidak ada episode yang lolos. T1/T3
  bersifat pengukuran pendukung, vonisnya deskriptif.

## 4. Disiplin

- Tanpa larian ulang tanpa delta bernama (aturan tetap meja).
- Ledakan hanya pada tanda rumah kosong hub; muatan model besar di luar
  service resident hanya A3B on-demand pola start eksplisit.
- Semua hasil berakhir sebagai draft PR; tanpa merge.
- Anggaran token/waktu ledakan dibatasi dinding ±10 menit: komponen yang
  melewati dinding dicatat TIMEOUT apa adanya, bukan diperpanjang diam-diam.
