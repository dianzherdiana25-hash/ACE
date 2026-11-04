# ACE E1.4 — pilot diagnosis representasi

**Status desain development, bukan protokol konfirmatori.** Hipotesisnya adalah kandidat yang dapat mendeteksi inkonsistensi demonstrasi terhadap keluarga representasi hitung dapat mengalihkan pencarian ke representasi urutan dan memulihkan akurasi pada kasus terkait. E1.3 memberi saksi bahwa menambah kapasitas penghitung tidak mengatasi kolaps urutan.

## Intervensi dan kontrol

- `counter_only` mencari definisi hitung E1.3 dari demonstrasi target.
- `order_only` menyintesis automata prefix dari semua kata kejadian panjang 1–3. Kandidat menerima demonstrasi dan kontrak tipe.
- `adaptive` menjalankan pencarian hitung. Ia beralih setelah seluruh basis diperiksa dan tak ada kecocokan eksak. Bila cap menghentikan pemeriksaan, ia menyatakan diagnosis belum selesai. Ia memilih kandidat yang lebih cocok dengan demo dan mengutamakan hitung saat seri.
- `beam` adalah pembanding E1.3 yang dibekukan. Semua kondisi menerima payload fit yang sama dan dinilai oleh interpreter evaluator.

Semua fit memakai sandbox terpisah, 75.000 langkah fit, 100.000 langkah gabungan dan batas CPU/wall yang sama. Untuk kondisi adaptif, biaya tahap hitung dan urutan memakai anggaran fit yang sama. Silsilah antargenerasi tidak diuji pada pilot ini. Field sumber dipenuhi oleh satu contoh dan kebijakan yang diuji memakai demo target.

## Bank dan kriteria

Bank development baru berisi dua keluarga, tiga strata dan tiga blok per keluarga per strata. Setiap blok satu episode dengan empat probe biasa dan empat probe ekstrapolasi. Strata hitung memakai aturan hitung. Strata urutan dengan saksi memasukkan pasangan berlawanan ke demo. Strata urutan ambigu hanya memperlihatkan satu contoh positif. Distribusi dirancang untuk diagnosis. Probe dan demo dinormalisasi lalu diperiksa terhadap data development publik E1.3, termasuk pasangan uji urutan. Audit graf mengurutkan sisi dan belum membuktikan ketiadaan isomorfisme. Data selection privat tidak digunakan untuk membuat atau menilai pilot.

Seed bank 141501 dan seed urutan arm 141502. Hitung akurasi per keluarga dan strata, jumlah rute urutan, cap dan kasus skor adaptif lebih rendah dari kontrol. Bukti engineering yang dicari adalah perpindahan setelah saksi, keberhasilan pada probe urutan, serta dipertahankannya representasi hitung ketika cocok. Perlakuan ambigu menguji batas diagnosis berdasarkan contoh. Hasil tetap deskriptif pada bank kecil. Menemukan pola di dalam ruang kata terbatas tidak menguji penemuan primitive fundamental, transfer umum, atau visi OAIE penuh.
