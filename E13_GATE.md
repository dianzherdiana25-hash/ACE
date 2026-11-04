# E1.3 — gerbang desain sebelum eksekusi
**Status:** DESIGN_ONLY. Belum ada eksperimen E1.3, data konfirmatori, atau evaluasi independen yang dijalankan.

## Hipotesis terpisah
- H1 (repr. baru): sistem yang dapat menambah node/operasi/abstraksi ke bahasa internal menyelesaikan masalah yang tidak dapat diselesaikan oleh vocab tertutup yang sepadan.
- H2 (generalisasi): pembelajaran memberi peningkatan pada grammar target yang disembunyikan dari pembuat kandidat sampai pengujian.
- H3 (kausal): peningkatan berasal dari pembelajaran/seleksi, bukan urutan mutasi, ukuran ruang pencarian, dan biaya komputasi tersembunyi.

## Persyaratan operasional untuk GO
- Benchmark dan evaluator dibangun/dikunci oleh jalur pengujian terpisah; ukur jarak domain secara eksplisit.
- Kontrol kuat: matematis terstruktur, enumerasi/beam, sham feedback, no-transfer, dan pembatasan representasi.
- Budget: CPU time, wall time, memori, kandidat, primitive evaluations sama atau diukur/diadjust dengan jelas.
- Hasil utama: akurasi tersegel pada grammar baru, kemajuan lintas kondisi, kebaruan semantik diukur oleh evaluator yang tidak ikut membangkitkan kandidat, negative transfer.
- Penguncian di Git commit/tag sebelum membuka tugas konfirmatori; lakukan evaluasi sekali tanpa tuning pascauji.
- Safety: kode kandidat hanya DSL/interpreter tepercaya atau sandbox isolasi nyata; tanpa kredensial/jaringan tidak sah.

**STOP jika:** evaluasi dapat bocor, kontrol tidak adil, atau fitur yang disebut baru sebenarnya sudah tertanam dalam grammar kandidat. Hasil harus ditulis sebagai eksploratori sampai persyaratan dipenuhi.
