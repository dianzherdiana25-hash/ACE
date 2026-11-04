# ACE — panduan kerja Codex

- Mulai dari [Master Record](ACE_RESEARCH_MASTER_RECORD_v1.0.md), [PRD](docs/PRD_ACE_v0.1.md), [RES](docs/ACE_Research_Execution_Spec_v0.1.md), [laporan E1.2](docs/E12_Research_Report_v0.1.md), dan [gerbang E1.3](E13_GATE.md). Cocokkan keputusan lintas sesi dengan [Master Record di Google Drive](https://docs.google.com/document/d/1esmTLeHNXpKsmVnH6rbUx7czKoIvbKZvzS-YEkVJkYE/edit?usp=drivesdk).
- Pertahankan snapshot E1.2 pada tag `ACE-research-checkpoint-E1.2-v1` (`38afa3b5cf3e5b5529157fc0cc71e039189a2098`). Jalankan `python3 verify_handoff.py` untuk memeriksa berkas historis. Kerjakan perubahan baru di jalur E1.3. Repositori dan plugin Tod berada di luar lingkup ACE.
- Baca [desain E1.3 saat ini](design/e1.3/E13_DESIGN_v0.1.md). Status `READY_FOR_E13_DESIGN`. Buat fixture publik dan uji rekayasa di mode development. Konfirmasi memerlukan manifest serta penguncian yang dicatat dalam desain.
- Pertahankan biaya tambahan Rp0, CPU lokal terlebih dahulu, dan pemisahan jalur evaluasi. Terima kandidat hanya sebagai data DSL bertipe. Jaga set tersegel dan evaluator privat di luar checkout kandidat.
- Catat keputusan dan status di Git. Untuk pekerjaan berikutnya, rekam perintah uji, status keluar, artefak, SHA, kegagalan, dan batas klaim secara terpisah dari hasil ilmiah.
