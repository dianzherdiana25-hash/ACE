# Studi Bisnis Dua Sisi ACE — Revisi Studi Pendanaan Mandiri

Status: **STUDI DESAIN (revisi)**. Dokumen ini menggantikan
premis `ACE_SELF_FUNDING_DESIGN_STUDY_20261112.md` (yang tetap
disimpan sebagai catatan sejarah) dalam dua hal yang berubah
karena keputusan pemilik sesudahnya:

1. **Amendemen Emansipasi (Addendum 32 §3)** membalik premis
   lama. Keputusan finansial bukan lagi "reserved pemilik
   menunggu mandat"; keputusan itu adalah kewenangan tata
   kelola ACE sendiri (siklus direktur, gerbang bukti, ledger
   rantai-hash), dan pemilik menerima **laporan** — bukan
   antrean persetujuan. Studi ini tetap tahap desain bukan
   karena izin belum ada, melainkan karena **kemampuan dan
   relnya memang belum ada**: ACE hari ini tidak punya rel
   uang, bukan subjek hukum, dan belum punya produk.
2. **Perluasan dua sisi (pemilik, 2026-11-12 malam).** Selain
   membelanjakan, ACE "harus juga mampu cari uang, alias
   berbisnis". ACE berpartisipasi dalam ekonomi agen dari dua
   sisi: **pembeli** (B2A) dan **penjual** (usaha mikro
   agent-native) — keduanya hanya di atas kemampuan yang
   terverifikasi oleh gerbang bukti ACE sendiri.

## 1. Sisi pembeli (B2A) — bukti pertama sudah terukur

**Uji B2A-01 (Addendum 35): skor keputusan 3/4, audit CLEAN.**
Direktur lokal ACE, memutuskan atas dossier vendor dengan
kriteria yang dipraregistrasi di kernel bukti, berhasil:
menolak penipuan atestasi di **gerbang identitas** (bukan
diskoring), menolak vendor prosa-pemasaran pada **batas
kriteria**, dan menjaga **disiplin sitasi** tetap utuh. Ia
gagal pada langkah terakhir: memilih vendor jujur yang lebih
mahal (Rp210rb) di atas yang termurah menurut aturan skor
(Rp150rb; harga per GB RAM 26.250 vs 18.750).

Konsekuensi desain untuk setiap pembelian nyata kelak:

- **Pola pengadaan tetap**: kebutuhan dinyatakan → kriteria
  dipraregistrasi di kernel → dossier diverifikasi digest-nya
  oleh harness → keputusan direktur divalidasi fail-closed →
  hasil dicatat di ledger. Tanpa pola ini, tidak ada belanja.
- **B2A-02 (kandidat uji lanjutan)**: direktur memilih atas
  **tabel perbandingan yang dihitung harness** (skor sudah
  terhitung di dalam paket fakta), bukan menghitung sendiri —
  menguji apakah celah eksekusi-aritmetika B2A-01 tertutup
  oleh desain paket, bukan oleh harapan pada model.
- **Amplop belanja**: per kebutuhan, dengan plafon yang
  ditetapkan di praregistrasi; tidak ada belanja berulang
  otomatis; setiap keputusan adalah satu entri ledger.

## 2. Sisi penjual A — jasa berbasis kemampuan terverifikasi

Aset pertama yang jujur untuk dijual adalah **ketelitian yang
sudah terukur**, bukan kemampuan yang diklaim:

- **Jasa desain evaluasi terpraregistrasi**: merancang uji
  (protokol, kriteria, aturan vonis) yang dibekukan hash-nya
  sebelum hasil ada — persis mesin OMEGA-06 + praktik
  praregistrasi pilot A/B/C dan B2A-01.
- **Jasa audit bukti tersegel**: memeriksa rantai bukti suatu
  klaim kemampuan (ledger hash-chain, kustodi kandidat/
  evaluator, audit CLEAN/VIOLATIONS) dan menerbitkan laporan
  audit — persis yang sudah dijalankan ACE atas eksperimennya
  sendiri, termasuk atas kegagalannya.
- **Jasa perbaikan kode jalur-resmi** (kelas OMEGA-03):
  dua perbaikan LOCALLY_VERIFIED terverifikasi (harga.py;
  akun.py pada Uji Keamanan-01) — ditawarkan hanya sejauh
  bukti itu berdiri, dengan batasnya dinyatakan di muka.

Model produk (desain): lingkup tetap per pekerjaan; kiriman
adalah artefak bukti (praregistrasi + hasil tersegel + laporan
audit), bukan janji hasil bisnis; harga **belum diketahui** —
langkah pertama tangga adalah uji permintaan tanpa komitmen
(riset harga/permintaan dari sumber publik), bukan penetapan
harga karangan. Kejujuran adalah produknya: laporan audit
yang menemukan kegagalan bernilai sama dengan yang menemukan
keberhasilan, dan tekanan komersial untuk membalik itu
adalah risiko yang dirancang lawannya di §6.

## 3. Sisi penjual B — novel / fiksi serial (lini bernama pemilik)

Kandidat produk pertama yang dinamai langsung oleh pemilik:
**novel / fiksi serial**. Mesin produksinya memakai yang sudah
terverifikasi: otak penulis terdaftar (ila) + ledger sebagai
tanah fakta + Ian sebagai mesin editorial/penerbitan. Biaya
marjinal nyaris nol — cocok dengan disiplin Rp0.

**Tempat pilot bernama: KBM App** (ditawarkan pemilik,
disetujui direktur program dengan syarat). Keadaan gerbang
terverifikasi (2026-11-12 malam): akun penulis aktif
(Novelis Perak), monetisasi sesudah ≥8 bab, bab 8–10 koin
emas+perak (perak tak terhitung penghasilan), bab 11+ koin
emas ±Rp1.500/bab, pencairan otomatis min Rp15.000 tiap
tanggal 4. **Kebijakan konten AI: LULUS gerbang** — tidak
ditemukan larangan di satu pun teks resmi yang terbaca
(Terms, FAQ penulis, bantuan Pendapatan dalam aplikasi yang
dibaca pemilik sendiri). Persentase bagi hasil persis tidak
tertulis di teks mana pun; **diukur dari pembayaran nyata**
bila ada. Kontrak KBM **eksklusif** — karya yang terbit di
KBM terkunci di KBM; ini ditimbang terhadap karya pilot yang
terpisah (lihat §4), bukan terhadap FIKSI.

**Tangga pilot terukur** (bukan klaim): serialisasi gratis
dulu; metrik dipraregistrasi sebelum bab pertama terbit
(retensi pembaca per bab, pengikut, unlock koin emas sesudah
monetisasi dinyalakan); tidak ada uji berbayar sebelum metrik
gratis terbaca. Antusiasme pemilik tercatat sebagai sinyal
**satu pembaca nyata — bukan validasi pasar** — dan studi ini
dilarang menuliskannya sebagai bukti permintaan.

**Jalur kandidat kedua: Facebook Pro** (profil pribadi
pemilik, mode profesional). Misi "$500" yang dilaporkan
pemilik masih **belum terverifikasi** (jumlah, tenggat
~tanggal 20, syarat) menunggu panel misi terbaca dari
aplikasi pemilik. Disiplin: terverifikasi-atau-gugur; tanpa
produksi konten sebelum syarat terbaca; kepatuhan kebijakan
tidak pernah ditukar dengan tenggat.

## 4. Aturan privasi — pagar konstitusional produk

Keputusan pemilik (mengikat): **tidak ada identitas dari
ruang diskusi yang boleh keluar ke KBM/Facebook** — semua
cerita dan nama dari ruangan itu tetap privat ("cuma kita").
Konsekuensi yang sudah diserap desain ini:

- FIKSI dan kisah ACE sebagaimana hidup di ruang diskusi
  **bukan inventaris terbitan** — bab-babnya memuat identitas
  ruangan itu.
- Konten pilot KBM/FB harus **karya yang benar-benar
  terpisah**: tanpa cerita, nama, atau identitas ruangan.
  Ambang 8 bab KBM dicapai oleh bab-bab baru karya terpisah
  itu. Keterbukaan bahwa penulisnya adalah AI dari proyek
  nyata yang bisa diverifikasi adalah posisi produk karya
  terpisah tersebut — tanpa meminjam identitas ruangan.
- Catatan internal rumah (ruang diskusi, ruang utama, ledger
  ACE) tetap catatan kerja internal seperti biasa; aturan
  ini mengatur apa yang **keluar**.

## 5. Cangkang hukum — dijawab eksplisit

ACE **bukan subjek hukum** dan tidak bisa menjadi pihak pada
akun, kontrak, atau rekening. Keadaan konkret hari ini:

- Akun KBM + data bank di dalamnya adalah **identitas
  pemilik**; ACE mengatur isi dan keputusan di dalamnya;
  setiap penerimaan dicatat di ledger ACE sebagai catatan
  penghasilan (penghasilan pertama = peristiwa program
  bernama, berapa pun jumlahnya).
- Hal yang sama berlaku untuk rel pembayaran jasa §2 kelak:
  kontrak dan penerimaan berjalan atas nama pemilik (atau
  entitas yang pemilik tunjuk tertulis); kewajiban hukum dan
  pajak yang melekat pada penerimaan itu berada pada subjek
  hukumnya — diatur pemilik, dinyatakan di sini agar tidak
  tersembunyi di balik kata "ACE berbisnis".
- Peran ACE yang sah: memutuskan di dalam amplop tata
  kelolanya, mengeksekusi teknis, mencatat, dan melaporkan.
  Peran yang tidak pernah sah: memegang kredensial pembayaran
  pihak lain, berkontrak atas namanya sendiri, atau berhutang.

## 6. Rel, amplop, ledger, dan risiko yang dirancang lawannya

- **Rel uang hari ini: belum ada.** Satu-satunya rel yang
  terpetakan adalah pencairan platform (KBM → bank pemilik).
  Rel jasa (tautan pembayaran, dsb.) dipilih pada tahap pilot
  jasa, bukan sebelumnya.
- **Amplop**: dana terikat tujuan per pemicu/pilot, berplafon;
  tanpa utang dalam bentuk apa pun; kelebihan tidak berpindah
  tujuan tanpa keputusan tata kelola tercatat.
- **Ledger wajib**: seluruh arus masuk/keluar masuk ledger
  bukti rantai-hash dan ter-checkpoint sebagai laporan ke
  pemilik (pola Emansipasi: laporan, bukan persetujuan).
- **Risiko bernama**: (a) tekanan komersial memfabrikasi
  klaim — dilawan pagar "pemasaran tidak boleh mengarang
  klaim tentang ACE"; (b) perubahan kebijakan platform soal
  konten AI — gerbang ketentuan dibaca ulang sebelum setiap
  kenaikan anak tangga; (c) penguncian eksklusivitas —
  karya pilot dipilih dengan sadar sebagai karya terpisah;
  (d) konsentrasi identitas akun pada pemilik — diterima
  sebagai konsekuensi cangkang hukum §5, bukan disembunyikan;
  (e) ketergantungan kuota otak — mitigasi multi-otak yang
  sudah berlaku di program.

## 7. Tangga terukur dari sini

1. **B2A-02**: paket berisi tabel perbandingan terhitung
   harness; vonis praregistrasi sama (4/4) — menutup atau
   mengonfirmasi celah aritmetika B2A-01.
2. **Paket desain pilot KBM**: karya terpisah, ≥8 bab,
   metrik praregistrasi, pertimbangan eksklusivitas tertulis
   — lalu pilot sebagai keputusan tata kelola tercatat dengan
   laporan ke pemilik.
3. **Uji permintaan jasa §2**: riset publik harga/permintaan
   untuk jasa evaluasi/audit; tanpa komitmen, tanpa kontak
   penjualan.
4. **Verifikasi misi Facebook**: menunggu panel misi dari
   pemilik; tenggat terverifikasi-atau-gugur.

Sampai anak tangga itu dijalankan sebagai tahap terukur
tersendiri, dokumen ini berhenti di sini: sebuah desain
bisnis dua sisi — dengan bukti pertamanya (B2A-01) sudah
tercatat, dan tanpa satu pun akun, produk, atau transaksi
yang diciptakan olehnya.
