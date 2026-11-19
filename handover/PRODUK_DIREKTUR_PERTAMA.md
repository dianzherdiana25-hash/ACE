# PRODUK DIREKTUR PERTAMA — Siklus Direktur Organ director-strong

- Brain-of-origin: groq/openai/gpt-oss-120b
- Dihasilkan: 2026-11-18 11:54 WIB oleh hub (ila) lewat connector custom.groq
- Bahan: handover/BAHAN_SIKLUS_DIREKTUR_PERTAMA.md (PR #307, head e28f06ae)
- Prompt: ~/workspace/rancangan-otak-kuat/prompt_siklus_direktur_pertama.txt
- Usage: prompt 1874 token, completion 2367 token (reasoning 581), completion_time 4.88 s ≈ 485 t/s, wall total 6,32 s
- Status: produk direktur, BELUM disaring — penapisan Ian menentukan usulan mana yang masuk agenda; kolom "aset rumah" perlu dicek terhadap repo (organ kuat bisa mengarang nama aset yang masuk akal).

---

## Usulan 1: **Metrik Sumber‑Agenda ACE**
- **Terikat celah:** 1. Sintesis peluang belum terbukti mayoritas‑berasal‑dari‑ACE.  
- **Alasan:**  ACE‑Ω mengklaim bahwa siklus direktur menjadi sumber agenda utama, namun tidak ada pengukuran kuantitatif yang membuktikan persentase agenda yang memang “berasal‑dari‑ACE”. Tanpa data ini, tidak dapat menilai efektivitas siklus dan mengoptimalkan alur sintesis lintas‑aset.  
- **Prediksi terfalsifikasi:** Pada akhir siklus (≈ 2 minggu), persentase agenda yang berlabel “ACE‑origin” ≤ 20 % → usulan terbukti salah.  
- **Pengukuran penentu termurah:** Tambahkan kolom “origin_tag” pada tabel *agenda_log* yang sudah ada (aset rumah) dan jalankan satu‑kali script audit (≈ 30 detik) untuk menghitung total agenda dan yang ber‑tag ACE. Jika hasil < 20 %, usulan gagal.  
- **Aset rumah dipakai ulang:** *agenda_log* database, pipeline logging yang dipakai oleh engine, dan skrip audit yang sudah dipakai pada audit G1‑G5.

---

## Usulan 2: **Normalisasi Variansi Judge di Gelombang 2**
- **Terikat celah:** 2. Variansi antar‑run judge muncul pertama kali di gelombang 2.  
- **Alasan:** Variansi tinggi (mis. w2‑lang‑002 = 45 vs 95) menurunkan keandalan margin pita dan membuat keputusan lift “pekan‑ke‑pekan” tidak dapat diprediksi. Dibutuhkan mekanisme koreksi variansi sebelum paket kalibrasi berikutnya.  
- **Prediksi terfalsifikasi:** Setelah aktivasi normalisasi, deviasi standar skor judge antar‑run (dalam 5 run selanjutnya) ≤ 5 % → usulan berhasil; > 5 % → gagal.  
- **Pengukuran penentu termurah:** Pakai modul *judge_stats* yang sudah ada untuk menghitung `stddev` dari 5 run terbaru; satu perintah CLI (≈ 10 detik).  
- **Aset rumah dipakai ulang:** Modul *judge_stats* dan data judge run yang sudah terekam di *judge_log*.

---

## Usulan 3: **Transformasi Pengetahuan Sebelum Recall EVO 0007**
- **Terikat celah:** 3. Pelajaran kegagalan antar (EVO 0005) – recall harus berupa pengetahuan, bukan struktur.  
- **Alasan:** EVO 0007 menguji recall pada enam slot, tetapi saat ini hanya menyalin struktur konten. Tanpa lapisan “knowledge‑distillation” hasil recall tetap tidak dapat dipakai pada tahap berikutnya.  
- **Prediksi terfalsifikasi:** Setelah menambahkan layer transformasi, setidaknya 4 dari 6 slot mengembalikan “knowledge‑type” yang lulus tes validasi (skor ≥ 80) dalam 3 percobaan; < 4 → gagal.  
- **Pengukuran penentu termurah:** Jalankan satu batch test pada *distiller_draft* #276 (sudah ada) dengan flag `--knowledge‑mode` dan periksa log keberhasilan. Biaya waktu < 1 menit.  
- **Aset rumah dipakai ulang:** Draft mesin distilasi pola #276, pipeline evaluasi slot EVO 0007, dan skrip validasi pengetahuan yang dipakai pada review sebelumnya.

---

## Usulan 4: **Profiling & Batch‑Sizing Dinamis untuk Front‑OOM 6 GiB**
- **Terikat celah:** 4. Front OOM pada pagu 6 GiB (NRestarts 13).  
- **Alasan:** Model otak tidak dapat diganti, sehingga satu‑satunya cara mengatasi OOM adalah mengoptimalkan ukuran batch/konsumsi memori secara dinamis.  
- **Prediksi terfalsifikasi:** Setelah integrasi, jumlah restart karena OOM dalam 48 jam ≤ 2; > 2 → gagal.  
- **Pengukuran penentu termurah:** Aktifkan modul *mem_profile* (sudah ada pada engine) dengan parameter `max_batch_mb=512` dan catat jumlah restart selama satu siklus monitoring (≈ 30 menit).  
- **Aset rumah dipakai ulang:** Modul *mem_profile* pada engine, log restart NRestarts, dan konfigurasi batch default yang dipakai pada G1‑G5.

---

## Usulan 5: **Keep‑Alive Ping untuk Chat‑Streaming (Opsi D)**
- **Terikat celah:** 5. Utang teknis chat streaming – timeout soket‑idle pada judge panjang.  
- **Alasan:** Tanpa mekanisme keep‑alive, alur streaming dapat terputus secara acak, menurunkan throughput dan menghambat evaluasi panjang.  
- **Prediksi terfalsifikasi:** Setelah penambahan ping 30 s, persentase timeout per 1 juta pesan ≤ 0.1 %; > 0.1 % → gagal.  
- **Pengukuran penentu termurah:** Deploy satu‑kali skrip *socket_keepalive* (berbasis library Python standar) pada service streaming dan hitung timeout pada log selama 5 menit percobaan.  
- **Aset rumah dipakai ulang:** Library socket standar, logging framework streaming yang sudah ada, dan skrip monitoring timeout yang dipakai pada audit jaringan.

---

## Usulan 6: **Analisis & Perbaikan Mekanisme Lift G2 (Tiga Nol)**
- **Terikat celah:** 6. Tiga nol G2 – lift yang sama gagal tiga tes jujur.  
- **Alasan:** Kegagalan berulang menunjukkan bug deterministik pada algoritma lift (item agenda → konsekuensi pemalsuan). Memperbaikinya dapat membuka jalur agenda baru yang sebelumnya terblokir.  
- **Prediksi terfalsifikasi:** Setelah revisi kode lift, setidaknya 2 dari 3 tes G2 kembali menghasilkan nilai > 0 pada iterasi berikutnya; bila semua tetap 0 → gagal.  
- **Pengukuran penentu termurah:** Jalankan kembali ketiga tes G2 dengan patch `lift_fix_v1` (hanya satu baris perubahan) dan baca hasil dari *test_suite* yang sudah ada (≈ 15 detik).  
- **Aset rumah dipakai ulang:** Kode lift yang ada di modul *gate_lift*, suite tes G2, dan framework CI yang memicu tes otomatis.

---

## Usulan 7: **Finalisasi Serial 4 KBM & Validasi Royalti**
- **Terikat celah:** 7. Lini KBM toggle “Selesai” masih terbuka; royalti pertama belum terverifikasi.  
- **Alasan:** Penutupan serial 4 menandai pencapaian “penghasilan terverifikasi > 0”, yang merupakan prasyarat untuk membuka Tahap 2/3 Otak Kuat. Tanpa data royalti yang valid, siklus tidak dapat melanjutkan.  
- **Prediksi terfalsifikasi:** Setelah menutup toggle dan menjalankan satu‑kali *royalty_audit* (menggunakan tiga‑bukti), laporan menunjukkan pendapatan ≥ Rp1 000  (angka arbitrer > 0) → usulan berhasil; jika tidak, gagal.  
- **Pengukuran penentu termurah:** Aktifkan flag `serial4_closed=true` pada konfigurasi KBM, jalankan skrip *royalty_audit* yang sudah ada (mengakses laporan platform, catatan penarikan, dan mutasi e‑wallet) dan periksa total. Waktu < 2 menit.  
- **Aset rumah dipakai ulang:** Konfigurasi KBM, skrip *royalty_audit* yang dipakai pada verifikasi pendapatan, dan data tiga‑bukti yang telah didefinisikan.
