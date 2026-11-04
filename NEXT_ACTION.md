# Aksi berikutnya untuk Work atau Codex

1. Baca [status](CURRENT_STATE.md) dan [desain E1.3](design/e1.3/E13_DESIGN_v0.1.md). Mulai dari kepala `research/e1.3-design` dan jalankan `python3 verify_handoff.py`.
2. Implementasikan oracle simbolik dan graf yang tidak mengimpor solver. Buat episode development berlabel demonstrasi, probe in-distribution dan ekstrapolasi, serta manifest blok aturan yang dapat diaudit.
3. Uji keterbedaan aturan, jarak struktur, dan tumpang tindih lintas split sebelum fit. Tahan selection dan konfirmasi bila isolasi, kustodi, atau audit gagal. Pertahankan bank konfirmatori di luar checkout kandidat.
4. Jalankan regresi E1.2 dan tes E1.3 dari checkout bersih. Catat hasil dan perbarui status serta ledger. Simpan hasil yang valid ke branch penelitian dan baca kembali SHA kepala branch.
5. Mulai pembanding buta terstruktur dan pencarian program setelah jalur bank lulus. Profilkan biaya pada data development. Gunakan kontrol lengkap sebelum memilih B* pada data selection.

Gunakan CPU lokal dan anggaran Rp0. [Piagam](PROJECT_CHARTER.md) menjelaskan batas otorisasi.
