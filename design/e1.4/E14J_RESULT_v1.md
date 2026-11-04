# E1.4j — pembuatan pertanyaan dan batas dua label

**SYNTHESIS_DEVELOPMENT_GO** pada uji terkontrol. **NATURAL_HOLD** untuk transfer. Worker menyusun input dari motif lima dan enam kejadian yang masih konsisten dengan contoh. Evaluator menyimpan target dan probe, lalu mengungkap label hanya untuk input yang dipilih.

[Pembekuan sebelum penilaian](https://github.com/dianzherdiana25-hash/ACE/commit/f62d4cf65d8a9e6b54e9062698378560a2881b95) · [Hasil mentah](../../evidence/e14/e14j_public_development_v1.json.gz) · [Replay](../../evidence/e14/e14j_replay_v1.json.gz) · [Verifikasi](../../evidence/e14/e14j_verification_v1.json)

| Kondisi terkontrol | Batas label | Diagnosis terarah S/G | Pool tetap S/G | Generator acak S/G | Probe tepat terarah S/G |
| --- | --- | --- | --- | --- | --- |
| Satu pertanyaan cukup | 1 | 8/8 · 8/8 | 0/8 · 0/8 | 0/8 · 4/8 | 64/64 · 64/64 |
| Perlu urutan bukti | 1 | 2/8 · 1/8 | 0/8 · 0/8 | 0/8 · 0/8 | 52/64 · 50/64 |
| Perlu urutan bukti | 2 | 8/8 · 8/8 | 0/8 · 0/8 | 0/8 · 2/8 | 56/64 · 56/64 |
| Di luar jaminan dua label | 2 | 2/8 · 3/8 | 0/8 · 0/8 | 0/8 · 1/8 | 52/64 · 53/64 |

- **Pertanyaan terarah mencapai target terkontrol.** Di setiap keluarga, kedua dunia di semua 4/4 blok satu-label terdiagnosis. Di kondisi berurutan, seluruh 8 dunia dengan aturan panjang baru terdiagnosis sesudah label kedua. Dalam kondisi di luar jaminan dua label, seluruh 8 dunia panjang masih abstain. Lima dunia pendek berhasil terdiagnosis. Tidak ada diagnosis terarah yang salah. Pool tetap pada strata terkontrol sengaja disusun tanpa saksi antara dua target cermin. Generator acak menjadi pembanding pembuatan pertanyaan dengan batas jumlah input dinilai yang sama.
- **Diagnosis panjang tidak selalu memperbaiki prediksi.** Pada simbol alami, pembuatan pertanyaan menaikkan diagnosis dari 1/12 tanpa label menjadi 8/12 dengan batas satu label. Pool tetap mencapai 3/12 dan acak 1/12. Semua metode tetap pada 95/96 probe tepat, dan empat label kedua dari metode terarah tidak menambah diagnosis. Pada graf alami seluruh 12 dunia sudah terdiagnosis dari demo dan menghasilkan 96/96 probe, sehingga ketiga metode meminta nol label.
- **Batas anggaran dapat dihitung.** Pada empat dunia simbol alami yang masih ambigu, hasil post-hoc menunjukkan semua jawaban yang dibeli kosong. Sebelum query, masing-masing memiliki 80–108 kandidat pendek dan 536–563 kandidat panjang. Query lima atau enam kejadian dapat menutup paling banyak dua kata pendek dan satu kata panjang. Untuk menjamin pemisahan pada lintasan jawaban kosong, batas bawahnya 40–54 pertanyaan pada empat dunia tersebut. Ini batas perlu di bahasa query E1.4j. Jumlah yang cukup belum diketahui.
- **Prediksi fallback dapat merugikan meski diagnosis ditunda.** Di graf berurutan, setelah satu label jumlah probe false positive naik dari 4 menjadi 12, lalu turun ke 0 sesudah label kedua. Pada kondisi di luar jaminan, generator acak memperoleh 54/64 probe graf dan metode terarah 53/64. Gerbang ini menguji diagnosis dan kalibrasi abstain, sehingga kedua hasil negatif tersebut tetap dilaporkan.
- **Verifikasi dan biaya.** 48 blok, 72 dunia, 2.304 input mentah baru dibanding inventaris 10.702 fingerprint. Satu eksekusi memakai 410 worker, 8.087.484 perbandingan kecocokan, dan 3.074 evaluasi oracle. Batas 8 input dinilai per putaran berlaku untuk semua metode. Angka input dinilai, percobaan pembangkitan, dan label aktual dicatat terpisah. Enam pemeriksaan isolasi lulus. Replay dengan ledger baru cocok pada 72 dunia, auditor memeriksa fit, urutan query, label dan hasil, dan resume ledger selesai identik byte. Tes pra-penilaian lulus 4/4 dan regresi dari sumber yang dapat dipulihkan lulus 87/87.

E1.4k akan menguji pertanyaan majemuk yang menutup lebih banyak hipotesis sekaligus. Bandingkan biaya label dan panjang input, serta pisahkan risiko prediksi fallback dari keputusan menunda diagnosis. Penemuan representasi baru dan transfer tetap merupakan pertanyaan lanjutan.
