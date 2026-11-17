# Diagnosis Mekanisme Recall — Kenapa Lift Nol di EVO 0005
## Catatan desain (Ian, 2026-11-16 malam, sesudah vonis 0005)

Vonis 0005 berdiri (NOL, PR #248). Dokumen ini membedah
KENAPA — dari rekonstruksi atas artefak lari, bukan dari
kesan. Tiga penyebab bertumpuk, urut menurut bobotnya,
lalu syarat instrumen untuk tes akumulasi berikutnya,
lalu hipotesis penerus (arah 0007).

## 1. Kegagalan pengantaran (dominan): treatment tidak sampai

Rekonstruksi recall atas store akumulasi (10 record:
2 seed + 8 verdict_sealed — write-back terbukti bekerja),
query = instruksi held-out persis seperti yang dipakai
runner, kinds=["semantic"], limit=10:

| episode | record ter-recall |
|---|---|
| ho-code-001 | 0 |
| ho-code-002 | 0 |
| ho-code-003 | 8 |
| ho-code-004 | 0 |
| ho-lang-001..004 | 0 (semua) |

**7 dari 8 episode tidak menerima konteks sama sekali.**
Bukti silang dari artefak: panjang output proposer
lengan BEFORE dan AFTER-akumulasi IDENTIK pada 6 episode
(1933/1933, 1409/1409, 1645/1645, 763/763, 319/319,
209/209 chars) — dengan daftar konteks kosong, guard
`if context:` di ratification_loop membiarkan prompt
proposer byte-identik dengan BEFORE, dan decoding yang
hampir deterministik menghasilkan output yang sama dan
vonis yang sama. Satu-satunya episode yang menerima
konteks (ho-code-003) justru satu-satunya yang outputnya
berubah panjang (1304 → 1329). Lengan AFTER-sham, yang
konteksnya selalu terisi, berubah panjang di semua
episode — pola yang konsisten penuh dengan diagnosis ini.

Kenapa recall kosong: permukaan teks record yang
tersimpan adalah METADATA ratifikasi ("Ratified episode
tr-code-003 (code) via coder->front") — hampir tidak ada
irisan leksikal/semantik dengan instruksi tugas held-out
(mis. memecah pecahan rupiah). Recall menilai relevansi
atas teks itu; receipt bukan pengetahuan dan tidak
menemukan jalannya ke tugas baru.

Konsekuensi pembacaan: lengan AFTER-akumulasi secara
efektif mengulang BEFORE pada 7/8 episode. Vonis NOL
tetap sahih untuk klaim sebagaimana diuji (mekanisme
sebagaimana dibangun, ujung-ke-ujung, memang tidak
menghasilkan lift) — tetapi komponen terbesarnya adalah
kegagalan pengantaran, bukan bukti bahwa akumulasi
pengetahuan tidak bisa bekerja.

## 2. Ketipisan isi (akan mengikat sekalipun terkirim)

Sekalipun recall mengembalikan record, isinya adalah
receipt: id episode, jenis, pasangan organ. Tidak ada
isi tugas, tidak ada pola solusi, tidak ada alasan
penerimaan judge. Bandingkan Blok D (EVO 0004): yang
ditransfer adalah KATALOG berisi operator yang bisa
dieksekusi — isi yang bisa dipakai — dan transfernya
terukur besar (pool 12/12 terpecahkan, −37% biaya).
Receipt tidak bisa dipakai proposer untuk apa pun;
paling jauh ia adalah priming metadata.

## 3. Insensitivitas instrumen (mengikat pengukuran apa pun)

- Language di PLAFON: 4/4 di semua lengan sahih — ruang
  naik nol; efek bahasa apa pun tidak terukur pada
  famili ini.
- Code mentok di episode yang sama: ho-code-001 gagal
  di semua lengan oleh penolakan judge yang substantif
  (logika greedy pecahan rupiahnya memang salah pada
  contoh) — lantai, bukan pita gerak.
- Jumlah episode di PITA SENSITIVITAS (yang vonisnya
  bisa bergerak oleh konteks) pada korpus ini = 0.
  Setiap episode selalu-lolos atau selalu-gagal lintas
  lengan. Dengan himpunan seperti itu, N=8 tidak punya
  daya statistik untuk efek sedang — instrumennya yang
  tumpul, terpisah dari mekanismenya.

Celah instrumentasi yang membiarkan ini tak terlihat:
runner 0005 TIDAK mencatat konteks yang disuntikkan
per episode. Kegagalan pengantaran baru ketahuan lewat
rekonstruksi sesudah lari.

## 4. Syarat instrumen — tes akumulasi berikutnya

1. **Gerbang pengantaran:** konteks per episode WAJIB
   tercatat sebagai field kelas-satu di hasil; lengan
   dinyatakan sahih hanya bila pengantaran ≥ ambang
   yang dibekukan di praregistrasi (mis. ≥ 75% episode
   menerima konteks non-kosong); di bawah itu vonisnya
   TIDAK_TERANTAR, bukan NOL.
2. **Kalibrasi pita sensitivitas:** kandidat episode
   disaring dulu 2× pada kondisi BEFORE; hanya episode
   ber-vonis belah (1/2) atau nyaris-batas yang masuk
   korpus ukur; target ≥ 50% himpunan berada di pita.
3. **Isi treatment berbentuk pengetahuan:** yang
   di-recall harus memuat isi tugas/pola (lihat §5),
   dan teks record harus memakai kosakata tugasnya
   sendiri agar recall bisa menemukan relevansi.
4. **Ukuran jujur:** nyatakan efek minimum yang bisa
   ditangkap himpunan terkalibrasi itu di praregistrasi;
   jangan lagi menguji efek sedang dengan himpunan
   plafon/lantai.

## 5. Hipotesis penerus — arah EVO 0007 (dicatat, belum praregistrasi)

Recall berbasis POLA TERDISTILASI ala katalog: setiap
episode ratified didistilasi menjadi record pola —
bentuk-tugas → pendekatan/ceklist yang lolos judge,
termasuk alasan penerimaan judge — tersimpan sebagai
isi memori berkosakata tugas. Bentuk katalog adalah
bukti keberadaan di program ini bahwa ACE memindahkan
artefak ber-isi lintas konteks dengan efek terukur
(Blok D); receipt bukan isi. Tes 0007 kelak menguji
apakah konteks pola-terdistilasi mengangkat rate pada
himpunan terkalibrasi pita-sensitivitas, dengan gerbang
pengantaran §4.1 dan kontrol sham yang sama.
