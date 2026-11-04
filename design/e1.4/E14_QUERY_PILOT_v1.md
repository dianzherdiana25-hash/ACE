# ACE E1.4b — pilot satu pertanyaan pembeda

**Development publik.** Hipotesisnya adalah memilih masukan tempat dua representasi yang sama-sama cocok pada demonstrasi awal menghasilkan prediksi berbeda dapat memberi label tambahan lebih berguna daripada satu masukan acak.

## Perlakuan dan batas informasi

1. Fit model hitung dan model urutan secara terisolasi dengan demonstrasi awal yang sama. Pemilih hanya menerima AST beku, status fit dan delapan masukan tanpa label. Jika kedua fit eksak, cari titik tempat prediksi berbeda lalu pilih satu dengan seed episode. Bila tak ada beda, salah satu fit tidak eksak, atau cap tercapai, gunakan pilihan acak dengan seed yang sama. Cap membatalkan pemakaian hasil pencarian sebagian.
2. Setelah pilihan dikunci, evaluator mengungkap satu label untuk cabang itu. Fit ulang kebijakan adaptif dari awal dengan demo tambahan. Probe penilaian berada di luar pool. Kode dan label evaluator tidak ikut dipasang di sandbox.
3. Kontrol utama adalah hasil harapan dari pemilihan satu masukan seragam. Jalankan delapan cabang independen dengan satu label masing-masing lalu rata-ratakan. Cabang aktif persis sama dengan satu anggota kontrol sehingga eksekusinya dipakai sekali. Kontrol kedua menjalankan adaptif dengan demonstrasi awal saja.

Biaya dua fit hipotesis awal dibebankan secara logis ke kedua kondisi satu-label. Setiap fit awal memiliki plafon 75.000 langkah, 1 detik CPU worker, dan 3 detik wall. Pemilih memiliki plafon 20.000 langkah, 0,1 detik CPU dan 0,25 detik wall. Fit ulang dan prediksi memakai plafon gabungan 100.000 langkah, 1 detik CPU dan 3 detik wall. Laporan membedakan CPU solver/pemilih dari CPU oracle. Kontrol tanpa label memiliki biaya lebih rendah dan ditampilkan terpisah.

## Bank dan aturan keputusan

Dua keluarga, tiga strata, dan tiga episode per keluarga/strata. Bank memakai seed 141601. Semua episode memiliki dua demonstrasi target awal, delapan pertanyaan, dan delapan probe akhir. Empat probe akhir berukuran biasa dan empat lainnya lebih panjang. Masukan dibandingkan secara kanonis dengan development publik E1.3 dan pilot routing E1.4. Audit mencakup masukan eksak setelah sisi graf diurutkan. Bank konfirmatori dan selection privat berada di luar pilot.

- **Pool bersaksi** menyediakan dua masukan yang mengubah urutan kejadian dan enam variasi jejak positif. Beberapa motif sengaja sama dengan strata kurang informasi agar dampak komposisi pool dapat diperiksa.
- **Pool kurang informasi** berisi variasi nilai atau biaya yang mempertahankan jejak kejadian positif. Dua model yang konsisten dapat tetap sepakat dan keliru di probe.
- **Di luar basis** memakai pola panjang empat. Empat pasangan probe per episode memerlukan pembedaan yang tak dapat dibuat oleh tabel hitung atau kata urutan panjang 1–3. Audit mengevaluasi semua definisi transisi dan pola, terpisah dari fit kandidat.

Untuk setiap keluarga dan strata, laporkan skor awal, skor aktif, nilai harapan satu label acak, dan jumlah episode menang/seri/kalah terhadap harapan itu. Gerbang engineering **GO ke replikasi publik** memerlukan skor aktif pada strata bersaksi lebih tinggi dari kontrol seragam dan kontrol awal di kedua keluarga, serta seluruh fase dalam batas. Cap memberi HOLD untuk pemeriksaan biaya. Hasil lainnya memberi HOLD untuk diagnosis. Jumlah episode kecil, pool sengaja direkayasa, dan kesimpulan tetap deskriptif. Jika hasil mendukung, eksperimen baru berikutnya menguji strategi pemilihan pada pool yang lebih beragam sebelum menambah transfer lintas episode.
