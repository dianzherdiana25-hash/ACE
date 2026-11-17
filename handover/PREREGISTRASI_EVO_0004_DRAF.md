# RANCANGAN EVO 0004 — draft praregistrasi (dirancang hub, 2026-11-16)

Status: DRAFT untuk ratifikasi hub. Basis: main @ f6d75462 + catatan konsolidasi EVO 0003 (PR #242).
Prinsip pemilik yang mengikat misi ini: masif di core, tidak aneh-aneh; tidak ada model baru, tidak ada front baru; semua bahan sudah ada di rumah.

## Mengapa misi ini ada (dari sisa EVO 0003)

1. Klaim §1 EVO 0003 (pasangan organ heterogen saling menilai) hanya terukur pada cakupan tereduksi: 2/8 episode, keduanya kode, karena perintah potong pemilik + jalur bahasa tidak pernah berlari (cacat filter "lang" vs "language").
2. Pertanyaan audit B4 (jalur tulis ingatan) belum terjawab: probe-nya ditolak karena kelas peristiwanya tidak terdaftar di EVENT_CLASSES.
3. T3 tuntas sebagai intake: Sahabat-AI-9B ter-bench (llama.cpp -t 1: pp 6,03/tg 0,99; ik_llama -t 1: pp 10,19/tg 0,90) — keputusan peran belum diambil.

## Blok A — §1 full scope (klaim utama)

- Jalankan 8 episode beku korpus ekor EVO 0003 (ep-code-001..004, ep-lang-001..004) dengan instrumen v2 (judge via chat_structured) dan pasangan asli PR #238 (kode: coder→front; bahasa: front→coder) demi komparabilitas dengan cakupan tereduksi.
- Preflight wajib: setiap jalur/filter diuji ke korpus sebelum launch dan harus cocok ≥1 item per jalur; kill proses terverifikasi (bukan diasumsikan).
- Engine dijeda selama jendela ukur (disiplin insiden T1), topi ace-front 6 GiB sudah terap.
- Kriteria vonis: laju ratifikasi atas 8 episode dilaporkan apa adanya; klaim TERDUKUNG bila laju > 0 di kedua jenis (kode DAN bahasa) — lebih ketat dari 0003 karena kali ini kedua arah terukur. Hasil nol di satu jenis = klaim menyempit ke jenis yang lolos, dicatat apa adanya.
- Bila Blok A lolos: kabelkan loop ratifikasi ke siklus engine (proposer organ mengusulkan, validator organ menilai, yang diratifikasi ditulis via memory write-back) sebagai perubahan terpisah dengan tesnya sendiri — bukan bagian dari pengukuran Blok A.

## Blok B — audit jalur tulis (pertanyaan B4 yang terbuka)

- Daftarkan kelas peristiwa probe audit secara resmi di EVENT_CLASSES memory_writeback (amendemen terdaftar, bukan tambalan diam-diam).
- Jalankan audit write-path yang sama dengan yang error di B4 EVO 0003: tulis peristiwa probe terverifikasi → baca kembali dari store → verifikasi isi + provenance.
- Kriteria: PASS bila tulis-baca kembali cocok dan peristiwa non-terverifikasi tetap ditolak (fail-closed tidak berubah).

## Blok C — keputusan peran Sahabat

- Dari angka T3: tg ±0,9–1,0 t/s terlalu lambat untuk loop penilai per-episode; pp ik_llama unggul. Keputusan rancangan: Sahabat = organ on-demand untuk tugas bahasa Indonesia batch (bukan slate always-on, bukan penilai loop). Blok ini hanya mencatat keputusan + satu smoke generation Bahasa Indonesia sebagai bukti fungsi; tidak ada pengkabelan service baru di misi ini.

## Blok D — transfer katalog (dari pola data 0003)

- Dua band segar: satu di-seed dengan katalog terakui band lain sebagai prior, satu cold start; instrumen solver yang sama, gerbang yang sama.
- Kriteria: band ter-seed mencapai cakupan katalog yang sama dengan panggilan discovery lebih sedikit secara terukur, tanpa mismatch vonis. Bila tidak ada beda terukur, hipotesis transfer ditutup apa adanya.

## Yang TIDAK dilakukan misi ini

- Tidak ada unduhan model/kuantisasi baru. Tidak ada A3B tanpa jendela RAM bernama. Tidak ada perubahan slate. Tidak ada venue baru. Kirim-sendiri di luar misi ini (jalurnya sendiri: perkerasan putaran 3 + verifikasi kancuto + keputusan proteksi repo pemilik).

## Urutan eksekusi

Blok B (paling kecil, menutup utang audit) → Blok A (klaim utama) → Blok D → Blok C (catatan keputusan). Konsolidasi EVO 0004 = satu draft PR di akhir, pola EVO 0003.

## Addendum hub (2026-11-16 14:36) — bahan mentah Ian dilipat masuk

- **Kelas probe B4:** daftarkan kelas audit BARU yang khusus (provenance bersih), bukan memakai ulang kelas ratifikasi yang ada.
- **Blok B2 (baru) — baterai dengan gerbang prasyarat:** uji ulang baterai HANYA pada semesta band yang kerentanan stoknya sudah terbukti ada saksi (band burst 20261903–20261906). Bila prasyarat saksi tidak terpenuhi di semesta pilihan, blok berhenti di gerbang dan tercatat NOT_RUN_BY_PRECONDITION — tidak ada lagi vonis nol yang ambigu.
- **Anggaran dinding Blok A:** dari laju terukur per episode (bukan kotak waktu): kode ±12 menit, bahasa diukur dari 2 episode pertama lalu diproyeksikan tertulis di log sebelum lanjut.
- **Protokol rumah sepi:** kelas tes sensitif-beban ditandai eksplisit; suite hanya sah sebagai penyewa tunggal (mengikat Blok A dan konsolidasi).
- **Di luar blok, tercatat sebagai pengikat:** panen G5 berakhir 30 Nov 2026 (bukti hanya dari pemakaian alami pemilik — misi ini tidak boleh mengganggunya); pemicu kirim-sendiri dikabelkan hanya sesudah kiriman uji lulus verifikasi; antrean tak-terukur (perplexity, sqlite-vec KNN, n-gram) hanya di jendela bernama; jalur hinted-CLI engine yang gagal 'unavailable' dibiarkan tercatat apa adanya; batas B1 untuk blok solver masa depan diturunkan dari distribusi terukur atau dibaca per-lengan.
