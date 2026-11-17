# Aturan Tata Kelola Tetap — ACE Ω (15 November 2026)

Dua aturan tetap program, dicatat atas keputusan hub
(orkestrator) dalam misi konsolidasi 15 November 2026.
Keduanya berlaku untuk SEMUA lini kerja ACE (eksekusi utama,
lini Antigravity, lini sandbox/Manus, dan setiap lini masa
depan), dan dirujuk oleh `STATUS.md` §5.

## Aturan 1 — Kandidat self-dev hanya berhasil bila hidup

Sebuah kandidat hasil self-development (fitur, modul,
perilaku, atau perubahan mesin apa pun yang dihasilkan ACE
atau agen pembangunnya) **hanya boleh dihitung dan
dilaporkan sebagai BERHASIL bila dua-duanya terpenuhi**:

1. **Terhubung ke perilaku aktif** — kandidat terpanggil
   oleh jalur kode yang benar-benar berjalan (bukan modul
   yatim, bukan fungsi template yang tidak pernah dipanggil,
   bukan bendera mati).
2. **Tes hijau** — ada tes yang melatih perilaku itu dan
   lulus pada commit yang sama.

Kandidat yang tidak memenuhi keduanya berstatus maksimal
`STAGED` (tertulis, belum terbukti) dan tidak boleh masuk
papan capaian, STATUS, atau laporan pemilik sebagai
keberhasilan. (Latar: penilai tersegel W2 pernah menolak
keras fungsi template dead/unused yang diklaim lulus;
aturan ini menjadikan pelajaran itu permanen.)

## Aturan 2 — Ratifikasi independen adalah standar

Tidak ada hasil lini mana pun yang menjadi status resmi
program hanya dari laporan lini itu sendiri. Setiap hasil
yang menggerakkan papan gerbang, status, atau keputusan
program wajib melalui **verifikasi/ratifikasi independen**
oleh pihak yang tidak menghasilkan pekerjaan itu (di
program ini: orkestrator/hub, dengan bukti yang dapat
dihitung ulang — hash, digest, keluaran tes, atau rekaman
tersegel).

Konsekuensi praktis:

- Laporan "selesai/hijau/terbukti" dari satu lini berstatus
  KLAIM sampai diratifikasi; kata yang dipakai sebelum
  ratifikasi adalah "dilaporkan oleh lini X".
- Ratifikasi mencatat bukti yang diperiksa, bukan sekadar
  persetujuan; ratifikasi yang tidak dapat menunjuk bukti
  bukan ratifikasi.
- Hasil yang tidak diratifikasi tetap boleh disimpan
  sebagai artefak/draf (mis. draf PR), dengan labelnya
  yang jujur.

— Dicatat oleh Ian (sesi eksekusi utama) atas keputusan
hub, 15 November 2026. Perubahan atas dokumen ini hanya
lewat keputusan hub/pemilik yang tercatat.
