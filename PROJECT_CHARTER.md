# Piagam penelitian ACE

## Visi dan ukuran kemajuan

**Open-Ended Autonomous Intelligence Evolution (OAIE)** adalah visi penelitian jangka panjang. Kecerdasan yang diteliti kelak diharapkan dapat memilih dan menghentikan arah riset berdasarkan bukti, mengenali keterbatasannya, menyintesis serta menguji metode baru, memperbaiki cara belajarnya, dan mewariskan kemampuan kepada penerus. Penerus dapat memakai arsitektur berbeda atau menggantikan generasi sebelumnya. LLM dapat membantu tahap awal, sedangkan rancangan tetap terbuka bagi pendekatan non-LLM, hibrida, dan model dunia.

**Autonomous Capability Evolution (ACE)** adalah generasi pertama. Uji awal mengisolasi penemuan kemampuan yang dapat diuji, transfer, dan pewarisan. Skor benchmark mengukur hipotesis lokal dalam keluarga tugas dan anggaran tertentu. Bukti OAIE, penemuan primitive fundamental, dan AGI/ASI masih terbuka.

Landasan berversi tersedia di [Master Record v1.0](ACE_RESEARCH_MASTER_RECORD_v1.0.md), [PRD](docs/PRD_ACE_v0.1.md), dan [Research Execution Spec](docs/ACE_Research_Execution_Spec_v0.1.md). [F5](docs/ACE_F5_Research_Synthesis_and_Decision_v0.1.md) menetapkan `CONTINUE_RESEARCH_WITH_SCOPE_LIMITS`.

## Kewenangan dan metode

- Work mengelola hipotesis, rancangan, dan keputusan berbasis bukti. Codex mengimplementasikan, men-debug, menguji, dan mereproduksi. Keduanya memakai branch ACE yang sama sebagai sumber status operasional.
- Kerja aktif berlanjut selama ada bukti, kapasitas, dan otorisasi. Gunakan CPU dan layanan yang tersedia dengan biaya tambahan Rp0. Otorisasi ini mencakup perubahan pada branch penelitian ACE. Merge ke `main`, perubahan Tod, pengeluaran, dan tindakan fisik berada di luar mandat.
- Pemilik mendelegasikan keputusan rutin implementasi, riset digital terisolasi, pilihan hipotesis, alokasi ulang upaya, checkpoint, dan keputusan GO/HOLD/NO-GO kepada Work. Mandat berlaku dalam sesi aktif dan dapat diteruskan lintas sesi dari GitHub tanpa konfirmasi rutin. Lanjutkan fase berikutnya jika gerbang ilmiah dan sumber daya lulus. Persetujuan wajib platform, biaya, publikasi di luar branch penelitian, dan merge ke main tetap di luar mandat teknis.
- Simpan bukti positif, negatif, dan inkonklusif. Nilai klaim terhadap kontrol kuat, catat biaya dan kegagalan, serta pisahkan kelulusan rekayasa dari dukungan ilmiah. Audit reproduksi teknis dilakukan sebagai pekerjaan terpisah di dalam proyek. Sertifikasi eksternal bersifat opsional.
- Jaga data konfirmatori di bawah jalur evaluator terpisah. Pertahankan bukti lama dan larang tuning terhadap evaluasi tersegel. Batasi artefak kandidat pada DSL bertipe dan jalankan kandidat tidak tepercaya hanya dalam isolasi yang sudah diuji.
- Rujukan jangka panjang di [Google Drive](https://docs.google.com/document/d/1esmTLeHNXpKsmVnH6rbUx7czKoIvbKZvzS-YEkVJkYE/edit) menerima lampiran ringkasan keputusan besar. Snapshot historis dan bukti asli tetap terarsip.

## Kontrak checkpoint lintas sesi

Mulai dari [status terkini](CURRENT_STATE.md), [ledger](RESEARCH_LEDGER.md), dan [aksi berikutnya](NEXT_ACTION.md). Sebelum bekerja, baca kepala branch `research/e1.3-design` di GitHub dan cocokkan kode, status, serta bukti. Bila suatu poin dalam snapshot lama menyebut repo belum tersedia atau desain belum dikerjakan, gunakan dokumen status untuk keadaan operasional terkini.

Pada setiap checkpoint, catat pekerjaan, perintah dan hasil tes, keputusan, kegagalan, serta aksi berikutnya. Tinjau piagam dan ubah hanya jika mandat atau prinsip berubah. Commit lalu verifikasi kepala branch dan isi tree di GitHub. SHA checkpoint yang berisi dokumen status dibaca dari kepala branch GitHub agar dokumen tidak perlu mereferensikan hash dirinya sendiri. Proses ini mendukung pengambilan alih melalui GitHub lintas percakapan yang punya akses ke repo.
