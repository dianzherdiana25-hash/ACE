# Pipeline Narasi TTS — Desain + Memo Gerbang Uji Dengar

**Item kemampuan 7 (ACE Ω).** Status: pipeline terbukti jalan end-to-end pada satu bab uji. Tidak ada akun apa pun yang dibuka; sintesis memakai CLI `tts` lokal (skill Spoken Audio).

**Artefak uji:** [audio/warung_bab01_tts_test.mp3](sandbox://workspace/ace-omega/handover/audio/warung_bab01_tts_test.mp3) — narasi Bab 1 "Wasiat di Hari Ketujuh" dari novelet *Empat Puluh Hari di Warung Bapak* (sumber: `MENULIS_WARUNG_BAB01_DRAF.md`).

---

## 1. Hasil terukur dari uji Bab 1

| Ukuran | Nilai |
|---|---|
| Karakter prosa sumber (tanpa header draf) | 13.249 |
| Kata prosa | 2.024 |
| Paragraf | 56 |
| Giliran naskah (paragraf + 1 judul lisan) | 57 |
| Chunk sintesis (dilaporkan alat) | 57 (satu per giliran) |
| Durasi audio (dilaporkan alat; dicek ffprobe 937,9 dtk) | **937 detik ≈ 15 menit 37 detik** |
| Ukuran berkas MP3 | 7.503.205 byte (±7,5 MB) |
| Waktu dinding sintesis | 264 detik (±4,4 menit; ±3,5× lebih cepat dari realtime) |
| Laju bicara tersirat | ±848 karakter/menit · ±130 kata/menit |
| Biaya | Alat tidak melaporkan biaya moneter; tidak ada akun/penagihan yang terlibat dalam uji ini |

Ekstrapolasi per bab untuk novelet ini (bab sebanding ±13 ribu karakter): **±15–16 menit audio, ±4–5 menit waktu sintesis, ±7,5 MB per bab.** Angka laju 800–900 karakter/menit dipakai sebagai pita kewajaran QA di langkah 5.

## 2. Desain pipeline

### Langkah 0 — Pemilihan suara (temuan penting)
Katalog suara sistem **tidak memiliki satu pun suara berbahasa Indonesia** (terukur: 1.203 suara `eng`, 15 `fra`, 0 Indonesia), dan tidak ada berkas suara rancangan tersimpan. Konsekuensinya: narasi Indonesia selalu dibawakan suara katalog Inggris dengan `--language id`. Itu risiko kualitas nomor satu pipeline ini — pelafalan fonem Indonesia (c = /tʃ/, ng, k akhir glotal, e pepet vs taling) tidak dijamin oleh suara yang tidak dirancang untuk bahasa ini.

Pilihan uji: **Aria (`avocado_v2:MAI_01`)**, suara produksi feminin-hangat, karena narasi novelet ini orang-ketiga terbatas mengikuti Ratna; satu suara narator tunggal adalah konfigurasi standar audiobook dan justru konfigurasi yang diuji gerbangnya di §3. Alat melaporkan suara dipakai persis seperti diminta (tanpa substitusi).

### Langkah 1 — Persiapan teks
Yang dilakukan pada uji ini:
1. Buang baris header/status draf dan judul berkas; prosa mulai dari paragraf pertama.
2. Lepas penanda markdown `**` dan `*` (tidak bisa diucapkan). **Catatan perbaikan wajib untuk produksi:** miring dalam naskah ini bermakna — wasiat Bapak adalah dokumen yang dibacakan di dalam adegan. Melepas penandanya tanpa ganti berarti menyerahkan pembeda suara itu ke gerbang §3; pipeline produksi harus menandai petikan dokumen sebagai segmen tersendiri (suara kedua atau jeda + perubahan register), bukan meratakannya diam-diam.
3. Tambahkan satu giliran judul lisan ("Bab 1. Wasiat di Hari Ketujuh.").
4. Teks selebihnya **verbatim** seperti tertulis, termasuk angka tahun dan singkatan — bahaya pelafalannya dicatat di bawah, bukan disunting diam-diam.

Bahaya pelafalan khas fiksi Indonesia yang harus masuk daftar cek produksi:
- **Angka tahun "1987"** — semestinya "seribu sembilan ratus delapan puluh tujuh"; TTS dapat membacanya sebagai deretan digit atau bilangan kardinal yang janggal.
- **Singkatan:** PNS, KTP, PR (pekerjaan rumah — rawan dieja huruf per huruf), ojol, "sif" (ejaan serapan *shift*).
- **Nama dan kosakata Jawa:** Ratna, Baskoro, Gilang, Sari, Darsim, Suyatno, Mahmud; *Nduk*, *tahlilan*, *berkat*, *Mbak*, *Mas*.
- **Fragmen elipsis** "*…untuk kalian…*" — sisa sobekan halaman; dalam audio hanya terdengar sebagai jeda dan fragmen, memang begitu maksud adegannya, tetapi pendengar tanpa teks akan bingung; ini keterbatasan medium, dicatat bukan diperbaiki.

### Langkah 2 — Chunking
Satu giliran naskah per paragraf, semua berlabel pembicara yang sama (`Narator`), dirender dengan `tts synthesize-script` (chunk maksimum bawaan 1.200 karakter; pemotongan di batas kalimat). Hasil terukur: 57 giliran → 57 chunk, jadi sambungan audio jatuh di batas paragraf — titik sambung paling aman untuk prosa. Paragraf yang lebih panjang dari 1.200 karakter (paragraf Bu Tini ±1.900 karakter) dipecah alat di batas kalimat di dalam paragraf; itu titik sambung lapis kedua yang harus masuk daftar dengar-cek.

### Langkah 3 — Sintesis
Perintah produksi: `tts synthesize-script --speaker Narator=<voice_id> --language id`, konkurensi 1 (berurutan, deterministik). Timeout bawaan 300 detik/chunk cukup longgar (total uji 264 detik untuk 57 chunk).

### Langkah 4 — Perakitan
Alat menggabungkan chunk menjadi satu MP3; tidak ada perakitan manual. Berkas uji: 7,5 MB / 15:37.

### Langkah 5 — Gerbang QA sebelum rilis apa pun
1. **Otomatis:** sintesis `ok`, jumlah chunk = jumlah giliran, durasi dalam pita 800–900 karakter/menit dari jumlah karakter naskah. (Bab 1: 848 ✓.)
2. **Dengar-cek pelafalan manusia:** daftar kata bahaya dari Langkah 1 (nama tokoh, "1987", PNS/KTP/PR) didengar pada sampelnya sebelum bab dinyatakan layak. Suara non-Indonesia membuat gerbang ini **wajib, bukan opsional**.
3. **Dengar-cek atribusi dialog:** adegan dengan pertukaran cepat (definisi di §3) didengar khusus untuk kebingungan pembicara.
4. **Gerbang struktural §3** memutuskan format rilis: suara tunggal, multi-suara, atau tidak diaudiokan.

---

## 3. Memo gerbang uji dengar — penilaian Bab 1 terhadap peringatan "TTS terlemah di fiksi padat dialog"

**Sifat penilaian:** struktural — dihitung dari teks dan dari fakta yang dilaporkan alat. Penilaian ini tidak mengklaim telah mendengar dengan telinga manusia; gerbang dengar-cek manusia tetap Langkah 5.2–5.3.

### Angka struktural Bab 1 (terukur dari naskah)
- Dialog dalam tanda petik: **45 segmen, 2.815 karakter = 21,2% karakter (22,6% kata)**.
- **Pembicara berbeda: 7** — Bu Tini, Pak Haji Mahmud, Baskoro, Sari, Gilang, Pak Darsim, Ratna — **ditambah 1 suara tertulis**: wasiat Bapak (2 petikan panjang, 696 karakter) yang dibacakan Pak Haji di dalam adegan, sehingga pendengar sesungguhnya menghadapi 8 identitas suara.
- **Pertukaran cepat: 24 dari 44 transisi** antardialog hanya disela narasi < 80 karakter (khas "kata X" / "tanya Y") — lebih dari separuh dialog berjalan dengan jeda atribusi minimal.
- Distribusi dialog per sepertiga bab: **8 / 20 / 17 segmen** — sepertiga tengah (pembacaan wasiat) dan sepertiga akhir (perundingan jadwal sif) adalah bagian terpadat dialog, dan keduanya adalah inti emosi bab: kejutan pasal-pasal wasiat serta perdebatan empat bersaudara. Bagian yang paling tidak boleh membingungkan justru bagian yang paling padat dialognya.

### Di mana kebingungan pembicara akan terjadi (suara tunggal)
1. **Adegan pembacaan wasiat.** Pak Haji membaca klausul → Baskoro menyela → Pak Haji menjawab sambil melanjutkan membaca → Baskoro lagi. Satu suara meratakan ketiganya; pendengar hanya dibantu atribusi singkat ("kata Pak Haji", "tanya Baskoro") yang dalam audio lewat dalam waktu kurang dari satu detik.
2. **Petikan wasiat itu sendiri.** Teks miring Bapak adalah suara ketiga di dalam suara Pak Haji di dalam suara narator — tiga lapis. Suara tunggal meratakan ketiganya menjadi satu register; pembeda "ini kata-kata almarhum" hilang.
3. **Perundingan akhir bab.** Empat bersaudara bergantian menetapkan sif (Sari → Gilang → Baskoro → Ratna) dengan atribusi yang kadang baru muncul di akhir kalimat; dalam audio, siapa menawarkan jam berapa mudah tertukar — padahal informasi itu beban plot untuk bab-bab berikutnya.

### Aturan gerbang (berlaku untuk semua bab berikutnya)
Hitung dari naskah sebelum sintesis: pangsa dialog (karakter dalam tanda petik ÷ total), jumlah pembicara berbeda, jumlah transisi cepat (jeda narasi < 80 karakter), dan ada-tidaknya dokumen yang dibacakan di dalam adegan (> 150 karakter).

- **LULUS suara tunggal:** pangsa dialog ≤ 15% **dan** ≤ 3 pembicara **dan** transisi cepat ≤ 8 **dan** tidak ada dokumen terbaca. Rilis tetap melewati QA Langkah 5.
- **BERSYARAT:** pangsa dialog 15–25% **atau** 4–5 pembicara **atau** transisi cepat 9–15 → wajib dengar-cek manusia pada semua adegan dialog sebelum rilis, atau naik ke format multi-suara.
- **GAGAL untuk suara tunggal:** pangsa dialog > 25% **atau** ≥ 6 pembicara **atau** ada dokumen terbaca > 150 karakter yang harus terdengar berbeda **atau** transisi cepat ≥ 16. Bab seperti ini hanya boleh rilis sebagai (a) narasi multi-suara dengan pemeran per tokoh, atau (b) tidak diaudiokan. Suara tunggal dilarang.

### Putusan untuk Bab 1
**GAGAL untuk rilis suara tunggal** — 7 pembicara + 1 suara tertulis (≥ 6), 24 transisi cepat (≥ 16), dan wasiat 696 karakter yang dibacakan di dalam adegan. Berkas uji `warung_bab01_tts_test.mp3` berdiri sebagai **bukti pipeline dan sampel dengar untuk menilai pelafalan** (gerbang 5.2), **bukan** kandidat rilis. Jalur rilis audio untuk bab ini, bila dikehendaki: pemeran multi-suara — minimal Narator, suara Pak Haji/Bapak yang dibedakan untuk petikan wasiat, dan pembeda untuk Baskoro sebagai penyela utama — lalu nilai ulang dengan aturan yang sama.

---

*Dokumen ini adalah desain + memo gerbang; tidak ada yang diterbitkan dan tidak ada akun yang dibuat. Bab-bab berikutnya diukur dengan §3 sebelum sintesis apa pun dimulai.*
