# W3 — penerimaan berdasarkan bukti development

Tanggal: 10 November 2026 (WIB). Basis: `e1fdbf09da6aaec4b7a3e426771af81b989ebe1c`
di branch PR #96. Ownership sesi ini: `code/ace_core_repair/admission.py`, jalur
`train` pada `code/ace_runtime/cli.py`, tes baru terpisah, tool benchmark baru,
workflow dan evidence `w3_admission`. Tidak mengubah sumber beku, evaluator
independen, bukti historis, main, daemon aktif atau konfigurasi eksternal.

## Hipotesis sebelum implementasi/scoring

- H1 (engineering): selector baru tidak menerima kandidat yang salah pada satu
  pun label validasi, walaupun training sempurna atau `max_errors` besar.
- H2 (engineering): kandidat dengan nol error validasi dan error training dalam
  toleransi tetap dapat diterima secara empiris. Kontrol always-abstain harus
  mempunyai coverage nol; nol false acceptance saja tidak cukup.
- H3 (integrasi): `ace.py train` memakai kandidat hasil fit yang sudah tersedia
  di semua arm, tanpa memanggil AI atau menambah grammar. Pada bank publik
  `starts`, jalur ini tidak lagi terikat pada arm composition yang gagal.
- H4 (batas ilmiah): bukti development yang identik tidak dapat membedakan dua
  semantik terminal yang berlawanan. Kontrol hidden flip harus tetap dicatat
  sebagai kegagalan generalisasi, bukan dianggap selesai oleh perbaikan ini.

Tidak ada hipotesis keunggulan metode baru/OAIE. `NOT_ASSESSED`, `BLOCK_RELEASE`,
`candidate_deployed=false` tetap berlaku. Status ADMITTED lokal hanya berarti
memenuhi kontrak development, bukan izin rilis.

## Rancangan terkunci

1. Reproduksi minimal bug lama disimpan sebelum source diubah.
2. Data validasi tidak masuk ke training/infer. Data terminal hanya diterima
   pemanggil benchmark sesudah kandidat dan keputusan dibekukan; tidak dipakai
   untuk revisi atau pemilihan kandidat.
3. Kontrak: training 1..63, validasi 1..128, string a/b <=100, label Boolean
   ketat, tanpa duplikasi/overlap. `max_errors` adalah integer nonnegatif dan
   hanya melonggarkan training; validasi harus sempurna. Error evaluasi dan
   output non-Boolean tidak boleh diterima.
4. Bank metamorfik: tiga predikat internal (equal counts, starts-a, even length),
   seluruh string a/b panjang 0..7; train panjang <=3, validasi 4..5, terminal
   6..7. Bandingkan kandidat benar dan memorizer-training. Train/val dibedakan
   sebelum scoring; label dan aturan ini publik, bukan holdout tersegel.
5. Integrasi: bank `compositional.bank`, delapan keluarga bawaan × tiga seed
   tetap 20261106/07/08. Bandingkan jalur lama composition, strong selector
   `compositional.select` atas semua fitted arms yang sama, selector baru dan
   always-abstain. Semua memakai hasil fit identik; fit sekali per task dan
   hitung biayanya sebagai biaya bersama, bukan klaim compute-matched end-to-end.
6. Pilih di antara program yang lolos bukti development lebih dahulu, lalu
   minimalkan error training, gunakan identity/arm untuk tie-break deterministik.
   Jika tidak ada kandidat yang lolos, abstain; simpan diagnostik setiap arm.
7. Simpan label nominal dan unik per split, evaluasi kandidat aktual, kerja
   prediksi/AST/DFA yang didukung meter lama, CPU/wall/RSS dan ukuran artefak.
   Jangan menyatakan metering infer RPNI lengkap. Maksimum 15 menit benchmark,
   24 task, 4 fitted-arm winners per task, nol API/panggilan model/label berbayar.
8. Ukur false admission yang teramati di validation, coverage empiris, terminal
   correctness (abstention dihitung gagal), kontra-contoh, serta hidden flip.
   Bandingkan dua replay; pisahkan profil nondeterministik dari hasil semantik.
9. Jalankan test selector+CLI baru, suite historis dan verifikasi source/evidence.
   Workflow exact SHA Python 3.12/3.13 dan draft PR ke branch #96; tidak merge.

## Kriteria berhenti dan interpretasi

H1 gagal bila satu kandidat dengan error validasi diterima. H2 gagal bila semua
kandidat positif ditolak. H3 gagal bila starts tidak menemukan kandidat yang
lulus, atau baseline kuat dikalahkan hanya karena memakai informasi/budget
berbeda. H4 diuji sebagai kontrol negatif; kegagalan hidden flip membatasi
klaim, bukan alasan mengubah label/grammar. Timeout, crash, ketidaksesuaian
receipt atau sumber beku berubah menghentikan run. Hasil negatif dipertahankan.

Sumber baseline dan benchmark telah dibaca sebelum protokol ini ditulis.
Keluarga/seeds adalah publik dan pernah dipakai pengembangan; hasil tidak
independen, tidak konfirmatori, dan tidak membuktikan transfer lintas keluarga.
